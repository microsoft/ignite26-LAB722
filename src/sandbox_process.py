import asyncio
import os
import signal
from dataclasses import dataclass


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


async def stop_process(process, pipes: list[_BoundedPipe], budget: _OutputBudget) -> None:
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


async def run_process(arguments: list[str], *, timeout: float, maximum: int, environment: dict) -> tuple:
    process = await asyncio.create_subprocess_exec(
        *arguments, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        limit=4096, env=environment,
        **({"start_new_session": True} if os.name == "posix" else {}),
    )
    budget = _OutputBudget(maximum)
    pipes = []
    for name in ("stdout", "stderr"):
        pipe = _BoundedPipe(getattr(process, name), budget)
        setattr(process, name, pipe)
        pipes.append(pipe)
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
    except (TimeoutError, asyncio.CancelledError, SandboxOutputLimitError):
        await stop_process(process, pipes, budget)
        raise
    if process.returncode is None:
        raise RuntimeError("The Sandbox CLI did not return an exit code.")
    return process.returncode, stdout.decode("utf-8"), stderr.decode("utf-8")
