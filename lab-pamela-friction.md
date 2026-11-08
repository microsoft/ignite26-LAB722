# Fresh allocation learner rehearsal

## Scope and timing

Requested November 7, 2026, 17:51:14 UTC-06:00. Target resource group:
`ig2026-lab-learner-2`, westus3. Baseline checkout: `lab-reactor`, `1981a84`.
This is a fresh allocation in the current Microsoft tenant, not an actual
Skillable tenant or VM. The signed-in operator has broader permissions than a
learner; only actions explicitly assigned to the learner count as learner work.
Facilitator actions are recorded separately.

Materials under test are the unchanged
`docs\runtime-rejig\lab-rejig-learner-instructions.md` and its linked facilitator
and identity guides. No implementation repair or guide correction will be
silently incorporated into this rehearsal. Checkpoints are classified as
passed as documented, documented recovery, undocumented repair, blocked or
not run. Tool execution time is not a measured human comprehension time.

**Latest outcome, November 7, 2026, 21:57:23 UTC-06:00: recovered runtime;
live minimum L1-L5 technical exercises completed after recorded repairs.**
The additional project in the requested allocation served a genuinely new
learner hosted version. Allowed work, ownership denials, independent
acceptance, negative execution, active cancellation/recovery, budget
rejection and actual two-Sandbox capacity were observed. Final task
inventory is zero; seed and fixed A are unchanged. This supersedes the
historical readiness stops below, not their evidence.

**Not a clean first-pass verdict.** The original project remains failed,
two learner-encountered helper defects required repair, and the prescribed
portal image fields required a read-only ARM/CLI fallback. Genuine grant
swap/replay and successful-but-wrong evaluator coverage remain offline.
The operator rehearsal took **39 minutes 13 seconds** after preparation,
including interruptions and automation overhead. Plan **90-120 minutes
for a learner**, pending a representative human pacing test; neither a
75-minute completion nor cross-tenant Skillable delivery is established.

**First-attempt outcome: fresh foundation deployed, learner readiness blocked.** Native
versions 1-4 all failed image authentication. The strict learner path stops
at the preparation/readiness gate; the full L1-L5 learner walkthrough was
not performed in this second allocation. The first allocation's successful
rehearsal is not substituted for missing evidence here.

**November 7 follow-up outcome, 19:49:54 UTC-06:00: still blocked.**
Both exact images passed complete local pulls and independent anonymous
blob-hash verification. The latest native version, 12, still failed image
authentication after the bounded configuration/identity checks below.
The image contents and anonymous registry availability are verified; an
effective Foundry image-broker authorization path is not.

The learner guide's exact machine-verified starting and ending SHA-256 is
`E8A12778467C3F9DDDE160FC2A31BCB63724A70195A87BE507EC5C96732BBF15`.

## Preparation observations

| ID | Observation | Impact |
|---|---|---|
| P1 | Facilitator contract names only the first authorized resource group. The owner explicitly authorized `ig2026-lab-learner-2` for this test. | Use the new scope; never copy old allocation identity, API, endpoint or snapshot IDs as if newly provisioned. |
| P2 | Reactor deployment creates the two services but requires a prepared Foundry project/model, Express environment and clean Sandbox snapshot. Their fresh creation is not an end-to-end recipe in the reactor facilitator guide. | Preparation must use repository foundation tooling and a separately recorded operator snapshot preparation; this is not learner time. |
| P3 | Facilitator provisioning paragraphs still say preparation does not pre-create the learner agent, while the later corrected section explicitly pre-creates a starter logical agent/version for grants. | Follow the explicit later sequencing; record the contradiction rather than editing the guide during the test. |
| P4 | Native starter versions 1 and 2 failed with `ImageError`: registry authentication failed. The documented new project MI has a verified `AcrPull` assignment created at 17:56:12; the registry is legacy RBAC, anonymous pull enabled and ARM authentication enabled. An explicit unchanged-image retry after additional propagation time also failed. | Fresh hosted readiness is blocked despite the documented grant. Further operator investigation is preparation, not learner work or a passed checkpoint. Current official private-ACR documentation identifies the per-agent identity as the image-pull actor; that differs from the lab's project-MI-only recipe. Do not infer which actor succeeded merely from an eventual cached pull. |
| P5 | Foundry initially rejected Agents access after the Project Manager grant, then allowed the page after a full reload. Notifications still asked for Foundry User. No extra user role was assigned. | Permission/UI-cache propagation needs an explicit refresh and wait checkpoint. This test still uses inherited Owner and does not establish minimum Skillable RBAC. |
| P6 | The Foundry Agents table displayed version 1 as `Running` while version-specific native read-back reported versions 1 and 2 `failed`. | A list-row status is not a sufficient readiness check; inspect the exact version and its deployment error. |
| P7 | The Azure portal Containers blade opened, but its digest-pinned image selection was blank and the image-tag field said `Failed to fetch data`. The configured service digest was available through ARM/CLI, not reliably through the prescribed Image field. | Step 6's exact portal digest comparison needs a supported read-only fallback. Do not save the incomplete portal form. This was a preparation observation, not a completed learner checkpoint. |
| P8 | The generic foundation template creates an allocation-local ACR even though the reactor uses the approved shared `acateam` registry. | Fresh Skillable preparation still carries unrelated legacy foundation resources. The new local registry was not used for the reactor images. |
| P9 | The facilitator guide requires a full live ownership/gateway rehearsal before timing, but leaves the frontend unconnected until the learner creates an agent/version and hands off its endpoint. | The guide needs an explicit starter-agent gate plus reset-to-unconnected sequence, or an explicitly deferred gate. This second allocation never reached either live gate because image readiness failed first. |
| P10 | After successful Alice sign-in, the application status said `Operation completed; inspect the evidence` even though Run was disabled and no research task or evidence existed. | Login feedback can be mistaken for execution feedback. This is observed UI wording, not evidence of task completion. |

