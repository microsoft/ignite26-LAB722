import asyncio
import hashlib
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from src.reactor.evaluation import PHASE_COUNTS, evaluate
from src.reactor.sandboxes import TaskSandboxes
from src.reactor.agent_runtime import VERSION, tools_for
from src.runtime.frozen import PINS


class Evaluation(unittest.TestCase):
    def test_successful_but_wrong_answer_fails_independent_check(self):
        source = {"trials": [{"trial_id": "NCT1"}], "safety_reports": [{"report_id": "R1"}, {"report_id": "R2"}]}
        correct = json.dumps({"counts": PHASE_COUNTS, "source_ids": ["NCT1"]})
        wrong = json.dumps({"counts": {"PHASE3": 77}, "source_ids": ["NCT1"]})
        self.assertTrue(evaluate("phases", correct, source)["passed"])
        self.assertFalse(evaluate("phases", wrong, source)["passed"])
        self.assertFalse(evaluate("safety", '{"count":3}', source)["passed"])
        self.assertFalse(evaluate("safety", '{"count":2}', source)["passed"])
        self.assertTrue(evaluate("safety", '{"count":2,"source_ids":["R1","R2"]}', source)["passed"])


class Lifecycle(unittest.IsolatedAsyncioTestCase):
    def manager(self):
        return TaskSandboxes(
            subscription=str(uuid4()), resource_group="test-rg", region="westus3",
            group="test-group", snapshot=str(uuid4()), identity_client_id=str(uuid4()),
        )

    async def test_resident_agent_uses_only_short_exec_and_collects_correlated_file_result(self):
        manager = self.manager()
        sandbox, run_id = str(uuid4()), str(uuid4())
        binding = {"run_id": run_id, "user_id": "user-alice", "customer_id": "customer-alice",
                   "conversation_id": "conversation-alice"}
        code = "print('{}')"
        receipt = {
            "schema_version": "1.0", "dataset_version": "caldova-public-lab-use-v2",
            "identity_endpoint_status": "not_exposed", "run_id": run_id,
            "execution_marker": f"LAB722_REACTOR:{run_id}:clinical_trials:{uuid4()}",
            "code": code, "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
            "files_sha256": PINS, "execution_uid": 65534, "environment_cleared": True,
            "no_new_privileges": True, "status": "completed", "stdout": "{}", "stderr": "",
            "captured_bytes": 2, "elapsed_seconds": 0.1, "exit_code": 0,
        }
        result = {"version": VERSION, "role": "clinical_trials", "run_id": run_id, "ownership": binding,
                  "agent_sha256": manager.agent_sha256, "files_sha256": PINS,
                  "model_calls": 1, "tool_calls": 1, "receipts": [receipt], "output": {}}
        request = {"request_id": uuid4().hex, "turn": 1, "tools": tools_for("clinical_trials"),
                   "messages": [{"role": "user", "content": "Inspect selected records."}]}
        polls = 0
        async def native(arguments, **kwargs):
            nonlocal polls
            if arguments[0] == "get":
                return json.dumps({"id": sandbox, "sourcesRef": {"snapshot": {"id": manager.snapshot}},
                                   "labels": {"lab": "LAB722", "purpose": "reactor-task", "run": run_id,
                                              "step": "clinical_trials", "user": binding["user_id"],
                                              "customer": binding["customer_id"], "conversation": binding["conversation_id"]},
                                   "egressPolicy": {"defaultAction": "Deny", "trafficInspection": "Full"}})
            if arguments[0] == "exec":
                self.assertLessEqual(kwargs["timeout"], 30)
                if arguments[-1].endswith("--start"):
                    return '{"started":true,"pid":123}'
                if "for name in" in arguments[-1]:
                    polls += 1
                    return json.dumps({"request": request if polls == 1 else None,
                                       "result": result if polls == 2 else None, "error": None})
                return "null"
            return ""
        manager.native = AsyncMock(side_effect=native)
        relay = Mock(complete=AsyncMock(return_value={
            "request_id": request["request_id"], "message": {"role": "assistant", "tool_calls": []},
        }))
        with patch("src.reactor.sandboxes.asyncio.sleep", new=AsyncMock()):
            collected = await manager.execute_agent(
                run_id, "clinical_trials", {}, "Inspect", binding=binding, customer_note="owned",
                specialists={}, model_relay=relay, on_created=Mock(), on_event=Mock(),
            )
        self.assertEqual(collected["cleanup"], "deleted")
        self.assertEqual(polls, 2)
        relay.complete.assert_awaited_once_with("clinical_trials", request)

    async def test_execution_failure_still_deletes_exact_task_sandbox(self):
        manager = self.manager()
        sandbox, run_id = str(uuid4()), str(uuid4())
        manager.native = AsyncMock(side_effect=[
            f"Created sandbox: {sandbox}",
            json.dumps({"id": sandbox, "sourcesRef": {"snapshot": {"id": manager.snapshot}},
                        "labels": {"lab": "LAB722", "purpose": "reactor-task", "run": run_id, "step": "failure"},
                        "egressPolicy": {"defaultAction": "Deny", "trafficInspection": "Full"}}),
            RuntimeError("interrupted execution"),
            "",
        ])
        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            await manager.execute(run_id, "failure", "raise SystemExit(19)")
        self.assertEqual(manager.native.call_args_list[-1].args[0], ["delete", "--id", sandbox, "--yes"])
        creation = manager.native.call_args_list[0].args[0]
        self.assertNotIn("--cpu", creation)
        self.assertNotIn("--memory", creation)

    async def test_receipt_is_correlated_and_cleanup_is_required(self):
        manager = self.manager()
        sandbox = str(uuid4())
        run_id = str(uuid4())

        async def native(arguments, **kwargs):
            if arguments[0] == "create":
                return f"Created sandbox: {sandbox}"
            if arguments[0] == "get":
                return json.dumps({"id": sandbox, "sourcesRef": {"snapshot": {"id": manager.snapshot}},
                                   "labels": {"lab": "LAB722", "purpose": "reactor-task", "run": run_id, "step": "phases"},
                                   "egressPolicy": {"defaultAction": "Deny", "trafficInspection": "Full"}})
            if arguments[0] == "exec":
                import base64
                import shlex
                environment = shlex.split(arguments[-1])[1]
                payload = json.loads(base64.b64decode(environment.split("=", 1)[1]))
                return json.dumps({
                    "schema_version": "1.0", "dataset_version": "caldova-public-lab-use-v2",
                    "identity_endpoint_status": 401,
                    "run_id": run_id, "execution_marker": payload["marker"],
                    "code_sha256": hashlib.sha256(payload["code"].encode()).hexdigest(),
                    "files_sha256": PINS, "execution_uid": 65534,
                    "environment_cleared": True, "no_new_privileges": True,
                    "status": "completed", "stdout": "{}", "stderr": "",
                    "captured_bytes": 2, "elapsed_seconds": 0.1, "exit_code": 0,
                })
            return ""

        manager.native = AsyncMock(side_effect=native)
        receipt = await manager.execute(run_id, "phases", 'print("{}")')
        self.assertEqual(receipt["sandbox_id"], sandbox)
        self.assertEqual(receipt["cleanup"], "deleted")
        self.assertEqual(manager.native.call_args_list[1].args[0],
                         ["get", "--selector", f"lab=LAB722,purpose=reactor-task,run={run_id},step=phases"])

    async def test_cancelled_execution_cleans_up_before_propagating(self):
        manager = self.manager()
        sandbox, run_id = str(uuid4()), str(uuid4())
        entered = asyncio.Event()
        deleted = asyncio.Event()

        async def native(arguments, **kwargs):
            if arguments[0] == "create":
                return f"Created sandbox: {sandbox}"
            if arguments[0] == "get":
                return json.dumps({"id": sandbox, "sourcesRef": {"snapshot": {"id": manager.snapshot}},
                                   "labels": {"lab": "LAB722", "purpose": "reactor-task", "run": run_id, "step": "phases"},
                                   "egressPolicy": {"defaultAction": "Deny", "trafficInspection": "Full"}})
            if arguments[0] == "exec":
                entered.set()
                await asyncio.sleep(60)
            deleted.set()
            return ""

        manager.native = AsyncMock(side_effect=native)
        task = asyncio.create_task(manager.execute(run_id, "phases", 'print("{}")'))
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(deleted.is_set())

    async def test_uncertain_creation_reconciles_only_matching_run(self):
        manager = self.manager()
        run_id, sandbox = str(uuid4()), str(uuid4())
        manager.native = AsyncMock(side_effect=[
            TimeoutError("create result lost"),
            json.dumps([{"id": sandbox, "labels": {"lab": "LAB722", "purpose": "reactor-task", "run": run_id}}]),
            "",
        ])
        with self.assertRaises(TimeoutError):
            await manager.execute(run_id, "phases", 'print("{}")')
        self.assertEqual(manager.native.call_args_list[-1].args[0], ["delete", "--id", sandbox, "--yes"])

    async def test_recovery_refuses_foreign_inventory(self):
        manager = self.manager()
        manager.native = AsyncMock(return_value=json.dumps([{
            "id": str(uuid4()), "labels": {"lab": "LAB722", "purpose": "runtime-clean-seed"},
        }]))
        with self.assertRaises(PermissionError):
            await manager.recover_abandoned(str(uuid4()))
        self.assertEqual(manager.native.await_count, 1)

    async def test_wrong_created_egress_policy_stops_execution_and_deletes(self):
        manager = self.manager()
        sandbox, run_id = str(uuid4()), str(uuid4())
        manager.native = AsyncMock(side_effect=[
            f"Created sandbox: {sandbox}",
            json.dumps({"id": sandbox, "sourcesRef": {"snapshot": {"id": manager.snapshot}},
                        "labels": {"lab": "LAB722", "purpose": "reactor-task", "run": run_id, "step": "egress"},
                        "egressPolicy": {"defaultAction": "Allow", "trafficInspection": "Full"}}),
            "",
        ])
        with self.assertRaises(PermissionError):
            await manager.execute(run_id, "egress", "pass")
        self.assertEqual(manager.native.await_count, 3)
        self.assertEqual(manager.native.call_args_list[-1].args[0], ["delete", "--id", sandbox, "--yes"])

    async def test_four_queued_tasks_never_create_more_than_two_active_sandboxes(self):
        manager = self.manager()
        entered, release = asyncio.Event(), asyncio.Event()
        active, peak = 0, 0

        async def native(arguments, **kwargs):
            nonlocal active, peak
            if arguments[0] == "create":
                active += 1
                peak = max(peak, active)
                await asyncio.sleep(0)
                return "Created sandbox"
            if arguments[0] == "get":
                labels = dict(part.split("=", 1) for part in arguments[-1].split(","))
                return json.dumps({"id": str(uuid4()), "sourcesRef": {"snapshot": {"id": manager.snapshot}},
                                   "labels": labels,
                                   "egressPolicy": {"defaultAction": "Deny", "trafficInspection": "Full"}})
            if arguments[0] == "exec":
                if active == 2:
                    entered.set()
                await release.wait()
                import base64
                import shlex
                environment = shlex.split(arguments[-1])[1]
                payload = json.loads(base64.b64decode(environment.split("=", 1)[1]))
                return json.dumps({
                    "schema_version": "1.0", "dataset_version": "caldova-public-lab-use-v2",
                    "identity_endpoint_status": 401, "run_id": payload["run_id"],
                    "execution_marker": payload["marker"],
                    "code_sha256": hashlib.sha256(payload["code"].encode()).hexdigest(),
                    "files_sha256": PINS, "execution_uid": 65534,
                    "environment_cleared": True, "no_new_privileges": True,
                    "status": "completed", "stdout": "{}", "stderr": "",
                    "captured_bytes": 2, "elapsed_seconds": 0.1, "exit_code": 0,
                })
            active -= 1
            return ""

        manager.native = AsyncMock(side_effect=native)
        tasks = [asyncio.create_task(manager.execute(str(uuid4()), "phases", "pass")) for _ in range(4)]
        await asyncio.wait_for(entered.wait(), timeout=5)
        self.assertEqual(peak, 2)
        release.set()
        await asyncio.gather(*tasks)
        self.assertEqual(peak, 2)
        self.assertEqual(active, 0)

    async def test_create_readback_refuses_foreign_task_and_reconciles_only_own_run(self):
        manager = self.manager()
        run_id = str(uuid4())
        foreign_id = str(uuid4())
        manager.native = AsyncMock(side_effect=[
            "Created sandbox",
            json.dumps({"id": foreign_id, "labels": {
                "lab": "LAB722", "purpose": "reactor-task", "run": str(uuid4()), "step": "phases",
            }}),
            "[]",
        ])
        with self.assertRaisesRegex(PermissionError, "exact owned task"):
            await manager.execute(run_id, "phases", "pass")
        self.assertEqual(manager.native.call_args_list[-1].args[0],
                         ["list", "--selector", f"lab=LAB722,purpose=reactor-task,run={run_id}"])
        self.assertFalse(any(call.args[0][0] in {"exec", "delete"}
                             for call in manager.native.call_args_list))

if __name__ == "__main__":
    unittest.main()
