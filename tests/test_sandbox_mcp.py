import asyncio
import hashlib
import json
import os
import shlex
import shutil
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from agent_framework import MCPStdioTool

from src.orchestrator.contracts import SandboxBinding
from src.orchestrator.mcp_client import worker_mcp_tools
from src.orchestrator.sandbox import (
    Execution, MAX_SOURCE_BYTES, RESULT_PREFIX, SandboxExecutor, SandboxOutputLimitError,
    SandboxScope,
)


# This fake models native gateway responses; it never executes the --command string.
FAKE_NATIVE = r'''#!/usr/bin/env python3
import ast
import base64
import hashlib
import json
import os
import re
import shlex
import sys
import time
from pathlib import Path

home = Path(__file__).parent
settings = json.loads((home / "settings.json").read_text())
arguments = sys.argv[1:]
command = arguments[arguments.index("--command") + 1] if "--command" in arguments else None
status_prefix = None
if command is not None and command.startswith("sh -c "):
    match = re.search(r"CALDOVA_EXEC_RESULT_[a-f0-9]{32}=", command)
    if match:
        status_prefix = match[0]
        command = shlex.split(command)[2]

def finish(exit_code):
    if status_prefix is not None:
        mode = settings.get("status_mode", "valid")
        if mode != "missing":
            value = "corrupt" if mode == "corrupt" else str(exit_code)
            print("\n" + status_prefix + value)
            if mode == "duplicate":
                print(status_prefix + value)
    sys.exit(0 if settings.get("cli_zero_on_failure") else exit_code)

entry = {
    "arguments": arguments, "pid": os.getpid(),
    "ai_credentials_present": any(key in os.environ for key in (
        "OPENAI_API_KEY", "AZURE_CLIENT_SECRET", "AZURE_AI_TOKEN", "CALDOVA_AI_TOKEN_FILE",
    )),
}
with (home / "calls.jsonl").open("a") as log:
    log.write(json.dumps(entry) + "\n")

if arguments[:2] == ["sandbox", "get"]:
    mode = settings.get("get_mode", "valid")
    if mode == "sleep":
        time.sleep(30)
    elif mode == "overflow":
        print("x" * 8192, flush=True)
        time.sleep(30)
    print(settings["metadata_json"] if "metadata_json" in settings else json.dumps(settings.get("metadata")))
    if mode == "error":
        print("native metadata lookup failed", file=sys.stderr)
        sys.exit(19)
    sys.exit(0)

if command == "sleep":
    time.sleep(30)
elif command in ("overflow-stdout", "overflow-stderr", "overflow-combined"):
    if command in ("overflow-stdout", "overflow-combined"):
        sys.stdout.write("o" * (400 if command == "overflow-combined" else 8192))
        sys.stdout.flush()
    if command in ("overflow-stderr", "overflow-combined"):
        sys.stderr.write("e" * (400 if command == "overflow-combined" else 8192))
        sys.stderr.flush()
    time.sleep(30)
elif command == "fail":
    print("remote failure output")
    print("remote command failed", file=sys.stderr)
    finish(7)
elif command.startswith("python3 -c "):
    script = shlex.split(command)[2]
    assignment = ast.parse(script).body[0].value
    payload = json.loads(ast.literal_eval(assignment.args[0]))
    path = payload["path"]
    mode = settings.get("file_mode", "valid")
    if mode == "symlink":
        guarded = "os.O_NOFOLLOW" in script and "dir_fd=directory" in script
        if guarded:
            print("remote symlink access rejected", file=sys.stderr)
            sys.exit(9)
    if mode == "remote-error":
        sys.exit(23)
    encoded = payload["content"]
    content = settings.get("content", "def feature():\n    return []\n") if encoded is None else (
        base64.b64decode(encoded).decode("utf-8")
    )
    if mode == "wrong-write":
        content = "different remote contents"
    if mode == "oversize":
        content = "x" * 16001
    value = {
        "path": path, "content": content,
        "sha256": hashlib.sha256(content.encode()).hexdigest(),
    }
    if mode == "wrong-path":
        value["path"] = "tests/test_research.py"
    if mode == "bad-checksum":
        value["sha256"] = "0" * 64
    if mode == "wrong-type":
        value = []
    if mode == "extra-field":
        value["untrusted"] = True
    if mode == "missing":
        print("only resume progress")
    else:
        line = payload["prefix"] + ("{invalid" if mode == "bad-json" else json.dumps(value))
        print("Sandbox resumed")
        print(line)
        if mode == "duplicate":
            print(line)
else:
    print("remote gateway response")
finish(0)
'''


class FakeGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = Path(__file__).resolve().parent / f".mcp-test-{uuid4().hex}"
        self.directory.mkdir()
        self.executable = self.directory / "fake-aca"
        self.executable.write_text(FAKE_NATIVE, encoding="utf-8")
        self.executable.chmod(0o700)
        self.settings()
        self.binding = SandboxBinding(
            role="clinical-trials", sandbox_id=uuid4(), snapshot_id=uuid4(),
        )
        self.scope = SandboxScope(uuid4(), "lab-rg", "westus3", "lab-sandboxes")
        self.executor = SandboxExecutor(str(self.executable), self.scope, self.binding)

    async def asyncTearDown(self):
        shutil.rmtree(self.directory)

    def settings(self, **values):
        (self.directory / "settings.json").write_text(json.dumps(values), encoding="utf-8")

    def calls(self):
        log = self.directory / "calls.jsonl"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    async def wait_for_calls(self, count=1):
        async with asyncio.timeout(10):
            while len(self.calls()) < count:
                await asyncio.sleep(0.02)
        return self.calls()

    async def assert_process_gone(self, pid):
        async with asyncio.timeout(10):
            while True:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    return
                await asyncio.sleep(0.02)

    def binding_metadata(self, **changes):
        return {
            "id": str(self.binding.sandbox_id),
            "sourcesRef": {"snapshot": {"id": str(self.binding.snapshot_id)}},
            "snapshotId": str(uuid4()),
            **changes,
        }

    def egress_metadata(self, **changes):
        return {
            "id": str(self.binding.sandbox_id),
            "egressPolicy": {
                "defaultAction": "Deny",
                "trafficInspection": "Full",
                "rules": [{
                    "name": "aca-host-rule-1",
                    "match": {"host": "open.fda.gov"},
                    "action": {"type": "Allow"},
                }],
            },
            **changes,
        }

    async def test_verify_egress_policy_uses_fixed_metadata_and_returns_configuration_only(self):
        self.settings(metadata=self.egress_metadata())
        verified = await self.executor.verify_egress_policy()
        self.assertEqual(verified, {
            "defaultAction": "Deny", "trafficInspection": "Full", "allowed_hosts": ["open.fda.gov"],
        })
        arguments = self.calls()[0]["arguments"]
        self.assertEqual(arguments[:2], ["sandbox", "get"])
        for flag, value in (
            ("--id", str(self.binding.sandbox_id)), ("--subscription", str(self.scope.subscription)),
            ("--resource-group", self.scope.resource_group), ("--region", self.scope.region),
            ("--group", self.scope.group), ("--output", "json"),
        ):
            self.assertEqual(arguments[arguments.index(flag) + 1], value)

    async def test_verify_egress_policy_rejects_missing_unreviewed_or_expanded_policies(self):
        policy = self.egress_metadata()["egressPolicy"]
        valid_rule = policy["rules"][0]
        for rejected in (
            None, [], {},
            {**policy, "defaultAction": "Allow"},
            {**policy, "trafficInspection": "None"},
            {**policy, "trafficInspection": None},
            {**policy, "unexpected": "policy option"},
            {**policy, "rules": None},
            {**policy, "rules": []},
            {**policy, "rules": [None]},
            {**policy, "rules": [valid_rule, {
                "match": {"host": "example.com"}, "action": {"type": "Allow"},
            }]},
            {**policy, "rules": [{**valid_rule, "match": {"host": "example.com"}}]},
            {**policy, "rules": [{**valid_rule, "match": {"host": "*.fda.gov"}}]},
            {**policy, "rules": [{**valid_rule, "match": {"host": "open.fda.gov", "path": "*"}}]},
            {**policy, "rules": [{**valid_rule, "action": {"type": "Deny"}}]},
            {**policy, "rules": [{**valid_rule, "action": {"type": "Allow", "unexpected": True}}]},
            {**policy, "rules": [{**valid_rule, "unexpected": True}]},
        ):
            with self.subTest(policy=rejected):
                self.settings(metadata=self.egress_metadata(egressPolicy=rejected))
                with self.assertRaises(ValueError):
                    await self.executor.verify_egress_policy()
        self.settings(metadata=self.egress_metadata(id=str(uuid4())))
        with self.assertRaisesRegex(ValueError, "assigned Sandbox"):
            await self.executor.verify_egress_policy()

    async def test_verify_egress_policy_native_and_protocol_failures_are_bounded_and_fail_closed(self):
        self.settings(metadata=self.egress_metadata(), get_mode="error")
        with self.assertRaisesRegex(RuntimeError, "exit code 19"):
            await self.executor.verify_egress_policy()
        self.settings(metadata_json="{invalid")
        with self.assertRaises(ValueError):
            await self.executor.verify_egress_policy()
        self.settings(get_mode="overflow")
        executor = SandboxExecutor(str(self.executable), self.scope, self.binding, max_output_bytes=512)
        with self.assertRaises(SandboxOutputLimitError):
            await executor.verify_egress_policy()
        await self.assert_process_gone(self.calls()[-1]["pid"])

    async def test_verify_binding_checks_real_clone_lineage_and_fixed_native_scope(self):
        metadata = self.binding_metadata()
        self.assertNotEqual(metadata["snapshotId"], str(self.binding.snapshot_id))
        self.settings(metadata=metadata)
        verified = await self.executor.verify_binding()
        self.assertEqual(verified, self.binding)
        arguments = self.calls()[0]["arguments"]
        self.assertEqual(arguments[:2], ["sandbox", "get"])
        for flag, value in (
            ("--id", str(self.binding.sandbox_id)), ("--subscription", str(self.scope.subscription)),
            ("--resource-group", self.scope.resource_group), ("--region", self.scope.region),
            ("--group", self.scope.group), ("--output", "json"),
        ):
            self.assertEqual(arguments[arguments.index(flag) + 1], value)
            self.assertEqual(arguments.count(flag), 1)
        self.assertNotIn("--selector", arguments)
        self.assertNotIn("--command", arguments)
        self.assertNotIn("--working-directory", arguments)

    async def test_verify_binding_rejects_foreign_missing_or_invalid_lineage_metadata(self):
        valid = self.binding_metadata()
        for metadata in (
            None, [], {},
            self.binding_metadata(id=str(uuid4())),
            self.binding_metadata(id="not-a-uuid"),
            self.binding_metadata(id=12),
            self.binding_metadata(sourcesRef=None),
            self.binding_metadata(sourcesRef=[]),
            self.binding_metadata(sourcesRef={"snapshot": None}),
            self.binding_metadata(sourcesRef={"snapshot": {"id": 12}}),
            self.binding_metadata(sourcesRef={"snapshot": {"id": "not-a-uuid"}}),
            # A matching current lifecycle snapshot cannot substitute for clone lineage.
            self.binding_metadata(
                sourcesRef={"snapshot": {"id": str(uuid4())}},
                snapshotId=str(self.binding.snapshot_id),
            ),
            {"id": valid["id"], "snapshotId": str(self.binding.snapshot_id)},
        ):
            with self.subTest(metadata=metadata):
                self.settings(metadata=metadata)
                with self.assertRaises(ValueError):
                    await self.executor.verify_binding()

    async def test_verify_binding_rejects_corrupt_json_duplicates_and_native_failure(self):
        valid = self.binding_metadata()
        for text in (
            "{invalid",
            "Sandbox details\n" + json.dumps(valid),
            json.dumps(valid)[:-1] + ',"sourcesRef":{"snapshot":{"id":"' + str(uuid4()) + '"}}}',
        ):
            with self.subTest(text=text):
                self.settings(metadata_json=text)
                with self.assertRaises(ValueError):
                    await self.executor.verify_binding()
        self.settings(metadata=valid, get_mode="error")
        with self.assertRaisesRegex(RuntimeError, "exit code 19"):
            await self.executor.verify_binding()

    async def test_verify_binding_timeout_and_output_bound_reap_owned_native_process(self):
        executor = SandboxExecutor(str(self.executable), self.scope, self.binding, max_output_bytes=512)
        for mode, error in (("sleep", TimeoutError), ("overflow", SandboxOutputLimitError)):
            with self.subTest(mode=mode):
                self.settings(get_mode=mode)
                with self.assertRaises(error):
                    await executor.verify_binding(timeout=1 if mode == "sleep" else 5)
                await self.assert_process_gone(self.calls()[-1]["pid"])

    async def test_verify_binding_cancellation_reaps_owned_native_process(self):
        self.settings(get_mode="sleep")
        pending = asyncio.create_task(self.executor.verify_binding())
        calls = await self.wait_for_calls()
        pending.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pending
        await self.assert_process_gone(calls[0]["pid"])

    async def test_workspace_discovery_matches_host_access_and_drives_role_permitted_operations(self):
        for role, writable in (
            ("clinical-trials", ["src/research-portal/backend/trial_feature.py"]),
            ("drug-safety", ["src/research-portal/backend/safety_feature.py"]),
            ("quality-governance", []),
        ):
            with self.subTest(role=role):
                executor = SandboxExecutor(
                    str(self.executable), self.scope, self.binding.model_copy(update={"role": role}),
                )
                async with worker_mcp_tools(executor) as tools:
                    before = len(self.calls())
                    functions = {function.name: function for function in tools.functions}
                    result = await functions["describe_workspace"].invoke(arguments={})
                    access = json.loads(result[0].text)
                    self.assertEqual(access, executor.source_access())
                    self.assertEqual(set(access), {"workspace", "readable_paths", "writable_paths"})
                    self.assertEqual(access["workspace"], "/opt/caldova-lab")
                    self.assertEqual(access["writable_paths"], writable)
                    self.assertEqual(len(self.calls()), before)
                    listed = {tool.name: tool for tool in (await tools.session.list_tools()).tools}
                    self.assertEqual(listed["describe_workspace"].inputSchema["properties"], {})
                    for path in access["readable_paths"]:
                        self.assertIn(path, listed["read_source"].description)
                    for path in writable:
                        self.assertIn(path, listed["write_source"].description)
                    schema_path = "data/pipeline/contracts.py"
                    self.assertIn(schema_path, access["readable_paths"])
                    read = await tools.session.call_tool("read_source", {"path": schema_path})
                    self.assertFalse(read.isError)
                    if writable:
                        write = await tools.session.call_tool(
                            "write_source", {"path": writable[0], "content": "pass\n"},
                        )
                        self.assertFalse(write.isError)
                    else:
                        self.assertNotIn("write_source", listed)
                        self.assertNotIn("write_source", functions)

    async def test_source_denials_reveal_exact_permitted_paths_and_support_recovery(self):
        async with worker_mcp_tools(self.executor) as tools:
            descriptor = await tools.session.call_tool("describe_workspace")
            access = descriptor.structuredContent
            denied = await tools.session.call_tool("read_source", {"path": "artifacts.sql"})
            self.assertTrue(denied.isError)
            message = "\n".join(item.text for item in denied.content if item.type == "text")
            for path in access["readable_paths"]:
                self.assertIn(path, message)
            self.assertIn("describe_workspace", message)
            recovered = await tools.session.call_tool(
                "read_source", {"path": "data/pipeline/contracts.py"},
            )
            self.assertFalse(recovered.isError)
            denied = await tools.session.call_tool(
                "write_source",
                {"path": "src/research-portal/backend/safety_feature.py", "content": "pass\n"},
            )
            self.assertTrue(denied.isError)
            message = "\n".join(item.text for item in denied.content if item.type == "text")
            for path in access["writable_paths"]:
                self.assertIn(path, message)
            recovered = await tools.session.call_tool(
                "write_source", {"path": access["writable_paths"][0], "content": "pass\n"},
            )
            self.assertFalse(recovered.isError)
        self.assertEqual(len(self.calls()), 2)

    async def test_stdio_negotiation_discovery_and_framework_function_dispatch(self):
        async with worker_mcp_tools(self.executor) as tools:
            self.assertIsInstance(tools, MCPStdioTool)
            functions = {function.name: function for function in tools.functions}
            self.assertEqual(set(functions), {"describe_workspace", "execute", "read_source", "write_source"})
            discovery = await tools.session.list_tools()
            schemas = {tool.name: tool.inputSchema["properties"] for tool in discovery.tools}
            self.assertEqual(schemas["describe_workspace"], {})
            self.assertEqual(set(schemas["execute"]), {"command"})
            self.assertEqual(set(schemas["read_source"]), {"path"})
            self.assertEqual(set(schemas["write_source"]), {"path", "content"})
            output = await functions["execute"].invoke(arguments={"command": "printf not-local"})
            self.assertIn("remote gateway response", "\n".join(item.text or "" for item in output))
            path = "src/research-portal/backend/trial_feature.py"
            contents = "def feature():\n    return ['UTF-8: café']\n"
            write = await tools.session.call_tool("write_source", {"path": path, "content": contents})
            self.assertFalse(write.isError)
            self.assertEqual(write.structuredContent["content"], contents)
            self.assertEqual(write.structuredContent["sha256"], hashlib.sha256(contents.encode()).hexdigest())
            read = await tools.session.call_tool("read_source", {"path": path})
            self.assertFalse(read.isError)
            self.assertEqual(read.structuredContent["path"], path)
        self.assertEqual(len(self.calls()), 3)

    async def test_quality_role_has_no_write_tool_even_on_the_wire(self):
        executor = SandboxExecutor(
            str(self.executable), self.scope,
            self.binding.model_copy(update={"role": "quality-governance"}),
        )
        async with worker_mcp_tools(executor) as tools:
            self.assertEqual({f.name for f in tools.functions}, {"describe_workspace", "execute", "read_source"})
            discovery = await tools.session.list_tools()
            self.assertEqual({tool.name for tool in discovery.tools}, {"describe_workspace", "execute", "read_source"})
            denied = await tools.session.call_tool(
                "write_source",
                {"path": "src/research-portal/backend/trial_feature.py", "content": "denied"},
            )
            self.assertTrue(denied.isError)
            allowed = await tools.session.call_tool("execute", {"command": "arbitrary remote command"})
            self.assertFalse(allowed.isError)
        self.assertEqual(len(self.calls()), 1)

    async def test_feature_verification_command_stays_in_fixed_stdio_configuration(self):
        command = "printf '%s' 'trusted verifier (no model quoting)'"
        async with worker_mcp_tools(self.executor, verification_command=command) as tools:
            discovery = {tool.name: tool for tool in (await tools.session.list_tools()).tools}
            self.assertEqual(discovery["verify_feature"].inputSchema["properties"], {})
            result = await tools.call_tool(
                "verify_feature", command="model replacement", sandbox_id=str(uuid4()),
            )
            self.assertIn("remote gateway response", "\n".join(item.text or "" for item in result))
        self.assertEqual(len(self.calls()), 1)
        actual = self.calls()[0]["arguments"]
        wrapped = actual[actual.index("--command") + 1]
        self.assertEqual(shlex.split(wrapped)[2], command)
        self.assertIn(str(self.executor.binding.sandbox_id), actual)

    async def test_fixed_binding_scope_and_auth_environment_survive_model_extra_arguments(self):
        original_id = self.binding.sandbox_id
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "not-a-real-credential", "AZURE_CLIENT_SECRET": "not-a-real-credential",
            "AZURE_AI_TOKEN": "not-a-real-credential", "CALDOVA_AI_TOKEN_FILE": "not-a-real-path",
            "ACA_SUBSCRIPTION": str(uuid4()), "ACA_RESOURCE_GROUP": "wrong-rg",
        }):
            async with worker_mcp_tools(self.executor) as tools:
                # The bridge configuration was snapshotted, never forwarded from model arguments.
                self.binding.sandbox_id = uuid4()
                result = await tools.call_tool(
                    "execute", command="--id not-a-sandbox; printf remote-only",
                    sandbox_id=str(uuid4()), group="different", workspace="/", subscription=str(uuid4()),
                )
                self.assertIn("remote gateway response", "\n".join(item.text or "" for item in result))
        call = self.calls()[0]
        arguments = call["arguments"]
        for flag, value in (
            ("--id", str(original_id)), ("--subscription", str(self.scope.subscription)),
            ("--resource-group", self.scope.resource_group), ("--region", self.scope.region),
            ("--group", self.scope.group), ("--working-directory", "/opt/caldova-lab"),
        ):
            self.assertEqual(arguments[arguments.index(flag) + 1], value)
            self.assertEqual(arguments.count(flag), 1)
        self.assertFalse(call["ai_credentials_present"])

    async def test_path_and_worker_write_boundaries_fail_before_any_native_invocation(self):
        async with worker_mcp_tools(self.executor) as tools:
            for path in (
                "../tests/test_research.py", "/etc/passwd", "tests//test_research.py",
                "tests/./test_research.py", "tests\\test_research.py", "tests/test_research.py/",
                "src/research-portal/backend/not-allowed.py",
            ):
                with self.subTest(path=path):
                    result = await tools.session.call_tool("read_source", {"path": path})
                    self.assertTrue(result.isError)
            for path in (
                "src/research-portal/backend/safety_feature.py",
                "data/fixtures/research-data.json", "tests/test_research.py",
            ):
                with self.subTest(path=path):
                    result = await tools.session.call_tool("write_source", {"path": path, "content": "denied"})
                    self.assertTrue(result.isError)
        self.assertEqual(self.calls(), [])

    async def test_drug_safety_role_writes_only_its_feature(self):
        executor = SandboxExecutor(
            str(self.executable), self.scope, self.binding.model_copy(update={"role": "drug-safety"}),
        )
        async with worker_mcp_tools(executor) as tools:
            accepted = await tools.session.call_tool(
                "write_source", {"path": "src/research-portal/backend/safety_feature.py", "content": "pass\n"},
            )
            denied = await tools.session.call_tool(
                "write_source", {"path": "src/research-portal/backend/trial_feature.py", "content": "pass\n"},
            )
            self.assertFalse(accepted.isError)
            self.assertTrue(denied.isError)
        self.assertEqual(len(self.calls()), 1)

    async def test_corrupted_remote_file_protocol_is_an_mcp_error_not_a_success(self):
        async with worker_mcp_tools(self.executor) as tools:
            for mode in (
                "bad-json", "bad-checksum", "wrong-path", "wrong-type", "extra-field",
                "oversize", "duplicate", "missing", "remote-error", "symlink",
            ):
                with self.subTest(mode=mode):
                    self.settings(file_mode=mode)
                    result = await tools.session.call_tool(
                        "read_source", {"path": "src/research-portal/backend/trial_feature.py"},
                    )
                    self.assertTrue(result.isError)
            self.settings(file_mode="wrong-write")
            result = await tools.session.call_tool(
                "write_source", {"path": "src/research-portal/backend/trial_feature.py", "content": "pass\n"},
            )
            self.assertTrue(result.isError)

    async def test_source_byte_limits_apply_before_write_and_after_remote_read(self):
        path = "src/research-portal/backend/trial_feature.py"
        async with worker_mcp_tools(self.executor) as tools:
            for content in ("", "é" * 6001):
                result = await tools.session.call_tool("write_source", {"path": path, "content": content})
                self.assertTrue(result.isError)
            self.assertEqual(self.calls(), [])
            # Base64 transport also accepts the full byte budget for heavily escaped source.
            content = "\0" * 12000
            accepted = await tools.session.call_tool("write_source", {"path": path, "content": content})
            self.assertFalse(accepted.isError)
            self.assertEqual(accepted.structuredContent["content"], content)
            self.settings(content="é" * (MAX_SOURCE_BYTES // 2))
            accepted = await tools.session.call_tool("read_source", {"path": path})
            self.assertFalse(accepted.isError)
            self.settings(content="é" * (MAX_SOURCE_BYTES // 2 + 1))
            rejected = await tools.session.call_tool("read_source", {"path": path})
            self.assertTrue(rejected.isError)

    async def test_nonzero_command_exit_is_preserved_in_mcp_results(self):
        self.settings(cli_zero_on_failure=True)
        async with worker_mcp_tools(self.executor) as tools:
            result = await tools.session.call_tool("execute", {"command": "fail"})
            self.assertFalse(result.isError)
            self.assertEqual(result.structuredContent, {
                "exit_code": 7, "stdout": "remote failure output\n", "stderr": "remote command failed\n",
            })

    async def test_missing_corrupt_or_duplicate_remote_exit_status_never_becomes_success(self):
        async with worker_mcp_tools(self.executor) as tools:
            for mode in ("missing", "corrupt", "duplicate"):
                with self.subTest(mode=mode):
                    self.settings(status_mode=mode)
                    result = await tools.session.call_tool("execute", {"command": "remote command"})
                    self.assertTrue(result.isError)

    async def test_each_pipe_and_combined_output_budget_stop_owned_native_process(self):
        executor = SandboxExecutor(str(self.executable), self.scope, self.binding, max_output_bytes=512)
        for command in ("overflow-stdout", "overflow-stderr", "overflow-combined"):
            with self.subTest(command=command):
                with self.assertRaises(SandboxOutputLimitError):
                    await executor.execute(command)
                await self.assert_process_gone(self.calls()[-1]["pid"])

    async def test_output_overflow_is_reported_through_stdio_and_connection_remains_usable(self):
        executor = SandboxExecutor(str(self.executable), self.scope, self.binding, max_output_bytes=512)
        async with worker_mcp_tools(executor) as tools:
            result = await tools.session.call_tool("execute", {"command": "overflow-stdout"})
            self.assertTrue(result.isError)
            await self.assert_process_gone(self.calls()[-1]["pid"])
            recovered = await tools.session.call_tool("execute", {"command": "remote recovery"})
            self.assertFalse(recovered.isError)

    async def test_timeout_stops_native_process_and_is_reported_through_stdio(self):
        async with worker_mcp_tools(self.executor, timeout=1) as tools:
            result = await tools.session.call_tool("execute", {"command": "sleep"})
            self.assertTrue(result.isError)
            await self.assert_process_gone(self.calls()[-1]["pid"])

    async def test_cancelled_executor_reaps_owned_native_process(self):
        pending = asyncio.create_task(self.executor.execute("sleep"))
        calls = await self.wait_for_calls()
        pending.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pending
        await self.assert_process_gone(calls[0]["pid"])

    async def test_cancelled_framework_function_closes_bridge_and_reaps_native_process(self):
        async with worker_mcp_tools(self.executor) as tools:
            execute = next(function for function in tools.functions if function.name == "execute")
            pending = asyncio.create_task(execute.invoke(arguments={"command": "sleep"}))
            calls = await self.wait_for_calls()
            pending.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await pending
            await self.assert_process_gone(calls[0]["pid"])


class ProtocolUnitTests(unittest.IsolatedAsyncioTestCase):
    def executor(self):
        return SandboxExecutor(
            "aca", SandboxScope(uuid4(), "lab-rg", "westus3", "lab-sandboxes"),
            SandboxBinding(role="clinical-trials", sandbox_id=uuid4(), snapshot_id=uuid4()),
        )

    async def test_mutating_source_access_descriptor_cannot_expand_permissions(self):
        executor = self.executor()
        access = executor.source_access()
        access["readable_paths"].append("artifacts.sql")
        access["writable_paths"].append("src/research-portal/backend/safety_feature.py")
        with patch("asyncio.create_subprocess_exec", AsyncMock()) as spawn:
            for path, content in (
                ("artifacts.sql", None),
                ("src/research-portal/backend/safety_feature.py", "pass\n"),
            ):
                with self.subTest(path=path), self.assertRaises(PermissionError):
                    await executor.file(path, content)
            spawn.assert_not_called()
        fresh = executor.source_access()
        self.assertNotIn("artifacts.sql", fresh["readable_paths"])
        self.assertNotIn("src/research-portal/backend/safety_feature.py", fresh["writable_paths"])

    async def test_untrusted_protocol_shapes_never_return_success(self):
        executor = self.executor()
        path = "src/research-portal/backend/trial_feature.py"
        for payload in (None, [], 12, "result", {"path": path}, {"path": path, "content": None, "sha256": 4}):
            with self.subTest(payload=payload):
                executor.execute = AsyncMock(return_value=Execution(
                    0, RESULT_PREFIX + json.dumps(payload), "",
                ))
                with self.assertRaises(ValueError):
                    await executor.file(path)

    async def test_invalid_command_timeout_and_output_configuration_fail_without_spawning(self):
        executor = self.executor()
        with patch("asyncio.create_subprocess_exec", AsyncMock()) as spawn:
            for command in ("", " ", "\0", "é" * 12001):
                with self.subTest(command_length=len(command)), self.assertRaises(ValueError):
                    await executor.execute(command)
            for timeout in (0, -1, float("inf"), float("nan"), True, 181):
                with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                    await executor.execute("remote", timeout=timeout)
            spawn.assert_not_called()
        for maximum in (0, -1, 1048577, True, 1.5):
            with self.subTest(maximum=maximum), self.assertRaises(ValueError):
                SandboxExecutor("aca", executor.scope, executor.binding, max_output_bytes=maximum)


if __name__ == "__main__":
    unittest.main()
