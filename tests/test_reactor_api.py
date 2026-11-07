import json
import asyncio
from collections import Counter
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx

from src.reactor.execution import create_app
from src.reactor.ownership import ACCOUNTS, OwnershipStore
from src.reactor.service_auth import ServiceCaller


class Verifier:
    async def verify(self, value):
        if value not in {"Bearer frontend", "Bearer project"}:
            raise PermissionError("untrusted service")
        return ServiceCaller(value[7:], "tenant", "api://execution")


class ExecutionAPI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.passwords = {p.username: secrets.token_urlsafe(24) for p in ACCOUNTS}
        self.store = OwnershipStore(Path(self.temp.name) / "state.db", create=True)
        self.store.seed_from_env({f"REACTOR_{name.upper()}_PASSWORD": value for name, value in self.passwords.items()})
        self.source = Path(__file__).parents[1] / "data" / "lab-datasets" / "caldova-public-lab-use-v2" / "source-records.json"
        self.sandboxes = AsyncMock()
        self.sandboxes.recover_abandoned.return_value = []
        app = create_app(store=self.store, sandboxes=self.sandboxes, verifier=Verifier(),
                         frontend_object_id="frontend", project_object_id="project", source_file=self.source)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://execution.test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.temp.cleanup()

    def headers(self, user="user-alice", service="frontend"):
        return {"Authorization": f"Bearer {service}", "X-Reactor-User": user}

    def offload_headers(self, binding, service="project"):
        return {**self.headers(service=service), "X-Reactor-Run-Grant": binding["run_grant"]}

    async def new_run(self, user="user-alice", task="phases", key=None):
        response = await self.client.post("/runs", headers=self.headers(user),
                                          json={"task": task, "idempotency_key": key or str(uuid4()),
                                                "user_id": "user-bob", "customer_id": "customer-bob"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def test_real_password_hash_login_and_service_routing(self):
        for principal in ACCOUNTS:
            response = await self.client.post("/login", headers=self.headers(),
                                              json={"username": principal.username, "password": self.passwords[principal.username]})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["user_id"], principal.user_id)
        response = await self.client.post("/login", headers=self.headers(),
                                          json={"username": "alice", "password": self.passwords["bob"]})
        self.assertEqual(response.status_code, 403)
        for service, expected in [("project", 403), ("other", 401)]:
            response = await self.client.post("/login", headers=self.headers(service=service), json={})
            self.assertEqual(response.status_code, expected)

    async def test_reference_bytes_and_overflow_json_are_rejected(self):
        changed = Path(self.temp.name) / "changed.json"
        changed.write_text('{"trials":[],"safety_reports":[]}')
        with self.assertRaisesRegex(ValueError, "approved frozen"):
            create_app(store=self.store, sandboxes=self.sandboxes, verifier=Verifier(),
                       frontend_object_id="frontend", project_object_id="project", source_file=changed)
        response = await self.client.post(
            "/runs", headers={**self.headers(), "Content-Type": "application/json"},
            content='{"task":"phases","idempotency_key":"overflow","ignored":1e999}',
        )
        self.assertEqual(response.status_code, 400)

    async def test_owned_management_cross_user_denial_and_idempotency(self):
        alice = await self.new_run(key="first")
        bob = await self.new_run("user-bob")
        self.assertEqual((await self.new_run(key="first"))["run_id"], alice["run_id"])
        for run, user in [(alice, "user-alice"), (bob, "user-bob")]:
            self.assertEqual(run["user_id"], user)
            self.assertEqual((await self.client.get(f"/runs/{run['run_id']}", headers=self.headers(user))).status_code, 200)
            foreign = "user-bob" if user == "user-alice" else "user-alice"
            for suffix in ["", "/conversations/" + run["conversation_id"], "/artifacts/fake"]:
                response = await self.client.get(f"/runs/{run['run_id']}{suffix}", headers=self.headers(foreign))
                self.assertEqual(response.status_code, 403)
            response = await self.client.post(f"/runs/{run['run_id']}/cancel", headers=self.headers(foreign))
            self.assertEqual(response.status_code, 403)

    async def test_bound_offload_allowed_and_forged_grant_denied(self):
        for principal in ACCOUNTS:
            run = await self.new_run(principal.user_id)
            grant = (await self.client.post(f"/runs/{run['run_id']}/grant", headers=self.headers(principal.user_id))).json()
            source = json.loads(self.source.read_text())
            output = json.dumps({
                "counts": dict(Counter(r["phase"] or "NA" for r in source["trials"])),
                "source_ids": sorted(r["trial_id"] for r in source["trials"]),
            })

            async def execute(run_id, step, code, *, customer_note, on_created):
                sandbox = str(uuid4())
                on_created(sandbox)
                return {"run_id": run_id, "sandbox_id": sandbox, "step": step, "status": "completed",
                        "stdout": output, "cleanup": "deleted", "sandbox_seconds": 1.2, "customer_note": customer_note}

            self.sandboxes.execute.side_effect = execute
            payload = {name: grant[name] for name in ("run_id", "user_id", "customer_id", "conversation_id")}
            payload["tasks"] = [{"step": "phases", "code": "pass"}]
            denied = await self.client.post("/offload", headers=self.offload_headers(grant),
                                            json={**payload, "customer_id": "foreign-customer"})
            self.assertEqual(denied.status_code, 403)
            self.assertEqual(self.store.get_run(principal, run["run_id"]).state, "submitted")
            denied = await self.client.post(
                "/offload", headers=self.offload_headers({**grant, "run_grant": "forged"}), json=payload,
            )
            self.assertEqual(denied.status_code, 403)
            denied = await self.client.post("/offload", headers=self.offload_headers(grant, service="frontend"), json=payload)
            self.assertEqual(denied.status_code, 403)
            result = await self.client.post("/offload", headers=self.offload_headers(grant), json=payload)
            self.assertEqual(result.status_code, 200, result.text)
            self.assertTrue(result.json()["accepted"], result.text)
            self.assertEqual(result.json()["demo_user"], principal.user_id)
            self.assertEqual(result.json()["service_caller"]["object_id"], "project")
            replay = await self.client.post("/offload", headers=self.offload_headers(grant), json=payload)
            self.assertIn(replay.status_code, {403, 409})

    async def test_pending_execution_collects_once_without_replay_or_foreign_binding(self):
        run = await self.new_run()
        grant = (await self.client.post(f"/runs/{run['run_id']}/grant", headers=self.headers())).json()
        payload = {name: grant[name] for name in ("run_id", "user_id", "customer_id", "conversation_id")}
        payload["tasks"] = [{"step": "phases", "code": "pass"}]
        release = asyncio.Event()
        source = json.loads(self.source.read_text())
        output = json.dumps({
            "counts": dict(Counter(r["phase"] or "NA" for r in source["trials"])),
            "source_ids": sorted(r["trial_id"] for r in source["trials"]),
        })

        async def execute(run_id, step, code, **kwargs):
            await release.wait()
            return {"run_id": run_id, "step": step, "status": "completed",
                    "stdout": output, "cleanup": "deleted", "sandbox_seconds": 1}

        self.sandboxes.execute.side_effect = execute
        with patch("src.reactor.execution.HANDOFF_SECONDS", 0.01):
            pending = await self.client.post("/offload", headers=self.offload_headers(grant), json=payload)
            self.assertEqual(pending.status_code, 202)
            self.assertTrue(pending.json()["pending"])
            self.assertNotIn(grant["run_grant"], pending.text)
            for headers, body in [
                (self.offload_headers(grant), {**payload, "customer_id": "foreign"}),
                (self.offload_headers({**grant, "run_grant": "forged"}), payload),
                (self.offload_headers(grant, service="frontend"), payload),
            ]:
                denied = await self.client.post("/offload", headers=headers, json=body)
                self.assertEqual(denied.status_code, 403)
            release.set()
            result = await self.client.post("/offload", headers=self.offload_headers(grant), json=payload)
            self.assertEqual(result.status_code, 200, result.text)
            self.assertTrue(result.json()["accepted"])
            self.sandboxes.execute.assert_awaited_once()
            self.assertEqual(len(self.store.list_artifacts(ACCOUNTS[0], run["run_id"])), 1)
            replay = await self.client.post("/offload", headers=self.offload_headers(grant), json=payload)
            self.assertIn(replay.status_code, {403, 409})

    async def test_pending_execution_cancellation_revokes_continuation(self):
        run = await self.new_run()
        grant = (await self.client.post(f"/runs/{run['run_id']}/grant", headers=self.headers())).json()
        payload = {name: grant[name] for name in ("run_id", "user_id", "customer_id", "conversation_id")}
        payload["tasks"] = [{"step": "phases", "code": "pass"}]
        deleted = asyncio.Event()

        async def execute(*args, **kwargs):
            try:
                await asyncio.sleep(60)
            finally:
                deleted.set()

        self.sandboxes.execute.side_effect = execute
        with patch("src.reactor.execution.HANDOFF_SECONDS", 0.01):
            response = await self.client.post("/offload", headers=self.offload_headers(grant), json=payload)
            self.assertEqual(response.status_code, 202)
            cancelled = await self.client.post(f"/runs/{run['run_id']}/cancel", headers=self.headers())
            self.assertEqual(cancelled.status_code, 200)
            self.assertTrue(cancelled.json()["cleaned"])
            self.assertTrue(deleted.is_set())
            replay = await self.client.post("/offload", headers=self.offload_headers(grant), json=payload)
            self.assertEqual(replay.status_code, 403)

    async def test_concurrent_owned_cancel_returns_explicit_http_failure_after_cleanup(self):
        run = await self.new_run()
        binding = (await self.client.post(f"/runs/{run['run_id']}/grant", headers=self.headers())).json()
        entered, deleted = asyncio.Event(), asyncio.Event()

        async def execute(*args, **kwargs):
            entered.set()
            try:
                await asyncio.sleep(60)
            finally:
                deleted.set()

        self.sandboxes.execute.side_effect = execute
        request = asyncio.create_task(self.client.post(
            "/offload", headers=self.offload_headers(binding),
            json={name: value for name, value in {**binding, "tasks": [{"step": "phases", "code": "pass"}]}.items()
                  if name not in {"run_grant", "expires_at"}},
        ))
        await entered.wait()
        response = await self.client.post(f"/runs/{run['run_id']}/cancel", headers=self.headers())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["cleaned"])
        self.assertTrue(deleted.is_set())
        interrupted = await request
        self.assertEqual(interrupted.status_code, 409)

    async def test_non_json_completed_result_retains_capacity_until_explicit_recovery(self):
        run = await self.new_run()
        binding = (await self.client.post(f"/runs/{run['run_id']}/grant", headers=self.headers())).json()
        self.sandboxes.execute.return_value = {"run_id": run["run_id"], "step": "phases",
                                               "status": "completed", "stdout": "not JSON"}
        response = await self.client.post(
            "/offload", headers=self.offload_headers(binding),
            json={name: value for name, value in {**binding, "tasks": [{"step": "phases", "code": "pass"}]}.items()
                  if name not in {"run_grant", "expires_at"}},
        )
        self.assertEqual(response.status_code, 502)
        self.assertFalse(self.store.get_run(ACCOUNTS[0], run["run_id"]).cleaned)
        recovered = await self.client.post(f"/runs/{run['run_id']}/cancel", headers=self.headers())
        self.assertTrue(recovered.json()["cleaned"])


if __name__ == "__main__":
    unittest.main()
