# LAB722 reactor facilitator setup and recovery

## Current gate and what is not provisioned

The owner declined tenant resource creation on November 7. **No dedicated execution API audience is supplied; the service-authenticated live path is blocked.** Do not create an API registration, use Microsoft first-party tokens as a substitute, or switch back to the old endpoint key. No new Express deployment or hosted/Toolbox live pass is claimed.

The code, local checks, container recipes, ARM template and definition helpers are prepared. `setup-reactor-foundry.py --describe` is an offline SDK-definition check, not deployment validation. Current build/review evidence is in [the report](reactor-walkthrough-report.md).

## Prepared allocation contract

Use only the owner's authorized `ig2026-lab-learner` allocation in westus3. The old seed and fixed A are preserved. Obtain equivalent values for Skillable; a historical resource ID is not permission.

Before learners arrive, supply:

- Existing Foundry project/model, approved clean frozen-data snapshot, Express environment, ACR and at least two available task slots.
- A **facilitator-provided existing dedicated service API registration/audience**, with the permitted frontend UAMI and Foundry project MI authorized to request service tokens. The backend separately validates tenant/audience/object IDs and routes by caller.
- PowerShell 7.3+, Azure CLI, native ACA CLI and pinned Python packages.
- Learner Foundry Project Manager permission and read-only Azure/resource/log inspection; no role-assignment or directory operation in the lesson.
- Both Express services, project identity connection, Toolbox version and approved hosted starter image. Hosted-agent creation remains a learner action.
- Two different secret demo passwords, delivered privately. Both must be 12-1024 characters. No passwords in parameter files, URLs, screenshots or logs.

The new frontend has project Foundry User and ACR Pull; the execution UAMI has group SandboxGroup Data Owner and ACR Pull. The group itself must have no usable Azure identity. Preserve existing grants/old runtime; do not detach unrelated identities or delete seed/A.

## Build and inspect

From the repository root:

```powershell
python -m pip install -r .\src\reactor\requirements.txt -r .\src\reactor\hosted-requirements.txt
python -B -m unittest discover -s tests -p 'test_reactor_*.py' -v
az bicep build --file .\infra\reactor.bicep --stdout
```

Use a prepared isolated Python environment. The Windows run skips the Linux-root private-note check. Run the same reactor tests during the Linux service-image build; the Containerfile includes them. Existing supervisor regressions also require Linux. No new linter is introduced.

Build from the repository root or a narrow staged context that preserves the referenced paths:

```powershell
az acr build --registry $RegistryName --resource-group $ResourceGroupName `
  --subscription $SubscriptionId --image "reactor-services:$BuildVersion" `
  --file .\src\reactor\Containerfile .
az acr build --registry $RegistryName --resource-group $ResourceGroupName `
  --subscription $SubscriptionId --image "reactor-hosted:$BuildVersion" `
  --file .\src\reactor\HostedContainerfile .
```

The file is resolved relative to the command's working directory. If the CLI archive handling rejects a Windows nested Containerfile path, stage that same recipe as a named root `Containerfile` and pass its root filename; preserve source paths. Do not alter commands silently in a learner run.

Use immutable ACR digests for both images, not floating tags. Recipes pin Python 3.13 and Linux ACA preview.4; the Windows facilitator CLI may be preview.5. Snapshot restoration deliberately sends no CPU/memory override.

## Provision the two Express apps (blocked until audience supplied)

`infra\reactor.bicep` creates only the two distinct Express apps, their UAMIs and scoped Azure roles. It takes the existing API audience as a required input; it creates no tenant applications, custom MCP server or old-runtime replacement.

Omit `-HostedResponsesEndpoint` during preparation. The frontend then supports sign-in and owned inspection, displays **Hosted orchestrator not connected**, disables **Run**, and rejects direct submission with HTTP 503 before reserving a run or issuing a grant. This prepares both services without pre-creating the learner's agent. Do not supply a remembered or fabricated protocol URL.

```powershell
$AlicePassword = Read-Host 'Private Alice demo password' -AsSecureString
$BobPassword = Read-Host 'Private Bob demo password' -AsSecureString
.\scripts\deploy-reactor.ps1 `
  -SubscriptionId $SubscriptionId -ResourceGroupName $ResourceGroupName `
  -RegistryName $RegistryName -ExpressEnvironmentName $ExpressEnvironmentName `
  -FoundryAccountName $FoundryAccountName -FoundryProjectName $FoundryProjectName `
  -SandboxGroupName $SandboxGroupName -SnapshotId $SnapshotId `
  -ServiceImage $ServiceImage -ExecutionApiAudience $ExecutionApiAudience `
  -AlicePassword $AlicePassword -BobPassword $BobPassword
```

At the learner connection checkpoint, copy the exact created agent's HTTPS Responses protocol endpoint and set the frontend's `HOSTED_RESPONSES_ENDPOINT` environment variable through the approved Azure portal configuration channel. Restart/activate the updated frontend revision and sign in again; its boot key invalidates old cookies. Alternatively rerun the same helper with `-HostedResponsesEndpoint $HostedResponsesEndpoint` and the same allocation inputs/private passwords. An incremental redeployment can replace ephemeral service state, so reconcile any existing task resources first. **Endpoint configured** means submissions are enabled, not that the live gate passed.

