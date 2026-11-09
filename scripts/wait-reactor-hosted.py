"""Wait for the exact hosted version; never create or retry a deployment."""
import argparse
import asyncio
import json
import time

from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import AzureCliCredential


async def wait(args):
    deadline = time.monotonic() + args.timeout
    async with AzureCliCredential() as credential, AIProjectClient(
        endpoint=args.project_endpoint, credential=credential, allow_preview=True,
    ) as project:
        while True:
            version = await project.agents.get_version(args.name, args.version)
            if version.status == "active":
                print(json.dumps({"name": args.name, "version": args.version, "status": "active"}))
                return
            if version.status in {"failed", "stopped", "deleted"}:
                raise RuntimeError(f"Hosted version {args.name}/{args.version} is {version.status}; inspect its retained error.")
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Hosted version {args.name}/{args.version} did not become active.")
            await asyncio.sleep(10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-endpoint", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--timeout", type=int, default=900)
    asyncio.run(wait(parser.parse_args()))
