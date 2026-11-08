import asyncio
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from agent_framework import Content
from src.reactor import hosted


class HostedWorkflow(unittest.IsolatedAsyncioTestCase):
    async def test_research_delegates_three_sandbox_roles_not_foundry_specialists(self):
        binding = {
            "run_id": "research-alice", "user_id": "user-alice", "customer_id": "customer-alice",
            "conversation_id": "conversation-alice", "run_grant": "fake-research-grant",
        }
        roles = ("clinical_trials", "drug_specialist", "quality_assurance")
        agents = []

        async def agent_run(agent, question):
            agents.append(agent.name)
            if agent.name == "research-orchestrator":
                return SimpleNamespace(text=json.dumps({role: "Inspect selected frozen records." for role in roles}))
            return SimpleNamespace(text="The selected frozen evidence passed its independent checks.")

        async def specialist(toolbox, role, supplied_binding, **kwargs):
            result = {"run_id": supplied_binding["run_id"], "role": role}
            if role == "quality_assurance":
                result.update(finalized=True, evidence={"accepted": True, "research": {"source_ids": []}, "qa": {}})
            return [Content.from_text(json.dumps(result))]

        request = SimpleNamespace(
            request={"metadata": {"reactor_binding": json.dumps(binding), "reactor_task": "research",
                                  "reactor_research": json.dumps({"candidate_id": "semaglutide", "condition": "obesity"})}},
            scope=SimpleNamespace(call_id="research-call", user_id="service-caller", session_id="research-session"),
        )
        with (
            patch.object(hosted, "get_request_context", return_value=SimpleNamespace(platform_headers=lambda: {})),
            patch.dict(os.environ, {"FOUNDRY_PROJECT_ENDPOINT": "https://example.services.ai.azure.com/api/projects/test",
                                   "MODEL_DEPLOYMENT": "test-model", "TOOLBOX_ENDPOINT": "https://example.test/mcp"}),
            patch.object(hosted.Agent, "run", new=agent_run),
            patch.object(hosted, "FoundryToolbox"),
            patch.object(hosted, "invoke_specialist", new=AsyncMock(side_effect=specialist)) as delegated,
        ):
            result = await hosted.build_workflow(request).run("Research the selected drug.")
        output = json.loads(result.get_outputs()[0])
        self.assertTrue(output["accepted"])
        self.assertEqual(agents, ["research-orchestrator", "research-answer"])
        self.assertEqual([call.args[1] for call in delegated.await_args_list], list(roles))
        self.assertTrue(all(call.args[2] == binding for call in delegated.await_args_list))
        self.assertNotIn(binding["run_grant"], json.dumps(output))

    async def test_native_dispatch_preserves_independent_request_bindings(self):
        called = set()
        async def agent_run(agent, question):
            if agent.name.startswith("research-"):
                return SimpleNamespace(text='{"code":"print(1)"}')
            return SimpleNamespace(text="The independent checker accepted this run.")

        async def execute_bound(toolbox, operation, binding, tasks):
            if binding["run_id"] not in called:
                called.add(binding["run_id"])
                return [Content.from_text(json.dumps({
                    "run_id": binding["run_id"], "state": "running", "pending": True,
                }))]
            return [Content.from_text(json.dumps({"run_id": binding["run_id"], "accepted": True}))]

        async def run(owner):
            binding = {
                "run_id": f"run-{owner}", "user_id": f"user-{owner}",
                "customer_id": f"customer-{owner}", "conversation_id": f"conversation-{owner}",
                "run_grant": f"fake-grant-{owner}",
            }
            request = SimpleNamespace(
                request={"metadata": {"reactor_binding": json.dumps(binding), "reactor_task": "phases"}},
                scope=SimpleNamespace(
                    call_id=f"call-{owner}", user_id="service-caller", session_id=f"session-{owner}",
                ),
            )
            result = await hosted.build_workflow(request).run("Analyze the frozen records.")
            return json.loads(result.get_outputs()[0])

        with (
            patch.object(hosted, "get_request_context",
                         return_value=SimpleNamespace(platform_headers=lambda: {})),
            patch.dict(os.environ, {
                "FOUNDRY_PROJECT_ENDPOINT": "https://example.services.ai.azure.com/api/projects/test",
                "MODEL_DEPLOYMENT": "test-model", "TOOLBOX_ENDPOINT": "https://example.test/mcp",
                "TOOLBOX_OPERATION": "reactor___reactor_execute",
            }),
            patch.object(hosted.Agent, "run", new=agent_run),
            patch.object(hosted, "FoundryToolbox"),
            patch.object(hosted.asyncio, "sleep", new=AsyncMock()),
            patch.object(hosted, "invoke_bound", new=AsyncMock(side_effect=execute_bound)) as invoke,
        ):
            outputs = await asyncio.gather(run("alice"), run("bob"))

        self.assertEqual({output["run_id"] for output in outputs}, {"run-alice", "run-bob"})
        self.assertEqual({output["hosted_session_id"] for output in outputs},
                         {"session-alice", "session-bob"})
        self.assertTrue(all(output["accepted"] for output in outputs))
        for call in invoke.await_args_list:
            binding, tasks = call.args[2:]
            self.assertEqual(binding["run_grant"], f"fake-grant-{binding['user_id'][5:]}")
            self.assertEqual(tasks, [{"step": "phases", "code": "print(1)"}])
        self.assertNotIn("fake-grant", json.dumps(outputs))


if __name__ == "__main__":
    unittest.main()
