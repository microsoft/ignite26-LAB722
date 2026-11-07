# LAB722 reactor facilitator setup and recovery

## Current live preparation

The owner authorized real provisioning on November 7, 2026. A dedicated single-tenant service API, both Express apps, the project-managed-identity OpenAPI connection, Toolbox and native hosted agent now exist. Hosted version 6, service image v8 and Toolbox v3 completed the L1-L5 minimum technical rehearsal, including real Alice/Bob work and the longer limit/recovery path. See [the report](reactor-walkthrough-report.md) for evidence, limitations and remaining delivery checks.

Use the approved allocation values, not historical IDs or first-party audiences. `setup-reactor-foundry.py --describe` remains an offline definition check, not deployment validation. No old endpoint key or custom offload MCP server is used.

## Prepared allocation contract

Use only the owner's authorized `ig2026-lab-learner` allocation in westus3. The old seed and fixed A are preserved. Obtain equivalent values for Skillable; a historical resource ID is not permission.

Before learners arrive, supply:

- Existing Foundry project/model, approved clean frozen-data snapshot, Express environment, the public `acateam.azurecr.io/lab722` image namespace and at least two available task slots.
- A **facilitator-provided existing dedicated service API registration/audience**, with the permitted frontend UAMI and Foundry project MI authorized to request service tokens. The backend separately validates tenant/audience/object IDs and routes by caller.
- PowerShell 7.3+, Azure CLI, native ACA CLI and pinned Python packages.
- Learner Foundry Project Manager permission and read-only Azure/resource/log inspection; no role-assignment or directory operation in the lesson.
- Both Express services, project identity connection, Toolbox version and approved hosted starter image. Hosted-agent creation remains a learner action.
- Two different secret demo passwords, delivered privately. Both must be 12-1024 characters. No passwords in parameter files, URLs, screenshots or logs.

The frontend has project Foundry User; the execution UAMI has group SandboxGroup Data Owner. Anonymous registry pulls suffice for both Express apps, but the native hosted image broker requires the **Foundry project MI's AcrPull grant on the registry**, even for these public images. The platform-created hosted runtime identity separately receives project Foundry User for model/Toolbox access. These identities are distinct. The group itself must have no usable Azure identity. Preserve existing grants/old runtime; do not detach unrelated identities or delete seed/A.

For the approved dedicated API, use token version 1 and `api://<application client ID>` consistently as the request resource and expected token audience. The verified API service principal has `appRoleAssignmentRequired=false`; backend authorization uses the allowed service object IDs, not an invented role claim. Corporate Microsoft application creation requires operator-supplied `serviceManagementReference`; keep its actual value out of source, images and parameter files. Do not repurpose a shared API or change its token version. No demo Entra users, client secrets or runtime Graph permissions are required. Foundry also creates its own managed blueprint/runtime service identity during hosted registration.

### Approved API preparation

Prefer an existing allocation-owned approved API. If an authorized operator must create one, the verified Graph sequence is:

1. `POST /v1.0/applications` with the allocation-specific `displayName`, `signInAudience: AzureADMyOrg`, `api.requestedAccessTokenVersion: 1` and the privately supplied `serviceManagementReference` when tenant policy requires it. Capture the returned object `id` and client `appId` in memory; do not print the private policy metadata.
2. `PATCH /v1.0/applications/<object-id>` with `identifierUris: ["api://<appId>"]`. Read back that URI and token version 1.
3. `POST /v1.0/servicePrincipals` with only `{"appId":"<appId>"}`. The live test received a definite propagation 404 immediately after application creation; waiting 15 seconds and repeating this minimal POST succeeded. Retry only a definite 404, once, not an uncertain POST outcome. An uncertain result requires an exact `appId` lookup before any new creation.
4. Read back the exact application/service principal, tenant, URI and `appRoleAssignmentRequired`. This allocation's approved ACL path requires `false`; do not modify a shared registration or override a different tenant's policy. No client secret, certificate, redirect URI, delegated Graph permission or app-role grant is added.
5. Supply the public IDs/audience to the deployment helper. Verify app-only tokens at the backend with signature, issuer, audience and allowed object-ID checks; do not log the token.

Directory operations use the authorized operator's Graph access, never either app's runtime identity. Keep private metadata and demo passwords out of build contexts.

## Build and inspect

From the repository root:

```powershell
python -m pip install -r .\src\reactor\requirements.txt -r .\src\reactor\hosted-requirements.txt
python -B -m unittest discover -s tests -p 'test_reactor_*.py' -v
python -B -m unittest discover -s tests -p 'test_hosted_workflow.py' -v
az bicep build --file .\infra\reactor.bicep --stdout
```

