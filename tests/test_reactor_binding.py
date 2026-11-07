import json
import unittest
from unittest.mock import AsyncMock

from src.reactor.binding import GRANT_HEADER, binding_from_metadata, invoke_bound


class RuntimeBinding(unittest.IsolatedAsyncioTestCase):
    async def test_runtime_binding_overrides_all_model_identity_fields(self):
        binding = {"run_id": "owned", "user_id": "alice", "customer_id": "alice-customer",
                   "conversation_id": "alice-conversation", "run_grant": "opaque-server-only"}
        toolbox = AsyncMock()
        toolbox.call_tool.return_value = '{"accepted":true}'
        model_tasks = [{"step": "phases", "code": "pass", "run_id": "bob",
                        "run_grant": "forged", "user_id": "bob", "url": "https://attacker.example"}]
        await invoke_bound(toolbox, "offload", binding, model_tasks)
        self.assertEqual(toolbox.call_tool.call_args.kwargs, {
            GRANT_HEADER: binding["run_grant"],
            "body": {**{name: value for name, value in binding.items() if name != "run_grant"},
                     "tasks": [{"step": "phases", "code": "pass"}]},
        })
        self.assertEqual(binding_from_metadata({"reactor_binding": json.dumps(binding)}), binding)

    async def test_missing_binding_cannot_start_a_workflow(self):
        for metadata in [{}, {"reactor_binding": "{}"}, {"reactor_binding": "x" * 513}]:
            with self.subTest(metadata=metadata), self.assertRaises(PermissionError):
                binding_from_metadata(metadata)


if __name__ == "__main__":
    unittest.main()
