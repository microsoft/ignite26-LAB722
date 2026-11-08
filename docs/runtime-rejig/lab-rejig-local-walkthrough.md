# LAB722 personal workstation walkthrough with azd

## Scope

This path prepares a **fresh `ig2026-lab-local` resource group and Foundry
project**, with a new dedicated single-tenant execution API as requested.
It uses the existing immutable images in `acateam.azurecr.io/lab722`.
No Skillable, new registry, image build/publish, shared-key runtime,
release packaging or deferred live gap-testing is involved.

Run commands in PowerShell 7.3+ from the repository root on branch
`lab-reactor`. The separate `local-reactor\azure.yaml` is the azd entry.
**Do not run the historical root `azd up`.**

Setup and the personal learner pass are different activities. The setup
hook checks infrastructure, exact starter readiness and service HTTP
readiness; it does **not** prove a hosted research transaction or label the
starter a known-good rollback reference. Your first fresh-allocation pass
is also a commissioning check. Record blockers before calling it a timed,
as-written learner success.

## 1. Check the workstation and Azure account

You need Azure CLI, azd 1.35.1+, native ACA CLI, PowerShell and an isolated
Python environment with the repository's pinned reactor packages. The
published containers stay on Python 3.13; the existing Windows rehearsal
interpreter was Python 3.14.

```powershell
git branch --show-current
azd version
aca version
python -B -c "import azure.ai.projects, azure.identity, requests, duckdb"
az login
az account set --subscription YOUR_AUTHORIZED_SUBSCRIPTION_ID
azd auth login
aca auth status
```