Use a prepared isolated Python environment. The Windows run skips the Linux-root private-note check. The service image runs its reactor suite; the hosted image separately runs the real MAF dispatcher regression with external calls mocked. This catches a handler accidentally replacing `Executor.execute` and checks request-owned bindings plus typed MCP text results. Existing supervisor regressions also require Linux. No new linter is introduced.

The verified shared registry is `acateam` in resource group `prodish-stuff`, subscription `30501c6c-81f6-41ac-a388-d29cf43a020d`. `lab722` is a repository namespace, not the registry name or a standalone repository. Prepared images are `lab722/reactor-services` and `lab722/reactor-hosted`. Building/publishing is a facilitator operation; anonymous pull access does not grant write access.

Build from the repository root or a narrow staged context that preserves the referenced paths. These variables identify the **registry allocation**, not the learner resource group:

```powershell
$RegistryName = 'acateam'
$RegistryResourceGroupName = 'prodish-stuff'
$RegistrySubscriptionId = '30501c6c-81f6-41ac-a388-d29cf43a020d'
az acr build --registry $RegistryName --resource-group $RegistryResourceGroupName `
  --subscription $RegistrySubscriptionId --image "lab722/reactor-services:$BuildVersion" `
  --file .\src\reactor\Containerfile .
az acr build --registry $RegistryName --resource-group $RegistryResourceGroupName `
  --subscription $RegistrySubscriptionId --image "lab722/reactor-hosted:$BuildVersion" `
  --file .\src\reactor\HostedContainerfile .
```

The file is resolved relative to the command's working directory. If the CLI archive handling rejects a Windows nested Containerfile path, stage that same recipe as a named root `Containerfile` and pass its root filename; preserve source paths. Do not alter commands silently in a learner run.

Use immutable ACR digests for both images, not floating tags. Recipes pin Python 3.13 and Linux ACA preview.4; the Windows facilitator CLI may be preview.5. Snapshot restoration deliberately sends no CPU/memory override.

## Provision the two Express apps

`infra\reactor.bicep` creates only the two distinct Express apps, their UAMIs and scoped Azure roles. It takes the existing API audience as a required input; it creates no tenant applications, custom MCP server or old-runtime replacement. Its public-registry default emits no registry credentials, resource lookup or image-pull role assignments, so `acateam` need not exist in the learner resource group. Set `-UsePrivateRegistry` only for an alternative private ACR in the learner allocation; that preserves the former UAMI/ACR Pull path.

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

At the learner connection checkpoint, copy the exact created agent's HTTPS Responses protocol endpoint and set the frontend's `HOSTED_RESPONSES_ENDPOINT` environment variable through the approved Azure portal configuration channel. After reconciling existing work, apply the frontend refresh below. Verify that `GET /api/session` returns `hosted_configured: true`; a saved environment value alone did not update the running Express process in the live rehearsal. Sign in again; its boot key invalidates old cookies. Alternatively rerun the same helper with `-HostedResponsesEndpoint $HostedResponsesEndpoint` and the same allocation inputs/private passwords, then independently verify the running process. An incremental redeployment can replace ephemeral service state, so reconcile any existing task resources first. **Endpoint configured** means submissions are enabled, not that the live gate passed.

### Apply an Express configuration refresh

Express explicitly rejects **revision restart**: use **app Stop/Start**, not `az containerapp revision restart`. The installed CLI has no app start/stop subcommands. The following supported ARM actions were exercised against the frontend only:

```powershell
$FrontendResourceId = az containerapp show --name lab722-reactor-frontend `
  --resource-group $ResourceGroupName --subscription $SubscriptionId --query id -o tsv
