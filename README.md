<p align="center">
<img src="img/banner-ignite-26.png" alt="Microsoft Ignite 2026" width="100%"/>
</p>

# LAB722: Operate secure, multi-tenant agentic apps on Azure Container Apps

## The story

Caldova, a fictional pharmaceutical company, needs a research experience that combines clinical-trial records and reported drug-safety events without confusing one customer's work with another's.

Ask the application a research question. A Microsoft Foundry hosted orchestrator delegates clinical-trials and drug-specialist work to agents running in separate Azure Container Apps Sandboxes. Both specialists finish before a QA agent reviews their combined findings in another Sandbox. The application returns cited findings and independently checked evidence, then reconciles the request-owned compute.

This is a **runtime agent application**, not a coding-agent exercise. You operate the application and inspect its identity, tool, compute and quality boundaries; you do not implement missing query functions or build a release candidate during the lab.

The application uses a bounded, frozen AACT/ClinicalTrials.gov-derived and openFDA sample. Results describe that sample, not live research coverage, clinical advice or comparative drug safety.

## Run the lab

Start with the **[lab instructions](instructions/README.md)** for guided or self-paced study in your assigned Skillable environment. The prepared VM includes the required Python packages. Open **Reactor 2 - sign in and prepare**, authenticate with the allocated Azure account and **Temporary Access Pass (TAP)**, and wait for `REACTOR2_SKILLABLE_READY`.

The lab focuses on three outcomes:

- Explain the request path across Express, Foundry, Toolbox and on-demand Sandbox agents.
- Verify customer/run ownership and independent quality checks rather than trusting an agent's success message.
- Observe bounded task creation, reuse, cancellation and cleanup.

To deploy from your own workstation and Azure subscription instead, use the quickstart below. Workstation deployment is facilitator/developer setup, not an extra learner step.

## Architecture

![Caldova runtime research architecture](docs/diagrams/application-architecture.svg)

```text
Browser
  -> Frontend Express app
    -> Foundry hosted orchestrator
      -> runtime-research Toolbox (MCP)
        -> Execution-manager Express API
          -> Clinical-trials and drug-specialist Sandboxes (concurrently)
          -> QA Sandbox (after both specialists finish)
```

**Express means Azure Container Apps Express**, not the Node.js Express framework. The services in this repository are Python applications. The diagram shows the main delegation path; the frontend also creates and polls owner-bound execution state, and results travel back to the browser.

