import hashlib
import shlex
import unittest
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import duckdb

from data.pipeline.build_dataset import SCHEMA_SQL
from data.pipeline.contracts import Manifest, SafetyReport, Trial
from src.orchestrator.contracts import ROLES, WorkerResult
from src.orchestrator.integration import (
    feature_conformance_script, feature_validation_script, integrate_and_validate, validate_egress, validate_worker_results,
)
from src.orchestrator.sandbox import Execution
from test_agents import development_manifest


def executor():
    return SimpleNamespace(
        binding=SimpleNamespace(sandbox_id=uuid4(), workspace="/opt/caldova-lab"),
        execute=AsyncMock(return_value=Execution(0, "", "")),
        verify_egress_policy=AsyncMock(return_value={
            "defaultAction": "Deny", "allowedHost": "open.fda.gov", "trafficInspection": "Full",
        }),
    )


class FeatureValidationTests(unittest.TestCase):
    def setUp(self):
        self.connection = duckdb.connect(":memory:")
        self.addCleanup(self.connection.close)
        self.connection.execute(SCHEMA_SQL)
        self.connection.execute("INSERT INTO candidates VALUES ('candidate-a','A','fixture'),('candidate-b','B','fixture'),('candidate-c','C','empty')")
        self.trial = {
            "trial_id": "trial-shared", "title": "Shared trial", "phase": "PHASE2", "status": "RECRUITING",
            "source_id": "fixture", "source_record_id": "trial-shared", "source_url": None,
            "candidate_ids": ["candidate-a", "candidate-b"], "conditions": ["obesity", "type-2-diabetes"],
        }
        self.report = {
            "report_id": "report-shared", "version": 2, "source_id": "fixture",
            "source_record_id": "report-shared", "source_url": None,
            "candidate_ids": ["candidate-a", "candidate-b"], "reaction_terms": ["NAUSEA", "VOMITING"],
        }
        self.connection.execute("INSERT INTO trials VALUES ('trial-shared','Shared trial','PHASE2','RECRUITING','fixture','trial-shared',NULL)")
        self.connection.execute("INSERT INTO trial_candidates VALUES ('trial-shared','candidate-a'),('trial-shared','candidate-b')")
        self.connection.execute("INSERT INTO trial_conditions VALUES ('trial-shared','obesity'),('trial-shared','type-2-diabetes')")
        self.connection.execute("INSERT INTO safety_reports VALUES ('report-shared',2,'fixture','report-shared',NULL)")
        self.connection.execute("INSERT INTO safety_report_candidates VALUES ('report-shared','candidate-a'),('report-shared','candidate-b')")
        self.connection.execute("INSERT INTO safety_reactions VALUES ('report-shared','NAUSEA'),('report-shared','VOMITING')")

    def verify(self, role, query):
        feature = SimpleNamespace(**{
            "query_trials" if role == "clinical-trials" else "query_safety_reports": query,
        })
        script = "if True:\n" + feature_validation_script(role)
        exec(compile(script, "<trusted-source-fidelity>", "exec"), {
            "connection": self.connection, "feature": feature, "Trial": Trial, "SafetyReport": SafetyReport,
        })

    def test_report_filter_cannot_hide_other_source_mentions(self):
        def query(connection, candidate):
            return [] if candidate == "candidate-c" else [{**self.report, "candidate_ids": [candidate]}]

        with self.assertRaisesRegex(AssertionError, "Source record fidelity mismatch"):
            self.verify("drug-safety", query)

    def test_trial_filter_cannot_narrow_source_conditions_or_associations(self):
        for field in ("conditions", "candidate_ids"):
            with self.subTest(field=field):
                def query(connection, candidate, condition):
                    if candidate == "candidate-c":
                        return []
                    record = dict(self.trial)
                    record[field] = [candidate] if field == "candidate_ids" else [condition or "obesity"]
                    return [record]

                with self.assertRaisesRegex(AssertionError, "Source record fidelity mismatch"):
                    self.verify("clinical-trials", query)

    def test_homogeneous_slice_cannot_hide_narrowed_shared_record_queries(self):
        self.connection.execute("DELETE FROM trial_candidates WHERE candidate_id = 'candidate-b'")
        self.connection.execute("DELETE FROM trial_conditions WHERE condition = 'type-2-diabetes'")
        self.connection.execute("DELETE FROM safety_report_candidates WHERE candidate_id = 'candidate-b'")

        def trials(connection, candidate, condition):
            cursor = connection.execute(
                "SELECT t.*, list(DISTINCT tc.condition ORDER BY tc.condition) AS conditions, "
                "list(DISTINCT tca.candidate_id ORDER BY tca.candidate_id) AS candidate_ids FROM trials t "
                "JOIN trial_conditions tc USING(trial_id) JOIN trial_candidates tca USING(trial_id) "
                "WHERE tca.candidate_id = ? AND (? IS NULL OR tc.condition = ?) GROUP BY ALL",
                [candidate, condition, condition],
            )
            return [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]

        def reports(connection, candidate):
            cursor = connection.execute(
                "SELECT sr.*, list(DISTINCT src.candidate_id ORDER BY src.candidate_id) AS candidate_ids, "
                "list(DISTINCT rx.reaction_term ORDER BY rx.reaction_term) AS reaction_terms FROM safety_reports sr "
                "JOIN safety_report_candidates src USING(report_id) JOIN safety_reactions rx USING(report_id) "
                "WHERE src.candidate_id = ? GROUP BY ALL", [candidate],
            )
            return [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]

        for role, query, name in (
            ("clinical-trials", trials, "query_trials"), ("drug-safety", reports, "query_safety_reports"),
        ):
            with self.subTest(role=role):
                self.verify(role, query)
                with self.assertRaisesRegex(AssertionError, "Source record fidelity mismatch"):
                    exec(feature_conformance_script(role), {
                        "duckdb": duckdb, "Trial": Trial, "SafetyReport": SafetyReport,
                        "feature": SimpleNamespace(**{name: query}),
                    })

    def test_complete_records_pass_all_candidates_conditions_and_empty_results(self):
        trials = Mock(side_effect=lambda connection, candidate, condition: (
            [] if candidate == "candidate-c" else [dict(self.trial)]
        ))
        reports = Mock(side_effect=lambda connection, candidate: (
            [] if candidate == "candidate-c" else [dict(self.report)]
        ))
        self.verify("clinical-trials", trials)
        self.verify("drug-safety", reports)
        self.assertEqual(trials.call_count, 9)
        self.assertEqual(reports.call_count, 3)
        self.trial["title"] = "Fictional shared trial"
        self.report["reaction_terms"] = sorted(["FICTIONAL, ONE", "FICTIONAL TWO"])
        for role, query, name in (
            ("clinical-trials", trials, "query_trials"), ("drug-safety", reports, "query_safety_reports"),
        ):
            exec(feature_conformance_script(role), {
                "duckdb": duckdb, "Trial": Trial, "SafetyReport": SafetyReport,
                "feature": SimpleNamespace(**{name: query}),
            })

    def test_missing_or_duplicate_records_and_altered_terms_are_rejected(self):
        for returned in (
            [], [self.report, self.report], [{**self.report, "reaction_terms": ["NAUSEA"]}],
            [{**self.report, "reaction_terms": ["VOMITING", "NAUSEA"]}],
        ):
            with self.subTest(returned=returned), self.assertRaises(AssertionError):
                self.verify("drug-safety", lambda connection, candidate: returned)

    def test_record_ordering_cannot_be_hidden_by_dictionary_comparison(self):
        other = {**self.report, "report_id": "report-second", "source_record_id": "report-second"}
        self.connection.execute("INSERT INTO safety_reports VALUES ('report-second',2,'fixture','report-second',NULL)")
        self.connection.execute("INSERT INTO safety_report_candidates VALUES ('report-second','candidate-a'),('report-second','candidate-b')")
        self.connection.execute("INSERT INTO safety_reactions VALUES ('report-second','NAUSEA'),('report-second','VOMITING')")
        with self.assertRaisesRegex(AssertionError, "Source record ordering mismatch"):
            self.verify("drug-safety", lambda connection, candidate: (
                [] if candidate == "candidate-c" else [self.report, other]
            ))


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.primary = executor()
        self.governance = executor()
        source = "def query():\n    return []\n"
        proposal = {"content": source, "sha256": hashlib.sha256(source.encode()).hexdigest()}
        self.implementors = {
            role: SimpleNamespace(file=AsyncMock(return_value=proposal))
            for role in ("clinical-trials", "drug-safety")
        }
        self.manifest = development_manifest()
        self.run_id = uuid4()

    async def run_candidate(self):
        return await integrate_and_validate(
            self.primary, self.governance, self.implementors, self.manifest, self.run_id,
        )

    async def test_only_scoped_files_transfer_before_independent_acceptance(self):
        self.primary.execute.side_effect = [
            Execution(0, "", ""), Execution(0, "", ""), Execution(0, "", ""),
            Execution(0, f"LAB722_SOURCE_FIDELITY:{self.run_id}:{self.primary.binding.sandbox_id}\n",
                      "Ran 9 tests in 1.0s\n\nOK\n"),
        ]
        checks = await self.run_candidate()
        self.assertEqual(len(checks), 5)
        self.assertTrue(all(check.passed and check.sandbox_id == self.primary.binding.sandbox_id
                            for check in checks))
        self.assertEqual(self.governance.execute.await_count, 2)
        self.implementors["clinical-trials"].file.assert_awaited_once_with(
            "src/research-portal/backend/trial_feature.py",
        )
        self.implementors["drug-safety"].file.assert_awaited_once_with(
            "src/research-portal/backend/safety_feature.py",
        )
        self.assertTrue(all(call.kwargs["verify_remote_status"]
                            for call in self.primary.execute.call_args_list))

    async def test_changed_frozen_data_blocks_before_acceptance(self):
        self.primary.execute.side_effect = [
            Execution(0, "", ""), Execution(0, "", ""), Execution(1, "", "data mismatch"),
        ]
        with self.assertRaisesRegex(RuntimeError, "changed its frozen data"):
            await self.run_candidate()
        self.assertEqual(self.primary.execute.await_count, 3)

    async def test_exit_zero_without_complete_acceptance_is_not_success(self):
        self.primary.execute.side_effect = [
            Execution(0, "", ""), Execution(0, "", ""), Execution(0, "", ""),
            Execution(0, "", "Ran 0 tests in 0.0s\n\nOK\n"),
        ]
        with self.assertRaisesRegex(RuntimeError, "Integrated acceptance failed"):
            await self.run_candidate()

    async def test_original_suite_cannot_substitute_for_source_fidelity(self):
        self.primary.execute.side_effect = [
            Execution(0, "", ""), Execution(0, "", ""), Execution(0, "", ""),
            Execution(0, "", "Ran 9 tests in 1.0s\n\nOK\n"),
        ]
        with self.assertRaisesRegex(RuntimeError, "Integrated acceptance failed"):
            await self.run_candidate()
        command = self.primary.execute.call_args.args[0]
        compile(shlex.split(command)[2], "<independent-source-fidelity>", "exec")

    async def test_public_integration_uses_original_source_bound_suite_and_full_pins(self):
        import test_worker_public as public_fixtures

        fixture = public_fixtures.PublicPackagingTests("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.manifest = Manifest.model_validate(fixture.manifest)
        self.primary.execute.side_effect = [
            Execution(0, "", ""), Execution(0, "", ""), Execution(0, "", ""),
            Execution(0, f"LAB722_SOURCE_FIDELITY:{self.run_id}:{self.primary.binding.sandbox_id}\n",
                      "Ran 8 tests in 1.0s\n\nOK\n"),
        ]
        checks = await self.run_candidate()
        self.assertTrue(all(check.passed for check in checks))
        integrity = shlex.split(self.primary.execute.call_args_list[2].args[0])[2]
        compile(integrity, "<public-frozen-verification>", "exec")
        self.assertIn("load_public_sources", integrity)
        self.assertIn("baseline_record['public_identity']", integrity)
        self.assertIn("baseline_record['protected_files']", integrity)
        command = self.primary.execute.call_args.args[0]
        validation = shlex.split(command)[2]
        compile(validation, "<public-source-fidelity>", "exec")
        anchor = next(line for line in validation.splitlines() if line.startswith("print('LAB722_PUBLIC_ANCHOR:"))
        output = StringIO()
        with redirect_stdout(output):
            exec(anchor, {
                "baseline_record": {"data_manifest_sha256": "frozen-manifest"},
                "record": {"source_record_id": "last-evidence-row"},
            })
        self.assertEqual(output.getvalue(), "LAB722_PUBLIC_ANCHOR:frozen-manifest\n")
        self.assertIn("-p test_frozen_public_research.py", command)
        self.assertIn("CALDOVA_ACCEPTANCE_PURPOSE=public-lab-development", command)
        self.assertIn("CALDOVA_DATA_MANIFEST_SHA256=", command)
        self.assertNotIn("-p test_research.py", command)
        self.primary.execute.side_effect = [
            Execution(0, "", ""), Execution(0, "", ""), Execution(0, "", ""),
            Execution(0, f"LAB722_SOURCE_FIDELITY:{self.run_id}:{self.primary.binding.sandbox_id}\n",
                      "Ran 9 tests in 1.0s\n\nOK\n"),
        ]
        with self.assertRaisesRegex(RuntimeError, "Integrated acceptance failed"):
            await self.run_candidate()

    async def test_egress_requires_verified_policy_and_run_bound_request_receipts(self):
        self.primary.execute.side_effect = [
            Execution(0, f"LAB722_{name}:{self.run_id}:{self.primary.binding.sandbox_id}\n", "")
            for name in ("egress-allowed", "egress-denied")
        ]
        checks = await validate_egress(self.primary, self.run_id)
        self.primary.verify_egress_policy.assert_awaited_once()
        self.assertEqual([check.name for check in checks], ["egress-allowed", "egress-denied"])
        self.assertTrue(all(check.passed for check in checks))
        denied = self.primary.execute.call_args_list[1]
        self.assertIn("error.code == 403", denied.args[0])
        self.assertTrue(denied.kwargs["verify_remote_status"])

    async def test_network_failure_or_unbound_output_is_not_policy_denial(self):
        for failure in (
            Execution(1, "", "TimeoutError"),
            Execution(0, "some other request was denied\n", ""),
        ):
            with self.subTest(failure=failure):
                self.primary.execute.side_effect = [
                    Execution(0, f"LAB722_egress-allowed:{self.run_id}:{self.primary.binding.sandbox_id}\n", ""),
                    failure,
                ]
                with self.assertRaisesRegex(RuntimeError, "egress-denied failed"):
                    await validate_egress(self.primary, self.run_id)

    async def test_unsafe_policy_stops_before_network_requests(self):
        self.primary.verify_egress_policy.side_effect = ValueError("Unexpected broad egress rule")
        with self.assertRaisesRegex(ValueError, "broad egress"):
            await validate_egress(self.primary, self.run_id)
        self.primary.execute.assert_not_awaited()

    async def test_worker_schema_receipt_uses_primary_and_cannot_accept_missing_remote_verification(self):
        executors = {role: executor() for role in ROLES}
        workers = [
            WorkerResult(
                schema_version="1.0", run_id=self.run_id, role=role,
                sandbox_id=executors[role].binding.sandbox_id,
                dataset_version=self.manifest.dataset_version,
                logical_sha256=self.manifest.logical_sha256,
                summary="Validated role", source_record_ids=[], blockers=[],
            ) for role in ROLES
        ]
        marker = f"LAB722_WORKERS_VALIDATED:{self.run_id}:{self.primary.binding.sandbox_id}"
        self.primary.execute.return_value = Execution(0, marker + "\n", "")
        receipt = await validate_worker_results(
            self.primary, workers, executors, self.manifest, self.run_id,
        )
        self.assertEqual(receipt.name, "worker-schema")
        self.assertEqual(receipt.sandbox_id, self.primary.binding.sandbox_id)
        self.assertTrue(self.primary.execute.call_args.kwargs["verify_remote_status"])
        script = shlex.split(self.primary.execute.call_args.args[0])[2]
        compile(script, "<trusted-worker-schema>", "exec")
        self.assertIn("worker['source_record_ids']", script)
        self.primary.execute.return_value = Execution(0, "", "")
        with self.assertRaisesRegex(RuntimeError, "worker-result validation failed"):
            await validate_worker_results(self.primary, workers, executors, self.manifest, self.run_id)
