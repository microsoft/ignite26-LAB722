"""Separate service-authenticated HTTP offload app; deliberately not an MCP server."""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict
import hashlib
import hmac
import json
import logging
import time
from pathlib import Path

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.routing import Route

from .evaluation import evaluate
from .binding import GRANT_HEADER
from .http import json_body
from .ownership import ACCOUNTS, AccessDenied, CapacityExceeded, Conflict, StateUnavailable
from ..runtime.frozen import PINS

LOG = logging.getLogger("reactor.execution")
HANDOFF_SECONDS = 20
TASKS = {
    "phases": {"phases"}, "safety": {"safety"},
    "workflow": {"phases", "safety"}, "limit": {"limit"},
    "egress": {"egress"}, "failure": {"failure"},
}


def create_app(*, store, sandboxes, verifier, frontend_object_id: str, project_object_id: str, source_file: Path):
    source_bytes = source_file.read_bytes()
    source_records = json.loads(source_bytes)
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if source_sha256 != PINS["source-records.json"]:
        raise ValueError("Independent evaluation requires the approved frozen source bytes.")
    active = {}
    deferred = {}

    async def caller(request, expected):
        try:
            identity = await verifier.verify(request.headers.get("authorization", ""))
        except PermissionError:
            raise HTTPException(401, "Service authentication failed.") from None
        if identity.object_id != expected:
            raise HTTPException(403, "This service cannot call this operation.")
        return identity

    async def owner(request):
        await caller(request, frontend_object_id)
        principal = next((p for p in ACCOUNTS if p.user_id == request.headers.get("x-reactor-user")), None)
        if principal is None:
            raise AccessDenied("Validated application identity required.")
        return principal

    async def health(request):
        return JSONResponse({"status": "ready", "component": "execution", "maximum_active": 2})

    async def login(request):
        await caller(request, frontend_object_id)
        body = await json_body(request, maximum=4096)
        principal = await asyncio.to_thread(store.authenticate, body.get("username"), body.get("password"))
        return JSONResponse(asdict(principal))

    async def create_run(request):
        principal = await owner(request)
        body = await json_body(request, maximum=8192)
        task = body.get("task")
        if task not in TASKS:
            raise HTTPException(400, "Choose a supported task.")
        key = body.get("idempotency_key")
        if not isinstance(key, str):
            raise HTTPException(400, "An idempotency key is required.")
        run = store.create_run(principal, key, {"task": task})
        return JSONResponse(asdict(run))

    async def register_grant(request):
        principal = await owner(request)
        run_id = request.path_params["run_id"]
        grant = store.issue_grant(principal, run_id, "execute", ttl_seconds=900)
        run = store.get_run(principal, run_id)
        return JSONResponse({
            "run_id": run.run_id, "user_id": run.user_id, "customer_id": run.customer_id,
            "conversation_id": run.conversation_id, "run_grant": grant.value,
            "expires_at": grant.expires_at,
        }, headers={"Cache-Control": "no-store"})

    async def get_run(request):
        principal = await owner(request)
        run_id = request.path_params["run_id"]
        return JSONResponse({
            **asdict(store.get_run(principal, run_id)),
            "artifacts": [{"artifact_id": aid, "name": name} for aid, name in store.list_artifacts(principal, run_id)],
        })

    async def conversation(request):
        principal = await owner(request)
        run_id = request.path_params["run_id"]
        if request.method == "POST":
            body = await json_body(request, maximum=4096)
            session_id = body.get("session_id")
            if not isinstance(session_id, str):
                raise HTTPException(400, "A platform session ID is required.")
            run = store.bind_foundry_session(principal, run_id, session_id)
        else:
            run = store.get_conversation(principal, run_id, request.path_params["conversation_id"])
        return JSONResponse(asdict(run))

    async def artifact(request):
        principal = await owner(request)
        result = store.get_artifact(principal, request.path_params["run_id"], request.path_params["artifact_id"])
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    async def cancel(request):
        principal = await owner(request)
        run_id = request.path_params["run_id"]
        run = store.cancel_run(principal, run_id)
        deferred.pop(run_id, None)
        task = active.get(run_id)
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        # Exact labels also reconcile a creation whose response was lost.
        await sandboxes.recover_abandoned(run_id)
        run = store.acknowledge_cleanup(principal, run_id, sandbox_id=run.sandbox_id)
        return JSONResponse(asdict(run))

    async def execution_response(task, run, principal):
        try:
            done, _ = await asyncio.wait({task}, timeout=HANDOFF_SECONDS)
            if not done:
                return JSONResponse({"run_id": run.run_id, "state": "running", "pending": True}, status_code=202)
            return JSONResponse(await task)
        except asyncio.CancelledError:
            if store.get_run(principal, run.run_id).state == "cancelled":
                raise HTTPException(409, "Owned run was cancelled; inspect its cleanup status.") from None
            raise
        except (RuntimeError, ValueError, TimeoutError, Conflict):
            LOG.exception("run=%s offload failed; explicit cancellation/reconciliation required", run.run_id)
            raise HTTPException(502, "Offload failed. Inspect owned status; cancel/reconcile before retrying.") from None
        finally:
            if task.done():
                active.pop(run.run_id, None)
                deferred.pop(run.run_id, None)

    async def offload(request):
        identity = await caller(request, project_object_id)
        body = await json_body(request)
        binding = {name: body.get(name) for name in ("run_id", "user_id", "customer_id", "conversation_id")}
        if not all(isinstance(value, str) for value in binding.values()):
            raise HTTPException(400, "An execution binding is required.")
        token = request.headers.get(GRANT_HEADER)
        continuation = deferred.get(binding["run_id"])
        if continuation is not None:
            if (
                not isinstance(token, str) or continuation["expires_at"] <= time.monotonic()
                or binding != continuation["binding"]
                or not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), continuation["digest"])
            ):
                raise AccessDenied("Execution authorization denied.")
            run = continuation["run"]
            principal = next(p for p in ACCOUNTS if p.user_id == run.user_id)
            return await execution_response(continuation["task"], run, principal)
        store.verify_grant(token, **binding, permission="execute")
        work = body.get("tasks")
        if not isinstance(work, list) or not 1 <= len(work) <= 2:
            raise HTTPException(400, "The workflow permits one or two tasks.")
        for item in work:
            if not isinstance(item, dict) or item.get("step") not in TASKS or item.get("step") == "workflow":
                raise HTTPException(400, "Unknown execution step.")
            code = item.get("code")
            if not isinstance(code, str) or not code.strip() or len(code.encode()) > 16384 or "\0" in code:
                raise HTTPException(400, "Each task requires bounded Python.")
        execution = store.start_execution(token, **binding, lease_seconds=600)
        run = execution.run
        principal = next(p for p in ACCOUNTS if p.user_id == run.user_id)
        steps = [item["step"] for item in work]
        if len(set(steps)) != len(steps) or set(steps) != TASKS[execution.input_data["task"]]:
            store.cancel_run(principal, run.run_id)
            store.acknowledge_cleanup(principal, run.run_id, sandbox_id=None)
            raise HTTPException(403, "Tool tasks do not match the server-owned run contract.")

        async def perform():
            first_sandbox = None

            def bind(sandbox_id):
                nonlocal first_sandbox
                if first_sandbox is None:
                    first_sandbox = sandbox_id
                    store.bind_sandbox(token, run, sandbox_id)

            children = [
                asyncio.create_task(sandboxes.execute(run.run_id, item["step"], item["code"],
                                                     customer_note=execution.customer_note, on_created=bind))
                for item in work
            ]
            try:
                receipts = await asyncio.gather(*children)
            except BaseException:
                for child in children:
                    child.cancel()
                await asyncio.gather(*children, return_exceptions=True)
                raise
            assessments = [
                evaluate(receipt["step"], receipt["stdout"], source_records)
                if receipt["status"] == "completed" and receipt["step"] in {"phases", "safety"}
                else {"passed": False, "task": receipt["step"], "explanation": "Execution failed or is a negative boundary probe."}
                for receipt in receipts
            ]
            evidence = {
                "run_id": run.run_id, "conversation_id": run.conversation_id,
                "demo_user": run.user_id, "customer": run.customer_id,
                "user_context": "application-asserted",
                "service_caller": asdict(identity), "input_sha256": source_sha256,
                "dataset_version": "caldova-public-lab-use-v2",
                "receipts": receipts, "assessments": assessments,
                "accepted": all(check["passed"] for check in assessments),
                "sandbox_seconds": round(sum(r["sandbox_seconds"] for r in receipts), 3),
                "worker_count": len(receipts),
            }
            store.finish_execution(token, run, success=evidence["accepted"], artifacts={"evidence": evidence})
            current = store.get_run(principal, run.run_id)
            store.acknowledge_cleanup(principal, run.run_id, sandbox_id=current.sandbox_id)
            LOG.info("run=%s workers=%s accepted=%s cleanup=deleted", run.run_id, len(receipts), evidence["accepted"])
            return evidence

        task = asyncio.create_task(perform())
        active[run.run_id] = task
        for key, entry in list(deferred.items()):
            if entry["task"].done() and (entry["expires_at"] <= time.monotonic() or len(deferred) >= 16):
                deferred.pop(key)
                active.pop(key, None)
        deferred[run.run_id] = {
            "task": task, "run": run, "binding": binding,
            "digest": hashlib.sha256(token.encode()).hexdigest(), "expires_at": time.monotonic() + 600,
        }

        def observe_failure(completed):
            if not completed.cancelled() and completed.exception() is not None:
                LOG.error("run=%s execution failed; owned reconciliation required type=%s",
                          run.run_id, type(completed.exception()).__name__)

        task.add_done_callback(observe_failure)
        return await execution_response(task, run, principal)

    async def ownership_error(request, error):
        status = 403 if isinstance(error, AccessDenied) else 429 if isinstance(error, CapacityExceeded) else 503 if isinstance(error, StateUnavailable) else 409
        LOG.warning("request=%s authorization/state rejected type=%s", request.url.path, type(error).__name__)
        return JSONResponse({"error": str(error)}, status_code=status)

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            for task in active.values():
                task.cancel()
            await asyncio.gather(*active.values(), return_exceptions=True)

    app = Starlette(routes=[
        Route("/health", health), Route("/login", login, methods=["POST"]),
        Route("/runs", create_run, methods=["POST"]),
        Route("/runs/{run_id}/grant", register_grant, methods=["POST"]),
        Route("/runs/{run_id}", get_run),
        Route("/runs/{run_id}/session", conversation, methods=["POST"]),
        Route("/runs/{run_id}/conversations/{conversation_id}", conversation),
        Route("/runs/{run_id}/artifacts/{artifact_id}", artifact),
        Route("/runs/{run_id}/cancel", cancel, methods=["POST"]),
        Route("/offload", offload, methods=["POST"]),
    ], exception_handlers={error: ownership_error for error in (AccessDenied, Conflict, CapacityExceeded, StateUnavailable)},
        lifespan=lifespan)
    return app