If the Python import check reports missing packages, prepare an isolated
environment before proceeding:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\src\reactor\requirements.txt -r .\src\reactor\hosted-requirements.txt
```

The preparation actor needs resource deployment and scoped role-assignment
rights in the new RG and on the shared `acateam` registry, plus authorized
directory application/service-principal creation. The model deployment
needs `gpt-5.2` GlobalStandard quota and native hosted capacity in westus3.
This owner-level preparation is not a minimum-learner-RBAC test.

Choose two different 12-1024-character demo passwords and retain them
privately. Obtain the approved `serviceManagementReference` when corporate
tenant policy requires it. Setup asks for it with hidden input and passes
it in-memory on stdin; **do not put it, demo passwords or tokens into azd
environment values, command arguments, transcripts or Git**.

## 2. Select the fresh local environment

The current workstation has an ignored `reactor-local` azd environment
prepared with your selected RG, subscription, region, registry ID and
Python executable. Review its public settings individually:

```powershell
azd -C .\local-reactor env select reactor-local
azd -C .\local-reactor env get-value AZURE_SUBSCRIPTION_ID
azd -C .\local-reactor env get-value AZURE_RESOURCE_GROUP
azd -C .\local-reactor env get-value AZURE_LOCATION
azd -C .\local-reactor env get-value REACTOR_REGISTRY_ID
```

For a new checkout/workstation, create equivalent local settings instead:

```powershell
azd -C .\local-reactor env new reactor-local --subscription YOUR_AUTHORIZED_SUBSCRIPTION_ID --location westus3
azd -C .\local-reactor env set AZURE_RESOURCE_GROUP ig2026-lab-local
azd -C .\local-reactor env set FOUNDRY_PROJECT_NAME reactor
azd -C .\local-reactor env set REACTOR_REGISTRY_ID YOUR_AUTHORIZED_ACATEAM_RESOURCE_ID
$PythonPath = (Get-Command python -CommandType Application | Select-Object -First 1).Source
azd -C .\local-reactor env set REACTOR_PYTHON "$PythonPath"
```

The initial hook records your signed-in user's public object ID. If you
selected a new Python environment after local configuration, update
`REACTOR_PYTHON` to that interpreter's full path. Model capacity defaults to
40; adjust `FOUNDRY_MODEL_CAPACITY` explicitly only when the approved quota
requires it. Do not silently substitute a model, region or SKU.

## 3. Prepare Azure resources

```powershell
azd -C .\local-reactor up
```

Run interactively: the hook asks for private policy metadata and both demo
passwords. No Azure resources have been provisioned by merely creating the
local environment; this command is the actual deployment. This profile's
`up` workflow runs provisioning and its preparation hook only: the native
helper deploys the published images, so there is no package/build step or
azd service deployment.

| Stage | What setup does |
|---|---|
| Preprovision | Checks tools/account/fresh scope, records your object ID, selects the known immutable images |
| Bicep | Creates a Foundry account/project/model, Express environment and capacity-8 identity-free research Sandbox group; no ACR |
| Project preparation | Adds scoped operator/project/model/image grants and the non-shared project-MI registry connection |
| Directory | Creates or reconciles only the exact allocation-owned v1 dedicated API and service principal; no client secret, demo Entra users or runtime Graph permission |
| Frozen data | Uses existing `RuntimeSeed` automation to verify/copy the three pinned v2 files, capture a clean snapshot and stop its retained seed |
| Services | Uses the existing secure deployment helper for the two digest-pinned Express apps/UAMIs and dedicated audience; frontend initially unconnected |
| Native setup | Creates/read-backs the verified ProjectManagedIdentity OpenAPI connection, registers Toolbox and a starter of `reactor-orchestrator`, grants the actual runtime identity and waits for that exact version |
| Ending | Requires responsive services, saves public values locally and leaves learner **Run** disabled until your endpoint handoff |

The connections use the specific non-secret ARM contract read back from
the working allocation. Native preview support still needs the fresh
cloud test: a successful syntax/mock check is not provisioning proof.
Setup stops on failures, retains resources and does not retry ambiguous
POSTs or silently change identity/registry policy.

If the hook was interrupted, inspect the retained stage before rerunning.
The API is reconciled by exact allocation name/ownership marker; duplicate
or foreign matches fail. A complete seed descriptor is reused only for
this scope and pinned data. An incomplete seed is **not** replaced with a
new one automatically. The existing helper's `RuntimeSeed -PrimaryId`
resume requires a new output directory; after inspecting the exact
retained seed, set `REACTOR_SEED_DESCRIPTOR` to its completed descriptor.

Once `REACTOR_PREPARED=true`, rerunning the hook does not redeploy services
or create new versions; it only checks HTTP readiness and prints the
handoff. Do not clear that marker casually: incremental service deployment
can replace ephemeral ownership state. A supported additional-project
recovery is described in [the facilitator guide](lab-rejig-instructions.md#supported-additional-project-recovery)
and needs explicit authorization plus zero live tasks.

## 4. Load your public learner settings

In the same root PowerShell:

```powershell
$LabValues = & .\scripts\prepare-local-reactor.ps1 -Mode Values
foreach ($Entry in $LabValues.GetEnumerator()) {
    Set-Variable -Name $Entry.Key -Value $Entry.Value
}
$FrontendUrl
$ProjectEndpoint
$PreparedHostedVersion
Start-Process $FrontendUrl
```

These values contain no passwords, token, CSRF or grant. Previous
known-good references start unavailable because provisioning/active status
alone does not prove a good research workflow. Record a verified reference
only after its actual accepted work/cleanup; rollback remains deferred.

Fresh local scope has a clean stopped seed and no inherited fixed A.
Record fixed A **not present** rather than copying a historical ID or
creating an unnecessary reference instance. Preserve any existing fixed A
if you later use another explicitly authorized allocation.

## 5. Follow the learner guide and connect your version

Open [the learner guide](lab-rejig-learner-instructions.md). In checkpoint 1,
inspect/describe and create a **new version of the prepared agent** with
`--new-version`. Verify the actual version became active in Foundry and is
the endpoint's latest selection. Do not credit the supplied starter.

Copy that agent's displayed Responses endpoint and run:

```powershell
$CopiedResponsesEndpoint = Read-Host 'Paste this agent's displayed HTTPS Responses endpoint'
.\scripts\prepare-local-reactor.ps1 -Mode Connect -HostedResponsesEndpoint $CopiedResponsesEndpoint
```

The helper checks this exact project/agent URL, adds `api-version=v1` if
absent, preserves existing query values and requires zero live reactor
tasks. It patches and refreshes **only the frontend** using supported app
Stop/Start, not revision restart or execution replacement. It checks the
running frontend's `hosted_configured` flag without displaying the full
session/CSRF response. Sign in again; this is connection readiness, not an
accepted task.

Continue checkpoints 2-6. Check normal portal settings/identities and use
the documented read-only CLI digest fallback if the generic image form is
blank. Your first real Alice/Bob work, foreign denial and exact deletion
establish this fresh runtime's live ownership gate; until then record the
allocation as **prepared, live gate pending**.

## 6. Record your personal result and stop

Record checkpoint classifications, start/end times, friction, actual
CLI/portal actions, owned run/artifact/version IDs and final task inventory.
Do not copy a password, token, run grant or full session response into
notes. Allocate **90-120 minutes provisionally** for the exercises,
separately from provisioning/diagnosis; representative human timing is
still to be measured by this walkthrough.

Reconcile your remaining owned tasks, verify the aggregate task selector
is empty and the seed remains stopped, and record the actual hosted/
Toolbox/service versions. Stop only identified finished rehearsal sessions
through supported Foundry management controls; preserve agent versions,
the seed and failed reproductions.

Do not run destructive teardown as part of the lesson. `azd down` does not
own the Graph application/service principal or registry-scoped role
assignment created by the hook; eventual authorized cleanup must use their
exact recorded IDs separately. We will wait for your walkthrough before
additional live gap testing, release publishing or ZIP/AGENTS packaging.
