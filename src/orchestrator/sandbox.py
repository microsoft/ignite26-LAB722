import asyncio
import base64
import hashlib
import json
import math
import os
import re
import shlex
import signal
from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from .contracts import CheckEvidence, SandboxBinding

READABLE_FILES = frozenset({
    "data/fixtures/research-data.json",
    "data/pipeline/contracts.py",
    "data/pipeline/build_dataset.py",
    "data/pipeline/validate_dataset.py",
    "src/research-portal/backend/app.py",
    "src/research-portal/backend/queries.py",
    "src/research-portal/backend/trial_feature.py",
    "src/research-portal/backend/safety_feature.py",
    "tests/test_research.py",
    "tests/test_frozen_public_research.py",
    "src/workers/frozen_contract.py",
})
WRITABLE_FILES = {
    "clinical-trials": frozenset({"src/research-portal/backend/trial_feature.py"}),
    "drug-safety": frozenset({"src/research-portal/backend/safety_feature.py"}),
    "quality-governance": frozenset(),
}
RESULT_PREFIX = "CALDOVA_FILE_RESULT="
MAX_OUTPUT_BYTES = 131072
MAX_SOURCE_BYTES = 16000
MAX_WRITE_BYTES = 12000
MAX_COMMAND_SECONDS = 180

_CLI_ENVIRONMENT = frozenset({
    "PATH", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
    "SystemRoot", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT",
    "AZURE_CONFIG_DIR", "ACA_SANDBOX_MANAGED_IDENTITY",
    "WSL_INTEROP", "WSL_DISTRO_NAME",
})


def sandbox_cli_environment() -> dict[str, str]:
    """Inherit CLI credential locations, not the orchestrator's AI credentials."""
    return {key: value for key, value in os.environ.items() if key in _CLI_ENVIRONMENT}


def validate_timeout(timeout: float) -> None:
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or \
            not math.isfinite(timeout) or not 0 < timeout <= MAX_COMMAND_SECONDS:
        raise ValueError(f"Sandbox timeout must be positive and at most {MAX_COMMAND_SECONDS} seconds.")


def _metadata_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Sandbox metadata contains duplicate object fields.")
        value[key] = item
    return value


class SandboxOutputLimitError(RuntimeError):
    pass


@dataclass
class _OutputBudget:
    maximum: int
    captured: int = 0
    discard: bool = False


class _BoundedPipe:
    def __init__(self, reader: asyncio.StreamReader, budget: _OutputBudget):
        self.reader = reader
        self.budget = budget
        self.task: asyncio.Task | None = None

    async def read(self) -> bytes:
        # Process.communicate() otherwise uses an unbounded StreamReader.read(-1).
        self.task = asyncio.current_task()
        captured = bytearray()
        while chunk := await self.reader.read(4096):
            if self.budget.discard:
                continue
            self.budget.captured += len(chunk)
            if self.budget.captured > self.budget.maximum:
                raise SandboxOutputLimitError(
                    f"Sandbox CLI output exceeded {self.budget.maximum} combined stdout/stderr bytes."
                )
            captured.extend(chunk)
        return bytes(captured)


_FILE_SCRIPT = """
import base64, hashlib, json, os, pathlib, stat
p["content"] = None if p["content"] is None else base64.b64decode(p["content"], validate=True).decode("utf-8")
directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
directory = os.open("/", directory_flags)
try:
    parts = pathlib.PurePosixPath(p["root"]).parts[1:] + pathlib.PurePosixPath(p["path"]).parts
    for part in parts[:-1]:
        child = os.open(part, directory_flags, dir_fd=directory)
        os.close(directory)
        directory = child
    flags = (os.O_RDONLY if p["content"] is None else os.O_RDWR) | os.O_NOFOLLOW | os.O_NONBLOCK
    target = os.open(parts[-1], flags, dir_fd=directory)
    try:
        metadata = os.fstat(target)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > p["maximum"]:
            raise ValueError("Source must be a bounded regular file.")
        if p["content"] is not None:
            pending = p["content"].encode("utf-8")
            os.ftruncate(target, 0)
            while pending:
                written = os.write(target, pending)
                if written == 0:
                    raise OSError("Source write made no progress.")
                pending = pending[written:]
            os.lseek(target, 0, os.SEEK_SET)
        data = bytearray()
        while chunk := os.read(target, min(4096, p["maximum"] + 1 - len(data))):
            data.extend(chunk)
            if len(data) > p["maximum"]:
                raise ValueError("Source exceeds its UTF-8 byte limit.")
        print(p["prefix"] + json.dumps({
            "path": p["path"], "content": data.decode("utf-8"),
            "sha256": hashlib.sha256(data).hexdigest(),
        }))
    finally:
        os.close(target)
finally:
    os.close(directory)
"""


