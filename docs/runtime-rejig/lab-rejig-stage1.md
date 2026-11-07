# LAB722 runtime lab: Stage 1 design

November 5, 2026. Working from `lab-rejig-instructions.md` and the unchanged `lab-ready-1` baseline at `beff601de8c77be3e8a960029e3a7ce24d0dee26`.

Status: the initial maintainer service-path experiment passed. On November 6 the user approved implementation of the simplified runtime: remove learner sign-in and partner authorization, use bounded generated Python, implement the UI/API, deploy in the current test allocation and complete its learner rehearsal. The earlier two-tenant proposal below is historical and superseded; no partner accounts are needed.

## Approved single-allocation runtime

The current implementation lives in `ignite26-LAB722\src\runtime`. The browser uses a facilitator-provided access key, held only in tab memory. There is no learner identity, tenant selection, result-link API or cross-user authorization claim.

Foundry exposes `execute_python(run_id, code)` through a dedicated versioned Toolbox. The backend accepts only its active run ID, allows one tool execution and fixes the Sandbox from deployment settings. Each request creates a fresh conversation. The UI shows generated code, actual stdout/stderr, correlated execution status and optional chart rows. Edited-code execution is separately labelled as a direct Express-to-Sandbox action.

The root supervisor verifies the frozen bytes, drops supplementary groups and UID/GID, sets no-new-privileges, clears the child environment and applies time, memory, process/file and output bounds. It reaps detached UID-65534 processes after each serial execution. Analysis requires the Sandbox group identity to be disabled. The Express managed identity and four existing service grants remain separate.

The arbitrary-code decision eliminates phase-count-specific validation. The UI still checks chart display shape; the backend still checks receipt correlation and execution bounds. A zero exit code is not a claim that an answer is correct.

The published `lab-ready-1` baseline remains unchanged. Deployment and rehearsal evidence will be recorded in `lab-rejig-learner-instructions.md`; the historical sections below are not the current sign-in or tenant requirements.

## November 6 scoped preparation

The approved work now includes a clean public-data seed/snapshot, two verified execution clones, opt-in runtime infrastructure and an executable current-deployment guide in `lab-rejig-learner-instructions.md`. See `lab-rejig-identity-flow.md` for the separate sign-in handoff. This does not approve or implement the proposed replacement application below; `lab-ready-1` is unchanged.

At that earlier preparation stage the analysis decision was open. It is now resolved above in favor of bounded arbitrary Python, without a phase-count validator.

The preparation baseline strips Azure-injected identity variables from the non-root analysis child environment. It does not establish that platform identity endpoints are unreachable. The existing fixed maintainer proof has not been changed to that execution prefix or to accept generated code.

## 1. Scenario

Learners operate Caldova as a runtime analysis service. A user asks a bounded question about the frozen trial records. A Foundry agent selects a tool and generates analysis code. A trusted backend chooses the user's assigned Sandbox, runs the code there, and checks the result before displaying chart data and source identifiers.

The audience is IT professionals and SREs, not primarily application developers. Learners inspect and operate the Azure components. They do not implement query functions, run the old development controller, approve implementation plans, build candidate images, or review release-approval files.

Keep the existing lab title. The learning is whether the application can explain who requested an operation, which service identity executed it, which tenant owned its state, and which enforced boundary accepted or rejected the operation.

## 2. Proposed runtime and trust boundaries

```text
Learner's lab-issued identity
  -> Express-hosted Caldova UI/API validates sign-in
  -> trusted backend resolves the logical tenant and owns the conversation/run
  -> Foundry agent selects the analysis tool and generates code
  -> tenant-bound Foundry Toolbox connection authenticates to the MCP backend
  -> backend selects the assigned ACA Sandbox and enforces execution limits
  -> unprivileged code reads the frozen public dataset
  -> backend validates the result and ownership
  -> UI displays the answer and correlated execution evidence
```

The first application can cohost its trusted API and HTTP MCP endpoints in one Express app. These are trusted service code; generated analysis code runs only in the Sandbox. Keep one agent implementation and a small tool surface, not the three development specialists.

No tool argument can authorize a different tenant, conversation, Sandbox, subscription or resource group. The backend derives those bindings from authenticated state. Prompts and model-selected IDs are not permission checks.

For the first two-tenant implementation, prefer two fixed, tenant-scoped tool connections over a custom user-token broker. Each connection authenticates to a backend scope that can access only its assigned Sandbox. Select the corresponding agent/tool binding on the server, before inference. Do not expose both tenants' connections to one model invocation.