The helper compiles ARM, submits an incremental deployment via an in-memory authenticated REST body and waits for the deployment result. It emits public endpoints/identity IDs, not passwords. It does not prove healthy apps, a valid service token or hosted gateway mapping. Independently inspect deployment operations, both `/health`/UI readiness, actual token-based login and one Toolbox offload.

Initial execution authority is SQLite under `/app/state`. On a fresh replica it checks that no `lab=LAB722,purpose=reactor-task` resources remain before seeding hashed accounts. Old grants/results are never imported. Existing state opens without recreation. Each app is one replica, minimum one; this does not make its files durable.

## Prepare the native connection and Toolbox

In the Foundry project **Connections**, create or inspect the fixed `reactor-execution` external API connection using the normal supported UI: target the execution HTTPS endpoint, select **Project managed identity**, and enter the **dedicated execution API audience**. Supply its full project connection resource ID. This is a facilitator operation; no API key or OAuth-user provider is involved.

The connection's live creation/authentication is not verified in this delivery. ARM's generic connection schema did not establish the new ProjectManagedIdentity payload, so no guessed template payload is shipped.

Register the declared HTTP operation with managed Toolbox:

```powershell
python -B .\scripts\setup-reactor-foundry.py toolbox `
  --project-endpoint $ProjectEndpoint --name runtime-reactor `
  --execution-endpoint $ExecutionUrl --connection-id $ExecutionConnectionId --describe
# After independent connection verification, remove --describe to register the version.
```

Inputs: project endpoint, execution target, existing connection ID and `src\reactor\openapi.json`. Changes: one Toolbox version with the OpenAPI execution operation. Outputs: public name/version/reused flag. Identical configuration hashes reuse the last matching version; changed configuration creates a version.

Independently inspect the actual advertised MCP operation name and its required fields before supplying `$ToolboxOperation`. It must declare `run_id`, `user_id`, `customer_id`, `conversation_id`, `run_grant`, and `tasks`. The hosted runtime supplies these binding fields programmatically; none are passed to the model. If the gateway wraps body fields differently or drops them, stop and record that exact boundary rather than guessing a mapping.

## Prepare hosted creation, then run the learner gate

The [learner guide](lab-rejig-learner-instructions.md) owns hosted-agent creation. Its helper uses `AIProjectClient.agents.create_version` with `HostedAgentDefinition`, image, CPU/memory and Responses protocol. Image-pull/runtime identity permissions and regional hosted capacity must be verified under the supplied project permissions. An SDK model serializing correctly does not prove those capabilities.

Before timing the lesson, rehearse a service-authenticated call under the frontend MI, a native Toolbox call under the hosted runtime, and an actual project-MI call at the execution API. Validate the live token's exact audience and object ID without logging the token. Prove both users' allowed and swapped-run/result/conversation/execution-denied cases. Inspect metadata privacy: the grant must never enter model input/output or retained diagnostics.

If that gate fails, classify delivery **blocked**. No historical November 6 runtime evidence substitutes for it.

## Recovery

For a known owned run, use the frontend's **Cancel and reconcile owned run** action. It authorizes ownership before cancelling tasks, fences late writes, deletes the exact run's labeled task resources and releases capacity only after confirmed cleanup. Reuse the old key only to inspect its tombstone; recover useful work with a new key.

If state is missing, old runs/grants/results cannot be recovered from Express ephemeral disk. Keep the service unavailable while task resources remain. As an authorized facilitator:

```powershell
aca sandbox list --subscription $SubscriptionId --resource-group $ResourceGroupName `
  --group $SandboxGroupName --region $Region --selector "lab=LAB722,purpose=reactor-task" -o json
# Inspect each exact ID and labels. Then delete only the confirmed abandoned task:
aca sandbox delete --subscription $SubscriptionId --resource-group $ResourceGroupName `
  --group $SandboxGroupName --region $Region --id $ConfirmedTaskId --yes
```

Never delete by a broad group selector. Preserve the seed and old fixed A. Restart the execution revision only after reconciliation; new authority rejects all old grants/IDs. Frontend boot keys invalidate old cookies. Log interruption, recovery and final inventory; do not call this durable restoration.

## Revert and ending state

Record the current/previous service digest, hosted version, Toolbox version, deployment/configuration and dataset version before any change. A revert is an operator action:

1. Stop submissions and cancel/reconcile all reactor tasks; confirm no matching live task remains.
2. Set the frontend's hosted endpoint/version selector to the recorded previous hosted version. Set the managed Toolbox default to the recorded previous version using its supported UI or `toolboxes.update(name, default_version=...)`.
3. Redeploy `infra\reactor.bicep` with the recorded service digest and the same dedicated audience/identity scope. Preserve ownership limitations: replica replacement loses ephemeral artifacts and invalidates old grants/cookies.
4. Verify one allowed Alice/Bob task, one denied foreign request and exact cleanup after rollback. Do not move `lab-ready-1`, reset the repository, or overwrite the old runtime.

No live revert has been performed. When ending a rehearsal, record the remaining service/hosted versions and usage, stop idle hosted sessions through their supported management UI, and preserve allocation recovery resources.