### Permission investigation, not a silent repair

The documented project MI grant was verified on the shared registry. Both
the project MI and native agent identity were checked as exact Entra service
principals; neither was confused with an identity client ID.

Current official ACR deployment guidance discusses the per-agent image-pull
identity, while the main hosted-deployment guidance also discusses the
project identity. This prompted one bounded **undocumented facilitator
experiment**: registry-scoped AcrPull for only the new agent identity.
Version 3 failed after that grant; version 4 failed after more than ten
minutes of propagation allowance. No working image pull was established,
and necessity of that extra grant was not proven. The exact experimental
assignment was removed afterward. No registry policy or original-allocation
grant was changed.

The same hosted manifest was independently confirmed to exist in ACR.
The first allocation still reported native version 6 active. No ACR connection
was present in either project's connection list; an absent registry
connection did not distinguish the allocations. The fresh failure remains
an unresolved hosted image-authentication blocker, not a demonstrated
application-code defect or a proven registry-identity root cause.

Official references reviewed during operator investigation, not added to
the learner's instructions:

```text
https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/deploy-hosted-agent-private-azure-container-registry
https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/deploy-hosted-agent
```

## Action and time ledger

Preparation started at the request time, 17:51:14 UTC-06:00. The first CLI
clock observation was 17:52:28. By roughly 18:04, the fresh foundation,
service API, clean snapshot, both Express services, UI-created connection,
Toolbox v1 and native starter v1 existed; hosted readiness had failed.

| Phase | CLI actions actually taken | Portal actions actually taken | Result |
|---|---|---|---|
| Foundation | Check empty RG; `az group create`; deploy `infra\main.bicep` with environment `skillable-rehearsal-2`, default model capacity 40 | Open the new RG overview and new Foundry project | Separate account/project/model, Express environment and Sandbox group deployed |
| API/credentials | Operator Graph application/URI/service-principal sequence; fresh random demo credentials stored with DPAPI | None; no tenant directory UI change | New dedicated API verified; no client secret or demo Entra users |
| Snapshot | Remove only the new group's identity; verify no usable identity; run `prepare-worker-baseline.ps1 -Mode RuntimeSeed`; create a separate fixed reference from its snapshot; stop seed/reference | None | Fresh verified frozen-data snapshot; seed/reference retained |
| Services | Run the published `deploy-reactor.ps1` without hosted endpoint; check frontend UI/session readiness and execution `/health` | Open the new RG | Both final v8 services deployed; frontend submissions deliberately disabled |
| Tool connection | Read back target, auth and `properties.audience`; describe/register Toolbox v1 | Manage > Project details > Connected resources > Add connection > OpenAPI > Managed identity; supply dedicated audience and execution URL | Actual UI-created `ProjectManagedIdentity` connection verified |
| Hosted preparation | Grant project MI registry `AcrPull`; register starter v1; grant its runtime project Foundry User; verify failure; explicit `--new-version` retry v2 | Build > Agents; reload after permission-cache failure | Both native versions failed image authentication; preparation remains blocked |
| Bounded investigation | Verify ACR policy and exact principals; temporarily grant only the new runtime AcrPull; explicitly create versions 3 and 4; allow propagation; read exact failures; verify hosted manifest; remove that one experimental grant | Select agent/version; observe ImageError in Playground; inspect Containers through the new app resource | No recovery established; no learner or registry-policy workaround |
| Frontend access | Use local browser CDP only to enter protected supplied credentials into the normal sign-in fields and click Sign in; no API login shortcut | Open the actual frontend, sign in as Alice, observe application-asserted owner and disabled Run | Login worked; no endpoint key or submitted research task |
| Ending inspection | Exact new-group inventory and native session list; original native v6 read-back; unchanged-material hash and Git whitespace check | Leave the new resource/project available for inspection | Only new seed/reference retained, both Stopped; zero task Sandboxes or native sessions |

Important timestamp anchors, all local UTC-06:00 on November 7, 2026:

| Time | Observed milestone |
|---|---|
| 17:51:14 | Owner request; preparation clock starts |
| 17:52:28 | First CLI clock/tool/material-hash observation |
| 17:54:09 | Dedicated API verified |
| 17:56:12 | New project MI registry AcrPull assignment created |
| 17:58:43 | Fresh seed and fixed reference both stopped |
| 18:01:37 | Starter v1 creation time displayed by Foundry |
| 18:06 | Unchanged-image starter v2 retry displayed by Foundry |
| 18:09:42 | Experimental new-agent image grant created |
| 18:11:08 | Version 3 definitively failed |
| 18:20:20 | Final version 4 definitively failed after bounded propagation wait |
| 18:20:39 | Alice owner visible, Run disabled; learner material hash unchanged |

Time from request to final native failure: **29 minutes 6 seconds**.
This is operator preparation/diagnosis, including my probe errors and
propagation allowance. It is not learner duration or a normal successful
deployment benchmark. Ending verification completed at **18:28:51
UTC-06:00**, after **37 minutes 37 seconds** total elapsed preparation,
diagnosis, reporting and cleanup. No learner completion time was measured.

My preparation probes also made mistakes: assuming a missing group identity
must serialize as `type: None`, looking for audience under `credentials`
instead of `properties.audience`, requesting `/health` from the frontend,
and using incorrect SDK import/optional-field/return-shape assumptions.
These are operator harness overhead, not evidence of learner-guide defects.
The published frontend UI/session readiness alternative worked. No source
or learner guide was edited to repair these probes.

Passwords, bearer tokens, cookies, run grants and private policy metadata are
excluded from this file and screenshots.

## Learner checkpoint results

