import asyncio
import copy
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx

from src.reactor import agent_runtime
from src.reactor.execution import create_app
from src.reactor.models import ModelRelay
from src.reactor.ownership import ACCOUNTS, OwnershipStore
from src.reactor.research import assess_specialist, reference_results, reviewed_source, selected_records
from src.reactor.service_auth import ServiceCaller
from src.runtime.frozen import PINS


SOURCE = Path(__file__).parents[1] / "data" / "lab-datasets" / "caldova-public-lab-use-v2" / "source-records.json"


class ModelRelayContracts(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.credential = SimpleNamespace(get_token=AsyncMock(return_value=SimpleNamespace(token="fake-model-token")))
        self.relay = ModelRelay("https://allocated.openai.azure.com/openai/v1/chat/completions",
                                "allocated-model", self.credential)
        await self.relay.http.aclose()
        self.requests = []
        self.reply = {"choices": [{"message": {"role": "assistant", "tool_calls": []}}], "usage": {"total_tokens": 5}}

        def receive(request):
            self.requests.append(request)
            return httpx.Response(200, json=self.reply)

        self.relay.http = httpx.AsyncClient(transport=httpx.MockTransport(receive))
        self.request = {"request_id": uuid4().hex, "turn": 1, "tools": agent_runtime.tools_for("clinical_trials"),
                        "messages": [{"role": "user", "content": "Inspect only selected public records."}]}

    async def asyncTearDown(self):
        await self.relay.close()

    async def test_model_token_stays_in_manager_and_response_is_correlated(self):
        result = await self.relay.complete("clinical_trials", self.request)
        self.credential.get_token.assert_awaited_once_with("https://cognitiveservices.azure.com/.default")
        self.assertEqual(self.requests[0].headers["Authorization"], "Bearer fake-model-token")
        self.assertEqual(json.loads(self.requests[0].content)["model"], "allocated-model")
        self.assertEqual(result["request_id"], self.request["request_id"])
        self.assertNotIn("fake-model-token", json.dumps(result))

    async def test_changed_tool_contract_is_rejected_before_token_or_model_call(self):
        self.request["tools"][0]["function"]["name"] = "select_foreign_customer"
        with self.assertRaisesRegex(ValueError, "invalid model/tool contract"):
            await self.relay.complete("clinical_trials", self.request)
        self.credential.get_token.assert_not_awaited()
        self.assertEqual(self.requests, [])

    async def test_missing_assistant_choice_is_an_explicit_error(self):
        self.reply = {"choices": []}
        with self.assertRaisesRegex(ValueError, "no valid assistant choice"):
            await self.relay.complete("clinical_trials", self.request)

    async def test_throttle_retries_the_same_turn_without_exposing_token(self):
        def receive(request):
            self.requests.append(request)
            if len(self.requests) == 1:
                return httpx.Response(429, headers={"retry-after": "0"})
            return httpx.Response(200, json=self.reply)
        await self.relay.http.aclose()
        self.relay.http = httpx.AsyncClient(transport=httpx.MockTransport(receive))
        result = await self.relay.complete("clinical_trials", self.request)
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.requests[0].content, self.requests[1].content)
        self.credential.get_token.assert_awaited_once()
        self.assertEqual(result["request_id"], self.request["request_id"])

    async def test_throttle_cannot_exceed_remaining_agent_budget(self):
        await self.relay.http.aclose()
        self.relay.http = httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(429, headers={"retry-after": "60"}),
        ))
        self.request["remaining_seconds"] = 1
        with self.assertRaises(httpx.HTTPStatusError):
            await self.relay.complete("clinical_trials", self.request)