| Component | Implementation | Product or protocol |
| --- | --- | --- |
| Browser and frontend | [Frontend service](src/reactor/frontend.py), [web UI](src/reactor/web/index.html) | [Azure Container Apps Express](https://learn.microsoft.com/azure/container-apps/express-overview) |
| Hosted research orchestrator | [Hosted agent](src/reactor/hosted.py), [Foundry setup](scripts/setup-reactor-foundry.py) | [Foundry hosted agents](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents), [Microsoft Agent Framework](https://learn.microsoft.com/agent-framework/overview) |
| `runtime-research` Toolbox | [OpenAPI operations](src/reactor/openapi.json), [discovery check](scripts/inspect-reactor-toolbox.py) | [Microsoft Foundry Toolbox](https://learn.microsoft.com/azure/foundry/agents/concepts/toolbox-overview), [MCP](https://modelcontextprotocol.io/docs/getting-started/intro) |
| Execution-manager API | [Execution service](src/reactor/execution.py), [ownership](src/reactor/ownership.py), [service authentication](src/reactor/service_auth.py) | [Express](https://learn.microsoft.com/azure/container-apps/express-overview), [managed identities](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/overview) |
| Specialist and QA agents | [Agent loops and tools](src/reactor/agent_runtime.py), [Sandbox lifecycle](src/reactor/sandboxes.py) | [Azure Container Apps Sandboxes](https://learn.microsoft.com/azure/container-apps/sandboxes-overview), Foundry model inference |
| Independent evidence | [Research contract](src/reactor/research.py), [evaluation](src/reactor/evaluation.py), [frozen data](data/README.md) | [ClinicalTrials.gov](https://clinicaltrials.gov/), [AACT](https://aact.ctti-clinicaltrials.org/), [openFDA](https://open.fda.gov/) |
| Images and deployment | [Digest-pinned catalog](data/reactor-research-images.json), [local Bicep](infra/local-reactor/main.bicep), [Skillable foundation](infra/reactor2-skillable.bicep) | [Azure Container Registry](https://learn.microsoft.com/azure/container-registry/container-registry-intro), [Bicep](https://learn.microsoft.com/azure/azure-resource-manager/bicep/overview), [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/overview) |

Agent loops and data tools run inside Sandboxes; model inference stays in Foundry. Frontend and execution identities are separate. Customer/conversation ownership and per-run grants accompany tool requests. The execution manager controls budgets and lifecycle; QA and deterministic evaluation are separate from the orchestrator's answer. See [architecture and trust boundaries](docs/architecture.md).

## Requirements

For deployment from a Windows workstation:

| Requirement | Purpose |
| --- | --- |
| Git, PowerShell **7.3+**, Python **3.13+** (x64 recommended on Windows) | Checkout, deployment helpers and the local preparation environment; published containers use Python 3.13 |
| [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) and [Azure Developer CLI 1.35.1+](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) | Azure authentication and root-level `azd up` |
| Prepared [`aca` Sandbox CLI](https://learn.microsoft.com/azure/container-apps/sandboxes-get-started) on `PATH` | Agent disk, seed, snapshot and task Sandbox operations; this is separate from `az` |
| Microsoft Entra-backed Azure account | Access to an explicitly selected subscription and resource group |
| Deployment and scoped role-assignment permissions | Provision resources and grant only the needed project, account, registry and Sandbox roles |
| Permission to create the dedicated Entra application/service principal | The execution API has its own `api://...` audience; tenant policy may require a privately supplied `serviceManagementReference` |
| Foundry hosted-agent access and model quota | The template requests `gpt-5.2`, version `2025-12-11`, `GlobalStandard`, capacity `40`, in `westus3` |
| Access to Express, Sandboxes and the pinned image sources | Required regional capabilities and enough Sandbox capacity for teaching resources and task agents |

This is not an Azure-free local emulator: the browser can run on your machine, but hosting, model inference, Toolbox and task Sandboxes run in Azure. The quickstart consumes pinned images; Node.js and a local Docker daemon are not required.

## Local deployment quickstart

Run in **PowerShell 7**. Use a new environment and an unused resource group in a subscription where you are authorized to provision resources. The commands create billable Azure resources.

```powershell
git clone https://github.com/microsoft/ignite26-LAB722.git
Set-Location .\ignite26-LAB722

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\infra\local-reactor\requirements.txt

az login
azd auth login
az account set --subscription '<your-subscription-id>'
azd env new caldova-research --subscription '<your-subscription-id>' --location westus3
azd env set AZURE_RESOURCE_GROUP '<your-new-resource-group>'
azd env set FOUNDRY_PROJECT_NAME reactor
azd env set REACTOR_PYTHON (Resolve-Path .\.venv\Scripts\python.exe).Path
azd up
```

The interactive preparation prompts for any tenant-required private service-management reference and for two distinct **Alice/Bob application demo passwords**. Enter these privately; they are not Azure passwords and are not written into the `azd` environment.

For unattended preparation, a private launcher may supply process-scoped `LAB722_SERVICE_MANAGEMENT_REFERENCE`, `LAB722_ALICE_PASSWORD` and `LAB722_BOB_PASSWORD` instead. Do not store these with `azd env set`, print them, commit them or leave them in a persistent environment; clear them when the child deployment exits.

When preparation succeeds, open the printed **Research frontend** URL and sign in with one of those demo accounts. Ask a supported drug/topic question, inspect its citations and returned evidence, and verify an accepted result and task cleanup. A responsive page or an active hosted version alone is not an accepted research run.

## Deployment details

### What `azd up` does

The root [azure.yaml](azure.yaml) uses [infra/local-reactor](infra/local-reactor/main.bicep). Its explicit `up` workflow runs provisioning and hooks; it does not try to source-build or deploy Express through an unrelated generic application host.

1. **Validate:** the `preup` hook runs [`prepare-local-reactor.ps1 -Mode Validate`](scripts/prepare-local-reactor.ps1) before required Bicep inputs are resolved. It checks the selected enabled Azure subscription, required tools/imports and existing resource ownership, then records the signed-in operator's object ID.
2. **Provision:** Bicep deploys the Foundry project/model, Express environment, Sandbox group, registry and supporting resources. [Parameters](infra/local-reactor/main.parameters.json) come from the selected root `azd` environment.
3. **Prepare the current runtime:** `-Mode Research` creates/reuses the dedicated execution API, mirrors the digest-pinned hosted image into the environment's own registry and configures its managed-identity connection. It calls [`prepare-reactor-swarm.ps1`](scripts/prepare-reactor-swarm.ps1) for the preloaded agent disk/seed/snapshot, two Express services, `runtime-research` Toolbox and hosted orchestrator.
4. **Connect:** preparation waits for the **exact hosted version** to become active, then connects and restarts only the frontend if necessary. It saves non-secret learner values under `.build-contexts\research-<environment>\learner-values.json`.

The public [image catalog](data/reactor-research-images.json) identifies three distinct artifacts: the services image, preloaded specialist-agent image and hosted-orchestrator image. Express uses anonymous public-image pulls without a registry identity. The hosted orchestrator uses the copied image in the deployment's own ACR with a project-managed-identity registry connection.

### Configuration and recovery

Before provisioning, override documented inputs only when the target region supports the requested services/model:

```powershell
azd env set FOUNDRY_MODEL_CAPACITY 40
azd env set FOUNDRY_PROJECT_NAME reactor
azd env get-value AZURE_SUBSCRIPTION_ID
azd env get-value AZURE_RESOURCE_GROUP
```

After a hook failure, inspect the exact retained deployment, hosted version or seed before rerunning preparation. To resume the same current environment without reprovisioning the foundation:

```powershell
.\scripts\prepare-local-reactor.ps1 -Mode Research
```

The helper reuses recorded research preparation, verifies the image/allocation contract and refuses to proceed over active owned tasks. Do not select an old developer-lab environment for this workflow or clear state to force a new version.

The older root `infra\main.bicep` and explicitly selected legacy helper modes remain for existing deployments; root `azd` no longer selects them. Local environment state is ignored by Git. Never commit `.azure`, `.build-contexts`, credentials, tokens or demo passwords.

### Skillable delivery

Skillable uses the separate [Reactor foundation](infra/reactor2-skillable.bicep), [compiled ARM](infra/skillable/reactor2.azuredeploy.json) and scoped lifecycle actions. Its prepared VM has the seven controller packages installed before image capture. The desktop launcher verifies those prerequisites and does **not** create a virtual environment or install packages.

The [source exporter](scripts/export-reactor-skillable.py) packages the preparation files for the first-display action. The [access action](scripts/skillable-reactor2-access.ps1) supplies the dedicated API and eight scoped role assignments; [teardown](scripts/skillable-reactor2-teardown.ps1) removes the exact allocation-owned API registration. See the [Skillable guide](instructions/reactor-2-skillable.md) for credential distinctions, resource checks and learner exercises.

## Troubleshooting

| Symptom | Check or action |
| --- | --- |
| Missing interpreter, SDK or `aca` | For workstation setup, install the declared local requirements and prepare the CLI before `azd up`. On Skillable, report the prepared-image issue; do not turn the launcher back into an installer. |
| Native package build fails on Windows ARM64 | Use x64 Python 3.13 and recreate the workstation virtual environment to consume binary wheels. Do not change runtime dependency pins to work around a missing compiler. |
| Wrong subscription or tenant | Check `az account show --query '{subscription:id,tenant:tenantId,state:state}' -o json` and the selected `azd` environment. In Skillable use only Resources credentials and TAP. |
| Foundry connection write denied after password-only login | Sign out with `az logout` and use the normal allocated TAP-backed sign-in. Do not weaken tenant policy or grant yourself roles. |
| Model, hosted-agent or Sandbox provisioning fails | Verify regional access, quota and actual capacity. Preserve the failed resource/version and error; do not automatically allocate replacements. |
| Hosted version reports `ImageError` | Check the exact failed version, mirrored image digest, project identity's registry-scoped `AcrPull` and managed-identity registry connection. Anonymous public manifest access alone does not prove Foundry can pull an image. |
| Frontend opens but research cannot start | Verify the exact hosted version is active, the frontend is connected, and `runtime-research` advertises the specialist/QA operations. Inspect the two apps separately. |
| API returns 401/403 | Compare the dedicated execution audience, caller object IDs, project-managed-identity connection, customer ownership and run grant. Do not substitute a first-party API audience or log full tokens/session responses. |
| Research or QA fails | Read the owning run's evidence and failed independent checks. Inspect frozen sample coverage and citations; do not relabel an unaccepted answer as success. |
| Task Sandboxes remain after cancellation | Reconcile the exact run and task labels in the supplied Sandbox group. Do not delete teaching seeds, unrelated work or resources selected only by a similar name. |
| A local retry reports retained or incompatible state | Inspect `.build-contexts` and the selected environment; use the recorded scope and images. Do not delete state or reuse another allocation's IDs to silence the check. |

## Repository map

| Path | Contents |
| --- | --- |
| [instructions](instructions/README.md) | Current guided and self-paced learner guide |
| [src/reactor](src/reactor) | Frontend, hosted orchestrator, execution API and Sandbox agents |
| [scripts](scripts/README.md) | Current deployment, preparation and delivery helpers |
| [infra](infra/README.md) | Workstation `azd` templates, Skillable foundation and shared Bicep modules |
| [data](data/README.md) | Frozen sample, provenance and pinned image catalog |
| [docs](docs/README.md) | Architecture and trust boundaries |
| [tests](tests) | Offline ownership, orchestration, evaluation and preparation regressions |

## Content owner

[Simon Jakesch](https://github.com/simonjj) · [Microsoft Ignite 2026](https://ignite.microsoft.com)

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general). Use must not cause confusion or imply Microsoft sponsorship. Third-party trademarks and logos are subject to their owners' policies.
