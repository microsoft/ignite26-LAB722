import asyncio
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from agent_framework import Content, MCPStdioTool

from .sandbox import SandboxExecutor, sandbox_cli_environment, validate_timeout


class _WorkerMCPStdioTool(MCPStdioTool):
    async def call_tool(self, tool_name: str, **kwargs: Any) -> str | list[Content]:
        started = time.monotonic()
        print(f"[{self.name}] MCP {tool_name}: started", file=sys.stderr, flush=True)
        try:
            return await super().call_tool(tool_name, **kwargs)
        except asyncio.CancelledError:
            # mcp 1.30 does not emit notifications/cancelled on request cancellation.
            # Close this worker's bridge so EOF cancels and reaps its active native CLI.
            await self.close()
            raise
        finally:
            error = sys.exception()
            state = f"failed ({type(error).__name__})" if error is not None else "returned"
            print(f"[{self.name}] MCP {tool_name}: {state} ({time.monotonic() - started:.1f}s)",
                  file=sys.stderr, flush=True)


@asynccontextmanager
async def worker_mcp_tools(
    executor: SandboxExecutor, *, timeout: float = 180, verification_command: str | None = None,
) -> AsyncIterator[MCPStdioTool]:
    """Connect one worker session to its fixed native-CLI stdio bridge.

    Keep this context open for the entire agent run and pass its yielded tool as
    ``tools=[sandbox_tools]``. All workers discover describe_workspace/execute/read_source;
    only feature specialists discover write_source.
    A supplied trusted command enables argument-free verify_feature without model-side quoting.
    Cancelling a discovered function closes this worker's bridge and ends its session.
    No generated commands or repository/application code execute on the host.
    """
    validate_timeout(timeout)
    allowed_tools = ["describe_workspace", "execute", "read_source"]
    if executor.binding.role != "quality-governance":
        allowed_tools.append("write_source")
    verification_args = []
    if verification_command is not None:
        allowed_tools.append("verify_feature")
        verification_args = ["--verification-command", verification_command]
    tool = _WorkerMCPStdioTool(
        name=f"caldova-{executor.binding.role}",
        command=sys.executable,
        args=[
            "-m", "src.sandbox-mcp.server",
            "--binding-json", executor.binding.model_dump_json(),
            "--aca", executor.executable,
            "--subscription", str(executor.scope.subscription),
            "--resource-group", executor.scope.resource_group,
            "--region", executor.scope.region,
            "--group", executor.scope.group,
            "--timeout", str(timeout),
            "--max-output-bytes", str(executor.max_output_bytes),
        ] + verification_args,
        cwd=str(Path(__file__).resolve().parents[2]),
        env=sandbox_cli_environment(),
        allowed_tools=allowed_tools,
        load_prompts=False,
        request_timeout=200,
        description="Commands and allowlisted source operations in one assigned remote Sandbox clone.",
    )
    async with tool:
        yield tool
