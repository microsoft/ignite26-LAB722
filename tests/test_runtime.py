import base64
import json
import io
import os
import pathlib
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

os.environ.update({
    "AZURE_CLIENT_ID": "00000000-0000-0000-0000-000000000001",
    "AZURE_SUBSCRIPTION_ID": "00000000-0000-0000-0000-000000000002",
    "SANDBOX_ID": "00000000-0000-0000-0000-000000000003",
    "SANDBOX_SNAPSHOT_ID": "00000000-0000-0000-0000-000000000004",
    "RESOURCE_GROUP": "fixture", "SANDBOX_REGION": "westus3", "SANDBOX_GROUP": "fixture",
    "PROOF_KEY": "fixture-only-not-an-application-key-00001",
    "SANDBOX_GROUP_IDENTITY_DISABLED": "true",
})
from starlette.testclient import TestClient
from src.runtime import remote_runner, server


class RuntimeAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(server.app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def test_api_and_mcp_need_key_but_page_is_public(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/api/config").status_code, 401)
        self.assertEqual(self.client.post("/mcp", json={}).status_code, 401)
        response = self.client.get("/api/config", headers={"X-Lab722-Proof-Key": os.environ["PROOF_KEY"]})
        self.assertEqual(response.status_code, 200)

    def test_direct_execution_reports_remote_failure_not_transport_success(self):
        async def native(arguments, timeout=45):
            if arguments[2] == "get":
                return 0, json.dumps({
                    "id": os.environ["SANDBOX_ID"],
                    "sourcesRef": {"snapshot": {"id": os.environ["SANDBOX_SNAPSHOT_ID"]}},
                }), ""
            command = arguments[arguments.index("-c") + 1]
            payload = shlex.split(command)[1].split("=", 1)[1]
            value = json.loads(base64.b64decode(payload))
            return 0, json.dumps({
                "run_id": value["run_id"], "execution_marker": value["marker"],
                "status": "failed", "exit_code": 19, "stdout": "", "stderr": "",
                "elapsed_seconds": 0.01, "captured_bytes": 0,
                "files_sha256": remote_runner.PINS, "execution_uid": 65534,
                "environment_cleared": True, "no_new_privileges": True,
            }), ""
        with patch.object(server, "native", native):
            response = self.client.post("/api/execute", json={"code": "raise SystemExit(19)"},
                                        headers={"X-Lab722-Proof-Key": os.environ["PROOF_KEY"]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "failed")
        self.assertEqual(response.json()["receipt"]["exit_code"], 19)
        self.assertIn("no agent call", response.json()["route"])

    def test_invalid_code_does_not_call_sandbox(self):
        with patch.object(server, "native", new_callable=AsyncMock) as native:
            response = self.client.post("/api/execute", json={"code": "x" * 16385},
                                       headers={"X-Lab722-Proof-Key": os.environ["PROOF_KEY"]})
        self.assertEqual(response.status_code, 400)
        native.assert_not_called()


class ToolScope(unittest.IsolatedAsyncioTestCase):
    async def test_model_cannot_invent_an_active_run(self):
        with patch.object(server, "native", new_callable=AsyncMock) as native:
            with self.assertRaises(PermissionError):
                await server.execute_python(str(uuid4()), "print(1)")
        native.assert_not_called()


class IdentityProbe(unittest.TestCase):
    def test_usable_platform_token_stops_execution(self):
        response = io.BytesIO(b'{"access_token":"fixture-only-not-a-real-token"}')
        with patch.dict(os.environ, {"IDENTITY_ENDPOINT": "http://fixture", "IDENTITY_HEADER": "fixture"}), \
                patch.object(remote_runner.urllib.request, "urlopen", return_value=response):
            with self.assertRaises(PermissionError):
                remote_runner.identity_endpoint_status()


class OutputFormatting(unittest.TestCase):
    def test_non_json_and_non_finite_results_remain_visible_text(self):
        for output in ("hello", "NaN", '{"value":1e999}'):
            with self.subTest(output=output):
                self.assertEqual(server.decode_output(output), (None, "text"))
        self.assertEqual(server.decode_output('{"value":3}'), ({"value": 3}, "json"))


@unittest.skipUnless(hasattr(os, "geteuid") and os.geteuid() == 0, "Linux root supervisor checks")
class Supervisor(unittest.TestCase):
    def run_code(self, code, seconds=1):
        original = subprocess.Popen
        with tempfile.TemporaryDirectory() as directory:
            os.chown(directory, 65534, 65534)
            def start(arguments, **kwargs):
                return original([sys.executable, *arguments[1:]], **{**kwargs, "cwd": directory})
            with patch.object(remote_runner, "frozen_files", return_value=remote_runner.PINS), \
                    patch.object(remote_runner.subprocess, "Popen", side_effect=start), \
                    patch.object(remote_runner, "WALL_SECONDS", seconds):
                return remote_runner.run({"run_id": str(uuid4()), "marker": "fixture", "code": code})

    def test_uid_environment_and_no_new_privileges(self):
        result = self.run_code(
            'import json,os,pathlib; print(json.dumps({"uid":os.getuid(),'
            '"identity":any(k.startswith(("IDENTITY_","AZURE_","PROOF_")) for k in os.environ),'
            '"privilege":next(l for l in pathlib.Path("/proc/self/status").read_text().splitlines() '
            'if l.startswith("NoNewPrivs:"))}))'
        )
        output = json.loads(result["stdout"])
        self.assertEqual(output["uid"], 65534)
        self.assertFalse(output["identity"])
        self.assertTrue(output["privilege"].endswith("1"))

    def test_nonzero_and_output_limit(self):
        self.assertEqual(self.run_code("raise SystemExit(19)")["exit_code"], 19)
        result = self.run_code('print("x"*300000)')
        self.assertEqual(result["status"], "output_limit")
        self.assertLessEqual(result["captured_bytes"], 131072)

    def test_closed_pipes_cannot_bypass_wall_timeout(self):
        result = self.run_code('import os,time; os.close(1); os.close(2); time.sleep(10)', seconds=0.2)
        self.assertEqual(result["status"], "timed_out")
        self.assertLess(result["elapsed_seconds"], 3)

    def test_detached_child_is_not_left_running(self):
        result = self.run_code(
            'import os,time; child=os.fork();'
            '\nif child==0:\n os.setsid(); os.close(1); os.close(2); time.sleep(10)'
            '\nelse:\n print(child)'
        )
        status = pathlib.Path("/proc") / result["stdout"].strip() / "status"
        self.assertFalse(status.exists(), "Detached descendant must be reaped, not left as a zombie.")


if __name__ == "__main__":
    unittest.main()