Use two saved agent configurations generated from the same implementation, one per fixed tenant/tool binding. They do not call each other or act as specialists. This avoids relying on client-side tool overrides: the documented `FoundryAgent` integration treats the saved tools as authoritative [5]. Verify the selected configuration and its exposed tools before inference. Do not create separate Foundry accounts, projects or model deployments for the two logical tenants.

This service-authentication design does not pass the learner's identity through Foundry. Record both the authenticated user and the executing service identity, and enforce conversation/result ownership in the API. A project managed identity by itself does not establish which learner owns a run.

| Hop | Actor authenticated in the maintainer proof | Tenant responsibility in the replacement |
|---|---|---|
| Caller -> app | Shared proof key; no learner sign-in. | Validate the learner's application session and resolve the owner/tenant on the server. |
| App -> Foundry | Runtime user-assigned managed identity. | Select the fixed tenant agent configuration and authorize conversation reuse. |
| Foundry -> Toolbox | Foundry project managed identity. | Expose only the selected tenant's tool binding. |
| Toolbox -> MCP backend | Stored connection key. | Authenticate one fixed tenant scope; do not accept a tenant claim from generated arguments. |
| Backend -> Sandbox | Runtime managed identity; code executes as UID 65534. | Backend fixes the target Sandbox; the cloud identity and OS execution identity are different. |

The proof runtime identity has group-wide Sandbox permission. That grant does not enforce application tenancy: trusted backend routing must still enforce the narrower tenant-to-Sandbox binding.

## 3. Pairing and sign-in

Each learner uses one existing lab-issued identity. Two learners represent two logical customer organizations. They share public trial data, but not conversations, execution state or results.

Keep the existing per-learner Azure allocation. For the paired exercise, choose one learner's application URL as the shared test endpoint. Both identities must be allowed to authenticate there and map to different logical tenants. The partner does not need Azure management access to the host learner's resource group.

Use two app-local tenant IDs, `tenant-a` and `tenant-b`. The host identity comes from trusted lab configuration; the partner supplies their principal ID from their authenticated app session. Only the authenticated host can bind that partner to the second prepared tenant. This is app-local authorization, not an Entra role, group or enterprise-app assignment. Never allow a chat message or an editable tenant selector to create that binding.

Neither the maintainer in the Microsoft directory nor learners in Skillable should need Entra administration rights. Use a lab-platform-supplied, preconfigured sign-in integration. Registration, consent, any required enterprise-app user assignments and disposable-URL configuration must be resolved before the learner timer. Do not ask learners to create applications, grant consent, administer groups or obtain extra Azure roles to pair.

Express does not support Easy Auth [1], so application code must validate the supplied sign-in integration's tokens or sessions. For Entra access tokens, validate signature, issuer, audience, expiry and the required scope, then map the verified principal to an app-local tenant [6]. Do not accept Azure management or Microsoft Graph tokens as tokens for the lab API. The harness's existing browser or Azure login is not automatically an app sign-in integration.

The supported integration has not yet been supplied or verified. Confirm one usable preconfigured path with the lab platform; do not build a new identity broker or choose a device-code flow that introduces registration/consent work for learners. If no path is available under the allowed permissions, record a delivery blocker and obtain an explicit scope decision rather than quietly replacing real sign-in with shared keys or simulated users.

The paired instructions must name the shared app URL and browser profile for each attempt:

1. Learner A signs in and creates a result; owner access succeeds.
2. Learner B signs into the same app with B's identity and opens A's non-secret result link/ID; access is denied.
3. Switch lab-app sessions in isolated browser profiles, with each account owner handling their own sign-in. Repeat the check and observe that access follows the authenticated identity.
4. Compare the tenant, acting principal and access decision. Do not exchange passwords, bearer tokens or execution capabilities.

Do not substitute a tenant dropdown, two tabs with the same identity, extra accounts per learner, or a mocked denial for this exercise. If the partner is unavailable, an instructor can be the second existing lab identity; otherwise record the paired check as not completed.

This tests the application's user-facing tenant boundary, not protection against the hosting resource group's Azure administrator. Keep that operator role distinct in the explanation.

## 4. The 75-minute learner outline

These are authoring targets, not measured completion times. Provisioning, image publication, directory preparation and dependency installation happen before the learner timer.

