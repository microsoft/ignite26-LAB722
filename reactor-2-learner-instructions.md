# Reactor 2: observe a Sandbox-resident research swarm

## What you will experience

Ask Caldova a research question about a drug in a frozen public dataset. A Foundry-hosted orchestrator delegates to clinical-trials, drug-specialist and quality-assurance agents. Their agent loops run in on-demand ACA Sandboxes. ACA Express hosts the research frontend/API and the execution manager, **not the hosted orchestrator's reasoning process**.

This is an architect-led inspection lab, not an application-building exercise. Model inference is remote; the Sandbox contains the agent loop, tools and data, not model weights.

| Objective | By the end you can |
| --- | --- |
| R2-01 | Use the original research experience, inspect cited public records and explain independent quality checks and sample limitations. |
| R2-02 | Observe full specialist agents appear on demand, explain bounded concurrency, and verify their task compute disappears. |
| R2-03 | Manually inspect a preloaded agent and locate Express, Foundry and Toolbox in the automated request path. |
| R2-04 | Correlate runtime observations with a run and owner; demonstrate allowed Alice/Bob work and denied cross-customer access. |
| R2-05 | Distinguish retry from new work, reconcile cancellation, and explain execution and quality budgets. |

## Before starting

Use the separately prepared **`ig2026-lab-local2`** allocation. Entry point: `https://lab722-research-frontend-v4r2.gentlecoast-8af52160.westus3.azurecontainerapps.io`. Use only the supplied **`*-v4r2`** services and Sandbox group **`lab722-zfwqfjb6saetq-sandboxes-r2`**; earlier local2 stacks retain failed reviews and teaching resources. Do not reuse the earlier `ig2026-lab-local` application or its IDs. The facilitator supplies `data\reactor2-local2-learner-values.json` alongside this guide; it contains resource identifiers, not passwords.

You need a browser, Azure portal access to the supplied allocation, PowerShell 7.3 or newer, Azure CLI signed into the supplied subscription, and the prepared `aca` CLI. The facilitator supplies **both demo passwords privately**. They are not Azure passwords. Do not paste passwords, cookies, CSRF tokens, bearer tokens or run grants into notes.

Run from this repository's root:

```powershell
$v = Get-Content -LiteralPath '.\data\reactor2-local2-learner-values.json' -Raw | ConvertFrom-Json
$native = @('--subscription', $v.SubscriptionId, '--resource-group', $v.ResourceGroupName,
    '--region', $v.Region, '--group', $v.SandboxGroupName, '-o', 'json')
az account show --query '{subscription:id,state:state}' -o json
$v | Select-Object ResourceGroupName,FrontendUrl,FoundryAccountName,SandboxGroupName
```

The subscription must match `SubscriptionId`, and its state must be `Enabled`. Open `FrontendUrl`. Stop and ask the facilitator if values, passwords, permissions or the prepared CLI are missing; granting yourself more access is not a learner step.

The allocation includes a retained teaching seed and snapshot. You will create one additional inspection Sandbox and retain it. Only request-owned task Sandboxes are automatically removed.

## 1. Locate the application and its tool boundary

**Goal:** identify where each part of a research request runs before sending one.

**Prediction:** the two Express apps should be separate from the Foundry-hosted orchestrator; the execution app should use different identities for its callers and its own Azure access.

In Azure portal, open resource group `ig2026-lab-local2`. Locate `lab722-research-frontend-v4r2`, `lab722-research-execution-v4r2`, Express environment `lab722-zfwqfjb6saetq-express`, the supplied Foundry account and Sandbox group.

For each Container App, open **Identity -> User assigned** and open its attached managed-identity resource:

| Inspect | Expected comparison |
| --- | --- |
| Frontend attached resource | `lab722-research-frontend-v4r2-mi`; its **Object (principal) ID** equals `FrontendObjectId`. |
| Execution attached resource | `lab722-research-execution-v4r2-mi`; its **Object (principal) ID** equals `ExecutionObjectId`. |
| Each app's `AZURE_CLIENT_ID` environment variable | Equals that attached identity's **Client ID**, not its Object ID. |
| Execution `FRONTEND_OBJECT_ID` | Equals supplied `FrontendObjectId`: the frontend service permitted to call the user-facing execution API. |
| Execution `PROJECT_OBJECT_ID` | Equals supplied `ProjectObjectId`: the Foundry project service permitted to call specialist operations. |
| Execution `EXECUTION_API_AUDIENCE` | Equals supplied `ExecutionApiAudience`: the intended API identifier for service tokens. |

