from contextlib import asynccontextmanager
import json
import logging
import os
from pathlib import Path
import secrets

from azure.identity.aio import ManagedIdentityCredential
from starlette.applications import Starlette

from .execution import create_app as execution_app
from .frontend import ExecutionClient, HostedClient, create_app as frontend_app
from .ownership import OwnershipStore
from .models import ModelRelay
from .sandboxes import TaskSandboxes
from .service_auth import ServiceTokenVerifier


def build_app(config=None, *, state_path=None, source_file=None):
    config = os.environ if config is None else config
    component = config["REACTOR_COMPONENT"]
    if component not in {"frontend", "execution"}:
        raise ValueError("REACTOR_COMPONENT must be frontend or execution.")
    credential = ManagedIdentityCredential(client_id=config["AZURE_CLIENT_ID"])

    @asynccontextmanager
    async def lifespan(app):
        try:
            if component == "frontend":
                hosted_endpoint = config.get("HOSTED_RESPONSES_ENDPOINT", "")
                child = frontend_app(
                    backend=ExecutionClient(config["EXECUTION_ENDPOINT"], config["EXECUTION_API_AUDIENCE"], credential),
                    hosted=HostedClient(hosted_endpoint, credential),
                    session_key=secrets.token_urlsafe(48),
                    hosted_configured=bool(hosted_endpoint),
                    public_origin=config.get("FRONTEND_PUBLIC_ORIGIN"),
                )
            else:
                sandboxes = TaskSandboxes(
                    subscription=config["AZURE_SUBSCRIPTION_ID"], resource_group=config["RESOURCE_GROUP"],
                    region=config["SANDBOX_REGION"], group=config["SANDBOX_GROUP"],
                    snapshot=config["SANDBOX_SNAPSHOT_ID"], identity_client_id=config["AZURE_CLIENT_ID"],
                )
                state = Path(state_path or "/app/state/ownership.db")
                if not state.is_file():
                    inventory = json.loads(await sandboxes.native([
                        "list", "--selector", "lab=LAB722,purpose=reactor-task",
                    ]))
                    if not isinstance(inventory, list) or inventory:
                        raise RuntimeError("State is missing and task resources remain; facilitator reconciliation is required.")
                    logging.warning("New ephemeral authority: previous runs, grants and results are not recoverable.")
                store = OwnershipStore(state, create=not state.is_file())
                store.seed_from_env(config)
                child = execution_app(
                    store=store, sandboxes=sandboxes,
                    verifier=ServiceTokenVerifier(
                        config["AZURE_TENANT_ID"], config["EXECUTION_API_AUDIENCE"],
                        {config["FRONTEND_OBJECT_ID"], config["PROJECT_OBJECT_ID"]},
                    ),
                    frontend_object_id=config["FRONTEND_OBJECT_ID"], project_object_id=config["PROJECT_OBJECT_ID"],
                    source_file=Path(source_file or "/app/data/lab-datasets/caldova-public-lab-use-v2/source-records.json"),
                    model_relay=ModelRelay(config["REACTOR_MODEL_ENDPOINT"], config["MODEL_DEPLOYMENT"], credential)
                    if config.get("REACTOR_AGENT_SWARM_ENABLED") == "true" else None,
                )
            app.mount("/", child)
            async with child.router.lifespan_context(child):
                yield
        finally:
            await credential.close()

    logging.basicConfig(level=logging.INFO)
    return Starlette(lifespan=lifespan)
