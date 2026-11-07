"""Register a prepared project connection in Toolbox, or create the hosted starter.

No tenant resource creation, credential provisioning or custom MCP server.
Use --describe to validate the exact SDK definitions without Azure writes.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import re

from azure.ai.projects.aio import AIProjectClient
from azure.ai.projects.models import (
    ContainerConfiguration, HostedAgentDefinition, OpenApiFunctionDefinition,
    OpenApiProjectConnectionAuthDetails, OpenApiProjectConnectionSecurityScheme,
    OpenApiToolboxTool, ProtocolVersionRecord,
)
from azure.core.exceptions import ResourceNotFoundError
from azure.identity.aio import AzureCliCredential


def definitions(args):
    if args.command == "toolbox":
        if not args.execution_endpoint.startswith("https://"):
            raise ValueError("The execution endpoint must use HTTPS.")
        spec = json.loads((Path(__file__).parents[1] / "src" / "reactor" / "openapi.json").read_text())
        spec["servers"] = [{"url": args.execution_endpoint.rstrip("/")}]
        return [OpenApiToolboxTool(
            name="reactor-execution",
            openapi=OpenApiFunctionDefinition(
                name="reactor", spec=spec,
                auth=OpenApiProjectConnectionAuthDetails(
                    security_scheme=OpenApiProjectConnectionSecurityScheme(
                        project_connection_id=args.connection_id,
                    ),
                ),
            ),
        )]
    if not re.fullmatch(r"[^ ]+@sha256:[a-f0-9]{64}", args.image):
        raise ValueError("Use an immutable hosted image digest, not a floating tag.")
    return HostedAgentDefinition(
        cpu="1", memory="2Gi",
        container_configuration=ContainerConfiguration(image=args.image),
        protocol_versions=[ProtocolVersionRecord(protocol="responses", version="v1")],
        environment_variables={
            "FOUNDRY_PROJECT_ENDPOINT": args.project_endpoint,
            "MODEL_DEPLOYMENT": args.model,
            "TOOLBOX_ENDPOINT": args.toolbox_endpoint,
            "TOOLBOX_OPERATION": args.operation,
        },
    )


async def run(args):
    definition = definitions(args)
    serialized = [v.as_dict() for v in definition] if isinstance(definition, list) else definition.as_dict()
    fingerprint = hashlib.sha256(json.dumps(serialized, sort_keys=True).encode()).hexdigest()
    if args.describe:
        print(json.dumps({"definition": serialized, "sha256": fingerprint}, indent=2))
        return
    async with AzureCliCredential() as credential, AIProjectClient(
        endpoint=args.project_endpoint, credential=credential,
    ) as project:
        operations = project.toolboxes if args.command == "toolbox" else project.agents
        try:
            versions = operations.list_versions(args.name, limit=1)
            current = next(iter([version async for version in versions]), None)
        except ResourceNotFoundError:
            current = None
        if current is not None and current.metadata.get("reactor_config_sha256") == fingerprint:
            if args.command == "toolbox":
                await operations.update(args.name, default_version=current.version)
            print(json.dumps({"name": args.name, "version": current.version, "reused": True}))
            return
        metadata = {"lab": "LAB722", "reactor_config_sha256": fingerprint}
        if args.command == "toolbox":
            created = await operations.create_version(args.name, tools=definition, metadata=metadata)
            await operations.update(args.name, default_version=created.version)
        else:
            created = await operations.create_version(args.name, definition=definition, metadata=metadata)
        print(json.dumps({"name": args.name, "version": created.version,
                          "status": getattr(created, "status", "registration-created"),
                          "reused": False}))
        # Creation is not readiness. Poll get_version and perform a real invocation independently.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["toolbox", "hosted"])
    parser.add_argument("--project-endpoint", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--execution-endpoint")
    parser.add_argument("--connection-id")
    parser.add_argument("--image")
    parser.add_argument("--model", default="gpt-5.2")
    parser.add_argument("--toolbox-endpoint")
    parser.add_argument("--operation", default="reactor_execute")
    args = parser.parse_args()
    required = ("execution_endpoint", "connection_id") if args.command == "toolbox" else ("image", "toolbox_endpoint")
    for field in required:
        if not getattr(args, field):
            parser.error("--" + field.replace("_", "-") + " is required")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
