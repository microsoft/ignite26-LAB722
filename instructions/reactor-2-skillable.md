# LAB722: Operate secure, multi-tenant agentic apps on Azure Container Apps

## Operate a Sandbox-resident research swarm

In this lab you will ask the Caldova application a question about a drug in a frozen public dataset. Watch a Foundry-hosted orchestrator delegate to clinical-trials, drug-specialist and quality-assurance agents running in on-demand ACA Sandboxes. Use the portals to inspect the application tier, agent compute, ownership and cleanup. We will focus on architecture and operations, not an application-building.

| Objective | By the end you can |
| --- | --- |
| 01 | Use the research application, inspect outcomes and explain its checks and limitations. |
| 02 | Observe full specialist agents appear on demand, explain concurrency and independently verify task compute disappears. |
| 03 | Inspect a preloaded agent and locate Express, Foundry and Toolbox in the automated request path. |
| 04 | Correlate a run with its owner and demonstrate allowed Alice/Bob work and denied cross-customer access. |
| 05 | Distinguish reuse from new work, reconcile cancellation and explain execution and quality budgets. |

Use the same sequence in a guided session or at your own pace. No measured learner completion time or human comprehension result is implied.

===

# 1. Sign in to your allocated environment

Use the Windows VM and Azure allocation supplied by this lab. Do not use a personal Azure account, a previous lab's subscription or an `ig2026-lab-local2` environment.

The Windows password, Azure **Password**, Azure **TAP**, and Caldova demo passwords serve different purposes:

| Credential | Use |
| --- | --- |
| Windows VM username/password | Sign in to the supplied Windows desktop. |
| Allocated Azure username and **TAP** | Authenticate the Azure preparation session and portals with the lab's Temporary Access Pass. |
| Azure **Password** row | Not a substitute for the separately supplied **TAP** in this sequence. |
| Alice/Bob demo passwords | Sign in to Caldova after preparation. These are not Azure credentials. |

## 1.1 Run the delivered preparation

1. Sign in to Windows. In the lab client's **Resources** panel, locate the allocated Azure username, subscription ID and the separate **TAP** row.
2. Open **Reactor 2 - sign in and prepare** on the desktop.
3. Follow the displayed device-login instructions in the browser. Use the allocated Azure username and **TAP**, not your own account or the Azure Password row. Complete the normal sign-in prompts.
4. Confirm the selected subscription matches Resources. Allow preparation to finish. Do not launch another preparation while one is running.
5. Continue only after the terminal shows **REACTOR2_SKILLABLE_READY**, followed by the frontend URL.

Preparation uses your ordinary Azure CLI user session. It does not require saving a custom bearer token, a client secret or a Skillable secure-token variable. Ordinary sign-in caching still applies.

**Recovery for a password-only or wrong CLI session:** close or leave the failed preparation at its idle prompt. In PowerShell 7 run `az logout`, reopen the delivered preparation shortcut and authenticate with the allocated **TAP**. On the tested allocation, password-only sign-in succeeded but a subsequent Foundry connection write was rejected because MFA had not been satisfied; normal logout and TAP-backed sign-in resolved it. Do not weaken policy, grant yourself roles or repeatedly retry a denied write.

If preparation fails for another reason, retain the exact error and contact the facilitator. A configured endpoint is not proof of a working research run.

## 1.2 Inspect what preparation delivered

Open a separate PowerShell 7 terminal and keep it for the read-only checks:

```powershell
Set-Location 'C:\Lab\Reactor2'
$v = Get-Content -LiteralPath '.\learner-values.json' -Raw | ConvertFrom-Json
az account show --query '{subscription:id,state:state}' -o json
$v | Select-Object SubscriptionId,ResourceGroupName,Region,FrontendName,ExecutionName,
    FoundryAccountName,FoundryProjectName,SandboxGroupName,FrontendUrl
```

**Expected:** the selected subscription equals `SubscriptionId`, its state is `Enabled`, the resource group is **LAB722**, and the region is **westus3**. Names have an allocation-specific suffix; use your values, not another learner's screenshots.

The initial preparation shortcut is system-installed on the shared desktop. The final **Reactor 2 research app** shortcut is written to the current learner's desktop. Open that final shortcut, or copy `FrontendUrl` from your own values.

Preparation is not an unexplained infrastructure deployment:

