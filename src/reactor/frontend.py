"""Demo sessions and owned application routes; never manages a Sandbox."""
import asyncio
from collections import OrderedDict
from contextlib import asynccontextmanager
import hmac
import json
import logging
from pathlib import Path
import secrets
import time
from urllib.parse import urlparse

import httpx
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from .binding import FIELDS
from .http import json_body
from .ownership import ACCOUNTS

LOG = logging.getLogger("reactor.frontend")


class ExecutionClient:
    def __init__(self, endpoint, audience, credential):
        self.endpoint, self.audience, self.credential = endpoint.rstrip("/"), audience, credential
        self.http = httpx.AsyncClient(timeout=240)

    async def call(self, method, path, *, user_id=None, body=None):
        token = await self.credential.get_token(self.audience.rstrip("/") + "/.default")
        headers = {"Authorization": "Bearer " + token.token}
        if user_id is not None:
            headers["X-Reactor-User"] = user_id
        response = await self.http.request(method, self.endpoint + path, json=body, headers=headers)
        if not response.is_success:
            LOG.warning("execution operation=%s status=%s", method, response.status_code)
            raise HTTPException(response.status_code, "Execution API rejected the operation; inspect owned status.")
        return response.json()

    async def close(self):
        await self.http.aclose()


class HostedClient:
    def __init__(self, endpoint, credential):
        self.endpoint, self.credential = endpoint, credential
        self.http = httpx.AsyncClient(timeout=240)

    async def invoke(self, *, question, task, binding):
        token = await self.credential.get_token("https://ai.azure.com/.default")
        metadata = json.dumps({name: binding[name] for name in FIELDS}, separators=(",", ":"))
        if len(metadata) > 512:
            raise ValueError("The run binding exceeds the hosted metadata budget.")
        response = await self.http.post(
            self.endpoint,
            headers={"Authorization": "Bearer " + token.token},
            json={
                "input": question, "metadata": {"reactor_binding": metadata, "reactor_task": task},
                # Grants must not be retained in the outer Responses transcript.
                "store": False,
            },
        )
        if not response.is_success:
            LOG.error("hosted invocation status=%s run=%s", response.status_code, binding["run_id"])
            raise HTTPException(502, "Hosted invocation failed. Inspect run status; reconcile before retry.")
        result = response.json()
        if result.get("status") != "completed":
            LOG.error("hosted workflow did not complete run=%s", binding["run_id"])
            raise HTTPException(502, "Hosted workflow did not complete. Inspect owned status; reconcile before retry.")
        # Metadata (including the grant) is never returned to the browser.
        output = []
        for item in result.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                    output.append(content["text"])
        if not output:
            raise HTTPException(502, "Hosted invocation returned no supported workflow output.")
        return {"output": output, "agent_session_id": result.get("agent_session_id"), "usage": result.get("usage")}

    async def close(self):
        await self.http.aclose()