class ResearchContracts(unittest.TestCase):
    def test_duplicate_short_launch_does_not_restart_resident_agent(self):
        payload = {"role": "clinical_trials", "run_id": str(uuid4()), "question": "Inspect this owned run."}
        with tempfile.TemporaryDirectory() as temporary, patch.object(
            agent_runtime, "BRIDGE", Path(temporary) / "bridge",
        ), patch.object(os, "getuid", return_value=0, create=True), patch.object(
            agent_runtime.subprocess, "Popen", return_value=SimpleNamespace(pid=123),
        ) as spawn:
            self.assertTrue(agent_runtime.start_agent(payload)["started"])
            self.assertFalse(agent_runtime.start_agent(payload)["started"])
            spawn.assert_called_once()
            self.assertTrue(spawn.call_args.kwargs["start_new_session"])
            self.assertNotIn("IDENTITY_ENDPOINT", spawn.call_args.kwargs["env"])
            with self.assertRaisesRegex(ValueError, "changed agent payload"):
                agent_runtime.start_agent({**payload, "question": "Changed work"})

    def test_snapshot_metadata_uses_pinned_manifest_without_rewriting_source(self):
        source = json.loads(SOURCE.read_text())
        before = copy.deepcopy(source)
        manifest = json.loads(SOURCE.with_name("data-manifest.json").read_text())
        result = reviewed_source(source, manifest)
        self.assertEqual(source, before)
        self.assertEqual(result["dataset_version"], "caldova-public-lab-use-v2")
        self.assertEqual(result["source_dataset_version"], source["dataset_version"])
        self.assertFalse(result["attendee_release_approved"])
        self.assertEqual(result["trials"], source["trials"])

    def test_research_operations_are_discoverable_paths_with_root_bound_schemas(self):
        spec = json.loads((SOURCE.parents[3] / "src" / "reactor" / "openapi.json").read_text())
        for path, role in (("/agents/clinical-trials", "clinical_trials"),
                           ("/agents/drug-specialist", "drug_specialist"),
                           ("/agents/quality-assurance", "quality_assurance")):
            operation = spec["paths"][path]["post"]
            self.assertEqual(operation["operationId"], role)
            header = operation["parameters"][0]
            self.assertEqual(header["name"], "X-Reactor-Run-Grant")
            self.assertEqual(header["in"], "header")
            self.assertTrue(header["required"])
            ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
            target = spec
            for segment in ref.removeprefix("#/").split("/"):
                target = target[segment]
            self.assertTrue(target)
        binding = spec["components"]["schemas"]["AgentBinding"]
        self.assertNotIn("run_grant", binding["properties"])
        self.assertNotIn("candidate_id", binding["properties"])
        self.assertNotIn("model", binding["properties"])

    def test_condition_filters_trials_but_not_drug_safety(self):
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        all_trials, all_safety = selected_records(source, {"candidate_id": "liraglutide", "condition": ""})
        filtered, safety = selected_records(source, {"candidate_id": "liraglutide", "condition": "obesity"})
        self.assertLess(len(filtered), len(all_trials))
        self.assertEqual(safety, all_safety)
        self.assertTrue(all("obesity" in row["conditions"] for row in filtered))

    def test_wrong_counts_and_missing_sources_cannot_pass(self):
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        selection = {"candidate_id": "semaglutide", "condition": ""}
        correct = reference_results(source, selection)["clinical_trials"]
        self.assertTrue(assess_specialist("clinical_trials", correct, source, selection)["passed"])
        wrong = copy.deepcopy(correct)
        key = next(iter(wrong["phase_counts"]))
        wrong["phase_counts"][key] += 1
        self.assertFalse(assess_specialist("clinical_trials", wrong, source, selection)["passed"])
        wrong = copy.deepcopy(correct)
        wrong["source_ids"] = wrong["source_ids"][:-1]
        self.assertFalse(assess_specialist("clinical_trials", wrong, source, selection)["passed"])
        self.assertFalse(assess_specialist(
            "clinical_trials", {**correct, "unsupported_recommendation": "invented"}, source, selection,
        )["passed"])
        with self.assertRaises(ValueError):
            selected_records(source, {"candidate_id": "invented-drug", "condition": ""})

    def test_full_agent_loop_requires_inspection_and_execution(self):
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        selection = {"candidate_id": "semaglutide", "condition": "obesity"}
        expected = reference_results(source, selection)["clinical_trials"]
        payload = {"role": "clinical_trials", "run_id": str(uuid4()), "selection": selection,
                   "question": "Group selected trials by phase.", "customer_note": "owned test note", "specialists": {}}
        payload["ownership"] = {"run_id": payload["run_id"], "user_id": "user-alice",
                                "customer_id": "customer-alice", "conversation_id": "conversation-alice"}

        def response(name, args):
            return {"message": {"role": "assistant", "tool_calls": [
                {"id": str(uuid4()), "type": "function",
                 "function": {"name": name, "arguments": json.dumps(args)}},
            ]}, "usage": {"total_tokens": 10}}

        calls = [response("query_trials", {}), response("run_python", {"code": "print('{}')"}),
                 response("finish", expected)]
        mocked_runner = SimpleNamespace(frozen_files=lambda: PINS, run=lambda payload: None)
        original_read = Path.read_text

        def read(path, *args, **kwargs):
            return json.dumps(source) if path.name == "source-records.json" else original_read(path, *args, **kwargs)

        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            sys.modules, {"src.runtime.remote_runner": mocked_runner},
        ), patch.object(os, "getuid", return_value=0, create=True), patch.object(
            agent_runtime, "BRIDGE", Path(temporary) / "bridge",
        ), patch.object(Path, "read_text", read):
            output = agent_runtime.run_agent(
                payload, model_exchange=lambda *args: calls.pop(0),
                python_executor=lambda payload: {"status": "completed", "stdout": "{}", "stderr": ""},
            )
            self.assertEqual(output["model_calls"], 3)
            self.assertEqual(output["output"], expected)
            self.assertEqual(output["ownership"], payload["ownership"])
            self.assertEqual([item["tool"] for item in output["events"]], ["query_trials", "run_python", "finish"])
            qa = {"passed": True, "issues": [], "clinical_source_ids": expected["source_ids"],
                  "safety_source_ids": reference_results(source, selection)["drug_specialist"]["source_ids"]}
            payload["role"] = "quality_assurance"
            payload["specialists"] = {"clinical_trials": {
                "output": expected, "assessment": {"passed": True},
                "receipts": [{"status": "completed", "stdout": "large-private-receipt" * 1000}],
            }}
            calls = [response("inspect_specialist_results", {}), response("run_python", {"code": "print('{}')"}),
                     response("finish", qa), response("query_trials", {}), response("query_safety_reports", {}),
                     response("finish", qa)]
            observed = []
            def model(*args):
                observed.append(copy.deepcopy(args[0]))
                return calls.pop(0)
            output = agent_runtime.run_agent(
                payload, model_exchange=model,
                python_executor=lambda payload: {"status": "completed", "stdout": "{}", "stderr": ""},
            )
            self.assertEqual(output["model_calls"], 6)
            self.assertEqual(output["output"], qa)
            self.assertNotIn("large-private-receipt", json.dumps(observed))
            self.assertIn("Finish rejected", json.dumps(observed))
            self.assertEqual(output["ownership"], payload["ownership"])
            with self.assertRaisesRegex(TimeoutError, "iteration budget"):
                agent_runtime.run_agent(payload, model_exchange=lambda *args: response("finish", expected))