Inspect only these non-secret variables. Do not open app secrets or change identities.

If the portal does not expose those app/identity fields, this read-only fallback selects only the required non-secret values:

```powershell
foreach ($appName in @($v.FrontendName, $v.ExecutionName)) {
    az identity show --subscription $v.SubscriptionId --resource-group $v.ResourceGroupName `
        --name "$appName-mi" --query '{resource:name,objectId:principalId,clientId:clientId}' -o json
    $appId = "/subscriptions/$($v.SubscriptionId)/resourceGroups/$($v.ResourceGroupName)/providers/Microsoft.App/containerApps/$appName"
    $variables = az rest --method get --url "https://management.azure.com${appId}?api-version=2026-03-02-preview" `
        --query 'properties.template.containers[0].env' -o json | ConvertFrom-Json
    $variables | Where-Object { $_.name -in @('AZURE_CLIENT_ID', 'FRONTEND_OBJECT_ID',
        'PROJECT_OBJECT_ID', 'EXECUTION_API_AUDIENCE') } |
        Select-Object name,value | ConvertTo-Json
}
```

Open the supplied Foundry account and project `reactor`. Under **Manage -> Project details -> Connected resources**, locate `reactor-swarm-execution-v4r2`. **Project Managed Identity** is its authentication method, not a separate navigation page. Its target is `ExecutionUrl`; its audience is `ExecutionApiAudience`, an `api://...` API identifier, not a user name or the frontend address.

If that portal view does not display target/audience, use the following read-only management request:

```powershell
az rest --method get --url "https://management.azure.com$($v.ExecutionConnectionId)?api-version=2025-06-01" `
    --query 'properties.{authentication:authType,target:target,audience:audience}' -o json
```

Inspect `data\reactor2-local2-toolbox-discovery.json`. In each specialist's `name` and `inputSchema.required`, find:

| Toolbox-advertised name | HTTP operation | Required arguments |
| --- | --- | --- |
| `reactor___clinical_trials` | `clinical_trials` | `body`, `X-Reactor-Run-Grant` |
| `reactor___drug_specialist` | `drug_specialist` | `body`, `X-Reactor-Run-Grant` |
| `reactor___quality_assurance` | `quality_assurance` | `body`, `X-Reactor-Run-Grant` |

The prefix is the managed Toolbox's advertised naming convention. These are capabilities reaching the execution manager, not three extra public agent servers. The legacy `reactor___reactor_execute` can also be present. The backend supplies the grant; learners do not obtain or edit it.

**Feedback:** attached identities, allowed caller IDs, connection target and audience agree with the supplied values. Discovery shows both required arguments, not just plausible tool names.

**Explain (R2-03):** when the orchestrator selects the clinical tool, which component creates the Sandbox, and where does the specialist agent loop run?

## 2. Slow-walk the preloaded agent

**Goal:** see what the application will launch without writing or deploying an agent.

**Prediction:** the custom disk contains three role definitions, local data tools and immutable public inputs, but no usable Azure/model credentials.

Create an inspection Sandbox from the supplied custom disk. This command is intentionally visible; it is not a provisioning helper.

```powershell
$inspectionLabel = [guid]::NewGuid().ToString('N')
aca sandbox create --disk-id $v.AgentDiskId --cpu 2000m --memory 4Gi --disk-size 40Gi `
    --label lab=LAB722 --label purpose=reactor2-learner-inspection `
    --label "inspection=$inspectionLabel" `
    --egress-default Deny --traffic-inspection Full @native | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'Inspection creation failed; inspect the operation before retrying.' }
$inspection = aca sandbox get --selector "lab=LAB722,purpose=reactor2-learner-inspection,inspection=$inspectionLabel" @native | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Inspection lookup failed; reconcile this label without repeating creation.' }
$inspectionId = $inspection.id
aca sandbox get --id $inspectionId @native
aca sandbox exec --id $inspectionId -c 'ls -l /opt/lab722-agent/src/reactor /opt/lab722-data' @native
aca sandbox exec --id $inspectionId -c 'sed -n "1,260p" /opt/lab722-agent/src/reactor/agent_runtime.py' @native
aca sandbox exec --id $inspectionId -c 'sha256sum /opt/lab722-data/source-records.json /opt/lab722-data/data-manifest.json /opt/lab722-data/caldova-research.duckdb' @native
```