| Checkpoint | Classification | What was actually established |
|---|---|---|
| Supplied allocation/readiness gate | **Blocked** | Fresh scope, model, snapshot, services, API, tool and identities exist; native hosted readiness failed. The documented stop condition applies. |
| 1. Create hosted orchestrator | **Not run as learner** | Four creations were facilitator starter/recovery attempts, not learner creation. Source inspection and definition checks during preparation are not mislabeled learner completion. |
| 2. Identify/connect services | **Not run as full learner checkpoint** | Preparation established frontend sign-in and actual owner plus public service identities/endpoints; native connection handoff was deliberately not applied. |
| 3. Micro-transaction/correlation | **Not run** | Run remained disabled. No new owned result, receipt or live independent acceptance was created. |
| 4. Bob/Alice ownership | **Not run** | No completed task IDs existed to test foreign access. An Alice login alone does not establish isolation. |
| 5. Expand/constrain/interrupt/evaluate | **Not run** | No fresh live egress, limit, failure, cancellation or two-worker evidence. Offline fixtures were not substituted for the missing live exercise. |
| 6. Budget/version/ending state | **Not run as full learner checkpoint** | Operator ending inventory passed; learner concurrency/usage/revert comparisons did not run. Missing known-good references remain unavailable. |

The user requested strict consumption, so I did not fabricate a Responses
URL, connect a failed version, invoke an old allocation, extract a real run
grant, modify source, or silently replace UI steps with direct research API
calls. No completed human or automated learner time can be reported for
this blocked allocation.

## Learner duration estimate

**Planning estimate only: budget 90-120 minutes for a healthy, fully prepared
allocation**, with the stated basic Python/JSON/HTTP/identity prerequisites.
The following is task-analysis judgment from the unchanged written steps,
not a measurement of a completed fresh learner run:

| Written section | Estimated human minutes | Main effort |
|---|---|---|
| 1. Hosted starter, definition, new version and handoff | 12-18 | Read nested workflow/binding code; predict identities; CLI creation; inspect exact version; wait for facilitator configuration |
| 2. Two services and sign-in | 8-12 | Scope the correct RG, compare UAMIs/object IDs and configuration, inspect portal and sign in |
| 3. Micro-transaction and full provenance | 18-24 | Follow result/artifact IDs, verify code hash and frozen pins, compare all source IDs and receipts, inspect deletion, test idempotency |
| 4. Ownership | 14-18 | Save IDs, switch owners, allowed/foreign/prompt tests, browser console, offline fixture and anonymous HTTP check |
| 5. Expansion and failures | 22-28 | Multiple fresh-key tasks, inspect two-worker/egress/limit/exit/cancel evidence, reconcile and explain offline evaluator controls |
| 6. Budget and ending state | 12-16 | Timing-sensitive cross-user capacity test, multiple version/image views, unavailable usage, exact inventory and revert explanation |
| Sum, before short orientation overhead | 86-116 | This makes 75 minutes tight without simplifying or making parts optional |

The biggest likely learner-time drivers are the eight correlation comparisons
and complete source-ID lists, context switches between CLI/Azure portal/Foundry/
application/browser console, and the 30-second concurrency/cancellation
windows. These are anticipated friction from the written exercises, not
fresh live failures observed here.

**As currently blocked, there is no finite completion-time estimate.**
A strict learner should stop at readiness and ask the facilitator; the
image-authentication investigation must happen before class, outside the
learner timer. A healthy-allocation human pilot is still required to turn
the planning range into measured pacing.

## First-attempt ending state

New allocation:

| Item | Recorded value/state |
|---|---|
| RG / region | `ig2026-lab-learner-2` / `westus3` |
| Foundry account/project/model | `lab722-j6w5khemy6mqq-ai` / `caldova` / `gpt-5.2` |
| Express environment | `lab722-j6w5khemy6mqq-express` |
| Frontend | `lab722-reactor-frontend`; service v8; UI/login works, hosted endpoint unconfigured, Run disabled |
| Execution | `lab722-reactor-execution`; service v8; `/health` ready |
| Dedicated API audience | `api://8db9d983-3fb2-4a82-9012-4880a06edabd` |
| Project MI / native agent identity | `bd2a7d0e-dc1c-4834-a05e-42ad3be42583` / `5e6e12c0-d494-459b-97f9-7f2ad8c9de7d` |
| Native agent | `reactor-orchestrator`; versions 1-4 failed; no active-ready version or native sessions |
| Toolbox | `runtime-reactor` v1; advertised `reactor___reactor_execute` verified |
| Sandbox group | `lab722-j6w5khemy6mqq-sandboxes`; no usable group identity |
| Clean snapshot | `5d0842e7-badf-41f9-bf22-c006d150675d` |
| Protected seed | `5fd06a74-20fc-412a-b869-b4aa38933610`, Stopped |
| Protected fixed reference A | `52993c7d-c12c-41e2-ba20-3c4fed535e5e`, Stopped |
| Reactor task Sandboxes / native sessions | Zero / zero |

Both services use the final immutable digest
`sha256:48d6a42cd9d7bc87a551f2f05264fb8de6de0efef10bf3ec31e947ca96ff355a`.
The attempted hosted image is the verified existing digest
`sha256:2b3ef7ec815035dd5cbfe2c9905cbc5307efd46364bb2b149c91d6e2cb3cb289`.
Known-good previous native/Toolbox/service revert references for this new
allocation were not invented.

The original `ig2026-lab-learner` allocation was not redeployed or modified;
its native version 6 remained active. The branch, `lab-ready-1` tag, learner
guide and unrelated presentation files were not changed. No push or commit
was performed for this report.

The experimental new-runtime registry grant is verified absent. Public seed
descriptors were preserved in the private session artifact folder; the exact
temporary seed-output folder was removed. The new frontend was signed out
and deliberately left unconnected. The remaining action is to resolve the
fresh project's hosted image-authentication failure, pass the facilitator
live gate, then repeat the unchanged learner route with a running timer.

## Registry verification and repair follow-up

The owner authorized image verification, deployment repair and continuation
at **19:18:20 UTC-06:00 on November 7**. This follow-up is facilitator
diagnosis, not learner execution. The written learner material stayed unchanged.