class TestServiceVerifier:
    async def verify(self, value):
        if value not in {"test:frontend", "test:project"}:
            raise PermissionError("Injected test verifier rejected the caller.")
        return ServiceCaller(value.split(":")[1], "test-tenant", "api://test-execution")


class SwarmAPI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = OwnershipStore(Path(self.temp.name) / "state.db", create=True)
        self.store.seed_from_env({
            f"REACTOR_{owner.username.upper()}_PASSWORD": secrets.token_urlsafe(24) for owner in ACCOUNTS
        })
        self.source = json.loads(SOURCE.read_text(encoding="utf-8"))
        self.sandboxes, self.relay = AsyncMock(), AsyncMock()
        self.sandboxes.recover_abandoned.return_value = []
        self.wrong_first = False
        self.calls = []

        async def execute(run_id, role, selection, question, *, on_created, on_event, **kwargs):
            self.calls.append(role)
            sandbox_id = str(uuid4())
            on_created(sandbox_id)
            on_event("sandbox_created", sandbox_id=sandbox_id)
            reference = reference_results(self.source, selection)
            if role == "quality_assurance":
                output = {"passed": True, "issues": [],
                          "clinical_source_ids": reference["clinical_trials"]["source_ids"],
                          "safety_source_ids": reference["drug_specialist"]["source_ids"]}
            else:
                output = copy.deepcopy(reference[role])
                if self.wrong_first and role == "clinical_trials" and self.calls.count(role) == 1:
                    key = next(iter(output["phase_counts"]))
                    output["phase_counts"][key] += 1
            on_event("sandbox_deleted", sandbox_id=sandbox_id)
            return {"run_id": run_id, "role": role, "output": output, "sandbox_id": sandbox_id,
                    "model_calls": 3, "tool_calls": 3, "receipts": [], "cleanup": "deleted", "sandbox_seconds": 1.5}

        self.sandboxes.execute_agent.side_effect = execute
        app = create_app(store=self.store, sandboxes=self.sandboxes, verifier=TestServiceVerifier(),
                         frontend_object_id="frontend", project_object_id="project", source_file=SOURCE,
                         model_relay=self.relay)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://execution.test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.temp.cleanup()

    def headers(self, user="user-alice", service="frontend", grant=None):
        headers = {"Authorization": "test:" + service, "X-Reactor-User": user}
        if grant is not None:
            headers["X-Reactor-Run-Grant"] = grant["run_grant"]
        return headers

    async def new_research(self, user="user-alice"):
        response = await self.client.post("/runs", headers=self.headers(user), json={
            "task": "research", "candidate_id": "semaglutide", "condition": "obesity",
            "question": "Show the frozen evidence.", "idempotency_key": str(uuid4()),
        })
        self.assertEqual(response.status_code, 200, response.text)
        run = response.json()
        grant = await self.client.post(f"/runs/{run['run_id']}/grant", headers=self.headers(user))
        self.assertEqual(grant.status_code, 200, grant.text)
        return run, grant.json()

    async def tool(self, role, grant, attempt=1, **changes):
        body = {name: grant[name] for name in ("run_id", "user_id", "customer_id", "conversation_id")}
        body.update(attempt=attempt, instruction="Inspect the selected frozen evidence.", **changes)
        return await self.client.post("/agents/" + role.replace("_", "-"),
                                      headers=self.headers(service="project", grant=grant), json=body)

    async def test_owned_three_agent_handoff_reuse_and_foreign_denial(self):
        for owner in ACCOUNTS:
            run, grant = await self.new_research(owner.user_id)
            early = await self.tool("quality_assurance", grant)
            self.assertEqual(early.status_code, 409)
            foreign = await self.tool("clinical_trials", grant, customer_id="other-customer")
            self.assertEqual(foreign.status_code, 403)
            first = await self.tool("clinical_trials", grant)
            self.assertEqual(first.status_code, 200, first.text)
            self.assertEqual((await self.tool("clinical_trials", grant)).json(), first.json())
            drug = await self.tool("drug_specialist", grant)
            self.assertEqual(drug.status_code, 200, drug.text)
            qa = await self.tool("quality_assurance", grant)
            self.assertEqual(qa.status_code, 200, qa.text)
            self.assertTrue(qa.json()["evidence"]["accepted"])
            current = await self.client.get(f"/runs/{run['run_id']}", headers=self.headers(owner.user_id))
            self.assertTrue(current.json()["cleaned"])
            self.assertEqual(current.json()["swarm"]["status"], "completed")
            foreign_user = "user-bob" if owner.user_id == "user-alice" else "user-alice"
            denied = await self.client.get(f"/runs/{run['run_id']}", headers=self.headers(foreign_user))
            self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.calls.count("clinical_trials"), 2)

    async def test_qa_cannot_override_wrong_result_and_one_revision_recovers(self):
        self.wrong_first = True
        run, grant = await self.new_research()
        for role in ("clinical_trials", "drug_specialist"):
            self.assertEqual((await self.tool(role, grant)).status_code, 200)
        qa = await self.tool("quality_assurance", grant)
        self.assertEqual(qa.status_code, 200, qa.text)
        self.assertNotIn("evidence", qa.json())
        self.assertEqual(self.store.get_run(ACCOUNTS[0], run["run_id"]).state, "running")
        for role in ("clinical_trials", "drug_specialist", "quality_assurance"):
            result = await self.tool(role, grant, attempt=2)
            self.assertEqual(result.status_code, 200, result.text)
        self.assertTrue(result.json()["evidence"]["accepted"])
        self.assertEqual(self.calls.count("clinical_trials"), 2)

    async def test_fatal_agent_failure_finishes_owned_run_with_rejected_evidence(self):
        run, grant = await self.new_research()
        self.sandboxes.execute_agent.side_effect = RuntimeError("test model failure")
        response = await self.tool("clinical_trials", grant)
        self.assertEqual(response.status_code, 502)
        current = await self.client.get(f"/runs/{run['run_id']}", headers=self.headers())
        self.assertEqual(current.json()["state"], "failed")
        self.assertTrue(current.json()["cleaned"])
        self.assertEqual(current.json()["swarm"]["status"], "failed")
        artifact = current.json()["artifacts"][0]["artifact_id"]
        evidence = await self.client.get(f"/runs/{run['run_id']}/artifacts/{artifact}", headers=self.headers())
        self.assertFalse(evidence.json()["accepted"])
        self.assertIn("RuntimeError", evidence.json()["error"])
        self.sandboxes.recover_abandoned.assert_awaited_once_with(run["run_id"])

    async def test_bad_role_context_and_changed_attempt_are_rejected(self):
        _, grant = await self.new_research()
        self.assertEqual((await self.tool("clinical_trials", grant)).status_code, 200)
        self.assertEqual((await self.tool("drug_specialist", grant, candidate_id="other")).status_code, 400)
        body = {name: grant[name] for name in ("run_id", "user_id", "customer_id", "conversation_id")}
        response = await self.client.post("/agents/clinical-trials", headers=self.headers(service="project", grant=grant),
                                         json={**body, "attempt": 1, "instruction": "Different instruction"})
        self.assertEqual(response.status_code, 409)
        response = await self.client.post("/agents/drug-specialist", headers=self.headers(service="frontend", grant=grant),
                                         json=body)
        self.assertEqual(response.status_code, 403)

    async def test_pending_role_is_not_replayed_and_owned_cancel_stops_it(self):
        run, grant = await self.new_research()
        release = asyncio.Event()
        execute = self.sandboxes.execute_agent.side_effect
        started = []

        async def slow(*args, **kwargs):
            started.append(args[1])
            await release.wait()
            return await execute(*args, **kwargs)

        self.sandboxes.execute_agent.side_effect = slow
        with patch("src.reactor.execution.HANDOFF_SECONDS", 0.01):
            pending = await self.tool("clinical_trials", grant)
            self.assertEqual(pending.status_code, 202)
            again = await self.tool("clinical_trials", grant)
            self.assertEqual(again.status_code, 202)
            self.assertEqual(started, ["clinical_trials"])
            denied = await self.tool("clinical_trials", grant, user_id="user-bob")
            self.assertEqual(denied.status_code, 403)
            cancelled = await self.client.post(f"/runs/{run['run_id']}/cancel", headers=self.headers())
            self.assertEqual(cancelled.status_code, 200, cancelled.text)
            self.assertTrue(cancelled.json()["cleaned"])
            self.assertEqual((await self.tool("clinical_trials", grant)).status_code, 409)