Record the ID before proceeding. In the returned Sandbox, inspect `sourcesRef.diskImage.id`, `credentialRefs`, `volumes` and its network policy. The disk ID must match `AgentDiskId`; credential and attached-volume lists must be empty. The default egress policy is Deny and traffic inspection is Full.

In the displayed Python, locate `VERSION`, `ROLES`, `tools_for` and the model/tool loop. Find `query_trials`, `query_safety_reports`, `inspect_specialist_results`, `run_python` and `finish`; not every role has every tool. Protocol version is `research-agent-v4`. Creation can print progress before JSON, so the separate exact-label lookup above is intentional; never create a second Sandbox just because progress could not be parsed.

| File | Expected SHA-256 |
| --- | --- |
| `source-records.json` | `5c31dcd20478c1644b50eff7a7286b9c568094dd1e26427843afd23fc9dfe57c` |
| `data-manifest.json` | `99810e57a77cd3bc8b107287037e54fb2521795a96ec71d431fd585c03289f91` |
| `caldova-research.duckdb` | `f12f3e239f7b439b5c4fde1b405bd4e2346fa49fba79b1c1b198f42874ef9559` |

**Feedback:** you can point to preloaded source and pinned data. Do not launch `agent_runtime` manually: the prepared teaching Sandbox has no execution-manager model relay attached. In the automated path the agent writes a request, the manager calls the remote model using its managed identity, and returns the response. Generated Python runs under a restricted child process rather than inheriting that identity.

The manager starts the resident agent once, then uses short native calls to poll its model requests and final result file. A retried launch cannot start a second agent in that Sandbox. Long model waits therefore do not require a single long-lived interactive `exec` connection.

Retain this Sandbox. It is not part of the task-cleanup inventory in the next step.

## 3. Ask a research question and observe the swarm

**Goal:** connect the research answer to actual ephemeral compute and independently checked public records.

**Prediction:** clinical and drug agents can run together; QA follows their results. Three logical roles do not mean three simultaneous Sandboxes.

Under **Demo application account**, enter **alice** in **Username**, enter the supplied password and select **Sign in**. Under **Research workspace**, choose **semaglutide** in **Research candidate / drug** and **Obesity** in **Trial condition**. Enter this in **Research question**:

> Show the selected frozen trials by phase and describe the recorded safety reactions. State sample limitations.

Select **Ask research**. Open **Inspect execution** and record **Run ID**. While it works, observe **On-demand agent swarm** and **Live role / Sandbox timeline**, including **Sandbox**, **Model calls** and **Tool calls** on the three role cards. Inspect actual native inventory:

```powershell
$runId = Read-Host 'Paste your research run ID'
aca sandbox list --selector "lab=LAB722,purpose=reactor-task,run=$runId" @native
```

Repeat the read-only list during work if necessary. Match each observed Sandbox ID and its role/run/user/customer/conversation labels to the application evidence. At most two task Sandboxes execute simultaneously; QA is staged after the specialists. A bounded correction may create another attempt.

An early `[]` can mean allocation has not happened yet or a role has just finished. It is not completion evidence until the run is terminal and the relevant creation/deletion events have been checked.

If the run becomes **failed**, inspect and record its rejected evidence and exact task inventory, then stop and contact the facilitator. Do not repeatedly submit new questions to obtain a pass. Cleanup can succeed while research is rejected; there are no accepted charts to inspect in that case.

After completion, inspect **Research answer**, **Trial evidence -> By phase / By status**, **Safety-report records -> Reported reaction terms**, and the source citations on each record. Inspect **Accepted result limitations** and **Data provenance and coverage**. These come from accepted analysis, not a replacement background catalog query. **Reload public catalog** only reloads metadata; it does not run agents. The frozen dataset is `caldova-public-lab-use-v2`: **168 trials and 38 safety reports overall**, not necessarily for your selected drug/condition.

