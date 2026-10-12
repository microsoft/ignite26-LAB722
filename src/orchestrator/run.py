import argparse
import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen
from uuid import UUID, uuid4

from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import AzureCliCredential

from data.pipeline.contracts import Manifest
from .contracts import ROLES, SandboxBinding
from .credentials import InMemoryFoundryCredential
from .foundry import CaldovaWorkflow, validate_endpoint
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
    async with (
        authentication as credential,
        AIProjectClient(
            endpoint=endpoint, credential=credential, headers={"Accept-Encoding": "identity"},
        ) as project_client,
    ):
        workflow = CaldovaWorkflow(
            project_client, arguments.model, uuid4(), manifest, executors, validation_executor,
        )
        agent = await workflow.provision()
        if arguments.mode == "tool-smoke":
            result = await workflow.tool_smoke(agent, arguments.role)
        else:
            plan = await workflow.create_plan(agent)
            result = {"plan": plan.model_dump(mode="json"), "release_status": "not-approved"}
            if arguments.mode == "workers":
                try:
                    results = await workflow.run_workers(agent)
                except (RuntimeError, ValueError, TimeoutError) as error:
                    print(json.dumps({
                        **result,
                        "status": "failed",
                        "error": str(error),
                        "workers": [
                            worker.model_dump(mode="json") for worker in workflow.worker_results.values()
                        ],
                        "integration_evidence": [
                            check.model_dump(mode="json") for check in workflow.integration_evidence
                        ],
                        "egress_evidence": [
                            check.model_dump(mode="json") for check in workflow.egress_evidence
                        ],
                        "worker_evidence": [
                            check.model_dump(mode="json") for check in workflow.worker_evidence
                        ],
                    }, indent=2), file=sys.stderr)
                    raise
                else:
                    result["workers"] = [worker.model_dump(mode="json") for worker in results]
                    result["integration_evidence"] = [
                        check.model_dump(mode="json") for check in workflow.integration_evidence
                    ]
                    result["egress_evidence"] = [
                        check.model_dump(mode="json") for check in workflow.egress_evidence
                    ]
                    result["worker_evidence"] = [
                        check.model_dump(mode="json") for check in workflow.worker_evidence
                    ]
                    result["candidate_sources"] = workflow.candidate_sources
                    result["release_status"] = "requires-complete-release-evidence-and-human-approval"
        print(json.dumps(result, indent=2))


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
