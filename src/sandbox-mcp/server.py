import argparse
from pathlib import Path
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from src.orchestrator.contracts import SandboxBinding
from src.orchestrator.sandbox import SandboxExecutor, SandboxScope, validate_timeout


def worker_server(
    executor: SandboxExecutor, *, timeout: float = 180, verification_command: str | None = None,
) -> FastMCP:
    validate_timeout(timeout)
    if verification_command is not None and (
        not isinstance(verification_command, str) or not verification_command.strip()
        or len(verification_command.encode("utf-8")) > 65536
    ):
        raise ValueError("The trusted feature verification command must be nonempty and at most 64 KiB.")
    server = FastMCP(f"caldova-{executor.binding.role}", log_level="WARNING")
    access = executor.source_access()

    @server.tool()
    async def describe_workspace() -> dict[str, str | list[str]]:
        """Discover the fixed remote workspace and exact permitted source paths.

        Call this before read_source/write_source rather than guessing schema or source paths.
        This read-only discovery performs no commands or file reads.
        """
        return executor.source_access()

    @server.tool()
    async def execute(command: str) -> dict[str, object]:
        """Run arbitrary commands remotely in this assigned clone, not on the host.

        File allowlists constrain read_source/write_source, not shell writes inside this clone.
        """
        result = await executor.execute(command, timeout=timeout, verify_remote_status=True)
        return {"exit_code": result.exit_code, "stdout": result.stdout, "stderr": result.stderr}

    if verification_command is not None:
        @server.tool()
        async def verify_feature() -> dict[str, object]:
            """Run the controller-configured feature verifier in this assigned remote Sandbox.

            No arguments or shell quoting are needed. Checks use unchanged frozen data plus
            isolated fictional in-memory conformance cases, never host-side candidate execution.
            """
            result = await executor.execute(
                verification_command, timeout=min(timeout, 30), verify_remote_status=True,
            )
            return {"exit_code": result.exit_code, "stdout": result.stdout, "stderr": result.stderr}

    @server.tool(description=(
        "Read a permitted source/data file inside the assigned Sandbox. "
        f"Paths are relative to {access['workspace']}. Exact permitted paths: "
        + ", ".join(access["readable_paths"]) + "."
    ))
    async def read_source(path: str) -> dict[str, str]:
        """Read an explicitly permitted source/data file inside the assigned Sandbox."""
        return await executor.file(path)

    if executor.binding.role != "quality-governance":
        @server.tool(description=(
            "Update only this specialist's permitted implementation file inside its Sandbox. "
            f"Paths are relative to {access['workspace']}. Exact permitted paths: "
            + ", ".join(access["writable_paths"]) + "."
        ))
        async def write_source(path: str, content: str) -> dict[str, str]:
            """Update only this specialist's permitted implementation file inside its Sandbox."""
            return await executor.file(path, content)

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="One assigned worker's local Sandbox MCP bridge.")
    binding_input = parser.add_mutually_exclusive_group(required=True)
    binding_input.add_argument("--binding", type=Path)
    binding_input.add_argument("--binding-json")
    parser.add_argument("--aca", required=True)
    parser.add_argument("--subscription", type=UUID, required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--group", required=True)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--max-output-bytes", type=int, default=131072)
    parser.add_argument("--verification-command")
    arguments = parser.parse_args()
    binding = SandboxBinding.model_validate_json(
        arguments.binding.read_text(encoding="utf-8")
        if arguments.binding is not None else arguments.binding_json
    )
    executor = SandboxExecutor(
        arguments.aca,
        SandboxScope(arguments.subscription, arguments.resource_group, arguments.region, arguments.group),
        binding, max_output_bytes=arguments.max_output_bytes,
    )
    worker_server(
        executor, timeout=arguments.timeout, verification_command=arguments.verification_command,
    ).run(transport="stdio")


if __name__ == "__main__":
    main()