The condition filter applies to trials. Safety reports are selected by drug, not trial condition. Reaction counts count each term once per report. A reported reaction is not proof of drug causation, incidence or a treatment recommendation. Read the application's source and coverage limitations.

The displayed snapshot label/provenance comes from the pinned `data-manifest.json`. Original `source-records.json` retains its historical `caldova-public-review-draft-v2` collection metadata; those bytes are not rewritten. The manifest records project-owner-selected lab use, not expert audit, clinical approval or blanket attendee-release approval. Those distinctions should remain visible in the source/coverage notes.

Under **Inspect execution**, select **Inspect owned run** and **Inspect evidence artifact**. The **Owned run / hosted response** and **Raw artifact / independent acceptance evidence** panels show the returned JSON. For a concise field selection and exact HTTP status in later exercises, open browser developer tools **Console** on the application page and run this read-only request, replacing the ID:

```javascript
const ownRun = await fetch('/api/runs/YOUR_RUN_ID').then(r => r.json());
console.log({run_id: ownRun.run_id, state: ownRun.state, cleaned: ownRun.cleaned,
  user_id: ownRun.user_id, customer_id: ownRun.customer_id,
  conversation_id: ownRun.conversation_id, agents: ownRun.swarm?.agents,
  events: ownRun.swarm?.events, artifacts: ownRun.artifacts});
```

GET returns the run fields directly. Locate the artifact with `name: "evidence"`; copy its `artifact_id` and fetch:

```javascript
const ownEvidence = await fetch('/api/runs/YOUR_RUN_ID/artifacts/YOUR_ARTIFACT_ID').then(r => r.json());
console.log({accepted: ownEvidence.accepted, assessments: ownEvidence.assessments,
  input_sha256: ownEvidence.input_sha256, service_caller: ownEvidence.service_caller,
  agents: ownEvidence.agents.map(a => ({role: a.role, ownership: a.ownership,
    model_calls: a.model_calls, tool_calls: a.tool_calls, cleanup: a.cleanup})),
  qa: ownEvidence.qa});
```

Expected: completed run, `accepted: true`, passing independent assessments, matching input hash, three roles with real model/tool iterations and cleanup receipts. The service caller's object ID matches `ProjectObjectId`. Owner fields match Alice; do not confuse a service caller with an end-user token.

Run the exact native list again after completion. It must return **`[]`**. If you missed the live resources, retained creation/deletion events explain what was reported, but do not claim you personally observed their appearance. The teaching Sandbox should still exist.

**Feedback:** useful cited research, correlated agent activity, accepted evidence and an empty task inventory agree. A successful program, a QA model saying “pass,” or `cleaned: true` alone is insufficient.

**Explain (R2-01):** if a program exits successfully but its phase count is one too high, what evidence should cause rejection rather than acceptance?

**Explain (R2-02):** why can an empty task inventory and a still-visible research result both be correct?

## 4. Demonstrate customer separation

**Goal:** show separation continues beyond the frontend into execution and retained results.

**Prediction:** Bob can complete his own research but cannot read or cancel Alice's run.

Keep Alice in the normal browser session. Use a separate InPrivate/incognito browser session for **bob**; two ordinary tabs share login cookies and are not independent users. Use **Demo application account -> Sign in** there and perform the same research as Bob, allowing Alice's run to finish first. Bob's successful receipt must show `user-bob` and `customer-bob`, with a different run/conversation and owned Sandbox IDs. Use the Console requests below for these probes: the UI's own denial handler clears its local account display, so a UI-button denial requires signing in again before another probe.

In Bob's Console, use Alice's non-secret run, conversation and evidence-artifact IDs:

```javascript
console.log('foreign run', (await fetch('/api/runs/ALICE_RUN_ID')).status);
console.log('foreign evidence', (await fetch('/api/runs/ALICE_RUN_ID/artifacts/ALICE_ARTIFACT_ID')).status);
console.log('foreign conversation', (await fetch('/api/runs/ALICE_RUN_ID/conversations/ALICE_CONVERSATION_ID')).status);
const bobSession = await fetch('/api/session').then(r => r.json());
console.log('foreign cancel', (await fetch('/api/runs/ALICE_RUN_ID/cancel', {
  method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': bobSession.csrf},
  body: '{}'
})).status);
```

Expected: **403** on all four attempts. Do not print `bobSession` or its CSRF token. Check Alice's own receipt again: denial did not alter her result. Check Bob's own completed run still succeeds.