### Image checks

- `acateam.azurecr.io` still has anonymous pulls and public access enabled,
  legacy registry RBAC, and ARM-token authentication enabled. No registry
  policy or admin credential was changed.
- `wslc pull` successfully downloaded both exact digest-pinned images.
  Independently, a standard-library client acquired only anonymous registry
  tokens, downloaded every config/layer, and verified all SHA-256 hashes and
  descriptor byte sizes: **11 hosted blobs / 81,985,887 bytes**, and
  **15 service blobs / 61,883,633 bytes**.
- Both are single Linux/amd64 images with Docker distribution schema 2
  manifests and gzip layers. Hosted declares port 8088 and
  `python -m src.reactor.hosted`; services declare port 8080 and the documented
  Uvicorn factory. Native read-back matched the approved hosted reference,
  CPU/memory, Responses protocol and model/Toolbox settings.
- Local runtime readiness was **not verified**: this machine is ARM64.
  The amd64 smoke container exited and auto-removed; no existing local
  container was stopped, deleted or pruned. Pull verification succeeded
  independently of this architecture limitation.

One probe incorrectly forwarded an ACR bearer token to the Azure Storage
blob redirect and received HTTP 401. Removing that cross-host authorization
header made the download succeed. This was a probe defect, not evidence of
broken registry anonymous access. An attempted named WSL session also did
not exist; normal WSL pulls worked.

### Bounded deployment checks

| Attempt | Exact observation | Meaning |
| --- | --- | --- |
| Native 5 | Unchanged approved image, after the longer grant interval: `ImageError` | Waiting and repulling locally did not repair this native allocation. |
| Native 6 | Supported `azd` prebuilt deployment to the existing project/agent: same `ImageError`; no new registry connection or pull grant was emitted | A separate deployment client did not recover readiness. |
| Managed ACR connection | Created `reactor-acateam`, category `ContainerRegistry`, auth `ManagedIdentity`, shared registry target/resource ID | Resource creation worked; that alone is not a live image-pull pass. |
| Rejected explicit binding / native 7 | The non-ACR `registryConnectionId` path returned HTTP 400 `not_a_registry_connection`; an allocated version 7 subsequently reported `ProvisioningError` | This option is not valid for that managed ACR connection. It was removed from the diagnostic YAML; an HTTP error cannot be assumed to have created no version. |
| Native 8 | Normal SDK path with the managed ACR connection present: `ImageError` | Connection-only recovery failed. |
| Native 9 | Registry-scoped `AcrPull` for the existing stable hosted-agent identity, with the project grant and ACR connection, after 90 seconds: `ImageError` | The documented project-plus-agent grant combination did not establish readiness. |
| Native 10 | Identical manifest digest copied to a fresh same-registry repository reference: `ImageError` | Changing the reference without changing image bytes did not recover the pull. This does not identify the backend's rejected identity. |
| Native 11 | Managed connection selected the verified project MI application/client ID and `useWorkspaceManagedIdentity: true`: `ImageError` | Explicit workspace-identity selection did not recover readiness. |
| Native 12 | One additional exact-scope pull test for the separately verified, project-owned Entra agent identity, after 90 seconds: `ImageError` at 19:49:54 | This third identity hypothesis also failed. No successful pull actor is proven. |

The existing project MI registry grant remains. The two temporary additional
pull assignments were revoked by their exact IDs and verified absent after
the failed checks. No Owner/Contributor grant or directory application was
created, and no original-allocation role was changed.

Support correlation IDs from the supported-client attempts:
`cd8e894adf0cfe9dd03848fe8b3e907a` (image-authentication failure) and
`189e2623a80287ea96adc10f9f1ca195` (rejected registry binding).
The shared registry has no diagnostic settings; no global logging change
was made. The next required evidence is the actual rejected image-broker
caller/token-exchange or registry request for this project, not another
assumed identity or a broader grant.

### Deployment helper repair

Added **P11**: identical hosted definitions were checked against an aggregate
list result that could say `active` for an exact failed version. The helper
now calls `get_version` before deciding to reuse that hosted version.

Two focused regressions passed: aggregate-active/exact-failed is rejected,
and reuse reports the exact provisioning status rather than aggregate-active.
A live invocation of the setup helper without `--new-version` correctly
rejected failed version 12 and created no new version. This is an
**implementation repair**, not a fix for the native image-authentication
failure. No runtime image rebuild was needed for this helper-only change.

The first `azd init` discovered the parent lab project despite its supplied
child cwd. Its tracked `azure.yaml` changes were fully restored, and generated
files were moved outside the lab checkout before deployment. The temporary
root default-environment selection was cleared rather than guessing which
older allocation to select. Existing environments were not removed.
Subsequent deployment targeted only the existing new-allocation agent from
the standalone session context. This is operator-tool overhead, not learner
timing or a guide-recommended project setup change.

### Follow-up timing and ending state

Request to the latest failed native check: **31 minutes 34 seconds**.
Through the 19:51:31 ending inventory, follow-up diagnosis/verification
elapsed **33 minutes 11 seconds**; subsequent reporting is additional.
No learner completion time was measured. The healthy-allocation **90-120
minute planning estimate** remains unverified.

CLI work comprised public-policy/manifest/config/layer checks, both WSL pulls,
normal native and supported prebuilt retries, the recorded connection and
scoped identity comparisons, helper regressions, and ending inspection.
No new portal research action or normal-UI research submission was performed
during this follow-up: the readiness stop condition still applies.

The execution service remains ready with maximum-active 2. The frontend
remains signed out, unconnected, and submission-disabled. Both protected
new-allocation seed/reference instances are Stopped; the task selector and
hosted session list are empty. Original native version 6 remains exactly
active. Learner material/hash and `lab-ready-1` are unchanged; no push or
commit was performed.

