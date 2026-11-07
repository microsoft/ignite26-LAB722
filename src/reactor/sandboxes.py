"""Task-scoped create/execute/collect/delete lifecycle, with bounded native transport."""
import asyncio
import base64
import hashlib
import json
import math
import os
import shlex
import time
from pathlib import Path
from uuid import UUID, uuid4

from ..runtime.frozen import PINS
from ..sandbox_process import run_process


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
                created = json.loads(await self.native([
                    "create", "--snapshot-id", self.snapshot,
                    "--label", "lab=LAB722", "--label", "purpose=reactor-task",
                    "--label", f"run={run_id}", "--label", f"step={step}",
                    "--egress-default", "Deny", "--traffic-inspection", "Full",
                ]))
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
