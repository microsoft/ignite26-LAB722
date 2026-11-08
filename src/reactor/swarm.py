"""Owner-bound, retry-safe specialist Toolbox operations and QA handoff."""
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
import time

from .ownership import ACCOUNTS, AccessDenied, Conflict
from .research import ROLES, assess_specialist, research_view, validate_selection


LOG = logging.getLogger("reactor.swarm")


class ResearchSwarm:
    def __init__(self, store, sandboxes, model_relay, source, source_sha256):
        self.store, self.sandboxes, self.model_relay = store, sandboxes, model_relay
        self.source, self.source_sha256 = source, source_sha256
        self.sessions = {}

    def event(self, session, role, event, **detail):
        value = {"at": datetime.now(timezone.utc).isoformat(), "role": role, "event": event, **detail}
        session["events"].append(value)
        if len(session["events"]) > 256:
            raise RuntimeError("Research event budget exceeded.")
        LOG.info("run=%s role=%s event=%s sandbox=%s",
                 session["run"].run_id, role, event, detail.get("sandbox_id", ""))

    def progress(self, run_id):
        session = self.sessions.get(run_id)
        if session is None:
            return None
        return {
            "status": session["status"],
            "agents": [
                {"role": role, **session["agents"].get(role, {"status": "waiting"})} for role in ROLES
            ],
            "events": list(session["events"]),
        }

    async def cancel(self, run_id):
        session = self.sessions.get(run_id)
        if session is not None and session["status"] == "running":
            tasks = [entry["task"] for entry in session["jobs"].values() if not entry["task"].done()]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            session["status"] = "cancelled"
            self.event(session, "orchestrator", "cancelled")

    async def close(self):
        for run_id in list(self.sessions):
            await self.cancel(run_id)
        await self.model_relay.close()

    async def invoke(self, role, body, token, identity):
        if role not in ROLES or not isinstance(body, dict):
            raise ValueError("Unknown research specialist operation.")
        binding = {key: body.get(key) for key in ("run_id", "user_id", "customer_id", "conversation_id")}
        if not all(isinstance(value, str) for value in binding.values()) or not isinstance(token, str):
            raise AccessDenied("A backend-bound research run is required.")
        attempt = body.get("attempt", 1)
        instruction = body.get("instruction", "")
        if type(attempt) is not int or attempt not in {1, 2} or not isinstance(instruction, str) or len(instruction) > 2000:
            raise ValueError("Research permits one initial attempt and one bounded revision.")
        if set(body) - {*binding, "attempt", "instruction"}:
            raise ValueError("Specialist tools cannot choose data, ownership, or model endpoints.")
        run_id = binding["run_id"]
        session = self.sessions.get(run_id)
        if session is None:
            if role == "quality_assurance" or attempt != 1:
                raise Conflict("Start the two research specialists before quality assurance.")
            self.store.verify_grant(token, **binding, permission="execute")
            for key, existing in list(self.sessions.items()):
                if existing["expires_at"] <= time.monotonic() and all(
                    job["task"].done() for job in existing["jobs"].values()
                ):
                    self.sessions.pop(key)
            if len(self.sessions) >= 16:
                raise Conflict("Research session budget reached; reconcile expired work.")
            execution = self.store.start_execution(token, **binding, lease_seconds=840)
            if execution.input_data.get("task") != "research":
                principal = next(p for p in ACCOUNTS if p.user_id == execution.run.user_id)
                self.store.cancel_run(principal, run_id)
                self.store.acknowledge_cleanup(principal, run_id, sandbox_id=None)
                raise AccessDenied("Specialist operation does not match the server-owned task.")
            selection = validate_selection(self.source, execution.input_data)
            session = {
                "run": execution.run, "principal": next(p for p in ACCOUNTS if p.user_id == execution.run.user_id),
                "binding": binding, "digest": hashlib.sha256(token.encode()).hexdigest(),
                "expires_at": time.monotonic() + 840, "execution": execution, "selection": selection,
                "jobs": {}, "agents": {}, "events": [], "status": "running", "results": {},
                "service_caller": asdict(identity), "bound_sandbox": False,
            }
            self.sessions[run_id] = session
            self.event(session, "orchestrator", "swarm_started")
        if (
            binding != session["binding"] or session["expires_at"] <= time.monotonic()
            or not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), session["digest"])
        ):
            raise AccessDenied("Research execution authorization denied.")
        if self.store.get_run(session["principal"], run_id).state == "cancelled":
            raise Conflict("Research run was cancelled; use a new key for new work.")
        job_key = (role, attempt)
        fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        existing = session["jobs"].get(job_key)
        if existing is not None:
            if fingerprint != existing["fingerprint"]:
                raise Conflict("A specialist attempt was already submitted with different instructions.")
            return existing["task"]
        if session["status"] != "running":
            raise Conflict("Completed research cannot create another specialist.")
        if attempt == 2:
            previous_qa = session["results"].get(("quality_assurance", 1))
            if previous_qa is None or previous_qa.get("finalized"):
                raise Conflict("A revision requires a completed, rejected first QA pass.")
        if role == "quality_assurance" and not all(
            (specialist, attempt) in session["results"] for specialist in ROLES[:2]
        ):
            raise Conflict("QA requires both completed specialist results for this attempt.")

        async def perform():
            session["agents"][role] = {"status": "starting", "attempt": attempt}
            self.event(session, role, "agent_started", attempt=attempt)

            def created(sandbox_id):
                session["agents"][role].update(status="running", sandbox_id=sandbox_id)
                if not session["bound_sandbox"]:
                    self.store.bind_sandbox(token, session["run"], sandbox_id)
                    session["bound_sandbox"] = True

            def event(name, **detail):
                self.event(session, role, name, attempt=attempt, **detail)
                if name == "model_completed":
                    session["agents"][role]["model_calls"] = detail["turn"]
                if name == "tool_selected":
                    session["agents"][role]["tool_calls"] = session["agents"][role].get("tool_calls", 0) + 1
                if name == "sandbox_deleted":
                    session["agents"][role]["status"] = "checking"

            specialists = {
                name: {key: session["results"][(name, attempt)][key] for key in ("output", "receipts", "assessment")}
                for name in ROLES[:2]
            } if role == "quality_assurance" else {}
            question = session["execution"].input_data["question"]
            if instruction:
                question += "\nOrchestrator delegation (does not override the fixed selection): " + instruction
            try:
                result = await self.sandboxes.execute_agent(
                    run_id, role, session["selection"], question,
                    binding=session["binding"],
                    customer_note=session["execution"].customer_note, specialists=specialists,
                    model_relay=self.model_relay, on_created=created, on_event=event,
                )
                assessment = assess_specialist(role, result["output"], self.source, session["selection"])
                result["assessment"] = assessment
                session["agents"][role].update(
                    status="completed" if assessment["passed"] else "rejected",
                    model_calls=result["model_calls"], tool_calls=result["tool_calls"],
                )
                self.event(session, role, "result_checked", passed=assessment["passed"])
                session["results"][job_key] = result
                if role == "quality_assurance":
                    selected = [session["results"][(name, attempt)] for name in ROLES]
                    accepted = all(row["assessment"]["passed"] for row in selected)
                    if accepted or attempt == 2:
                        evidence = {
                            "run_id": run_id, "conversation_id": session["run"].conversation_id,
                            "demo_user": binding["user_id"], "customer": binding["customer_id"],
                            "user_context": "application-asserted", "service_caller": session["service_caller"],
                            "dataset_version": self.source["dataset_version"], "input_sha256": self.source_sha256,
                            "accepted": accepted, "agents": selected, "qa": result["output"],
                            "assessments": [row["assessment"] for row in selected],
                            "receipts": [receipt for row in selected for receipt in row["receipts"]],
                            "worker_count": 3, "attempt": attempt,
                            "sandbox_seconds": round(sum(row["sandbox_seconds"] for row in session["results"].values()), 3),
                            "research": research_view(self.source, session["selection"]) if accepted else None,
                            "events": list(session["events"]),
                        }
                        self.store.finish_execution(token, session["run"], success=accepted, artifacts={"evidence": evidence})
                        current = self.store.get_run(session["principal"], run_id)
                        self.store.acknowledge_cleanup(session["principal"], run_id, sandbox_id=current.sandbox_id)
                        session["status"] = "completed" if accepted else "failed"
                        self.event(session, "orchestrator", "swarm_completed", accepted=accepted)
                        result = {"run_id": run_id, "role": role, "finalized": True, "evidence": evidence}
                        session["results"][job_key] = result
                    else:
                        self.event(session, "orchestrator", "revision_required")
                return {"run_id": run_id, "role": role, "attempt": attempt, **result}
            except BaseException:
                session["agents"][role]["status"] = "cancelled" if asyncio.current_task().cancelling() else "failed"
                self.event(session, role, "agent_failed")
                raise

        task = asyncio.create_task(perform())
        session["jobs"][job_key] = {"task": task, "fingerprint": fingerprint}

        def observed(completed):
            if not completed.cancelled() and completed.exception() is not None:
                LOG.error("run=%s role=%s specialist failed type=%s",
                          run_id, role, type(completed.exception()).__name__)

        task.add_done_callback(observed)
        return task