Failed versions 1-12, the managed ACR connection, and
`acateam.azurecr.io/lab722/reactor-hosted-pullcheck-20261107` are retained for
inspection. The diagnostic repository's manifest has the exact approved
hosted digest; it is not a new application build or a successful deployment.
No reproduction resource was deleted as ending cleanup.

**Remaining blocker:** the fresh Foundry image broker still rejects the
verified image. Versions are not active-ready, and the strict learner
walkthrough cannot continue. These customer-side checks do not prove a
platform defect or its root cause; Foundry-side request/identity diagnostics
are needed before choosing another repair.

## Expert-assisted identity-bootstrap investigation

Investigation resumed November 7, 2026, at 20:04 UTC-06:00. This is
facilitator diagnosis, not learner time. **Shared-ACR provisioning recovered
in the sibling at 20:50:45. The subsequent live pre-lesson ownership gate
completed at 21:16:40; learner outcomes are recorded below. The original
`caldova` project remains failed.**

### The failing stage is now identified

Service-side diagnostics place the failure in Foundry's image-build
managed-identity bootstrap, **before ACR token exchange or image download**.
The build instance starts successfully and the correct project MI client
identifier reaches provisioning, but the identity proxy cannot use an
associated identity-enabled group. The recorded failing build-group updates
contain no managed identities; the successful control group's recorded
update contains one. This is stronger evidence than the generic
customer-facing `ImageError`, but does not yet identify the supported
reconciliation action or why the identity list is empty.

The build group is platform-managed and separate from the allocation's
research execution group. No platform-owned resource was modified and the
research group's deliberately disabled identity was not re-enabled.
Internal group/subscription identifiers, raw backend logs and credential
metadata remain in private session evidence, not this report.

**P12:** the visible AcrPull/image-authentication message does not distinguish
a registry denial from a pre-registry identity-bootstrap failure. A correct
registry grant plus successful anonymous local pulls cannot establish hosted
readiness. Preserve the readiness stop and obtain the actual failing stage
before adding more principals or permissions.

### Additional actions and observed results

| Control or action | Observation | Classification |
|---|---|---|
| Registry diagnostics | Added Login/Repository diagnostic events to the existing allocation workspace. A developer-authenticated manifest control produced delivered Login/Pull HTTP 200 events. | Diagnostic delivery verified; not a project-MI test |
| Foundry diagnostics | Added allocation-account Audit, Trace and ManagedNetworkEvent categories; did not enable request/response-body capture. | Facilitator-only observability |
| Native 13 and explicit session check | Version failed; creating a session against it returned `agent_version_failed` before any session existed. | Pre-session failure; runtime session logs cannot diagnose this stage |
| Documented connection/account-role corrections | Restored the ordinary managed ACR connection to the official principal-ID contract and added fresh project MI account-scoped Foundry User for model access. The original working project lacks that account role. | Neither change is a demonstrated image-pull repair |
| Fresh logical agent in the failing project | Diagnostic version 1 failed at the same bootstrap stage; no additional runtime/registry grants were given to its agent identity. | Changing only the logical agent did not recover provisioning |
| Native 14 | Failed after more than ten minutes of account-role propagation; terminal bootstrap failure was independently correlated. | No recovery |
| Current positive control in original project | Native version 7 became active at 20:35:07, about 24 seconds after the control began, using a fresh repository reference to the exact approved hosted bytes. ACR attributed Login/Pull HTTP 200 to the original project MI, with the expected digest. Original version 6 stayed active. | Current authenticated provisioning success; not merely an old active version |
| Identity-only project update | Supported `PATCH` with only `identity.type: SystemAssigned` returned HTTP 200/Succeeded and preserved the project principal. Native 15 still failed at the same bootstrap stage at 20:38. | Supported ARM operation, unsuccessful and undocumented as a reconciliation mechanism; not repeated |
| Account/effective-project comparison | Both accounts have the same relevant visible public hosting settings and no capability hosts. Both original/failing projects are default projects with SystemAssigned identities. The sibling is a supported non-default project. | No identified customer-visible hosting prerequisite difference |
| Same-account sibling project | Created one SystemAssigned project with its own registry-scoped AcrPull and deploying-user project-scoped Foundry User. After ten minutes of propagation, native 1 became active at 20:50:45 with the canonical digest. Delivered ACR Login/Pull HTTP 200 events identify this sibling's project MI. | Authenticated image-provisioning recovery in the requested allocation |
| Original project after sibling success | An unchanged native 16 retry still failed at 20:51:51. | Creating the sibling did not repair the original project |

**P13 (diagnostic preparation only):** using `reactor-acateam` in the sibling
returned HTTP 400 because that account-wide connection name belongs to the
original workspace. The original connection was left intact. Recovery uses
a unique, non-shared sibling diagnostic connection; no shared connection was
overwritten. This is not a completed learner recovery or a new requirement
for the normal one-project-per-account lab.

The positive control proves that these bytes and the shared registry can
provision through a current authenticated Foundry path. It does not prove
every layer avoided cache reuse or establish readiness in the fresh
allocation.

The canonical-reference sibling control independently establishes image
readiness in `caldova-pull-diag-20261107`, under the same Foundry account in
`ig2026-lab-learner-2`. This changes project identity/provisioned state and
the diagnostic connection name/sharing setting; it does not prove which
change enabled recovery or that non-default projects are required. The
original currently successful default project is a counterexample to that
claim.

### Preparing the validated backend

Use the already validated additional project for this allocation's supplied
project values, rather than replacing or deleting the failed default
project. This is a **facilitator recovery using a supported project
surface**, not a demonstrated repair of the original binding or a universal
installation prerequisite. The unchanged learner guide accepts supplied
project/identity/Toolbox values.