@dataclass(frozen=True)
class SandboxScope:
    subscription: UUID
    resource_group: str
    region: str
    group: str

    def __post_init__(self):
        if not isinstance(self.subscription, UUID):
            raise ValueError("Sandbox subscription must be a UUID.")
        for value in (self.resource_group, self.region, self.group):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._()-]{0,89}", value):
                raise ValueError("Sandbox scope names must be bounded Azure resource names.")


@dataclass(frozen=True)
class Execution:
    exit_code: int
    stdout: str
    stderr: str

    def evidence(self, run_id: UUID, name: str, sandbox_id: UUID, passed: bool) -> CheckEvidence:
        return CheckEvidence(
            run_id=run_id, name=name, sandbox_id=sandbox_id,
            exit_code=self.exit_code, passed=passed,
            output_sha256=hashlib.sha256(
                json.dumps([self.stdout, self.stderr], ensure_ascii=False).encode()
            ).hexdigest(),
        )


class SandboxExecutor:
    def __init__(
        self, executable: str, scope: SandboxScope, binding: SandboxBinding, *,
        max_output_bytes: int = MAX_OUTPUT_BYTES,
    ):
        if isinstance(max_output_bytes, bool) or not isinstance(max_output_bytes, int) or \
                not 0 < max_output_bytes <= 1048576:
            raise ValueError("Sandbox output limit must be between 1 and 1048576 bytes.")
        self.executable = executable
        self.scope = scope
        self.binding = SandboxBinding.model_validate(binding.model_dump())
        self.max_output_bytes = max_output_bytes

    def source_access(self) -> dict[str, str | list[str]]:
        """Describe only this worker's fixed remote workspace and source API permissions."""
        return {
            "workspace": self.binding.workspace,
            "readable_paths": sorted(READABLE_FILES),
            "writable_paths": sorted(WRITABLE_FILES[self.binding.role]),
        }

    def _bound_arguments(self, operation: str) -> list[str]:
        return [
            self.executable, "sandbox", operation, "--id", str(self.binding.sandbox_id),
            "--subscription", str(self.scope.subscription),
            "--resource-group", self.scope.resource_group, "--region", self.scope.region,
            "--group", self.scope.group,
        ]

    async def _sandbox_metadata(self, *, timeout: float) -> dict[str, object]:
        expected_id = self.binding.sandbox_id
        result = await self._run_cli(
            [*self._bound_arguments("get"), "--output", "json"], timeout=timeout,
        )
        if result.exit_code != 0:
            raise RuntimeError(f"Sandbox metadata retrieval failed with exit code {result.exit_code}.")
        try:
            metadata = json.loads(result.stdout, object_pairs_hook=_metadata_object)
        except json.JSONDecodeError:
            raise ValueError("Sandbox metadata is not valid JSON.") from None
        if not isinstance(metadata, dict) or not isinstance(metadata.get("id"), str):
            raise ValueError("Sandbox metadata is missing a valid Sandbox id.")
        try:
            sandbox_id = UUID(metadata["id"])
        except ValueError:
            raise ValueError("Sandbox metadata contains an invalid Sandbox UUID.") from None
        if sandbox_id != expected_id:
            raise ValueError("Sandbox metadata does not match the assigned Sandbox id.")
        return metadata

    async def verify_binding(self, *, timeout: float = 30) -> SandboxBinding:
        """Verify the fixed clone's actual lineage before opening its worker session.

        The source snapshot is sourcesRef.snapshot.id. The top-level snapshotId
        represents mutable lifecycle state and must not establish clone lineage.
        This host-only operation is not an MCP/model tool.
        """
        expected = self.binding.model_copy(deep=True)
        metadata = await self._sandbox_metadata(timeout=timeout)
        sources = metadata.get("sourcesRef")
        snapshot = sources.get("snapshot") if isinstance(sources, dict) else None
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("id"), str):
            raise ValueError("Sandbox metadata is missing a valid sourcesRef.snapshot.id.")
        try:
            snapshot_id = UUID(snapshot["id"])
        except ValueError:
            raise ValueError("Sandbox metadata contains an invalid source snapshot UUID.") from None
        if snapshot_id != expected.snapshot_id:
            raise ValueError("Sandbox sourcesRef.snapshot.id does not match the declared source snapshot.")
        return expected

    async def verify_egress_policy(self, *, timeout: float = 30) -> dict[str, str | list[str]]:
        """Verify configured egress for this fixed Sandbox, not runtime enforcement.

        Require the reviewed single-host policy exactly. Request receipts remain
        independent evidence; this host-only check does not query denial telemetry.
        """
        metadata = await self._sandbox_metadata(timeout=timeout)
        policy = metadata.get("egressPolicy")
        if not isinstance(policy, dict) or \
                set(policy) != {"defaultAction", "trafficInspection", "rules"} or \
                policy["defaultAction"] != "Deny" or policy["trafficInspection"] != "Full":
            raise ValueError("Sandbox egress policy must have defaultAction Deny and trafficInspection Full.")
        rules = policy["rules"]
        if not isinstance(rules, list) or len(rules) != 1 or not isinstance(rules[0], dict):
            raise ValueError("Sandbox egress policy must contain exactly the reviewed open.fda.gov allow rule.")
        rule = rules[0]
        if set(rule) - {"name", "match", "action"} or \
                rule.get("match") != {"host": "open.fda.gov"} or \
                rule.get("action") != {"type": "Allow"}:
            raise ValueError("Sandbox egress policy must allow only the exact host open.fda.gov.")
        return {"defaultAction": "Deny", "trafficInspection": "Full", "allowed_hosts": ["open.fda.gov"]}

    async def execute(
        self, command: str, *, timeout: int = 180, workspace: bool = True,
        verify_remote_status: bool = False,
    ) -> Execution:
        """Run arbitrary commands remotely; file allowlists do not constrain this shell.

        Trusted callers can require a remote shell exit-status protocol instead
        of treating the native CLI's transport exit code as the command status.
        """
        validate_timeout(timeout)
        if not command.strip() or len(command.encode()) > 24000 or "\0" in command:
            raise ValueError("The remote command must be nonempty and at most 24000 bytes.")
        status_prefix = f"CALDOVA_EXEC_RESULT_{uuid4().hex}=" if verify_remote_status else None
        if status_prefix is not None:
            command = (
                f"sh -c {shlex.quote(command)} ; caldova_status=$?; "
                f"printf '\\n{status_prefix}%s\\n' \"$caldova_status\"; exit \"$caldova_status\""
            )
        result = await self._run_cli([
            *self._bound_arguments("exec"), "--working-directory",
            self.binding.workspace if workspace else "/", "--command", command,
        ], timeout=timeout)
        if status_prefix is None:
            return result
        marker = "\n" + status_prefix
        if marker not in result.stdout and result.exit_code != 0:
            return result
        if result.stdout.count(marker) != 1:
            raise RuntimeError("The Sandbox command did not return one remote exit-status result.")
        output, status = result.stdout.split(marker)
        if not re.fullmatch(r"[0-9]{1,3}\n", status) or int(status) > 255:
            raise ValueError("The Sandbox command returned a corrupt remote exit-status result.")
        return Execution(
            exit_code=int(status) or result.exit_code, stdout=output, stderr=result.stderr,
        )

    async def _run_cli(self, arguments: list[str], *, timeout: float) -> Execution:
        validate_timeout(timeout)
        process = await asyncio.create_subprocess_exec(
            *arguments, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            limit=4096, env=sandbox_cli_environment(),
            **({"start_new_session": True} if os.name == "posix" else {}),
        )
        budget = _OutputBudget(self.max_output_bytes)
        pipes = []
        for name in ("stdout", "stderr"):
            reader = getattr(process, name, None)
            if reader is not None:
                pipe = _BoundedPipe(reader, budget)
                setattr(process, name, pipe)
                pipes.append(pipe)
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
        except TimeoutError:
            await self._stop(process, pipes, budget)
            raise TimeoutError(f"Sandbox {self.binding.sandbox_id} exceeded {timeout} seconds.") from None
        except asyncio.CancelledError:
            await self._stop(process, pipes, budget)
            raise
        except SandboxOutputLimitError:
            await self._stop(process, pipes, budget)
            raise
        if process.returncode is None:
            raise RuntimeError("The Sandbox CLI did not return an exit code.")
        return Execution(
            exit_code=process.returncode, stdout=stdout.decode("utf-8"), stderr=stderr.decode("utf-8"),
        )

    @staticmethod
    async def _stop(process, pipes: list[_BoundedPipe], budget: _OutputBudget) -> None:
        async def reap() -> None:
            if os.name == "posix" and isinstance(getattr(process, "pid", None), int):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            tasks = [pipe.task for pipe in pipes if pipe.task is not None]
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            budget.discard = True
            await process.communicate()

        # MCP cancellation is level-triggered. Reap outside that cancelled scope
        # and finish cleanup before allowing cancellation to leave this method.
        cleanup = asyncio.create_task(reap())
        cancellation = None
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError as error:
                cancellation = error
        cleanup.result()
        if cancellation is not None:
            raise cancellation

    async def file(self, path: str, content: str | None = None) -> dict[str, str]:
        relative = PurePosixPath(path)
        if path != str(relative) or "\\" in path or relative.is_absolute() or ".." in relative.parts:
            raise ValueError(
                "A source file must be a canonical relative POSIX path. "
                "Call describe_workspace to discover permitted paths."
            )
        permitted = READABLE_FILES if content is None else WRITABLE_FILES[self.binding.role]
        if path not in permitted:
            operation = "read" if content is None else "write"
            allowed = ", ".join(sorted(permitted)) or "none for this role"
            raise PermissionError(
                f"{self.binding.role} cannot {operation} this source path. "
                f"Permitted {operation} paths relative to {self.binding.workspace}: {allowed}. "
                "Call describe_workspace for source access."
            )
        if content is not None and (not content or len(content.encode()) > MAX_WRITE_BYTES):
            raise ValueError("Source contents must be nonempty and at most 12000 UTF-8 bytes.")
        payload = json.dumps({
            "root": self.binding.workspace, "path": path,
            "content": None if content is None else base64.b64encode(content.encode()).decode("ascii"),
            "maximum": MAX_SOURCE_BYTES, "prefix": RESULT_PREFIX,
        }, ensure_ascii=False)
        script = f"p=__import__('json').loads({payload!r})\n" + _FILE_SCRIPT
        result = await self.execute("python3 -c " + shlex.quote(script))
        if result.exit_code != 0:
            raise RuntimeError(f"Sandbox file operation failed with exit code {result.exit_code}.")
        lines = [line for line in result.stdout.splitlines() if line.startswith(RESULT_PREFIX)]
        if len(lines) != 1:
            raise RuntimeError("The Sandbox file operation did not return one protocol result.")
        try:
            value = json.loads(lines[0][len(RESULT_PREFIX):])
        except json.JSONDecodeError:
            raise ValueError("The Sandbox file result is not valid JSON.") from None
        if not isinstance(value, dict) or set(value) != {"path", "content", "sha256"} or \
                value["path"] != path or not isinstance(value["content"], str) or \
                len(value["content"].encode()) > MAX_SOURCE_BYTES or \
                value["sha256"] != hashlib.sha256(value["content"].encode()).hexdigest() or \
                (content is not None and value["content"] != content):
            raise ValueError("The Sandbox file result does not match its path and content checksum.")
        return value