| Mechanism | Inputs and changes | Independent check |
| --- | --- | --- |
| Skillable ARM deployment | Creates the allocated foundation, identities, Foundry model, Express environment and Sandbox group. | Resource inventory and deployment status in Azure portal. |
| Post-Build Lifecycle Action | Creates the allocation-owned execution API registration and service principal; applies eight child-resource-scoped role assignments. | Exact API metadata and principal/scope/role comparison; facilitator check below. |
| First Displayable Lifecycle Action | Installs the digest-pinned preparation source and initial shortcut on the existing VM. | Inspect `C:\Lab\Reactor2\scripts` and the delivered shortcut. |
| `run-reactor-skillable-vm.ps1` and `initialize-reactor-skillable.ps1` | Use the allocated user session and foundation outputs; restore declared Python dependencies, prepare image/seed/snapshot, mirror the hosted image to the allocated registry, configure services, Foundry connections and Toolbox, and wait for hosted readiness. | Actual portal resources, exact hosted version and a real accepted run; not just `HostedConnected`. |
| Final handoff | Writes `learner-values.json`, the learner-desktop URL shortcut and random DPAPI-protected Alice/Bob demo credentials. | Read your values and use the normal application sign-in. |
| Tearing Down Lifecycle Action | Removes the exact allocation-owned execution API registration/service principal. | Allocation lifecycle and scoped directory cleanup; not a learner delete step. |

You can open those preparation scripts in a text editor. Do not edit them or rerun native creates just to inspect them.

===

# 2. Locate the application and its tool boundary

**Goal:** identify where the request runs before sending one.

**Predict:** should the three specialist roles already occupy three running task Sandboxes?

## 2.1 Explore Express first

1. Open **[Azure Container Apps portal](https://containerapps.azure.com)**. Sign in with the allocated Azure user using TAP-backed authentication.
2. Select your allocated subscription and **LAB722**.
3. Open the environment containing `FrontendName` and `ExecutionName`. Open each app's **Live Overview**.
4. Confirm both apps are **Running / Ready for traffic** and **Environment mode** is **Express**.
5. Compare their immutable image digests with `ServiceImage`. The shared image runs different application entry points; it is not the preloaded specialist image.
6. On **Identity**, inspect only the attached managed identities. Compare their object/principal IDs with `FrontendObjectId` and `ExecutionObjectId` in your values.

If the portal does not display an identity comparison, this read-only fallback selects only the non-secret fields:

```powershell
foreach ($appName in @($v.FrontendName, $v.ExecutionName)) {
    az identity show --subscription $v.SubscriptionId --resource-group $v.ResourceGroupName `
        --name "$appName-mi" --query '{name:name,objectId:principalId,clientId:clientId}' -o json
}
```

## 2.2 Locate Foundry and Toolbox

In Azure portal, open your allocated Foundry account, then project **reactor**. Locate the hosted agent named by `HostedName`, its exact `HostedVersion`, and the **runtime-research** Toolbox. A registered agent version must actually be active; an existing name is insufficient.

Under the project's connected resources, find **reactor-swarm-execution**. Its authentication is **Project Managed Identity**. Compare its target and audience with `ExecutionUrl` and `ExecutionApiAudience`.

If those connection fields are not exposed in the portal:

```powershell
az rest --method get `
    --url "https://management.azure.com$($v.ExecutionConnectionId)?api-version=2025-06-01" `
    --query 'properties.{authentication:authType,target:target,audience:audience}' -o json
```

The managed Toolbox advertises `reactor___clinical_trials`, `reactor___drug_specialist` and `reactor___quality_assurance`. Each requires a request body and **X-Reactor-Run-Grant**. The backend supplies that grant; do not obtain, copy or edit it. These are tools reaching the execution manager, not three permanently running public agent servers.

For an exact read-only check when the Foundry portal does not expose these fields:

```powershell
& .\.venv\Scripts\python.exe .\scripts\wait-reactor-hosted.py `
    --project-endpoint $v.ProjectEndpoint --name $v.HostedName `
    --version $v.HostedVersion --timeout 30
if ($LASTEXITCODE -ne 0) { throw 'Exact hosted version readiness was not verified.' }
$toolboxText = & .\.venv\Scripts\python.exe .\scripts\inspect-reactor-toolbox.py `
    --endpoint $v.ToolboxEndpoint
if ($LASTEXITCODE -ne 0) { throw 'Managed Toolbox discovery failed.' }
$toolbox = ($toolboxText -join "`n") | ConvertFrom-Json
$toolbox.tools | ForEach-Object {
    [pscustomobject]@{Name=$_.name; Required=($_.inputSchema.required -join ', ')}
} | Format-Table -Wrap
```

These two small scripts are readable under `scripts`: one calls the SDK's exact agent-version GET until active or timeout; the other authenticates normally and performs MCP initialization and `tools/list`. Neither creates a deployment or saves a bearer token. Expect the exact hosted version to be active and all three specialist names to require both arguments.

```text
Browser / application account
  -> Express frontend and API
  -> Foundry-hosted orchestrator
  -> Managed Toolbox + project-identity connection
  -> Express execution manager
  -> On-demand clinical / drug / QA Sandboxes
  -> Owned evidence and response
