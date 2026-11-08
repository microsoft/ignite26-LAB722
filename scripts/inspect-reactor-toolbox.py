"""Print the allocated managed Toolbox's real operation names and input schemas."""
import argparse
import asyncio
import json
from urllib.parse import urlparse

from azure.identity.aio import AzureCliCredential
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client


async def inspect(endpoint):
    parsed = urlparse(endpoint)
    if (parsed.scheme != "https" or not parsed.hostname
            or not parsed.hostname.endswith(".services.ai.azure.com")
            or "/api/projects/" not in parsed.path or not parsed.path.endswith("/mcp")
            or parsed.username or parsed.password or parsed.fragment):
        raise ValueError("Supply the allocated project's managed Toolbox HTTPS endpoint.")
    async with AzureCliCredential() as credential:
        token = await credential.get_token("https://ai.azure.com/.default")
        async with create_mcp_http_client(headers={"Authorization": "Bearer " + token.token}) as client:
            async with streamable_http_client(endpoint, http_client=client) as channels:
                async with ClientSession(channels[0], channels[1]) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    tools = [tool.model_dump(by_alias=True, exclude_none=True) for tool in result.tools]
    expected = {"reactor___clinical_trials", "reactor___drug_specialist", "reactor___quality_assurance"}
    if not expected.issubset({tool["name"] for tool in tools}):
        raise RuntimeError("Managed Toolbox research operations are missing; advertised names: "
                           + repr(sorted(tool["name"] for tool in tools)))
    for tool in tools:
        if tool["name"] not in expected:
            continue
        schema = tool["inputSchema"]
        if ("X-Reactor-Run-Grant" not in schema.get("properties", {})
                or "X-Reactor-Run-Grant" not in schema.get("required", [])
                or "body" not in schema.get("required", [])):
            raise RuntimeError("Managed Toolbox omitted required runtime authorization arguments for " + tool["name"])
    return {"endpoint": endpoint, "expected_research_operations": sorted(expected), "tools": tools}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(inspect(args.endpoint)), indent=2))


if __name__ == "__main__":
    main()