| Segment | Minutes | Main service | Learner action and visible evidence |
|---|---:|---|---|
| 1. Identify the caller and tenant | 7.5 | Other | Sign in, inspect the assigned tenant/principal and frozen dataset version, and identify a partner. |
| 2. Inspect the running application | 7.5 | Express | Find the app URL, runtime identity and backend settings. Follow the proposed execution path; distinguish user identity from service identity. |
| 3. Prepare isolated execution | 15 | Sandboxes | Use short, manual `aca.exe` commands to inspect the group, create tenant execution Sandboxes from the clean supplied baseline, and inspect their bindings and filesystem. |
| 4. Follow a real agent request | 15 | Foundry | Inspect the agent, selected tool and Toolbox connection. Ask for trial counts by phase. Inspect generated code, the remote execution receipt, validated chart data and source IDs. |
| 5. Find the enforced boundary | 12.5 | Sandboxes | Inspect separate writable state and read-only public data. Exercise allowed/denied network access and one bounded failure. Follow its request ID to the actual failure rather than relying on the agent's wording. |
| 6. Operate the Sandbox lifecycle | 10 | Sandboxes | Inspect and change the idle-suspend policy with `aca.exe`; observe state, perform an explicit supported stop/resume check, and inspect a subsequent run's evidence. |
| 7. Try the partner's result | 7.5 | Other | Run the owner-allowed/partner-denied check on the shared app, switch signed-in sessions, and explain which boundary enforced the decision. |
| Total | 75 | | |

This allocates 37.5 minutes to Sandboxes (50%), 7.5 to Express (10%), 15 to Foundry (20%) and 15 to identity/tenant operations (20%). Keep pairing setup within this budget; do not add a separate identity workshop.

## 5. Execution and evidence contract

The first question is "Group these frozen trial records by phase." Keep `caldova-public-lab-use-v2`: 168 trials and 38 safety reports. Do not expand or refresh it during the redesign.

Propose one MCP tool, `analyze_frozen_trials(run_id, code)`. The run ID must refer to a server-created pending request in the authenticated tool scope; it is a correlation key, not permission to choose a tenant or Sandbox. Generated code returns JSON containing `schema_version`, `phase_counts` and `source_ids`; the backend adds the pinned dataset version, execution evidence and validated chart data. This iteration validates the phase-count task, not arbitrary research answers.

The planned tool accepts bounded analysis code, not arbitrary Azure resource targets. The backend fixes the dataset, tenant/Sandbox binding, timeout and output limit. Proposed starting bounds are 30 seconds, 16 KiB of code and 128 KiB of combined stdout/stderr. Enforce the execution timeout inside the Sandbox as well as bounding the client wait. Start with one active execution per assigned Sandbox; define overload as an explicit busy response, not an unbounded queue.

Use a clean prepared public-data baseline when creating tenant Sandboxes. Never snapshot one tenant's active workspace to create another tenant's workspace. Azure credentials, connection keys and user tokens stay outside generated code and the analysis Sandbox.

Persist the server-owned owner/tenant association with conversation and result state. Prefer existing Foundry conversation metadata over adding a new Azure datastore, subject to verifying its read/update and result-link behavior. Restarts must not cause the API to guess ownership. The prototype's in-memory receipt dictionary is only test correlation, not an ownership store.

Validate a versioned result schema, dataset identity, referenced source IDs, actual remote exit status and output bounds. For the phase-count exercise, compare counts against the pinned source records. Reject malformed, fabricated or mismatched output instead of repairing it into a successful response.

Reuse the bounded output readers and remote-exit checks in `ignite26-LAB722\src\orchestrator\sandbox.py` where practical. Separate runtime-neutral execution code from development-role contracts; do not make learners operate the old controller.

Use one compact execution view in the existing UI or terminal:

```text
Request/run ID | authenticated principal | logical tenant
Agent/tool | executing service identity | assigned Sandbox
Policy decision | exit status | validation outcome | elapsed time
```

Show generated code and the actual failure/result for the current tenant. The owner can inspect Azure operator logs separately; the application must not expose another tenant's prompts, results or credentials through its diagnostics.

## 6. Changes after approval

| Area | Required change | Keep out of this iteration |
|---|---|---|
| Application | Runtime chat/results UI, application sign-in, server-owned tenant/conversation/run bindings, authenticated HTTP MCP, bounded Sandbox execution, deterministic result checks and the compact evidence view. | Specialist development workflow, approval/controller segments, general-purpose tenant administration and a new monitoring dashboard. |
| Foundry data plane | One agent implementation, two fixed tenant-specific saved configurations, versioned Toolboxes and authenticated project connections. Pin the selected configuration and verify its tool surface. | New model deployments per logical tenant, multi-agent routing and unproven user-delegation plumbing. |
| Infrastructure | Express app deployment, user-assigned runtime identity, scoped Foundry/Sandbox/image-pull grants and supplied identity/tenant configuration. Retain the existing Foundry project/model, registry and Sandbox group pattern. | Separate Entra directories, new network topology and subscription-wide runtime grants. |
| Sandbox baseline | Pinned public data and analysis dependencies, clean seed/snapshot, separate tenant workspaces and bounded lifecycle/egress. | Credentials in the disk, cloning active tenant state and automatic resource deletion. |
| Delivery | Bicep as source of truth; generate the complete Skillable ARM template, including the app, identities, connections and scoped role grants. Configure agent/Toolbox data-plane objects through the same idempotent non-core automation on the `azd` and Skillable rails. | A second hand-maintained ARM definition, hidden core exercises and assumed harness identity substitutions. |

