import hashlib
import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from pydantic import ValidationError

from data.pipeline.contracts import Manifest
from src.orchestrator.contracts import (
    APPROVED_TASKS, ROLE_CHECKS, Assignment, CheckEvidence, HumanApproval,
    ImplementationPlan, REQUIRED_CHECKS, ROLES,
    SandboxBinding, WorkerResult, decide_release,
)
from src.orchestrator.sandbox import Execution, SandboxExecutor, SandboxScope


def development_manifest():
    return Manifest(
        schema_version="1.0", dataset_version="synthetic-test",
        dataset_kind="synthetic-development", built_at=datetime.now(timezone.utc),
        pipeline_commit="uncommitted-development", logical_sha256="a" * 64,
        database={"path": "research.duckdb", "sha256": "b" * 64, "bytes": 1},
        record_counts={"trials": 1},
        sources=[{
            "source_id": "synthetic", "name": "Invented fixtures", "release": "test",
            "attribution": "Lab-owned invented data", "license_notes": "No clinical evidence",
        }],
    )


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.run_id = uuid4()
        self.validation_sandbox_id = uuid4()
        self.manifest = development_manifest()
        snapshot_id = uuid4()
        self.bindings = [
            SandboxBinding(role=role, sandbox_id=uuid4(), snapshot_id=snapshot_id) for role in ROLES
        ]
        self.workers = [
            WorkerResult(
                schema_version="1.0", run_id=self.run_id, role=binding.role,
                sandbox_id=binding.sandbox_id, dataset_version=self.manifest.dataset_version,
                logical_sha256=self.manifest.logical_sha256, summary="Validated worker output",
                source_record_ids=[], blockers=[],
            ) for binding in self.bindings
        ]
        self.checks = [
            CheckEvidence(
                run_id=self.run_id, name=name, sandbox_id=self.validation_sandbox_id,
                exit_code=0, passed=True, output_sha256="c" * 64,
            ) for name in sorted(REQUIRED_CHECKS)
        ]
        self.image_digest = "sha256:" + "d" * 64
        self.approval = HumanApproval(
            run_id=self.run_id, logical_sha256=self.manifest.logical_sha256,
            image_digest=self.image_digest, approved_by="Test maintainer",
        )

    def decide(self, **changes):
        values = dict(
            run_id=self.run_id, manifest=self.manifest, bindings=self.bindings,
            validation_sandbox_id=self.validation_sandbox_id,
            workers=self.workers, checks=self.checks, approval=self.approval,
            image_digest=self.image_digest, reviewed_release=False,
        )
        values.update(changes)
        return decide_release(**values)

    def test_synthetic_evidence_can_only_approve_a_development_preview(self):
        self.assertEqual(self.decide().status, "development-preview-approved")
        reviewed = self.decide(reviewed_release=True)
        self.assertEqual(reviewed.status, "blocked")
        self.assertIsNone(reviewed.image_digest)
        self.assertTrue(any("reviewed public data" in reason for reason in reviewed.reasons))

    def test_local_public_source_snapshot_cannot_enable_an_attendee_release(self):
        content = self.manifest.model_dump(mode="json")
        review = {"approved_by": "Fictional unit-test owner", "approved_at": "2026-10-10T06:00:00Z"}
        content.update(dataset_kind="reviewed-public", review=review)
        for source in content["sources"]:
            source.update(url="https://example.invalid/source", retrieved_at="2026-10-10T00:00:00Z")
        content["source_records"] = {"path": "source-records.json", "sha256": "e" * 64, "bytes": 1}
        content["pipeline_source"] = {"path": "pipeline-source.zip", "sha256": "f" * 64, "bytes": 1}
        content["public_extract"] = {
            "source_use": {
                **review, "scope": "project-owner-selected-public-lab-use",
                "draft_sha256": "e" * 64, "draft_provenance_sha256": "0" * 64,
                "instruction": "Use the exact fictional unit-test slice locally.",
            },
            "mapping_version": "conservative-exact-generics-v1", "coverage_notes": ["Fictional test slice"],
            "trial_bucket_counts": {}, "report_candidate_counts": {}, "source_quality_counts": {},
        }
        public = Manifest.model_validate(content)
        self.assertFalse(public.has_committed_pipeline)
        self.assertTrue(public.model_copy(update={"pipeline_commit": "9" * 40}).has_committed_pipeline)
        invalid = {**content, "pipeline_commit": "a" * 39 + "g"}
        with self.assertRaisesRegex(ValidationError, "full pipeline commit"):
            Manifest.model_validate(invalid)
        decision = self.decide(manifest=public, reviewed_release=True)
        self.assertEqual(decision.status, "blocked")
        self.assertTrue(any("committed pipeline" in reason for reason in decision.reasons))

    def test_approval_must_bind_the_exact_run_dataset_and_image(self):
        for changes in (
            {"approval": None},
            {"image_digest": "sha256:" + "e" * 64},
            {"run_id": uuid4()},
        ):
            with self.subTest(changes=changes):
                self.assertEqual(self.decide(**changes).status, "blocked")

    def test_workers_must_be_complete_distinct_and_from_one_snapshot(self):
        repeated = self.bindings[-1].model_copy(update={"sandbox_id": self.bindings[0].sandbox_id})
        another_snapshot = self.bindings[-1].model_copy(update={"snapshot_id": uuid4()})
        for changes in (
            {"workers": self.workers[:2]},
            {"bindings": [*self.bindings[:2], repeated]},
            {"bindings": [*self.bindings[:2], another_snapshot]},
            {"validation_sandbox_id": self.bindings[0].sandbox_id},
        ):
            with self.subTest(changes=changes):
                self.assertEqual(self.decide(**changes).status, "blocked")

    def test_foreign_results_and_unresolved_blockers_are_rejected(self):
        for changes in (
            {"logical_sha256": "e" * 64},
            {"sandbox_id": uuid4()},
            {"dataset_version": "another-dataset"},
            {"blockers": ["Integration is missing"]},
        ):
            with self.subTest(changes=changes):
                worker = self.workers[-1].model_copy(update=changes)
                self.assertEqual(self.decide(workers=[*self.workers[:2], worker]).status, "blocked")

    def test_missing_duplicate_failed_or_foreign_checks_cannot_pass(self):
        for checks in (
            self.checks[:1],
            [*self.checks, self.checks[0]],
            [*self.checks[:-1], self.checks[-1].model_copy(update={"exit_code": 1})],
            [*self.checks[:-1], self.checks[-1].model_copy(update={"passed": False})],
            [*self.checks[:-1], self.checks[-1].model_copy(update={"sandbox_id": uuid4()})],
            [check.model_copy(update={"sandbox_id": self.bindings[-1].sandbox_id})
             if check.name == "application-acceptance" else check for check in self.checks],
        ):
            with self.subTest(checks=checks):
                self.assertEqual(self.decide(checks=checks).status, "blocked")

    def test_model_confidence_cannot_be_smuggled_into_worker_evidence(self):
        result = self.workers[0].model_dump()
        result["release_approved"] = True
        with self.assertRaises(ValidationError):
            WorkerResult.model_validate(result)

    def test_plan_rejects_duplicate_specialists(self):
        values = dict(
            schema_version="1.0", run_id=self.run_id, dataset_version=self.manifest.dataset_version,
            logical_sha256=self.manifest.logical_sha256, release_requires_human_approval=True,
            limitations=self.manifest.limitations,
            assignments=[
                {"role": role, "task": APPROVED_TASKS[role], "acceptance_criteria": sorted(ROLE_CHECKS[role])}
                for role in ("clinical-trials", "clinical-trials", "drug-safety")
            ],
        )
        with self.assertRaisesRegex(ValidationError, "each specialist"):
            ImplementationPlan.model_validate(values)

    def test_plans_cannot_turn_software_delivery_into_clinical_analysis(self):
        with self.assertRaisesRegex(ValidationError, "approved software task"):
            Assignment(
                role="drug-safety", task="Analyze safety signals attached to candidates and trials",
                acceptance_criteria=["Summarize adverse-event frequencies"],
            )


class SandboxTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.binding = SandboxBinding(
            role="clinical-trials", sandbox_id=uuid4(), snapshot_id=uuid4(),
        )
        self.scope = SandboxScope(uuid4(), "lab-rg", "westus3", "lab-sandboxes")
        self.executor = SandboxExecutor("aca.exe", self.scope, self.binding)

    async def test_execution_uses_only_bound_id_scope_and_workspace(self):
        process = SimpleNamespace(
            communicate=AsyncMock(return_value=(b"remote output", b"")),
            returncode=0, kill=Mock(),
        )
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)) as create:
            result = await self.executor.execute("printf 'remote output'")
        arguments = create.call_args.args
        self.assertEqual(arguments[arguments.index("--id") + 1], str(self.binding.sandbox_id))
        self.assertEqual(arguments[arguments.index("--subscription") + 1], str(self.scope.subscription))
        self.assertEqual(arguments[arguments.index("--group") + 1], self.scope.group)
        self.assertEqual(arguments[arguments.index("--working-directory") + 1], self.binding.workspace)
        self.assertEqual(result.stdout, "remote output")

    async def test_paths_and_cross_specialist_writes_fail_before_remote_execution(self):
        self.executor.execute = AsyncMock()
        for path, content in (
            ("../../.azure/accessTokens.json", None),
            ("data\\fixtures\\research-data.json", None),
            ("data/fixtures/research-data.json", "overwrite fixtures"),
            ("src/research-portal/backend/safety_feature.py", "cross-worker update"),
            ("/etc/passwd", None),
        ):
            with self.subTest(path=path), self.assertRaises((ValueError, PermissionError)):
                await self.executor.file(path, content)
        self.executor.execute.assert_not_called()

    async def test_remote_file_checksum_is_verified_despite_cli_resume_progress(self):
        path = "src/research-portal/backend/trial_feature.py"
        content = "def query_trials():\n    return []\n"
        payload = {"path": path, "content": content, "sha256": hashlib.sha256(content.encode()).hexdigest()}
        self.executor.execute = AsyncMock(return_value=Execution(
            0, "Sandbox resumed\nCALDOVA_FILE_RESULT=" + json.dumps(payload) + "\n", "",
        ))
        result = await self.executor.file(path)
        self.assertEqual(result["content"], content)
        payload["sha256"] = "0" * 64
        self.executor.execute.return_value = Execution(0, "CALDOVA_FILE_RESULT=" + json.dumps(payload), "")
        with self.assertRaisesRegex(ValueError, "checksum"):
            await self.executor.file(path)

    async def test_timeout_terminates_the_owned_cli_process(self):
        async def expire(awaitable, timeout):
            awaitable.close()
            raise TimeoutError

        process = SimpleNamespace(
            communicate=AsyncMock(return_value=(b"", b"")),
            returncode=None, kill=Mock(),
        )
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)), \
                patch("asyncio.wait_for", expire):
            with self.assertRaises(TimeoutError):
                await self.executor.execute("sleep 999")
        process.kill.assert_called_once()


if __name__ == "__main__":
    unittest.main()