Created the new project's OpenAPI connection in the normal Foundry UI using
Managed identity and the existing dedicated execution API audience. Its
unique `reactor-execution-recovery` name avoids the same account-wide
collision; ARM read-back verified `ProjectManagedIdentity`, target and
audience. Registered native Toolbox 1 and the actual `reactor-orchestrator`
starter 1, verified the starter active, and granted its runtime only
project-scoped Foundry User. The new project MI's account-level model-access
role and the deploying user's project-level Project Manager role were
prepared separately.

The existing `deploy-reactor.ps1 -FoundryProjectName` input repointed both
Express services without source/image changes or new credentials. Both
original Express URLs and UAMIs stayed unchanged. An empty task-Sandbox
inventory preceded the execution app's supported Stop/Start to apply its
new allowed project object ID; execution HTTP readiness returned ready
with maximum-active 2.

Actual MCP discovery returned `reactor___reactor_execute` with required
`body` and `X-Reactor-Run-Grant`, matching the declared runtime contract.
Local diagnostic probes hit installed MCP API naming/stream/model-shape
differences; these were corrected in the operator harness without changing
the pinned hosted image or learner commands. They are not learner-guide
failure evidence.

The prepared starter's Responses endpoint was derived using the supported
SDK for facilitator preflight. This temporary connection is not counted as
the later learner's portal endpoint handoff. Runtime invocation, owned
acceptance and actual post-run deletion passed before the frontend was
reset to unconnected and learner timing began.

### Expert collaboration and preservation

Used the requested signed-in ChatGPT thread for bounded public-documentation
research, allowing asynchronous waits of up to fifteen minutes rather than
polling or resending while it was busy. Only anonymized technical summaries
were sent: no private source, resource/tenant identifiers, credentials or
raw internal logs.

The expert found no published customer-side repair for this binding.
Project identity PATCH is supported, but its reconciliation effect is not
documented. An ordinary `ContainerRegistry` connection with `authType: None`
exists in ARM; a hosted-agent anonymous ACR override is not established by
that contract. No unsupported explicit registry binding, capability host,
identity reset, directory application or broader registry grant was added
as a workaround.

All diagnostic settings, failed versions, the diagnostic logical agent,
original positive-control version, sibling project and scoped diagnostic
grants are retained. No reproduction resource was deleted. The account-level
model-access grant and connection correction are retained but are not
claimed to have fixed the image pull.

## Verified live gate before learner timing

The prepared starter completed real Alice and Bob phases work. Alice's
first preflight run was `4fb808e8-76ef-4497-9853-045a96d5c06d`; Bob's was
`9af4b6b6-810d-4027-8b3d-2738427c2b45`. Both were accepted under their
application-asserted owners. Independent in-page checks matched code
SHA-256, all three frozen hashes, every source ID, run/marker correlation,
project service caller and dedicated audience. Actual task inventories
were empty after cleanup.

Bob's foreign Alice run, artifact and conversation reads, and UI
cancellation, returned HTTP 403. Alice re-login still retrieved her
unchanged accepted evidence with HTTP 200. Unauthenticated execution
returned 401. A native Toolbox forged-owner/invalid-grant request reached
execution and returned 403; its error redacted the grant and Authorization
headers. This did not extract or reuse a genuine foreign grant.

The operator harness expected an `isError` result but the gateway returned
the expected denial as an `MCPError` exception. That was a harness-shape
deviation, not an execution authorization failure; no duplicate probe was
submitted. A requested browser export outside configured roots was denied.
No alternate export path or permission workaround was used; evidence was
verified in-page and derived findings are recorded here.

After zero task inventory, the supplied deployment helper without a hosted
endpoint and a supported frontend Stop/Start restored
`hosted_configured: false` at 21:18:03. Starter 1 is a verified known-good
hosted reference, not the learner's creation.

## Learner checkpoints and repairs

The learner guide remained byte-for-byte unchanged. The operator consumed
its source inspection, describe/create, portal handoff, demo UI, console
comparisons, exact inventory selectors and offline fixture commands.
Read-only inspections were interleaved with running tasks; this automated
rehearsal is not a literal human, sequential comprehension/pacing test.

| Checkpoint | Actual result | Classification |
|---|---|---|
| 1: source and definition | Inspected `Orchestrator`, proposals, runtime-only binding, independent review and hosting entry point; `--describe` showed the immutable image and Responses 2.0.0 contract. | Passed as documented |
| 1: explicit creation | First `--new-version` returned existing active starter 1 with `reused: false`. After the helper repair, the same learner command created native 2; exact native read-back and Foundry both showed it active/running. Its prepared runtime identity stayed unchanged. | Undocumented repair, then verified new creation |
| 1: portal handoff | Foundry Details showed Latest (Version 2), the runtime identity and displayed Responses endpoint. That unversioned URL initially caused frontend HTTP 400 before a receipt or task existed. Cancel/reconcile and helper normalization recovered the handoff. | Documented run reconciliation plus undocumented helper repair |
| 2: Express services | Normal RG resource list, both app Overviews, environment tabs and Identity > User assigned were inspected. Both UAMI resources' client/principal IDs matched the supplied values; only non-secret authorization/origin/endpoint fields were read. | Passed after portal reload |
| 3: phases and correlation | Learner version 2 produced 168 exact source IDs, PHASE3=76, accepted hosted output and all independent receipt/hash/caller checks. Actual run-scoped inventory was empty. Same-key Run returned `reused: true` and the same run. | Passed as documented after handoff repair |
| 4 / L1: ownership | Bob's allowed run passed; foreign Alice run/artifact/conversation/cancel returned 403. Bob's prompt requesting Alice's run/customer still produced Bob-owned accepted evidence. Alice's original result stayed accessible. Unbound execution returned 401 with no task. | Passed as documented; genuine-grant combinations remain offline |
| 5 / L2: two workers | Phases and safety both passed with 168/38 exact IDs and two independently checked/deleted task instances. | Passed as documented |
| 5 / L3: egress | Actual Sandbox-side `urllib` code failed under the created resource's Deny/Full policy; owned failed evidence and deletion were retained. No successful connection was observed. No policy-specific traffic verdict is exposed. | Passed at the guide's partial coverage; enforcement not fully verified |
| 5 / L3: limits and exit | The limit receipt was `timed_out`, elapsed 30.105 seconds, with deletion and hosted completion. Controlled failure returned exit 19 and retained owned failure evidence. | Passed as documented |
| 5: cancel/recover | A first attempt missed the active window during portal inspection and completed as another timeout; it is not counted as cancellation. A fresh attempt observed a running Sandbox, cancelled it, verified deletion and suppressed same-key replay. Fresh-key phases then passed. | Operator timing deviation, then passed active cancellation/recovery |
| 5 / L4: wrong answer | All nine execution fixtures passed, including rejecting PHASE3=77 and incomplete safety IDs while accepting correct controls. | Offline evaluator evidence, not a live malicious-worker run |
| 6 / L5: budget/capacity | Alice's second fresh submission returned 429 while her long attempt reserved its slot. Bob was admitted and completed. Actual aggregate inventory reached two, never exceeded two, then returned to zero. | Passed as documented |
| 6: versions and usage | Foundry showed hosted image/native 2 and Toolbox v1/OpenAPI tool. Both service digests were verified through ARM/CLI because generic portal image/tag fields were unreliable. Dataset v2 and actual receipt Sandbox seconds were present; hosted usage was not returned. | Portal image fallback; unavailable usage explicitly recorded |
| 6: revert and ending | Reviewed the linked operator procedure and verified known-good hosted 1/image. Previous Toolbox/service references are unavailable; no rollback was performed. All task inventory is empty; seed/A remain stopped. | Explanation completed; rollback not run |