def create_app(*, backend, hosted, session_key, secure_cookies=True, hosted_configured=True, public_origin=None):
    if len(session_key) < 32:
        raise ValueError("A strong boot-specific session signing key is required.")
    if public_origin is not None:
        parsed = urlparse(public_origin)
        if not parsed.netloc or parsed.username or parsed.password or public_origin != f"https://{parsed.netloc}":
            raise ValueError("The public origin must be an HTTPS origin without credentials or a path.")
    login_attempts = OrderedDict()
    active = {}
    outcomes = OrderedDict()

    def principal(request):
        user_id = request.session.get("user_id")
        owner = next((p for p in ACCOUNTS if p.user_id == user_id), None)
        if owner is None:
            raise HTTPException(401, "Sign in to the demo application.")
        return owner

    def csrf(request):
        expected = request.session.get("csrf", "")
        supplied = request.headers.get("x-csrf-token", "")
        if not expected or not hmac.compare_digest(expected, supplied):
            raise HTTPException(403, "Request verification failed.")
        origin = request.headers.get("origin")
        base = urlparse(str(request.base_url))
        expected_origin = public_origin or f"{base.scheme}://{base.netloc}"
        if origin and origin != expected_origin:
            raise HTTPException(403, "Request origin is not permitted.")

    async def home(request):
        request.session.setdefault("csrf", secrets.token_urlsafe(32))
        return HTMLResponse((Path(__file__).parent / "web" / "index.html").read_text(),
                            headers={"Cache-Control": "no-store", "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'"})

    async def session(request):
        request.session.setdefault("csrf", secrets.token_urlsafe(32))
        owner = next((p for p in ACCOUNTS if p.user_id == request.session.get("user_id")), None)
        return JSONResponse({"csrf": request.session["csrf"], "user_id": owner.user_id if owner else None,
                             "customer_id": owner.customer_id if owner else None,
                             "user_context": "application-asserted", "hosted_configured": hosted_configured},
                            headers={"Cache-Control": "no-store"})

    async def login(request):
        csrf(request)
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        attempts = [when for when in login_attempts.get(ip, []) if now - when < 60]
        if len(attempts) >= 5:
            raise HTTPException(429, "Too many login attempts; wait one minute.")
        attempts.append(now)
        login_attempts[ip] = attempts
        login_attempts.move_to_end(ip)
        if len(login_attempts) > 1024:
            login_attempts.popitem(last=False)
        body = await json_body(request, maximum=4096)
        owner = await backend.call("POST", "/login", body={"username": body.get("username"), "password": body.get("password")})
        if not any(owner.get("user_id") == p.user_id and owner.get("customer_id") == p.customer_id for p in ACCOUNTS):
            raise HTTPException(502, "Execution API returned an invalid demo principal.")
        request.session.clear()
        request.session.update(user_id=owner["user_id"], csrf=secrets.token_urlsafe(32))
        return JSONResponse({"user_id": owner["user_id"], "customer_id": owner["customer_id"]})

    async def logout(request):
        csrf(request)
        request.session.clear()
        return JSONResponse({"signed_out": True})

    async def submit(request):
        owner = principal(request)
        csrf(request)
        if not hosted_configured:
            raise HTTPException(503, "The learner-created hosted orchestrator is not connected yet.")
        body = await json_body(request, maximum=8192)
        task, question = body.get("task"), body.get("question")
        if task not in {"phases", "safety", "workflow", "limit", "egress", "failure"} or not isinstance(question, str) or not 1 <= len(question) <= 4000:
            raise HTTPException(400, "Choose a task and a bounded question.")
        run = await backend.call("POST", "/runs", user_id=owner.user_id,
                                 body={"task": task, "idempotency_key": body.get("idempotency_key")})
        if run["state"] != "submitted":
            # A retried creation returns its original record, never replays execution.
            return JSONResponse({"run": run, "reused": True})
        key = run["run_id"]
        if key in active:
            return JSONResponse({"run": run, "reused": True})
        async def invoke():
            try:
                grant = await backend.call("POST", f"/runs/{key}/grant", user_id=owner.user_id, body={})
                output = await hosted.invoke(question=question, task=task, binding=grant)
                session_id = output.get("agent_session_id")
                if isinstance(session_id, str) and session_id:
                    await backend.call("POST", f"/runs/{key}/session", user_id=owner.user_id,
                                       body={"session_id": session_id})
                outcomes[key] = output
            except (HTTPException, httpx.HTTPError, ValueError) as error:
                LOG.error("run=%s hosted operation failed type=%s", key, type(error).__name__)
                outcomes[key] = {"error": "Hosted invocation failed; inspect owned status and reconcile before retry."}
            except asyncio.CancelledError:
                outcomes[key] = {"cancelled": True}
                raise
            finally:
                active.pop(key, None)
                if len(outcomes) > 1024:
                    outcomes.popitem(last=False)

        active[key] = asyncio.create_task(invoke())
        return JSONResponse({"run": run, "submitted": True}, status_code=202)

    async def owned_get(request):
        owner = principal(request)
        path = request.url.path.removeprefix("/api")
        result = await backend.call("GET", path, user_id=owner.user_id)
        if path == f"/runs/{request.path_params.get('run_id')}":
            result["hosted"] = outcomes.get(request.path_params["run_id"])
        return JSONResponse(result,
                            headers={"Cache-Control": "no-store"})

    async def cancel(request):
        owner = principal(request)
        csrf(request)
        key = request.path_params["run_id"]
        # Authorize at the authority before cancelling any in-memory task.
        result = await backend.call("POST", f"/runs/{key}/cancel", user_id=owner.user_id, body={})
        worker = active.get(key)
        if worker is not None:
            worker.cancel()
        return JSONResponse(result)

    @asynccontextmanager
    async def lifespan(app):
        yield
        for task in active.values():
            task.cancel()
        await asyncio.gather(*active.values(), return_exceptions=True)
        await backend.close()
        await hosted.close()

    return Starlette(routes=[
        Route("/", home), Route("/api/session", session),
        Route("/api/login", login, methods=["POST"]), Route("/api/logout", logout, methods=["POST"]),
        Route("/api/runs", submit, methods=["POST"]),
        Route("/api/runs/{run_id}", owned_get),
        Route("/api/runs/{run_id}/artifacts/{artifact_id}", owned_get),
        Route("/api/runs/{run_id}/conversations/{conversation_id}", owned_get),
        Route("/api/runs/{run_id}/cancel", cancel, methods=["POST"]),
    ], middleware=[
        Middleware(
            SessionMiddleware, secret_key=session_key, same_site="strict", https_only=secure_cookies,
            max_age=3600, session_cookie="reactor_session",
        ),
    ], lifespan=lifespan)