```

The frontend identity calls the user-facing execution API; the Foundry project identity calls specialist operations. The execution manager's identity accesses the allocated Sandbox group and model. Tokens for those Azure calls do not enter the task Sandbox.

**Feedback:** two Express apps, an active hosted orchestrator and a managed tool boundary are distinct resources. No research task has been submitted yet.

**Explain (R2-03):** which component creates the Sandbox when the orchestrator selects a specialist tool, and where does the specialist's agent loop run?

===

# 3. Inspect a preloaded agent manually

**Goal:** slow-walk the compute that the application will later create automatically.

## 3.1 Record the baseline

1. Open **[ACA Sandboxes portal](https://sandboxes.azure.com)** in the same allocated-user, TAP-backed browser session.
2. Select your subscription, **LAB722**, and `SandboxGroupName`.
3. On **Overview**, record the teaching Sandbox, custom image and snapshot. Compare their IDs with `SeedId`, `AgentDiskId` and `SnapshotId`.
4. Open **Sandboxes** and use **Refresh sandboxes**. The retained seed can be **Stopped** after its idle timeout. It is not a request-owned task.

Before any research, expect one retained teaching seed, one custom image and one teaching snapshot, with no `purpose: reactor-task` Sandboxes.

## 3.2 Create your inspection Sandbox

1. Return to **Overview** and choose **Create from custom image**.
2. Select the entry containing your `AgentDiskId`. The tested portal displayed **LAB722**, the disk UUID and a date, rather than a friendly image name.
3. Choose **L: 2 cores / 4 GiB / 40 GiB**. Set the name label to **reactor-manual-inspection**.
4. Expand **Advanced**, then **Network Egress Policy**. Select **Full** traffic inspection first, then default action **Deny**. The Deny option is not available under Partial inspection.
5. Leave ports, volumes and connectors unconfigured. Review those settings and submit **Create** once.
6. Wait for **Running**. Record this new Sandbox's exact ID separately from `SeedId`.

The manual Sandbox is for inspection only. Do not start a research agent or put Azure/model credentials into it.

## 3.3 Use the portal terminal

Open the Sandbox terminal and run these Linux commands there, not in Windows PowerShell:

```bash
head -45 /opt/lab722-agent/src/reactor/agent_runtime.py
ls -l /opt/lab722-data
sha256sum /opt/lab722-data/* /opt/lab722-agent/src/reactor/agent_runtime.py
```

Locate the three `ROLE_INSTRUCTIONS`, protocol **research-agent-v4**, the **12-turn** bound and **180-second** specialist wall-time bound. The code and data are preloaded; a Sandbox does not download the dataset or a model during the request.

| File | Expected SHA-256 |
| --- | --- |
| `source-records.json` | `5c31dcd20478c1644b50eff7a7286b9c568094dd1e26427843afd23fc9dfe57c` |
| `data-manifest.json` | `99810e57a77cd3bc8b107287037e54fb2521795a96ec71d431fd585c03289f91` |
| `caldova-research.duckdb` | `f12f3e239f7b439b5c4fde1b405bd4e2346fa49fba79b1c1b198f42874ef9559` |
| `agent_runtime.py` | `d820b713d186cbad244dacb90cd3778c7204895089821199af6ae96be1776e7b` |

The three data files should show read-only permissions, `-r--r--r--`. The role loop coordinates tools and remote model requests. Generated Python runs separately with a cleared environment, UID 65534, no-new-privileges and resource limits.

## 3.4 Remove only your manual Sandbox

Use **More actions -> Delete** on the exact ID you just recorded. Type the confirmation prefix displayed by the portal and submit Delete once.

Refresh the Sandbox list. Your inspection ID should be absent, while the teaching seed, image and snapshot remain. Do not delete the group or teaching resources. Do not repeat an uncertain create/delete; first inspect the actual resource list.

===

# 4. Ask a real research question

**Goal:** connect the research experience to actual ephemeral agent compute and accepted evidence.

## 4.1 Sign in to Caldova

Open the **Reactor 2 research app** desktop shortcut.

The demo credentials are encrypted for the Windows learner account in `C:\Lab\Reactor2\.build-contexts\demo-credentials.clixml`. To retrieve Alice's password privately in your own PowerShell window:

```powershell
$demo = Import-Clixml -LiteralPath '.\.build-contexts\demo-credentials.clixml'
$demo.alice.GetNetworkCredential().Password
```

Use username **alice** in the normal Caldova sign-in form. Do not include the password or this output in screenshots, notes or support messages.

**Expected:** **user-alice / customer-alice (application-asserted)**. Alice and Bob are application accounts, not separate Entra users or directories. The server selects customer ownership; the research question cannot change it.

## 4.2 Submit and observe

Keep the Sandbox portal open beside Caldova.

1. In Caldova select **semaglutide** and trial condition **Obesity**.
2. Ask: **For semaglutide, show obesity trials by phase and summarize report mentions in this frozen sample. Cite the selected source IDs and explain the coverage limitations.**
3. Click **Ask research** once.
4. Expand **Inspect execution** and record the run ID, conversation ID and idempotency key. These are correlation values, not permission to access another customer's result.
5. Immediately use **Refresh sandboxes** in the Sandbox portal. Inspect the new task rows and their **+ more** label descriptions. Refresh again as the work progresses.
6. Compare **run**, **user**, **customer**, **conversation**, **step**, and **purpose: reactor-task** with the application's timeline.

**Predict:** three roles do not mean three simultaneous task Sandboxes. Clinical and drug specialists may run concurrently, with at most two task Sandboxes active. QA is staged after their results.

The application timeline should show actual `sandbox_created`, `model_requested`, `tool_selected`, `model_completed`, validation and deletion events. Counts and durations vary. A failed Python proposal can be corrected within the bounded agent loop; process completion alone is not answer acceptance.

## 4.3 Inspect accepted evidence

Continue only when the owned run is completed and its evidence is **accepted**, all three independent assessments pass, and QA has no outstanding issues.

For this exact selection, expect:

| Evidence | Expected |
| --- | --- |
| Trial records | **30** |
| Phase counts | PHASE1 **8**, PHASE2 **4**, PHASE3 **15**, PHASE4 **3** |
| Safety-report records mentioning semaglutide | **21** |
| QA | Passed, no issues; exact selected trial/report IDs |
| Provenance | `caldova-public-lab-use-v2`; the same three frozen-file hashes |

Inspect the phase/status charts, reaction-term chart, source IDs and original-source links. In **Inspect execution**, enter the evidence artifact ID listed by the owned run and select **Inspect evidence artifact**. Compare agent ownership, source hashes, model/tool counts and execution receipts with the timeline.

The full frozen sample contains **168 trials and 38 reports**. The trial condition filters trials only; safety reports cover mentions of the selected drug across the frozen sample. Report mentions are not incidence rates, proof of causality or a comparative safety assessment. A live source link does not turn frozen record values into current evidence. This lab provides no treatment recommendations.

Use **Refresh sandboxes** after completion. The task IDs from the timeline must be absent; the teaching seed/image/snapshot remain. A JSON `cleaned: true` field is not an independent deletion check.

**Explain (R2-01):** what evidence distinguishes a plausible generated summary from an accepted answer, and why can the reaction chart not establish a drug's incidence rate?

**Explain (R2-02):** which observations show compute was created on demand and disappeared afterward, rather than simply being hidden by the application?

===

# 5. Compare ownership, reuse and cancellation

## 5.1 Allowed work and denied cross-customer access

1. Keep Alice signed in. Record her accepted run, artifact and conversation IDs.
2. Open a separate browser profile or private window, not merely a second tab sharing Alice's cookies.
3. Retrieve `$demo.bob.GetNetworkCredential().Password` privately and sign in as **bob**. Confirm **user-bob / customer-bob**.
4. In Bob's **Inspect execution**, enter Alice's run ID and choose **Inspect owned run**. Expect **403 Forbidden**, shown as **Access denied**, not Alice's result. The UI clears the current account and owned results after a denial. Sign in again before the next check; a page reload is not required.
5. Re-enter Alice's run ID and evidence artifact ID, then choose **Inspect evidence artifact**. Expect denial. Do not repeatedly submit a denied operation.
6. Start Bob's own research with semaglutide/Obesity. Confirm an accepted result and Bob-owned labels in the Sandbox portal.
7. Return to Alice and try Bob's run/evidence IDs. Expect denial while Bob's own allowed result remains accessible.

The private run, evidence, conversation and cancellation APIs enforce owner checks. Correlation IDs and an application dropdown would not themselves provide isolation. The frozen public inputs can be shared while private execution and results remain owner-scoped.

**Explain (R2-04):** which identity is application-asserted, which identities authenticate service calls, and which observed labels carry customer context into task compute?

## 5.2 Reuse is not re-execution

On an accepted owned request, keep the same selection, question and idempotency key. Select **Ask research** again.

**Expected:** `reused: true`, the same run ID and existing artifact. The timeline must not gain a new set of agent executions, and the portal must not show new task Sandboxes for that run.

Choose **New request key** only when intentionally starting new work. Changing a key is not a repair for an unknown operation still in progress.

## 5.3 Cancel actual running work

1. Choose **New request key** and submit a separate request.
2. Wait until the application reports running work and the Sandbox portal shows one or two of that run's actual task Sandboxes.
3. Select **Cancel current run** once.
4. Inspect the owned run until it is **cancelled** and cleanup is acknowledged.
5. Independently refresh the portal. Those task IDs must disappear; the seed/image/snapshot remain.

If status or cancellation fails, use **Inspect owned run** to reconcile first. Do not assume a browser timeout stopped backend work, or submit another cancellation without checking the current result.

For a terminal failed run, inspect its retained rejected evidence and error before deciding on new work. Verify its task inventory is empty. Only then deliberately choose a new key. A later successful request does not erase the first failure. If QA or cleanup failures recur, stop and provide the facilitator with non-secret run IDs and exact errors.

Each specialist has a 12-turn/180-second bound. Generated Python has tighter execution limits. Model throttling uses bounded retries within the remaining budget; one QA correction round is allowed. These controls limit work, not guarantee success or answer quality.

**Explain (R2-05):** how would you distinguish safe same-key reuse, an intentionally new request and an incomplete cancellation?

===

# 6. Finish and verify

Sign out of Alice and Bob after completing the comparisons. Do not capture or save an authenticated VM image.

In the Sandbox portal refresh the list and confirm **zero `purpose: reactor-task` Sandboxes**. Only the retained teaching seed, custom image and snapshot should remain, unless the facilitator has explicitly assigned another exercise.

If the portal is unavailable, this is a read-only native inventory check:

```powershell
$native = @('--subscription', $v.SubscriptionId, '--resource-group', $v.ResourceGroupName,
    '--region', $v.Region, '--group', $v.SandboxGroupName, '-o', 'json')
aca sandbox list @native --selector 'lab=LAB722,purpose=reactor-task'
if ($LASTEXITCODE -ne 0) { throw 'Task inventory could not be verified.' }
```

**Expected:** `[]`. A failed read is not an empty inventory.

Your final explanation should connect: research question, Express application tier, Foundry-hosted orchestration, managed Toolbox, propagated customer context, bounded Sandbox agents, independent evidence and independently observed cleanup.

## Facilitator: scoped permissions check

Eight additional role assignments are supplied by the allocation's Post-Build Lifecycle Action, not by attendee commands:

| Principal | Resource scopes |
| --- | --- |
| Allocated learner | Foundry project data access; Sandbox group data owner |
| Frontend managed identity | Foundry project data access |
| Execution managed identity | Sandbox group data owner; Foundry account/model data access |
| Foundry project managed identity | Foundry project data access; Foundry account/model data access; allocated registry AcrPull |

Read exact child-resource assignments with:

```powershell
$prefix = "/subscriptions/$($v.SubscriptionId)/resourceGroups/$($v.ResourceGroupName)/"
az role assignment list --all --query "[?starts_with(scope, '$prefix')]" -o json
if ($LASTEXITCODE -ne 0) { throw 'Scoped role assignments could not be read.' }
```

Compare all eight **principal ID / exact resource scope / role definition ID** triples against the successful foundation outputs and current learner. A count of eight alone is insufficient. The Foundry data-role GUID is `53ca6127-db72-4b80-b1b0-d745d6d5456d`; Sandbox group data owner is `c24cf47c-5077-412d-a19c-45202126392c`; AcrPull is `7f951dda-4ed3-4680-a7ca-43fe172d538d`.

Do not grant Owner, add temporary setup-principal access or modify the shared policy to obtain a pass. The harness's existing Contributor allocation is separate from these eight scoped assignments.