$AppApiVersion = '2026-03-02-preview'
try {
  az rest --method post --url "$FrontendResourceId/stop?api-version=$AppApiVersion" -o none
  if ($LASTEXITCODE -ne 0) { throw 'Frontend Stop failed.' }
  $Deadline = [DateTime]::UtcNow.AddSeconds(120)
  do {
    $State = az rest --method get --url "$FrontendResourceId`?api-version=$AppApiVersion" `
      --query properties.runningStatus -o tsv
    if ($LASTEXITCODE -ne 0) { throw 'Frontend state read failed.' }
    if ($State -eq 'Stopped') { break }
    if ([DateTime]::UtcNow -gt $Deadline) { throw 'Frontend Stop timed out.' }
    Start-Sleep -Seconds 5
  } while ($true)
} finally {
  az rest --method post --url "$FrontendResourceId/start?api-version=$AppApiVersion" -o none
  if ($LASTEXITCODE -ne 0) { throw 'Frontend Start failed; restore it before continuing.' }
}
Invoke-RestMethod "$FrontendUrl/api/session" | Select-Object hosted_configured
```

Retry HTTP readiness briefly during startup; do not interpret ARM success or a missing `latestReadyRevisionName` as application readiness. The execution app is not restarted by this frontend-only operation.

The template sets `FRONTEND_PUBLIC_ORIGIN` to the frontend's canonical HTTPS origin. This is necessary behind TLS-terminating ingress: preserve CSRF/foreign-origin checks rather than trusting arbitrary forwarded headers or removing Origin validation.

Supply `$ServiceImage` as `acateam.azurecr.io/lab722/reactor-services@sha256:<verified digest>` and the hosted helper's image as `acateam.azurecr.io/lab722/reactor-hosted@sha256:<verified digest>`. The helper checks that the service image belongs to the selected registry. It compiles ARM, submits an incremental deployment via an in-memory authenticated REST body and waits for the deployment result. It emits public endpoints/identity IDs, not passwords. It does not prove healthy apps, a valid service token or hosted gateway mapping. Independently inspect deployment operations, both `/health`/UI readiness, actual token-based login and one Toolbox offload.

Initial execution authority is SQLite under `/app/state`. On a fresh replica it checks that no `lab=LAB722,purpose=reactor-task` resources remain before seeding hashed accounts. Old grants/results are never imported. Existing state opens without recreation. Each app is one replica, minimum one; this does not make its files durable.

## Prepare the native connection and Toolbox

In the Foundry project **Connections**, create or inspect the fixed `reactor-execution` external API connection using the normal supported UI: target the execution HTTPS endpoint, select **Project managed identity**, and enter the **dedicated execution API audience**. Supply its full project connection resource ID. This is a facilitator operation; no API key or OAuth-user provider is involved.

Live UI creation and ARM read-back verified category `OpenAPI`, authentication `ProjectManagedIdentity`, the exact execution target and dedicated audience. No guessed generic connection payload is shipped. The native gateway reached execution and rejected an invalid run grant with HTTP 403 after service authentication.

Register the declared HTTP operation with managed Toolbox:

```powershell
python -B .\scripts\setup-reactor-foundry.py toolbox `
  --project-endpoint $ProjectEndpoint --name runtime-reactor `
  --execution-endpoint $ExecutionUrl --connection-id $ExecutionConnectionId --describe
# After independent connection verification, remove --describe to register the version.
```

Inputs: project endpoint, execution target, existing connection ID and `src\reactor\openapi.json`. Changes: one Toolbox version with the OpenAPI execution operation. Outputs: public name/version/reused flag. Identical configuration hashes reuse the last matching version; changed configuration creates a version.

Independently inspect the actual advertised MCP operation before supplying `$ToolboxOperation`. Live discovery returned **`reactor___reactor_execute`** with required arguments `body` and `X-Reactor-Run-Grant`. `body` contains `run_id`, `user_id`, `customer_id`, `conversation_id` and `tasks`; the opaque grant is a runtime-supplied header, not a JSON body field. The hosted runtime supplies every authorization field outside model control. The gateway echoed JSON request bodies in errors; moving the grant to its redacted header passed a live error-redaction probe. Stop if the advertised schema differs.

## Prepare hosted creation, then run the learner gate

The facilitator first creates the allocation's logical hosted agent and one starter version solely to prepare its runtime identity and grants. The [learner guide](lab-rejig-learner-instructions.md) then creates a **new version of that same prepared agent** as its hands-on deployment activity. Its helper uses `AIProjectClient.agents.create_version` with `HostedAgentDefinition`, image, CPU/memory and Responses protocol. Image-pull/runtime identity permissions and regional hosted capacity must be verified before learners arrive. An SDK model serializing correctly does not prove those capabilities.

Prepare the allocation's approved logical agent name and runtime identity before the lesson; learners deploy a new version of that agent from the starter with `--new-version`. Grant the project MI image access first, register the starter, then retrieve the platform-created runtime principal and grant it project Foundry User. No learner registry or directory write is required:

```powershell
az role assignment create --assignee-object-id $ProjectObjectId `
  --assignee-principal-type ServicePrincipal --role AcrPull --scope $RegistryResourceId
# Facilitator preparation, before the learner checkpoint: create/reuse the logical agent.
python -B .\scripts\setup-reactor-foundry.py hosted --project-endpoint $ProjectEndpoint `
  --name $HostedName --image $HostedImage --model $Model `
  --toolbox-endpoint $ToolboxEndpoint --operation $ToolboxOperation
$HostedPrincipalId = az rest --method get --resource https://ai.azure.com `
  --url "$ProjectEndpoint/agents/$HostedName`?api-version=v1" `
  --query instance_identity.principal_id -o tsv
az role assignment create --assignee-object-id $HostedPrincipalId `
  --assignee-principal-type ServicePrincipal --role "Foundry User" --scope $ProjectResourceId
```

Keep these operator role assignments scoped to the registry/project. The current registry uses legacy RBAC, so `AcrPull` is the applicable image role. Validate a separate Skillable tenant's registry authorization rather than assuming this Microsoft-tenant grant transfers.

The helper opts into the native preview, declares Responses container protocol `2.0.0`, and disables Python user-site package loading. Do not set reserved `FOUNDRY_*` or `AGENT_*` environment variables; Foundry injects its project endpoint and runtime identity. A failed matching version now causes an explicit error, not a reused-success response. Correct the prerequisite before using `--new-version` for a deliberate retry.

Derive the protocol URL from `AIProjectClient(..., allow_preview=True).get_openai_client(agent_name=...)` or copy the displayed endpoint. The SDK-derived base URL ends in `/agents/<name>/endpoint/protocols/openai`; append `/responses?api-version=v1`. This is distinct from the REST API version and the container protocol version.

The pinned SDK's MCP result is normally a single text `Content` item, not a plain string. The runtime accepts that supported shape, parses the correlated execution object and rejects unsupported content. Worker instructions specify `trials[].trial_id/phase` and `safety_reports[].report_id` plus exact result schemas; workers do not guess the frozen file's layout. HTTP 200 alone is not a successful hosted workflow: require Responses `status: completed`, owned execution evidence and session binding.

The live long-limit probe exposed a separate **30-second managed gateway timeout**: the Sandbox correctly timed out at 30 seconds and was deleted, but the gateway had already abandoned the HTTP response. The current execution operation waits at most 20 seconds, then returns declared HTTP 202 with only `run_id`, `state` and `pending`. Runtime code repeats the same bound operation to collect the original task's result; it does not start execution again. Continuations require the original validated service caller, exact ownership IDs and grant digest, expire within the execution lease, and are removed on cancellation or final delivery. At most 16 completed awaiting-delivery entries are retained in memory. Losing that ephemeral continuation is an explicit owned-inspection/reconciliation case, not permission to replay work.

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

Never delete by a broad group selector. Preserve the seed and old fixed A. Refresh the execution **app** with Stop/Start only after reconciliation, using its exact resource ID and the same lifecycle actions above; revision restart is unsupported. New authority rejects all old grants/IDs. Frontend boot keys invalidate old cookies. Log interruption, recovery and final inventory; do not call this durable restoration.

## Revert and ending state

Record the current/previous service digest, hosted version, Toolbox version, deployment/configuration and dataset version before any change. A revert is an operator action:

1. Stop submissions and cancel/reconcile all reactor tasks; confirm no matching live task remains.
2. Restore the recorded **known-good hosted image** as a new native version with the supported helper below, then wait for active readiness. Do not invent a version query parameter on the Responses URL. Set the managed Toolbox default to the recorded known-good version using its supported UI or `toolboxes.update(name, default_version=...)`.
3. Redeploy `infra\reactor.bicep` with the recorded service digest and the same dedicated audience/identity scope. Preserve ownership limitations: replica replacement loses ephemeral artifacts and invalidates old grants/cookies.
4. Verify one allowed Alice/Bob task, one denied foreign request and exact cleanup after rollback. Do not move `lab-ready-1`, reset the repository, or overwrite the old runtime.

```powershell
python -B .\scripts\setup-reactor-foundry.py hosted --project-endpoint $ProjectEndpoint `
  --name $HostedName --image $PreviousHostedImage --model $Model `
  --toolbox-endpoint $ToolboxEndpoint --operation $ToolboxOperation --new-version
```

Record `$PreviousHostedImage` separately from the previous version number. Versions that failed image pull, dispatch or schema checks are troubleshooting history, not known-good rollback candidates. The short-task baseline was hosted image v6/native version 5 and service image v7. The long-task repair uses hosted image v7/native version 6, service image v8 and Toolbox v3. Use the report's final verified digests as rollback references, not the broken intermediate builds.

No live revert has been performed. When ending a rehearsal, record remaining service/hosted versions and usage, stop idle hosted sessions through their supported management UI/API, and preserve allocation recovery resources. Microsoft-tenant registry grants do not prove cross-tenant Skillable delivery; verify that tenant's native image broker permissions or import the same immutable hosted manifest into an approved registry in its tenant.