### Additional friction and surgical repairs

**P14: explicit version creation was silently deduplicated by the service.**
Skipping local reuse was insufficient when the submitted definition and
metadata matched the prepared starter. `setup-reactor-foundry.py` now adds
a unique creation identifier to metadata only for explicit `--new-version`
and rejects a response returning the existing version. The immutable image,
runtime definition and stable configuration fingerprint are unchanged.
Actual native 2 creation and both new regression cases passed. Ordinary
reuse still checks the exact version's provisioning status, including the
earlier regression preventing an aggregate active status hiding failure.

**P15: the displayed portal Responses URL omits `api-version=v1`.**
The successful preflight used the SDK-derived versioned URL; the exact
displayed learner URL produced a logged HTTP 400 before execution.
`deploy-reactor.ps1` now adds the protocol API version when missing,
preserves explicit query values and leaves unconnected input empty. The
same portal-visible input then yielded a saved versioned endpoint and real
learner completion. The production normalization block passed plain-URL,
additional-query, existing-version and null cases. This is a protocol API
version, not an invented native-agent version selector. A direct portal
environment edit still needs that API-version query; it does not run the
deployment helper's normalization.

**P16: browser Copy was not visible to the operator's host clipboard.**
The Copy endpoint control was clicked, but the host clipboard check did
not return the expected value. The exact displayed text was read in-page
and supplied, never guessed. This is an automation transport limitation,
not proof that a learner's local clipboard is broken.

**P17: distinguish an omitted iframe from a real loading stall.**
Initial automation snapshots omitted the normal portal's rendered iframe
content. Inspecting that visible UI context recovered the RG/frontend
views without a private API, token extraction or security change. The
execution Overview later really stalled at a spinner; a normal full reload
recovered it. Both identities and authorization settings were subsequently
compared in the actual portal.

**P7 follow-up: the prescribed digest display remains unreliable.**
The frontend's generic ACR image/tag selectors were blank for the existing
immutable deployment. No incomplete form was saved and no tag substituted.
The read-only ARM/CLI comparison verified the same service digest in both
apps; Foundry's Code asset displayed the hosted digest normally. This
remains a deviation from the exact Containers > Image instruction.

### Selected live evidence ledger

These are actual owned run IDs, not fixtures. Creation-to-inspection times
include intervening reads and are not isolated model latency measurements.

| Exercise | Run ID | Actual evidence |
|---|---|---|
| Alice phases | `581fc4b8-d2a1-4a3b-b636-fbce836e74a5` | Accepted; 168 IDs; PHASE3=76; 6.996 Sandbox seconds |
| Bob phases | `8eded150-2949-40a0-8129-1bdd0c87d392` | Accepted as Bob; 6.996 Sandbox seconds |
| Bob ownership injection | `0243faa7-2c9c-4166-8156-8670a3721d27` | Still Bob-owned/accepted; 6.832 Sandbox seconds |
| Two workers | `5d8c429a-6b4c-4cad-85f6-3a1a90a4d0f5` | Two passing receipts, 168/38 IDs; 14.177 total Sandbox seconds |
| Egress negative | `d7376d12-a772-4960-a4bd-198c31029b76` | Failed/not accepted; actual `urllib`; Deny/Full; deleted |
| Limit | `b3273e71-ec78-453e-80d0-2a0c77f8ee77` | Timed out at 30.105 seconds; 32.712 Sandbox seconds; deleted |
| Exit 19 | `281ef4a9-b83f-490d-9d58-5860454cbe05` | Exit 19; failure evidence retained; 6.995 Sandbox seconds |
| Active cancellation | `5f35e4d7-aff0-4b2a-8398-5023538ca90a` | Running Sandbox observed; cancelled/cleaned; actual selector empty; same-key tombstone reused |
| Fresh-key recovery | `724606c5-7b60-407b-93e0-22002f967180` | Accepted phases after cancellation; 7.774 Sandbox seconds |
| Alice budget reservation | `73e5548a-bd1a-40bd-9e4a-e6e2bfa6a46c` | Second Alice key rejected 429; original timed out at 30.108 seconds and cleaned |
| Bob beside Alice budget | `5bb7b626-2846-42bc-aed2-458d44b98b12` | Admitted and accepted while Alice reserved; 6.744 Sandbox seconds |