The proof uses four new service-scoped grants:

| Principal | Role | Scope |
|---|---|---|
| Runtime managed identity | Foundry User | Foundry project `caldova`. |
| Runtime managed identity | SandboxGroup Data Owner | Sandbox group `lab722-4fpje6f4ykpcg-sandboxes`. |
| Runtime managed identity | AcrPull | Registry `lab7224fpje6f4ykpcgacr`. |
| Foundry project managed identity | Foundry User | The same Foundry project, for Toolbox authentication. |

These are additional to the tagged baseline's maintainer grants, not grants to the paired users. Reuse existing provisioned identities and permissions where practical. Any unavoidable service grants must be automated by an approved lab-platform provisioning step and confirmed before delivery; learners must not assign them or obtain Owner rights to repair setup. The successful maintainer grants do not establish that Skillable permits the same provisioning. Directory sign-in configuration must likewise be supplied, not performed by learners.

## 7. Stage 1 evidence and remaining checks

Development resources are in ACAPMS, West US 3, resource group `ig2026-lab-testing`. `ig2026-lab-production` is reserved for final confirmation after approval.

| Check | Current evidence |
|---|---|
| Baseline infrastructure | ARM deployment `runtime-stage1-baseline-20261105` succeeded using the tagged Bicep; GPT-5.2 capacity 10 and Sandbox group capacity 4. |
| Runtime permissions | Separate proof runtime identity with resource/project-scoped grants; no learner credentials embedded in the proof image. |
| Dataset delivery | Exact manifest, source-record JSON and DuckDB bytes copied to the remote Sandbox and made read-only. |
| Execution identity and policy | The full request executed as UID 65534. Default-deny egress and 900-second idle suspension in Memory mode are configured; policy settings alone are not network enforcement tests. |
| Express -> Foundry -> Toolbox -> backend -> Sandbox | Passed with HTTP 200 and 6.57 seconds of server-measured elapsed time: saved agent version 1 invoked the authenticated tool, the Sandbox returned a fresh marker, and the answer contained that marker, dataset version and manifest hash. This was one warmed maintainer request, not a latency or class-capacity benchmark. |
| Frozen result validation | All three pinned hashes matched; dataset files had no write bits; 168 unique trial IDs; six phase counts summed to 168. The tool inspected source JSON and hashed the DuckDB file; it did not test a DuckDB query or model-generated analysis. |
| Lifecycle retention | The existing Sandbox reported `Stopped`; explicit resume succeeded and the request verified the original dataset bytes afterward. No replacement Sandbox was allocated. |
| Invalid input | The authenticated live MCP tool rejected a malformed run ID with `isError=true`, before execution. |
| Read-only data enforcement | A live UID 65534 process attempted an append-open on the manifest and received a permission denial; it did not alter the file. |
| Network enforcement | With default deny / Full inspection and one temporary `example.com` allow-rule, HTTPS HEAD returned 200 for `example.com` and 403 for `example.net`. After restoring the original deny-all policy, `example.com` also returned 403. The decision feed recorded both denied hosts. |
| Remote failure status | A deliberate trusted command exited 19; the remote wrapper and native CLI both reported 19. This was an operator probe, not the final generated-code error UI. |
| Rejection guards | Four unit tests passed against the deployed image in ACR run `ds3`, covering altered marker/hash/UID/source IDs, CLI failure, oversized stdout and client-timeout cleanup. The CLI subprocess was mocked; this does not prove hard remote termination. |
| Paired learner authentication | Not tested. Two active Skillable identities are unavailable; ask later. |
| Tenant-bound tool selection and cross-tenant result denial | Proposed above; not implemented or tested. |
| Fresh local and Skillable learner runs | Not tested. Complete after the approved implementation exists. |
| Production confirmation | Not started. |

The maintainer experiment is separate from the learner application and retained outside the repository in the session's `files\runtime-stage1-proof-20261105` directory. Do not call it a finished lab or a tenant-isolation proof.

