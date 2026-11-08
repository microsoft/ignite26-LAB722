"""Task-scoped create/execute/collect/delete lifecycle, with bounded native transport."""
import asyncio
import base64
import hashlib
import json
import math
import os
import re
import shlex
import time
from pathlib import Path
from uuid import UUID, uuid4

from ..runtime.frozen import PINS
from ..sandbox_process import run_process
from .agent_runtime import MAX_TURNS, ROLES, VERSION, WALL_SECONDS


class TaskSandboxes:
    def __init__(self, *, subscription: str, resource_group: str, region: str,
                 group: str, snapshot: str, identity_client_id: str, executable: str = "aca",
                 maximum_active: int = 2):
        self.scope = [
            "--subscription", str(UUID(subscription)), "--resource-group", resource_group,
            "--region", region, "--group", group, "--managed-identity", str(UUID(identity_client_id)),
        ]
        self.snapshot = str(UUID(snapshot))
        self.executable = executable
        if maximum_active not in {1, 2}:
            raise ValueError("The lab permits at most two simultaneous task Sandboxes.")
        self.slots = asyncio.Semaphore(maximum_active)
        self.maximum_active = maximum_active
        self.runner = (Path(__file__).parents[1] / "runtime" / "remote_runner.py").read_text()
        self.agent_sha256 = hashlib.sha256((Path(__file__).parent / "agent_runtime.py").read_bytes()).hexdigest()

    async def execute_agent(self, run_id, role, selection, question, *, binding, customer_note, specialists,
                            model_relay, on_created, on_event):
        run_id = str(UUID(run_id))
        if role not in ROLES:
            raise ValueError("Unknown Sandbox specialist role.")
        if (set(binding) != {"run_id", "user_id", "customer_id", "conversation_id"}
                or binding["run_id"] != run_id
                or not all(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9-]{1,128}", value)
                           for value in binding.values())):
            raise ValueError("Specialist Sandbox requires the validated application ownership context.")
        async with self.slots:
            sandbox_id = None
            started = time.monotonic()
            execution_task = None
            try:
                await self.native([
                    "create", "--snapshot-id", self.snapshot, "--label", "lab=LAB722",
                    "--label", "purpose=reactor-task", "--label", f"run={run_id}",
                    "--label", f"step={role}", "--egress-default", "Deny", "--traffic-inspection", "Full",
                    "--label", f"user={binding['user_id']}", "--label", f"customer={binding['customer_id']}",
                    "--label", f"conversation={binding['conversation_id']}",
                ])
                created = json.loads(await self.native([
                    "get", "--selector", f"lab=LAB722,purpose=reactor-task,run={run_id},step={role}",
                ]))
                if any(created.get("labels", {}).get(key) != value for key, value in {
                    "lab": "LAB722", "purpose": "reactor-task", "run": run_id, "step": role,
                    "user": binding["user_id"], "customer": binding["customer_id"],
                    "conversation": binding["conversation_id"],
                }.items()) or created.get("sourcesRef", {}).get("snapshot", {}).get("id") != self.snapshot:
                    raise PermissionError("Specialist Sandbox did not match its owned snapshot contract.")
                sandbox_id = str(UUID(created["id"]))
                policy = created.get("egressPolicy", {})
                if policy.get("defaultAction") != "Deny" or policy.get("trafficInspection") != "Full":
                    raise PermissionError("Specialist Sandbox lacks the required network restrictions.")
                on_created(sandbox_id)
                on_event("sandbox_created", sandbox_id=sandbox_id)
                payload = base64.b64encode(json.dumps({
                    "run_id": run_id, "role": role, "selection": selection, "question": question,
                    "ownership": binding,
                    "customer_note": customer_note, "specialists": specialists,
                }).encode()).decode()
                command = (
                    "env -i PATH=/opt/python/3/bin:/usr/bin:/bin PYTHONPATH=/opt/lab722-agent "
                    "LAB722_AGENT_PAYLOAD=" + shlex.quote(payload)
                    + " /opt/python/3/bin/python3 -B -m src.reactor.agent_runtime"
                )
                execution_task = asyncio.create_task(self.native(
                    ["exec", "--id", sandbox_id, "-c", command], timeout=WALL_SECONDS + 30,
                ))
                seen = set()
                deadline = time.monotonic() + WALL_SECONDS + 15
                while not execution_task.done():
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Specialist agent exceeded its model/tool budget.")
                    await asyncio.sleep(1)
                    request_text = await self.native([
                        "exec", "--id", sandbox_id, "-c",
                        "/opt/python/3/bin/python3 -I -c "
                        + shlex.quote(
                            "from pathlib import Path; p=Path('/run/lab722-agent/request.json'); "
                            "print(p.read_text() if p.exists() else 'null')"
                        ),
                    ], timeout=30)
                    request = json.loads(request_text)
                    if request is None:
                        continue
                    request_id = request.get("request_id")
                    if not isinstance(request_id, str) or len(request_id) != 32:
                        raise ValueError("Invalid model relay request identifier.")
                    if request_id in seen:
                        continue
                    if len(seen) >= MAX_TURNS:
                        raise ValueError("Agent exceeded its model-call budget.")
                    seen.add(request_id)
                    on_event("model_requested", sandbox_id=sandbox_id, turn=request["turn"])
                    response = await model_relay.complete(role, request)
                    for call in response["message"].get("tool_calls", []):
                        on_event("tool_selected", sandbox_id=sandbox_id, turn=request["turn"],
                                 detail=call["function"]["name"])
                    encoded = base64.b64encode(json.dumps(response, allow_nan=False).encode()).decode()
                    await self.native([
                        "exec", "--id", sandbox_id, "-c", "/opt/python/3/bin/python3 -I -c "
                        + shlex.quote(
                            "import base64,os; from pathlib import Path; "
                            "p=Path('/run/lab722-agent/response.tmp'); "
                            f"p.write_bytes(base64.b64decode({encoded!r})); "
                            "p.chmod(0o600); p.replace('/run/lab722-agent/response.json'); print('null')"
                        ),
                    ], timeout=30)
                    on_event("model_completed", sandbox_id=sandbox_id, turn=request["turn"],
                             usage=response.get("usage", {}))
                result = json.loads(await execution_task)
                if (
                    result.get("version") != VERSION or result.get("role") != role
                    or result.get("run_id") != run_id or result.get("agent_sha256") != self.agent_sha256
                    or result.get("ownership") != binding
                    or result.get("files_sha256") != PINS
                    or type(result.get("model_calls")) is not int or not 1 <= result["model_calls"] <= MAX_TURNS
                    or result["model_calls"] != len(seen)
                    or not isinstance(result.get("receipts"), list) or not result["receipts"]
                    or not isinstance(result.get("output"), dict)
                ):
                    raise ValueError("Sandbox returned invalid specialist-agent evidence.")
                for receipt in result["receipts"]:
                    code = receipt["code"]
                    marker = receipt["execution_marker"]
                    if not marker.startswith(f"LAB722_REACTOR:{run_id}:{role}:"):
                        raise ValueError("Specialist code receipt is not correlated to this role.")
                    self.validate_receipt(receipt, run_id, marker, hashlib.sha256(code.encode()).hexdigest())
                    receipt.update(sandbox_id=sandbox_id, snapshot_id=self.snapshot, egress_policy=policy)
                result.update(sandbox_id=sandbox_id, snapshot_id=self.snapshot)
            finally:
                if execution_task is not None and not execution_task.done():
                    execution_task.cancel()
                    await asyncio.gather(execution_task, return_exceptions=True)
                removal = asyncio.create_task(
                    self.delete(sandbox_id) if sandbox_id else self.recover_abandoned(run_id)
                )
                cancellation = None
                while not removal.done():
                    try:
                        await asyncio.shield(removal)
                    except asyncio.CancelledError as error:
                        cancellation = error
                removal.result()
                on_event("sandbox_deleted" if sandbox_id else "sandbox_reconciled", sandbox_id=sandbox_id)
                if cancellation is not None:
                    raise cancellation
            result.update(cleanup="deleted", sandbox_seconds=round(time.monotonic() - started, 3))
            return result

    async def native(self, arguments: list[str], *, timeout: int = 120):
        environment = {
            name: value for name, value in os.environ.items()
            if name in {"PATH", "HOME", "IDENTITY_ENDPOINT", "IDENTITY_HEADER", "IMDS_ENDPOINT"}
        }
        status, stdout, stderr = await run_process(
            [self.executable, "sandbox", *arguments, *self.scope, "-o", "json"],
            timeout=timeout, maximum=1048576, environment=environment,
        )
        if status:
            raise RuntimeError(f"Sandbox operation {arguments[0]} failed with exit {status}: {stderr[:500]}")
        return stdout

    async def delete(self, sandbox_id: str):
        await self.native(["delete", "--id", str(UUID(sandbox_id)), "--yes"])

    async def recover_abandoned(self, run_id: str) -> list[str]:
        run_id = str(UUID(run_id))
        items = json.loads(await self.native([
            "list", "--selector", f"lab=LAB722,purpose=reactor-task,run={run_id}",
        ]))
        if not isinstance(items, list):
            raise ValueError("Task recovery requires a valid Sandbox inventory.")
        removed = []
        for item in items:
            labels = item.get("labels", {})
            if labels.get("lab") != "LAB722" or labels.get("purpose") != "reactor-task" or labels.get("run") != run_id:
                raise PermissionError("Task recovery returned a Sandbox outside the exact run scope.")
            sandbox_id = str(UUID(item["id"]))
            await self.delete(sandbox_id)
            removed.append(sandbox_id)
        return removed

    @staticmethod
    def validate_receipt(receipt: dict, run_id: str, marker: str, code_sha256: str):
        if (
            not isinstance(receipt, dict) or receipt.get("schema_version") != "1.0"
            or receipt.get("run_id") != run_id or receipt.get("execution_marker") != marker
            or receipt.get("code_sha256") != code_sha256
            or receipt.get("files_sha256") != PINS or receipt.get("execution_uid") != 65534
            or receipt.get("environment_cleared") is not True
            or receipt.get("no_new_privileges") is not True
            or receipt.get("identity_endpoint_status") not in {"not_exposed", 400, 401, 403, 404}
            or receipt.get("dataset_version") != "caldova-public-lab-use-v2"
            or receipt.get("status") not in {"completed", "failed", "timed_out", "output_limit"}
        ):
            raise ValueError("The Sandbox returned invalid correlated execution evidence.")
        stdout, stderr = receipt.get("stdout"), receipt.get("stderr")
        captured, elapsed, exit_code = receipt.get("captured_bytes"), receipt.get("elapsed_seconds"), receipt.get("exit_code")
        if (
            not isinstance(stdout, str) or not isinstance(stderr, str)
            or type(captured) is not int or not 0 <= captured <= 131072
            or type(elapsed) not in {int, float} or not math.isfinite(elapsed) or not 0 <= elapsed <= 40
            or type(exit_code) is not int
            or (receipt["status"] == "completed" and exit_code != 0)
            or (receipt["status"] == "failed" and exit_code == 0)
            or len(stdout.encode()) + len(stderr.encode()) > 393216
        ):
            raise ValueError("The Sandbox returned invalid bounded process output.")

    async def execute(self, run_id: str, step: str, code: str, *, customer_note: str = "", on_created=None) -> dict:
        run_id = str(UUID(run_id))
        if step not in {"phases", "safety", "limit", "egress", "failure"}:
            raise ValueError("The requested task step is outside the lab contract.")
        if not isinstance(code, str) or not code.strip() or len(code.encode()) > 16384 or "\0" in code:
            raise ValueError("Python must be nonempty, NUL-free and at most 16 KiB.")
        async with self.slots:
            started = time.monotonic()
            sandbox_id = None
            cleanup = "not_created"
            try:
                await self.native([
                    "create", "--snapshot-id", self.snapshot,
                    "--label", "lab=LAB722", "--label", "purpose=reactor-task",
                    "--label", f"run={run_id}", "--label", f"step={step}",
                    "--egress-default", "Deny", "--traffic-inspection", "Full",
                ])
                created = json.loads(await self.native([
                    "get", "--selector", f"lab=LAB722,purpose=reactor-task,run={run_id},step={step}",
                ]))
                labels = created.get("labels", {})
                if any(labels.get(key) != value for key, value in {
                    "lab": "LAB722", "purpose": "reactor-task", "run": run_id, "step": step,
                }.items()):
                    raise PermissionError("Created task Sandbox did not match the exact owned task.")
                sandbox_id = str(UUID(created["id"]))
                if created.get("sourcesRef", {}).get("snapshot", {}).get("id") != self.snapshot:
                    raise PermissionError("Created task Sandbox did not restore the approved snapshot.")
                policy = created.get("egressPolicy", {})
                if policy.get("defaultAction") != "Deny" or policy.get("trafficInspection") != "Full":
                    raise PermissionError("Created task Sandbox did not enforce the required egress policy.")
                if on_created is not None:
                    on_created(sandbox_id)
                marker = f"LAB722_REACTOR:{run_id}:{step}:{uuid4()}"
                payload = base64.b64encode(json.dumps({
                    "run_id": run_id, "marker": marker, "code": code, "customer_note": customer_note,
                }).encode()).decode()
                command = (
                    "env LAB722_PAYLOAD=" + shlex.quote(payload)
                    + " /opt/python/3/bin/python3 -I -c " + shlex.quote(self.runner)
                )
                receipt = json.loads(await self.native(["exec", "--id", sandbox_id, "-c", command], timeout=45))
                self.validate_receipt(receipt, run_id, marker, hashlib.sha256(code.encode()).hexdigest())
                receipt.update(sandbox_id=sandbox_id, step=step, snapshot_id=self.snapshot, code=code, egress_policy=policy)
            finally:
                removal = asyncio.create_task(
                    self.delete(sandbox_id) if sandbox_id else self.recover_abandoned(run_id)
                )
                cancellation = None
                while not removal.done():
                    try:
                        await asyncio.shield(removal)
                    except asyncio.CancelledError as error:
                        cancellation = error
                removal.result()
                cleanup = "deleted" if sandbox_id else "reconciled"
                if cancellation is not None:
                    raise cancellation
            receipt["cleanup"] = cleanup
            receipt["sandbox_seconds"] = round(time.monotonic() - started, 3)
            return receipt
