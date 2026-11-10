import json
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx

from src.reactor.main import build_app


class AsyncStartup(unittest.IsolatedAsyncioTestCase):
    def config(self):
        return {
            "REACTOR_COMPONENT": "execution", "AZURE_CLIENT_ID": str(uuid4()),
            "AZURE_TENANT_ID": str(uuid4()), "AZURE_SUBSCRIPTION_ID": str(uuid4()),
            "RESOURCE_GROUP": "fixture", "SANDBOX_REGION": "westus3",
            "SANDBOX_GROUP": "fixture", "SANDBOX_SNAPSHOT_ID": str(uuid4()),
            "EXECUTION_API_AUDIENCE": "api://fixture",
            "FRONTEND_OBJECT_ID": str(uuid4()), "PROJECT_OBJECT_ID": str(uuid4()),
            "REACTOR_ALICE_PASSWORD": secrets.token_urlsafe(24),
            "REACTOR_BOB_PASSWORD": secrets.token_urlsafe(24),
        }

    async def test_frontend_starts_without_a_precreated_hosted_endpoint(self):
        credential, backend, hosted = AsyncMock(), AsyncMock(), AsyncMock()
        config = self.config()
        config.update(REACTOR_COMPONENT="frontend", EXECUTION_ENDPOINT="https://execution.test")
        with patch("src.reactor.main.ManagedIdentityCredential", return_value=credential), \
                patch("src.reactor.main.ExecutionClient", return_value=backend), \
                patch("src.reactor.main.HostedClient", return_value=hosted) as hosted_factory:
            app = build_app(config)
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://frontend.test") as client:
                    result = await client.get("/api/session")
                    self.assertEqual(result.status_code, 200)
                    self.assertFalse(result.json()["hosted_configured"])
                    self.assertIsNone(result.json()["user_id"])
            hosted_factory.assert_called_once_with("", credential)
            backend.close.assert_awaited_once()
            hosted.close.assert_awaited_once()
            credential.close.assert_awaited_once()

    async def test_real_managed_identity_transport_initializes_without_network(self):
        config = self.config()
        config.update(REACTOR_COMPONENT="frontend", EXECUTION_ENDPOINT="https://execution.test")
        with patch.dict("os.environ", {
            "IDENTITY_ENDPOINT": "http://127.0.0.1:40342/identity",
            "IDENTITY_HEADER": "synthetic-identity-header",
        }):
            app = build_app(config)
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://frontend.test") as client:
                    result = await client.get("/api/session")
                    self.assertEqual(result.status_code, 200)
                    self.assertFalse(result.json()["hosted_configured"])

    async def test_fresh_startup_inside_asgi_loop_and_abandoned_state_fail_closed(self):
        source = Path(__file__).parents[1] / "data" / "lab-datasets" / "caldova-public-lab-use-v2" / "source-records.json"
        credential, sandboxes = AsyncMock(), AsyncMock()
        sandboxes.native.return_value = "[]"
        with tempfile.TemporaryDirectory() as directory, \
                patch("src.reactor.main.ManagedIdentityCredential", return_value=credential), \
                patch("src.reactor.main.TaskSandboxes", return_value=sandboxes):
            app = build_app(self.config(), state_path=Path(directory) / "state.db", source_file=source)
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://fixture") as client:
                    result = await client.get("/health")
                    self.assertEqual(result.status_code, 200)
                    self.assertEqual(result.json()["component"], "execution")
            credential.close.assert_awaited_once()
            sandboxes.native.return_value = json.dumps([{"id": str(uuid4())}])
            blocked = build_app(self.config(), state_path=Path(directory) / "missing.db", source_file=source)
            with self.assertRaisesRegex(RuntimeError, "reconciliation"):
                async with blocked.router.lifespan_context(blocked):
                    self.fail("Startup must not accept orphaned task resources.")
            self.assertFalse((Path(directory) / "missing.db").exists())


if __name__ == "__main__":
    unittest.main()
