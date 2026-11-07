import asyncio
import secrets
import unittest
from unittest.mock import AsyncMock

import httpx
from starlette.exceptions import HTTPException

from src.reactor.frontend import HostedClient, create_app


class FrontendSessions(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.backend = AsyncMock()
        self.hosted = AsyncMock()
        self.application = create_app(backend=self.backend, hosted=self.hosted, session_key=secrets.token_urlsafe(48))
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.application), base_url="https://frontend.test")
        self.csrf = (await self.client.get("/api/session")).json()["csrf"]

    async def asyncTearDown(self):
        await self.client.aclose()

    async def login(self):
        self.backend.call.return_value = {"user_id": "user-alice", "customer_id": "customer-alice"}
        result = await self.client.post("/api/login", headers={"X-CSRF-Token": self.csrf},
                                        json={"username": "alice", "password": "fixture"})
        self.assertEqual(result.status_code, 200)
        self.csrf = (await self.client.get("/api/session")).json()["csrf"]

    async def test_csrf_and_cookie_security(self):
        result = await self.client.post("/api/login", json={})
        self.assertEqual(result.status_code, 403)
        self.backend.call.assert_not_awaited()
        result = await self.client.get("/api/session")
        self.assertIn("httponly", result.headers["set-cookie"].lower())
        self.assertIn("secure", result.headers["set-cookie"].lower())
        self.assertIn("samesite=strict", result.headers["set-cookie"].lower())
        result = await self.client.post("/api/login", headers={"X-CSRF-Token": self.csrf, "Origin": "https://foreign.test"}, json={})
        self.assertEqual(result.status_code, 403)

    async def test_signed_session_derives_owner_not_browser_metadata(self):
        await self.login()
        self.backend.call.return_value = {"run_id": "owned-run", "state": "completed", "artifacts": []}
        result = await self.client.get("/api/runs/owned-run", params={"user_id": "user-bob"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.backend.call.call_args.kwargs["user_id"], "user-alice")
        self.client.cookies.set("reactor_session", "forged-cookie")
        result = await self.client.get("/api/runs/owned-run")
        self.assertEqual(result.status_code, 401)

    async def test_public_origin_survives_tls_termination_and_rejects_foreign_origin(self):
        await self.client.aclose()
        application = create_app(
            backend=self.backend, hosted=self.hosted, session_key=secrets.token_urlsafe(48),
            public_origin="https://frontend.test",
        )

        async def tls_ingress(scope, receive, send):
            await application({**scope, "scheme": "http"}, receive, send)

        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=tls_ingress), base_url="https://frontend.test",
        )
        self.csrf = (await self.client.get("/api/session")).json()["csrf"]
        self.backend.call.return_value = {"user_id": "user-alice", "customer_id": "customer-alice"}
        result = await self.client.post(
            "/api/login", headers={"X-CSRF-Token": self.csrf, "Origin": "https://frontend.test"},
            json={"username": "alice", "password": "fixture"},
        )
        self.assertEqual(result.status_code, 200)
        self.csrf = (await self.client.get("/api/session")).json()["csrf"]
        self.backend.call.reset_mock()
        result = await self.client.post(
            "/api/login", headers={"X-CSRF-Token": self.csrf, "Origin": "https://foreign.test"},
            json={"username": "alice", "password": "fixture"},
        )
        self.assertEqual(result.status_code, 403)
        self.backend.call.assert_not_awaited()

    async def test_foreign_cancel_is_rejected_before_touching_hosted_task(self):
        await self.login()
        self.backend.call.side_effect = HTTPException(403, "foreign run")
        result = await self.client.post("/api/runs/bob-run/cancel", headers={"X-CSRF-Token": self.csrf}, json={})
        self.assertEqual(result.status_code, 403)
        self.hosted.invoke.assert_not_awaited()

    async def test_unconnected_preparation_supports_login_and_inspection_without_reserving_work(self):
        await self.client.aclose()
        application = create_app(
            backend=self.backend, hosted=self.hosted, session_key=secrets.token_urlsafe(48),
            hosted_configured=False,
        )
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url="https://frontend.test")
        session = (await self.client.get("/api/session")).json()
        self.assertFalse(session["hosted_configured"])
        self.csrf = session["csrf"]
        await self.login()
        self.backend.call.reset_mock()
        result = await self.client.post("/api/runs", headers={"X-CSRF-Token": self.csrf},
                                        json={"task": "phases", "question": "Analyze phases", "idempotency_key": "same"})
        self.assertEqual(result.status_code, 503)
        self.assertIn("not connected", result.text)
        self.backend.call.assert_not_awaited()
        self.hosted.invoke.assert_not_awaited()
        self.backend.call.return_value = {"run_id": "owned-run", "state": "completed"}
        result = await self.client.get("/api/runs/owned-run")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.backend.call.call_args.kwargs["user_id"], "user-alice")

    async def test_submit_returns_run_before_hosted_work_and_does_not_expose_grant(self):
        await self.login()
        entered, release = asyncio.Event(), asyncio.Event()
        run = {"run_id": "owned-run", "state": "submitted"}
        binding = {"run_id": "owned-run", "user_id": "user-alice", "customer_id": "customer-alice",
                   "conversation_id": "owned-conversation", "run_grant": "server-only-opaque-secret"}
        self.backend.call.side_effect = [run, binding]

        async def invoke(**kwargs):
            entered.set()
            await release.wait()
            return {"output": ["ok"], "agent_session_id": None}

        self.hosted.invoke.side_effect = invoke
        result = await self.client.post("/api/runs", headers={"X-CSRF-Token": self.csrf},
                                        json={"task": "phases", "question": "Analyze phases", "idempotency_key": "same"})
        self.assertEqual(result.status_code, 202)
        self.assertNotIn(binding["run_grant"], result.text)
        await entered.wait()
        self.assertEqual(self.hosted.invoke.call_args.kwargs["binding"], binding)
        release.set()
        await asyncio.sleep(0.02)


class HostedResponses(unittest.IsolatedAsyncioTestCase):
    async def test_http_success_is_not_workflow_success_and_metadata_stays_private(self):
        credential = AsyncMock()
        credential.get_token.return_value.token = "fake-token"
        client = HostedClient("https://hosted.test/responses", credential)
        await client.http.aclose()
        binding = {
            "run_id": "owned-run", "user_id": "user-alice", "customer_id": "customer-alice",
            "conversation_id": "owned-conversation", "run_grant": "fake-private-grant",
        }
        response_body = {
            "status": "completed", "agent_session_id": "owned-session",
            "metadata": {"reactor_binding": binding},
            "output": [{"content": [{"type": "output_text", "text": "Accepted execution evidence."}]}],
        }
        client.http = httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=response_body),
        ))
        try:
            for status in ("failed", "in_progress"):
                response_body["status"] = status
                with self.subTest(status=status), self.assertRaises(HTTPException) as raised:
                    await client.invoke(question="Analyze phases.", task="phases", binding=binding)
                self.assertEqual(raised.exception.status_code, 502)
                self.assertNotIn(binding["run_grant"], raised.exception.detail)
            response_body["status"] = "completed"
            result = await client.invoke(question="Analyze phases.", task="phases", binding=binding)
            self.assertEqual(result["agent_session_id"], "owned-session")
            self.assertEqual(result["output"], ["Accepted execution evidence."])
            self.assertNotIn("metadata", result)
            self.assertNotIn(binding["run_grant"], str(result))
        finally:
            await client.close()


if __name__ == "__main__":
    unittest.main()
