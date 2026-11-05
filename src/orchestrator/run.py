import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen
from uuid import UUID, uuid4

from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import AzureCliCredential

from data.pipeline.contracts import Manifest
from .contracts import ROLES, SandboxBinding
from .credentials import InMemoryFoundryCredential
from .foundry import CaldovaWorkflow, service_error_details, validate_endpoint
from .sandbox import SandboxExecutor, SandboxScope


def read_manifest(arguments) -> Manifest:
    if arguments.manifest:
        return Manifest.model_validate_json(arguments.manifest.read_text(encoding="utf-8"))
    uri = urlsplit(arguments.metadata_url)
    if uri.scheme != "https" or not uri.hostname or \
            not uri.hostname.endswith(".azurecontainerapps.io") or uri.username or uri.password or \
            uri.query or uri.fragment or uri.path != "/api/metadata" or uri.port not in (None, 443):
        raise ValueError("Metadata must come from an HTTPS Express /api/metadata endpoint.")
    with urlopen(arguments.metadata_url, timeout=20) as response:
        raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("The metadata response exceeded its 1 MiB limit.")
    return Manifest.model_validate(json.loads(raw)["manifest"])


async def run(arguments) -> None:
    endpoint = validate_endpoint(arguments.project_endpoint)
    manifest = read_manifest(arguments)
    scope = SandboxScope(arguments.subscription, arguments.resource_group, arguments.region, arguments.group)
    executors = {}
    if arguments.bindings:
        for value in json.loads(arguments.bindings.read_text(encoding="utf-8")):
            binding = SandboxBinding.model_validate(value)
            if binding.role in executors:
                raise ValueError("A specialist cannot have multiple Sandbox bindings.")
            executors[binding.role] = SandboxExecutor(arguments.aca, scope, binding)
    if arguments.mode == "tool-smoke" and arguments.role not in executors:
        raise ValueError("Diagnostic mode requires the requested role's explicit Sandbox binding.")
    if arguments.mode == "workers" and not arguments.approve_plan:
        raise PermissionError("Use --approve-plan to explicitly authorize specialist execution, not deployment.")
    validation_executor = None
    if arguments.validation_sandbox_id:
        if not executors:
            raise ValueError("Integration requires the prepared worker bindings.")
        validation_executor = SandboxExecutor(arguments.aca, scope, SandboxBinding(
            role="quality-governance", sandbox_id=arguments.validation_sandbox_id,
            snapshot_id=next(iter(executors.values())).binding.snapshot_id,
        ))
    authentication = (
        InMemoryFoundryCredential(sys.stdin.read(16384))
        if arguments.token_stdin else AzureCliCredential(subscription=str(arguments.subscription))
    )
    run_id = uuid4()
    started = time.monotonic()
    directory = arguments.output_directory / str(run_id)
    directory.mkdir(parents=True, exist_ok=False)
    print(f"Run {run_id}; evidence directory: {directory}", file=sys.stderr, flush=True)
    workflow = None
    result = {"release_status": "not-approved"}
    try:
        async with (
            authentication as credential,
            AIProjectClient(
                endpoint=endpoint, credential=credential, headers={"Accept-Encoding": "identity"},
            ) as project_client,
        ):
            workflow = CaldovaWorkflow(
                project_client, arguments.model, run_id, manifest, executors, validation_executor,
            )
            async with workflow.progress("Connect persistent Foundry agent"):
                agent = await workflow.provision(planning=arguments.mode != "tool-smoke")
            if arguments.mode == "tool-smoke":
                async with workflow.progress(f"Verify assigned Sandbox tool ({arguments.role})"):
                    result = await workflow.tool_smoke(agent, arguments.role)
            else:
                async with workflow.progress("Generate and validate plan"):
                    plan = await workflow.create_plan(agent)
                result["plan"] = plan.model_dump(mode="json")
                if arguments.mode == "workers":
                    async with workflow.progress("Connect tool-enabled Foundry agent"):
                        agent = await workflow.provision()
                    async with workflow.progress("Run implementation, integration and governance"):
                        results = await workflow.run_workers(agent)
                    result["workers"] = [worker.model_dump(mode="json") for worker in results]
                    for field in ("integration_evidence", "egress_evidence", "worker_evidence"):
                        result[field] = [
                            check.model_dump(mode="json") for check in getattr(workflow, field)
                        ]
                    result["candidate_sources"] = workflow.candidate_sources
                    result["release_status"] = "requires-complete-release-evidence-and-human-approval"
    finally:
        error = sys.exception()
        if error is not None:
            failure = {
                **result, "run_id": str(run_id), "mode": arguments.mode,
                "status": "failed", "release_status": "not-approved",
                "error_type": type(error).__name__, "error": str(error) or type(error).__name__,
                **service_error_details(error),
                "elapsed_seconds": round(time.monotonic() - started, 1),
                "worker_failures": workflow.worker_failures if workflow else [],
                "workers": [
                    worker.model_dump(mode="json") for worker in workflow.worker_results.values()
                ] if workflow else [],
                **{
                    field: [check.model_dump(mode="json") for check in getattr(workflow, field)]
                    if workflow else []
                    for field in ("integration_evidence", "egress_evidence", "worker_evidence")
                },
            }
            path = directory / "failure.json"
            path.write_text(json.dumps(failure, indent=2), encoding="utf-8", newline="\n")
            print(f"Run failed ({type(error).__name__}). Diagnostics saved to {path}; do not build.",
                  file=sys.stderr, flush=True)
    text = json.dumps(result, indent=2)
    path = directory / ("worker-result.json" if arguments.mode == "workers" else "result.json")
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"Result saved to {path}", file=sys.stderr, flush=True)
    print(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Caldova persistent Foundry orchestrator and remote worker sessions.")
    parser.add_argument("--mode", choices=("plan", "tool-smoke", "workers"), default="plan")
    parser.add_argument("--project-endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--subscription", type=UUID, required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--group", required=True)
    parser.add_argument("--aca", required=True)
    parser.add_argument(
        "--output-directory", type=Path, default=Path(".validation-workspaces") / "agent-runs",
        help="Save each run's result or failure evidence in a new run-ID subdirectory.",
    )
    parser.add_argument("--bindings", type=Path)
    parser.add_argument("--role", choices=ROLES, default=ROLES[0])
    parser.add_argument("--approve-plan", action="store_true")
    parser.add_argument("--validation-sandbox-id", type=UUID)
    parser.add_argument(
        "--token-stdin", action="store_true",
        help="Read a short-lived Foundry token JSON from stdin only; never pass tokens as arguments or files.",
    )
    data = parser.add_mutually_exclusive_group(required=True)
    data.add_argument("--manifest", type=Path)
    data.add_argument("--metadata-url")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