These are two authenticated demo users/customers, **not two Entra tenants**. Ownership is application-asserted and bound by backend-issued grants; backend calls use real service authentication. Toolbox is a managed boundary, not automatic customer isolation. The artifact denial covers the exposed retained result/working evidence; there is no separate browser endpoint for reading arbitrary Sandbox working files.

**Explain (R2-04):** why would an owner dropdown or a correctly authenticated Toolbox service be insufficient without run/owner authorization?

## 5. Observe cancellation, reuse and budgets

**Goal:** distinguish safe recovery from accidentally launching duplicate work.

**Prediction:** a repeated submission key returns the same run; cancellation fences later writes and removes owned task compute.

For a transparent retry demonstration, use Alice's Console. This makes one new research request and keeps its exact body in memory:

```javascript
const retrySession = await fetch('/api/session').then(r => r.json());
const retryBody = {task: 'research', candidate_id: 'semaglutide', condition: 'obesity',
  question: 'Summarize the selected frozen trials and safety reactions, with sample limitations.',
  idempotency_key: 'learner-retry-' + crypto.randomUUID()};
const sendSame = () => fetch('/api/runs', {method: 'POST',
  headers: {'Content-Type': 'application/json', 'X-CSRF-Token': retrySession.csrf},
  body: JSON.stringify(retryBody)}).then(r => r.json());
const firstSubmission = await sendSame();
const repeatedSubmission = await sendSame();
console.log({first: firstSubmission.run.run_id, repeated: repeatedSubmission.run.run_id,
  reused: repeatedSubmission.reused});
```

The IDs must agree and `reused` must be true. This is not a new answer or a restart. Inspect that exact run's progress, then cancel while it is running:

```javascript
const cancellation = await fetch('/api/runs/' + firstSubmission.run.run_id + '/cancel', {
  method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': retrySession.csrf},
  body: '{}'
});
console.log({status: cancellation.status, result: await cancellation.json()});
```

Expected: HTTP 200, `state: "cancelled"`, `cleaned: true`; verify `[]` with the native selector for this run. In the UI, **Cancel current run** and **Inspect execution -> Cancel and reconcile owned run** perform this owned cancellation. **New request key** creates a new key; changing the drug/condition also changes the key and clears displayed results but does not cancel existing server work. If it completed before cancellation, record that timing and use one explicitly new key for a cancellation observation; do not call an already-completed run an observed interruption.

Limits: at most two active task Sandboxes, one active research run per demo owner, 12 model turns and 180 seconds per specialist, one QA correction attempt. Model HTTP 429 responses receive at most two logged retries within that same remaining wall-time budget; they do not authorize a new agent run. Generated Python additionally has a 30-second wall limit, 15-second CPU limit and 256 MiB memory limit. These are different budgets. Limits and deterministic wrong-result rejection are also covered by offline implementation checks; this normal research question does not deliberately exhaust all limits or force QA rejection.

**Explain (R2-05):** after canceling a failed run and confirming no owned task resources remain, should new work use its old key or a new key, and why?

## Recovery and ending state

If the app reports **Hosted orchestrator not connected**, do not edit `hosted_configured`: it is derived when the frontend starts. Ask the facilitator to compare the frontend's `HOSTED_RESPONSES_ENDPOINT` with supplied `HostedEndpoint`, confirm the exact hosted version is active, save the endpoint including `?api-version=v1`, then **Stop/Start the frontend only**. Reload and check the running `/api/session` field without printing the complete session. Never restart the execution authority to repair a frontend flag.

For a failed or stalled research request, record its ID and first visible failure, inspect owned status, cancel/reconcile that exact run, and verify empty native task inventory before submitting with a new key. Do not silently switch credentials, add model roles or submit repeatedly after an uncertain response.

At the end, retain completed owned evidence, the supplied seed/snapshot and your recorded inspection Sandbox. Confirm each completed/cancelled task selector is empty. Sign out of Alice and Bob and clear Console variables by closing those app tabs. Do not delete the resource group or retained teaching resources.

Record steps as **passed as documented / documented recovery / undocumented repair / blocked / not run**. Note what you actually saw versus what a receipt reported. Human comprehension and pacing are still to be measured in a representative walkthrough.
