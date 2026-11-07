"""Request-owned native Responses workflow running in Foundry, not either Express app."""
import asyncio
import json
import os

from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.foundry import FoundryChatClient, FoundryToolbox
from agent_framework_foundry_hosting import HostedResponseRequest, ResponsesHostServer, WorkflowTurn
from azure.ai.agentserver.core import get_request_context
from azure.identity.aio import ManagedIdentityCredential

from .binding import binding_from_metadata, invoke_bound

WORK = {
    "phases": "Count every trial by its phase (use NA for empty phase), emit counts and sorted trial_id values as source_ids.",
    "safety": "Count every safety report, emit count and sorted report_id values as source_ids.",
    "limit": "Demonstrate the wall-time limit by sleeping for 35 seconds, then printing a completion message.",
    "egress": "Attempt urllib.request.urlopen('https://example.com', timeout=8). Let the network exception remain visible.",
    "failure": "Create /workspace/retry-marker.txt containing a harmless note, then exit with code 19.",
}


class Orchestrator(Executor):
    def __init__(self, request: HostedResponseRequest):
        super().__init__(id="reactor-orchestrator-v1")
        metadata = request.request.get("metadata", {})
        self.binding = binding_from_metadata(dict(metadata))
        self.task = metadata.get("reactor_task")
        if self.task not in {*WORK, "workflow"}:
            raise ValueError("Unknown server-owned task contract.")
        self.scope = request.scope
        self.platform_headers = get_request_context().platform_headers()

    def client(self, credential):
        return FoundryChatClient(
            project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            model=os.environ["MODEL_DEPLOYMENT"], credential=credential,
            default_headers=self.platform_headers, timeout=90,
        )

    @handler
    async def execute(self, question: str, ctx: WorkflowContext[str]):
        credential = ManagedIdentityCredential(client_id=os.environ.get("FOUNDRY_AGENT_INSTANCE_CLIENT_ID"))
        try:
            steps = ["phases", "safety"] if self.task == "workflow" else [self.task]

            async def propose(step):
                agent = Agent(
                    client=self.client(credential), name=f"research-{step}",
                    instructions=(
                        "Generate one short Python program for the assigned frozen-data task. "
                        "Use only standard-library modules and /opt/lab722-data/source-records.json. "
                        "The Sandbox has no Azure credentials or internet access. "
                        "The customer's private note is /workspace/customer-note.txt. "
                        "Never read environment secrets or invent identities. "
                        'Return only a JSON object {"code":"..."} without Markdown fences. '
                        "For analysis, print exactly one JSON object and no commentary. "
                        + WORK[step]
                    ),
                )
                response = await agent.run(question[:4000])
                value = json.loads(response.text)
                if not isinstance(value, dict) or not isinstance(value.get("code"), str):
                    raise ValueError("Worker did not produce a Python proposal.")
                return {"step": step, "code": value["code"]}

            tasks = await asyncio.gather(*[propose(step) for step in steps])
            # Discovery is not exposed to the model; authorization fields stay in this request closure.
            async with FoundryToolbox(
                credential, url=os.environ["TOOLBOX_ENDPOINT"], timeout=180,
            ) as toolbox:
                result = await invoke_bound(toolbox, os.environ["TOOLBOX_OPERATION"], self.binding, tasks)
            if not isinstance(result, str):
                raise ValueError("Toolbox returned unsupported non-text execution evidence.")
            evidence = json.loads(result)
            if not isinstance(evidence, dict) or evidence.get("run_id") != self.binding["run_id"]:
                raise ValueError("Toolbox returned uncorrelated execution evidence.")
            review = Agent(
                client=self.client(credential), name="independent-review-explanation",
                instructions=(
                    "Explain the execution evidence briefly. Acceptance is already decided by the "
                    "execution service's frozen-source checker. Do not override it, invent successful "
                    "execution, or claim that a demo user has an Entra credential."
                ),
            )
            summary = await review.run(json.dumps(evidence, allow_nan=False))
            await ctx.yield_output(json.dumps({
                "run_id": evidence["run_id"], "accepted": evidence.get("accepted"),
                "summary": summary.text, "hosted_call_id": self.scope.call_id,
                "hosted_user_context": self.scope.user_id,
                "user_context_kind": "platform-resolved; delegation not established",
                "hosted_session_id": self.scope.session_id,
                "evidence_location": "owned execution-service artifact",
            }, allow_nan=False))
        finally:
            await credential.close()


def build_workflow(request: HostedResponseRequest):
    return WorkflowBuilder(name="reactor-v1", start_executor=Orchestrator(request)).build()


async def parse_response(request: HostedResponseRequest):
    text = await request.get_input_text()
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise ValueError("A bounded task question is required.")
    return WorkflowTurn(input=text)


if __name__ == "__main__":
    ResponsesHostServer(workflow=build_workflow, parse_response=parse_response).run()