The successful run is `1d576c7f-4ef4-443b-81cf-6444bae749a9`, retained in `maintainer-proof-result.json`. Its phase counts are `NA=2`, `PHASE1=45`, `PHASE2=23`, `PHASE2/PHASE3=1`, `PHASE3=76` and `PHASE4=21`.

Other retained evidence is in `mcp-invalid-argument-result.json`, `rejection-unit-results.json`, `sandbox-policy-proof.json` and `remote-exit-proof.json`. The network test restored and read back the original default-deny / Full-inspection policy; no test allow-rule remains.

The retained development resources are Express app `lab722-runtime-stage1`, Foundry account `lab722-4fpje6f4ykpcg-ai` / project `caldova`, Toolbox `runtime-stage1-proof` version 1, Sandbox group `lab722-4fpje6f4ykpcg-sandboxes`, Sandbox `2f9ffc13-be51-4763-96d9-0514727f0824`, registry `lab7224fpje6f4ykpcgacr` and runtime identity `lab722-runtime-proof-mi`. The proof uses one Sandbox in a group configured for four; it does not prove capacity for parallel classes.

The proof bounds are a 45-second client wait and a 128 KiB stdout check after capture. They are not a hard remote deadline or a streaming memory bound. Generated-code execution, durable ownership, per-tenant bindings and scale-out behavior remain replacement work. Do not promote this fixed-script prototype as that implementation.

The image-pull result applies to this development registry/deployment, not the Skillable image rail. Publish the replacement app and clean analysis baseline through the approved lab-image distribution path, then verify pulls in the actual Skillable environment.

One of the five planning questions has been used: access to the actual paired Skillable identities. The answer was that they are not available yet and to ask later. No substitute accounts or simulated tenant switch have been used.

Compatibility findings already observed:

- The authenticated Toolbox exposes one tool, `proof___inspect_frozen_dataset`; discovery returned HTTP 200.
- The first agent request reached the authenticated MCP tool, then failed because ACA CLI preview.4 requires `GLIBC_2.38`, which the existing Bookworm base does not provide. ACR build `ds2` passed with a pinned Python 3.13 Slim Trixie base and a build-time `aca --version` check. Its deployed image digest is `sha256:15bb3076da9ea844a3b7f2bb120108f025deb8a6107fd426d64320ff087eced6`. Use a compatible, pinned analysis-backend base if retaining the native CLI.
- Azure CLI's standard Container Apps log command failed for this Express app with `eventStreamEndpoint`. The native `aca.exe express logs --no-follow` command returned the actual application error.
- The installed Foundry connection extension could not discover ARM context in a project with no connections. Bootstrap the first connection through its ARM resource; do not require a manual portal connection as a hidden prerequisite. Keep its credentials in secure parameters, not generated public ARM output.
- The native Sandbox CLI can resume a stopped Sandbox when executing a command. Make that transition visible in the lifecycle exercise instead of assuming every request starts warm.

## 8. Approval and acceptance

Before approving implementation, confirm a preconfigured sign-in path and service provisioning that work within the maintainer's and learners' existing permissions. Verify that the same app can recognize two real lab identities without directory administration or learner role-assignment steps. Prove that each request receives only its tenant-bound tools; a prompt instruction is not enough.

After approval, implement on a separate branch without moving `lab-ready-1`. Validate both deployment rails, execute the revised exercises in `ig2026-lab-testing`, and use `ig2026-lab-production` for final confirmation. Measure a fresh human run before claiming the lab fits 75 minutes.

Before enabling generated-code execution, prove hard remote termination, bounded streaming capture, result-schema rejection and tenant-bound target selection. The fixed-script maintainer experiment does not satisfy those acceptance tests.

Keep the existing lab and its current instructions intact until the replacement passes those checks. Retain test resources unless cleanup is explicitly requested.

The post-experiment repository check still has HEAD and `lab-ready-1` at `beff601de8c77be3e8a960029e3a7ce24d0dee26`. The existing modified PDF and four untracked diagram/presentation artifacts were preserved. No replacement code, current learner-instruction edits, commit, push or production deployment were made in Stage 1.

## 9. Product references

Checked November 5, 2026. These document service capabilities; they are not evidence that the lab's own configuration works.

1. Express supported features and limitations: `https://learn.microsoft.com/en-us/azure/container-apps/express-overview`
2. Toolbox setup and versioned endpoints: `https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox`
3. Toolbox service versus user authentication: `https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/tool-authentication`
4. Remote MCP tool connections: `https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/model-context-protocol`
5. Saved-agent tool configuration: `https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/agent-services/foundry?pivots=programming-language-csharp`
6. API-owned token validation: `https://learn.microsoft.com/en-us/entra/identity-platform/access-tokens`
