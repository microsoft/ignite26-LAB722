import io
import json
import shlex
import time
import unittest
from contextlib import asynccontextmanager, redirect_stderr
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from azure.core.exceptions import ClientAuthenticationError, ResourceNotFoundError

from src.orchestrator.credentials import InMemoryFoundryCredential
from src.orchestrator.contracts import (
    APPROVED_TASKS, ROLE_CHECKS, ROLES, CheckEvidence,
    ImplementationPlan, SandboxBinding, WorkerResult,
)
from src.orchestrator.foundry import AGENT_NAME, CaldovaWorkflow
from src.orchestrator.run import run
from src.orchestrator.sandbox import Execution
from test_agents import development_manifest


@asynccontextmanager
async def connected_mcp_tools(executor, *, verification_command=None):
    yield "connected test tools"


class CredentialTests(unittest.IsolatedAsyncioTestCase):
    async def test_handoff_cannot_authorize_management_or_refresh_after_close(self):
        credential = InMemoryFoundryCredential(json.dumps({
            "accessToken": "not-a-real-token", "expires_on": int(time.time()) + 3600,
        }))
        token = await credential.get_token("https://ai.azure.com/.default")
        self.assertEqual(token.token, "not-a-real-token")
        with self.assertRaises(ClientAuthenticationError):
            await credential.get_token("https://management.azure.com/.default")
        await credential.close()
        with self.assertRaises(ClientAuthenticationError):
            await credential.get_token("https://ai.azure.com/.default")

    async def test_expired_tokens_cannot_look_like_successful_authentication(self):
        with self.assertRaises(ClientAuthenticationError):
            InMemoryFoundryCredential(json.dumps({
                "accessToken": "not-a-real-token", "expires_on": int(time.time()) - 1,
            }))


class FoundryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.manifest = development_manifest()
        self.client = SimpleNamespace(agents=SimpleNamespace(
            get=AsyncMock(side_effect=ResourceNotFoundError("Missing test agent")),
            create_version=AsyncMock(),
        ))
        self.workflow = CaldovaWorkflow(self.client, "test-model", uuid4(), self.manifest, {})

    async def test_owned_persistent_version_is_reused_with_matching_service_tool_schema(self):
        version = SimpleNamespace(name=AGENT_NAME, version="1", metadata={})
        self.client.agents.create_version.return_value = version
        with patch("src.orchestrator.foundry.FoundryAgent") as connected:
            await self.workflow.provision()
            created = self.client.agents.create_version.call_args.kwargs
            version.metadata = created["metadata"]
            declarations = created["definition"].tools
            self.assertEqual({tool.name for tool in declarations}, {"check_sandbox", "dispatch_worker"})
            self.assertTrue(all(tool.strict and tool.parameters["additionalProperties"] is False
                                for tool in declarations))
            self.client.agents.get.side_effect = None
            self.client.agents.get.return_value = SimpleNamespace(
                versions=SimpleNamespace(latest=version),
            )
            await self.workflow.provision()
        self.client.agents.create_version.assert_awaited_once()
        self.assertEqual(connected.call_args.kwargs["agent_version"], "1")

    async def test_an_existing_unowned_agent_is_not_overwritten(self):
        self.client.agents.get.side_effect = None
        self.client.agents.get.return_value = SimpleNamespace(
            versions=SimpleNamespace(latest=SimpleNamespace(metadata={"lab": "another-owner"})),
        )
        with self.assertRaises(PermissionError):
            await self.workflow.provision()
        self.client.agents.create_version.assert_not_awaited()


class WorkerWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.run_id = uuid4()
        self.manifest = development_manifest()
        snapshot_id = uuid4()
        self.executors = {
            role: SimpleNamespace(
                binding=SandboxBinding(role=role, sandbox_id=uuid4(), snapshot_id=snapshot_id),
                verify_binding=AsyncMock(),
                verify_egress_policy=AsyncMock(),
                execute=AsyncMock(return_value=Execution(
                    0, f"LAB722_FEATURE_READY:{self.run_id}:{role}\n", "",
                )),
                source_access=Mock(return_value={
                    "workspace": "/opt/caldova-lab",
                    "readable_paths": ["tests/test_research.py"],
                    "writable_paths": [],
                }),
            ) for role in ROLES
        }
        self.primary = SimpleNamespace(
            binding=SandboxBinding(
                role="quality-governance", sandbox_id=uuid4(), snapshot_id=snapshot_id,
            ),
            file=AsyncMock(return_value={"content": "scoped test source", "sha256": "d" * 64}),
        )
        self.egress_patch = patch("src.orchestrator.foundry.validate_egress", AsyncMock(return_value=[]))
        self.egress_patch.start()
        self.addCleanup(self.egress_patch.stop)
        self.result_patch = patch("src.orchestrator.foundry.validate_worker_results", AsyncMock(return_value=CheckEvidence(
            run_id=self.run_id, name="worker-schema", sandbox_id=self.primary.binding.sandbox_id,
            exit_code=0, passed=True, output_sha256="e" * 64,
        )))
        self.result_patch.start()
        self.addCleanup(self.result_patch.stop)
        self.workflow = CaldovaWorkflow(
            SimpleNamespace(), "test-model", self.run_id, self.manifest,
            self.executors, self.primary,
        )
        self.workflow.plan = ImplementationPlan(
            schema_version="1.0", run_id=self.run_id,
            dataset_version=self.manifest.dataset_version,
            logical_sha256=self.manifest.logical_sha256,
            release_requires_human_approval=True, limitations=self.manifest.limitations,
            assignments=[
                {"role": role, "task": APPROVED_TASKS[role],
                 "acceptance_criteria": sorted(ROLE_CHECKS[role])} for role in ROLES
            ],
        )
        self.results = {
            role: WorkerResult(
                schema_version="1.0", run_id=self.run_id, role=role,
                sandbox_id=self.executors[role].binding.sandbox_id,
                dataset_version=self.manifest.dataset_version,
                logical_sha256=self.manifest.logical_sha256,
                summary="Verified assigned implementation", source_record_ids=[], blockers=[],
            ) for role in ROLES
        }

    async def test_worker_receives_discovered_paths_and_frozen_database_location(self):
        worker = SimpleNamespace(
            run=AsyncMock(return_value=SimpleNamespace(text=self.results["clinical-trials"].model_dump_json())),
            create_session=Mock(return_value="isolated session"),
        )
        self.workflow.mode = "workers"
        with (
            patch("src.orchestrator.foundry.worker_mcp_tools", side_effect=connected_mcp_tools) as mcp_tools,
            patch("src.orchestrator.foundry.FoundryChatClient") as connected_client,
            patch("src.orchestrator.foundry.Agent", return_value=worker) as create_worker,
        ):
            sdk_client = connected_client.return_value.client
            await self.workflow.dispatch_worker("clinical-trials", APPROVED_TASKS["clinical-trials"])
        payload = json.loads(worker.run.call_args.args[0])
        self.assertEqual(payload["source_access"], self.executors["clinical-trials"].source_access())
        self.assertEqual(payload["database_path"], "data/artifacts/development/research.duckdb")
        self.assertEqual(payload["manifest"], self.manifest.model_dump(mode="json"))
        self.executors["clinical-trials"].verify_binding.assert_awaited_once()
        sdk_client.with_options.assert_called_once_with(max_retries=6)
        self.assertIs(create_worker.call_args.kwargs["client"].client, sdk_client.with_options.return_value)
        self.assertTrue(self.executors["clinical-trials"].execute.call_args.kwargs["verify_remote_status"])
        script = shlex.split(self.executors["clinical-trials"].execute.call_args.args[0])[2]
        compile(script, "<trusted-feature-check>", "exec")
        self.assertIn("source_record_id", script)
        self.assertEqual(payload["verification_tool"], "verify_feature")
        self.assertNotIn("verification_command", payload)
        worker_script = shlex.split(mcp_tools.call_args.kwargs["verification_command"])[2]
        compile(worker_script, "<worker-feature-check>", "exec")
        self.assertIn("Source record fidelity mismatch", worker_script)
        self.assertIn("read_only=True", worker_script)
        self.assertIn(payload["verification_success_marker"], worker_script)
        self.assertIn("'from queries import records'", payload["runtime_contract"])

    async def test_failed_import_returns_diagnostics_to_the_same_worker_session(self):
        role = "drug-safety"
        worker = SimpleNamespace(
            run=AsyncMock(return_value=SimpleNamespace(text=self.results[role].model_dump_json())),
            create_session=Mock(return_value="isolated safety session"),
        )
        self.executors[role].execute.side_effect = [
            Execution(1, "", "ModuleNotFoundError: No module named src.research_portal"),
            Execution(0, f"LAB722_FEATURE_READY:{self.run_id}:{role}\n", ""),
        ]
        self.workflow.mode = "workers"
        with (
            patch("src.orchestrator.foundry.worker_mcp_tools", connected_mcp_tools),
            patch("src.orchestrator.foundry.FoundryChatClient"),
            patch("src.orchestrator.foundry.Agent", return_value=worker),
        ):
            await self.workflow.dispatch_worker(role, APPROVED_TASKS[role])
        self.assertEqual(worker.run.await_count, 2)
        self.assertTrue(all(call.kwargs["session"] == "isolated safety session"
                            for call in worker.run.call_args_list))
        feedback = json.loads(worker.run.call_args_list[1].args[0])
        self.assertIn("src.research_portal", feedback["validation_failure"]["stderr"])
        initial = json.loads(worker.run.call_args_list[0].args[0])
        self.assertEqual(feedback["verification_tool"], initial["verification_tool"])
        self.assertEqual(feedback["verification_success_marker"], initial["verification_success_marker"])
        self.assertEqual(feedback["source_access"], initial["source_access"])
        for field in ("role", "run_id", "sandbox_id", "dataset_version", "logical_sha256"):
            self.assertEqual(feedback[field], initial[field])
        self.assertIn("'from queries import records'", feedback["instruction"])
        self.assertEqual(self.workflow.worker_results[role], self.results[role])
        self.assertEqual(len(self.workflow.worker_evidence), 1)
        self.assertTrue(self.workflow.worker_evidence[0].passed)

    async def test_identity_drift_is_repaired_without_tools_before_feature_acceptance(self):
        role = "drug-safety"
        invalid = self.results[role].model_copy(update={
            "role": "clinical-trials", "run_id": uuid4(), "sandbox_id": uuid4(),
            "dataset_version": "foreign-dataset", "logical_sha256": "f" * 64,
        })
        worker = SimpleNamespace(
            run=AsyncMock(side_effect=[
                SimpleNamespace(text=invalid.model_dump_json()),
                SimpleNamespace(text=self.results[role].model_dump_json()),
            ]),
            create_session=Mock(return_value="isolated safety session"),
        )
        self.workflow.mode = "workers"
        diagnostic = io.StringIO()
        with (
            patch("src.orchestrator.foundry.worker_mcp_tools", connected_mcp_tools),
            patch("src.orchestrator.foundry.FoundryChatClient"),
            patch("src.orchestrator.foundry.Agent", return_value=worker),
            redirect_stderr(diagnostic),
        ):
            returned = await self.workflow.dispatch_worker(role, APPROVED_TASKS[role])
        self.assertEqual(WorkerResult.model_validate_json(returned), self.results[role])
        self.assertEqual(self.workflow.worker_results[role], self.results[role])
        self.executors[role].execute.assert_awaited_once()
        initial = json.loads(worker.run.call_args_list[0].args[0])
        feedback = json.loads(worker.run.call_args_list[1].args[0])
        expected = self.results[role].model_dump(mode="json")
        received = invalid.model_dump(mode="json")
        for field in ("role", "run_id", "sandbox_id", "dataset_version", "logical_sha256"):
            self.assertEqual(initial[field], expected[field])
            self.assertEqual(feedback[field], expected[field])
            self.assertEqual(feedback["identity_mismatches"][field], {
                "expected": expected[field], "received": received[field],
            })
        self.assertEqual(json.loads(diagnostic.getvalue())["identity_mismatches"],
                         feedback["identity_mismatches"])
        self.assertEqual(worker.run.call_args_list[1].kwargs["options"], {"tool_choice": "none"})
        self.assertTrue(all(call.kwargs["session"] == "isolated safety session"
                            for call in worker.run.call_args_list))
        self.assertIn("Repair only the report", feedback["instruction"])
        self.assertEqual(len(self.workflow.worker_evidence), 1)

    async def test_persistent_identity_drift_stops_before_integration(self):
        role = "drug-safety"
        invalid = self.results[role].model_copy(update={"sandbox_id": uuid4()})
        worker = SimpleNamespace(
            run=AsyncMock(return_value=SimpleNamespace(text=invalid.model_dump_json())),
            create_session=Mock(return_value="isolated safety session"),
        )

        async def dispatch(*args, **kwargs):
            await self.workflow.dispatch_worker(role, APPROVED_TASKS[role])

        agent = SimpleNamespace(run=AsyncMock(side_effect=dispatch))
        diagnostic = io.StringIO()
        with (
            patch("src.orchestrator.foundry.worker_mcp_tools", connected_mcp_tools),
            patch("src.orchestrator.foundry.FoundryChatClient"),
            patch("src.orchestrator.foundry.Agent", return_value=worker),
            patch("src.orchestrator.foundry.integrate_and_validate", AsyncMock()) as integrate,
            redirect_stderr(diagnostic),
        ):
            with self.assertRaisesRegex(ValueError, "identity mismatch after bounded report repair"):
                await self.workflow.run_workers(agent)
        self.assertEqual(worker.run.await_count, 3)
        self.assertTrue(all(call.kwargs["options"] == {"tool_choice": "none"}
                            for call in worker.run.call_args_list[1:]))
        failures = [json.loads(line) for line in diagnostic.getvalue().splitlines()]
        self.assertEqual([failure["attempt"] for failure in failures], [1, 2, 3])
        self.assertEqual(failures[-1]["identity_mismatches"]["sandbox_id"]["received"],
                         str(invalid.sandbox_id))
        self.executors[role].execute.assert_not_awaited()
        integrate.assert_not_awaited()
        self.assertEqual(self.workflow.worker_results, {})
        self.assertEqual(self.workflow.worker_evidence, [])
        self.assertFalse(self.workflow.candidate_integrated)

    async def test_feature_and_report_repairs_share_the_same_attempt_budget(self):
        role = "drug-safety"
        invalid = self.results[role].model_copy(update={"run_id": uuid4()})
        worker = SimpleNamespace(
            run=AsyncMock(side_effect=[
                SimpleNamespace(text=self.results[role].model_dump_json()),
                SimpleNamespace(text=invalid.model_dump_json()),
                SimpleNamespace(text=self.results[role].model_dump_json()),
            ]),
            create_session=Mock(return_value="isolated safety session"),
        )
        self.executors[role].execute.return_value = Execution(1, "", "Feature is still invalid")
        self.workflow.mode = "workers"
        with (
            patch("src.orchestrator.foundry.worker_mcp_tools", connected_mcp_tools),
            patch("src.orchestrator.foundry.FoundryChatClient"),
            patch("src.orchestrator.foundry.Agent", return_value=worker),
            redirect_stderr(io.StringIO()),
        ):
            with self.assertRaisesRegex(RuntimeError, "feature contract failed after bounded repair"):
                await self.workflow.dispatch_worker(role, APPROVED_TASKS[role])
        self.assertEqual(worker.run.await_count, 3)
        self.assertEqual(self.executors[role].execute.await_count, 2)
        self.assertIsNone(worker.run.call_args_list[1].kwargs["options"])
        self.assertEqual(worker.run.call_args_list[2].kwargs["options"], {"tool_choice": "none"})
        self.assertNotIn(role, self.workflow.worker_results)
        self.assertEqual(self.workflow.worker_evidence, [])

    async def test_repeated_import_failure_cannot_become_a_completed_worker_result(self):
        role = "clinical-trials"
        worker = SimpleNamespace(
            run=AsyncMock(return_value=SimpleNamespace(text=self.results[role].model_dump_json())),
            create_session=Mock(return_value="isolated trial session"),
        )
        self.executors[role].execute.return_value = Execution(1, "", "invalid module import")
        self.workflow.mode = "workers"
        with (
            patch("src.orchestrator.foundry.worker_mcp_tools", connected_mcp_tools),
            patch("src.orchestrator.foundry.FoundryChatClient"),
            patch("src.orchestrator.foundry.Agent", return_value=worker),
        ):
            with self.assertRaisesRegex(RuntimeError, "feature contract failed after bounded repair"):
                await self.workflow.dispatch_worker(role, APPROVED_TASKS[role])
        self.assertEqual(worker.run.await_count, 3)
        self.assertNotIn(role, self.workflow.worker_results)
        self.assertEqual(self.workflow.worker_evidence, [])

    async def test_governance_repairs_foreign_record_ids_without_implementation_access(self):
        role = "quality-governance"
        invalid = self.results[role].model_copy(update={"source_record_ids": ["candidate-a"]})
        valid = self.results[role].model_copy(update={"source_record_ids": ["DEMO-TRIAL-001"]})
        worker = SimpleNamespace(
            run=AsyncMock(side_effect=[
                SimpleNamespace(text=invalid.model_dump_json()),
                SimpleNamespace(text=valid.model_dump_json()),
            ]),
            create_session=Mock(return_value="isolated governance session"),
        )
        self.executors[role].execute.side_effect = [
            Execution(1, "", "Reported source_record_ids are not frozen evidence identifiers"),
            Execution(0, f"LAB722_FEATURE_READY:{self.run_id}:{role}\n", ""),
        ]
        self.workflow.mode = "workers"
        self.workflow.candidate_integrated = True
        with (
            patch("src.orchestrator.foundry.worker_mcp_tools", connected_mcp_tools),
            patch("src.orchestrator.foundry.FoundryChatClient"),
            patch("src.orchestrator.foundry.Agent", return_value=worker),
        ):
            await self.workflow.dispatch_worker(role, APPROVED_TASKS[role])
        self.assertEqual(self.workflow.worker_results[role].source_record_ids, ["DEMO-TRIAL-001"])
        script = shlex.split(self.executors[role].execute.call_args.args[0])[2]
        compile(script, "<trusted-governance-check>", "exec")
        self.assertNotIn("feature =", script)
        feedback = json.loads(worker.run.call_args.args[0])
        self.assertIn("Governance must repair its report, not source files", feedback["instruction"])

    async def test_governance_cannot_start_against_an_unintegrated_starter(self):
        self.workflow.mode = "workers"
        with self.assertRaisesRegex(PermissionError, "independently tested integrated"):
            await self.workflow.dispatch_worker("quality-governance", APPROVED_TASKS["quality-governance"])
        self.executors["quality-governance"].verify_binding.assert_not_awaited()

    async def test_implementation_blockers_report_the_role_and_stop_before_integration(self):
        async def dispatch_implementors(*args, **kwargs):
            self.workflow.worker_results.update({
                role: self.results[role] for role in ("clinical-trials", "drug-safety")
            })
            self.workflow.worker_results["drug-safety"] = self.results["drug-safety"].model_copy(
                update={"blockers": ["Could not inspect the frozen database schema"]},
            )

        agent = SimpleNamespace(run=AsyncMock(side_effect=dispatch_implementors))
        with patch("src.orchestrator.foundry.integrate_and_validate", AsyncMock()) as integrate:
            with self.assertRaisesRegex(RuntimeError, "drug-safety: Could not inspect"):
                await self.workflow.run_workers(agent)
        integrate.assert_not_awaited()
        self.assertEqual(agent.run.await_count, 1)

    async def test_governance_starts_only_after_independent_integration_with_receipts(self):
        evidence = [CheckEvidence(
            run_id=self.run_id, name="application-acceptance",
            sandbox_id=self.primary.binding.sandbox_id,
            exit_code=0, passed=True, output_sha256="c" * 64,
        )]

        async def dispatch(*args, **kwargs):
            payload = json.loads(args[0])
            if "assignments" in payload:
                self.assertEqual(
                    {item["role"] for item in payload["assignments"]}, {"clinical-trials", "drug-safety"},
                )
                self.workflow.worker_results.update({
                    role: self.results[role] for role in ("clinical-trials", "drug-safety")
                })
            else:
                self.assertTrue(self.workflow.candidate_integrated)
                self.assertEqual(payload["integration_evidence"], [check.model_dump(mode="json") for check in evidence])
                self.workflow.worker_results["quality-governance"] = self.results["quality-governance"]

        agent = SimpleNamespace(run=AsyncMock(side_effect=dispatch))
        with patch("src.orchestrator.foundry.integrate_and_validate", AsyncMock(return_value=evidence)) as integrate:
            results = await self.workflow.run_workers(agent)
        self.assertEqual({result.role for result in results}, set(ROLES))
        integrate.assert_awaited_once_with(
            self.primary, self.executors["quality-governance"],
            self.executors, self.manifest, self.run_id,
        )

    async def test_failed_acceptance_never_dispatches_governance(self):
        async def dispatch_implementors(*args, **kwargs):
            self.workflow.worker_results.update({
                role: self.results[role] for role in ("clinical-trials", "drug-safety")
            })

        agent = SimpleNamespace(run=AsyncMock(side_effect=dispatch_implementors))
        with patch("src.orchestrator.foundry.integrate_and_validate", AsyncMock(
            side_effect=RuntimeError("Integrated acceptance failed"),
        )):
            with self.assertRaisesRegex(RuntimeError, "Integrated acceptance failed"):
                await self.workflow.run_workers(agent)
        self.assertFalse(self.workflow.candidate_integrated)
        self.assertEqual(agent.run.await_count, 1)

    async def test_cli_failure_keeps_worker_diagnostics_without_claiming_release(self):
        self.workflow.worker_results["drug-safety"] = self.results["drug-safety"].model_copy(
            update={"blockers": ["Frozen schema inspection failed"]},
        )
        self.workflow.provision = AsyncMock()
        self.workflow.create_plan = AsyncMock(return_value=self.workflow.plan)
        self.workflow.run_workers = AsyncMock(side_effect=RuntimeError("drug-safety: Frozen schema inspection failed"))
        arguments = SimpleNamespace(
            project_endpoint="https://example.services.ai.azure.com/api/projects/caldova",
            subscription=uuid4(), resource_group="lab-rg", region="westus3", group="lab-sandboxes",
            bindings=None, mode="workers", approve_plan=True, validation_sandbox_id=None,
            token_stdin=False, model="test-model",
        )
        diagnostic = io.StringIO()
        with (
            patch("src.orchestrator.run.read_manifest", return_value=self.manifest),
            patch("src.orchestrator.run.AzureCliCredential"),
            patch("src.orchestrator.run.AIProjectClient"),
            patch("src.orchestrator.run.CaldovaWorkflow", return_value=self.workflow),
            redirect_stderr(diagnostic),
        ):
            with self.assertRaisesRegex(RuntimeError, "Frozen schema inspection failed"):
                await run(arguments)
        report = json.loads(diagnostic.getvalue())
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["release_status"], "not-approved")
        self.assertEqual(report["workers"][0]["blockers"], ["Frozen schema inspection failed"])