The two-worker aggregate selector was sampled 24 times from 21:35:56 to
21:36:51. It showed exactly two physical instances at 21:36:12, :14 and :16,
then zero; no sample exceeded two. A separate live budget-exercise
inspection also showed two. Ending inspection showed only the two
protected stopped seed/A instances and zero reactor tasks.

### Actions, measured timing and learner estimate

Preparation/investigation ran from 17:51:14 to the first learner start at
21:18:10: approximately **3 hours 27 minutes**, not learner time. It
includes the exceptional failed-project diagnosis, role propagation,
supported sibling preparation and separate live gate/reset.

The learner/operator envelope ran **21:18:10-21:57:23: 39:13 elapsed**.
Recorded windows were 21:18:10-21:19:03 (first creation stop),
21:21:01-21:27:02 (new creation/readiness and failed handoff), and
21:31:19-21:57:23 (corrected live exercises, portal checks and ending state).
Gaps contain explicit facilitator repair/deployment work. Even these
windows include debugging and automated/parallel inspections: do not
present their sum as a successful human duration.

| Channel | Actions actually taken |
|---|---|
| Learner CLI | Source inspection; unchanged `hosted --describe` and explicit `--new-version`; trusted source SHA-256; exact run/aggregate `aca sandbox list` selectors; the documented eight API and nine execution tests |
| Learner portal/browser | Foundry Agents/version 2, Details/latest/runtime identity/Responses endpoint, Code asset digest, Tools > Toolbox v1/OpenAPI tool; normal Azure RG/app Overviews, Containers environment tabs and both UAMI Overviews; demo sign-in/out, Run, owned run/evidence inspection, foreign/cancel denials, console digest/source comparisons, same-key reuse, negative probes and recovery |
| Facilitator CLI | Supported additional-project/runtime/model/registry preparation; existing helper repoint/reset/endpoint handoff; Express Stop/Start; exact native readiness and non-secret ARM/CLI digest/identity comparisons; five helper regressions; scoped session ending |
| Facilitator portal | Original supported OpenAPI connection creation and read-back; no image form, role, secret or identity change during learner portal inspection |
| Automation only | Existing signed-in Chrome transport; explicit visible-iframe context inspection; normal UI clicks and bounded owned status reads; no cookie/token extraction, private portal API or export-permission bypass |

Keep the **90-120 minute learner estimate** provisional. A practical
allocation is 15-20 minutes for source/create, 10-15 for services/identities,
15-20 for correlation/idempotency, 15-20 for ownership, 20-25 for boundaries/
recovery and 10-15 for budget/versions/ending, plus transitions. Schedule
120 minutes until a representative learner validates the shorter target.

### Ending state and validation

- Both Express URLs/UAMIs, dedicated API audience, canonical immutable
  images and frozen snapshot stayed unchanged by the helper repairs.
  Only supplied project/connection/configuration and deliberate native
  version metadata changed. No image rebuild, tag movement, commit or push.
- Hosted native 2 and Toolbox 1 remain the learner configuration;
  known-good hosted 1/image are retained. All failed original versions,
  original positive controls, diagnostic project/agent/settings/grants
  remain. No platform-owned group or research-group identity was altered.
- Final task inventory is zero; protected seed and fixed A retain their
  exact IDs and stopped state. Every recorded Alice owned run was terminal
  and cleaned. Bob's tested runs were also terminal and cleaned.
- After work finished, one of eight previously identified active native
  sessions had already idled. The operator stopped only the remaining
  seven exact rehearsal-version-2 sessions through the supported API.
  Read-back showed zero active and 14 retained idle session records.
  No agent version, diagnostic agent or historical deployment was deleted.
- Five helper regressions and the 17 documented API/evaluator fixtures
  passed. Deployment compiled/applied successfully with existing preview
  Bicep type warnings. Final `git diff --check` and report fence checks
  passed. Learner-guide SHA-256 remains
  `E8A12778467C3F9DDDE160FC2A31BCB63724A70195A87BE507EC5C96732BBF15`;
  HEAD remains `1981a84`. Final independent read-back confirmed native 2
  active, zero active/14 retained sessions and HTTP 200 from the frontend
  and execution health endpoint.
- Review explains evidence but cannot override acceptance; service
  authentication is not demo-user Entra delegation. After authority loss,
  a prompt cannot reconstruct an old run/grant. No ownership-state-loss
  incident occurred during these learner exercises, so that conditional
  privileged recovery path is not counted as tested here.

The expert independently calibrated the reported recovery as end-to-end
runtime success, not original-project repair or universal additional-project
necessity. Its final reply agreed that the exercised technical rehearsal
succeeded with the stated gaps; it did not inspect our private evidence.
Final collaboration used only anonymized technical outcomes.

## November 8 local walkthrough preparation

The guides now incorporate P14/P15, distinguish the normal Toolbox view
from operation discovery, and specify the P7 read-only image fallback.
Supported additional-project recovery is explicit; no original-binding
repair, live rollback, representative human pacing or cross-tenant
delivery is claimed.

For the owner's personal pass, the separate `local-reactor` azd profile
targets fresh `ig2026-lab-local`/project `reactor`, creates its own approved
dedicated API during setup, and uses the canonical images. Public local
settings are prepared and ignored by Git. The real preprovision hook and
local Bicep compilation passed; 14 targeted helper regressions passed.
The new Graph/orchestration branches are checked with mocks, not a fresh
live deployment. No new RG/API was created during this preparation.

The local endpoint handoff patches and Stop/Starts only the frontend,
preserving execution state; it rejects active tasks, foreign project
endpoints and a prepared marker belonging to another project. Native
build/identity failure stops rather than auto-creating another version.
Passwords/policy metadata are hidden input and never local azd settings.
This is ready for the owner's commissioning walkthrough, not an additional
completed cloud rehearsal. Live gap checks, push/release and packaging wait
for that walkthrough.
