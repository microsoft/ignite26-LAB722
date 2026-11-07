# LAB722 reactor walkthrough report

## Scope and verdict

**November 7, 2026; branch `lab-reactor`; implementation commit `2c23e1a5de6dd1fcabcfaf1baf8f49c6ed1c5122`; intended environment: the authorized `ig2026-lab-learner` allocation. Literal learner execution: blocked at readiness.**

The owner declined creation of a tenant service API registration. No existing dedicated execution API audience was supplied. We did not create tenant resources or substitute first-party-audience tokens, shared keys, the old runtime or a self-hosted orchestrator. No new Express apps, hosted agent or reactor Toolbox have been deployed.

The new source uses separate frontend/execution Express apps, a request-owned native hosted Responses workflow, managed Toolbox OpenAPI and dynamically created task Sandboxes. This is source-supported/local-validation evidence, not a verified live call path. The learner entry is [the maintained guide](lab-rejig-learner-instructions.md); the root walkthrough contract is unchanged. Commits are local only; `lab-ready-1` remains at `572037ae91d419c87d98ed5f577cf6cf5ac953a9`.

## Objective coverage

| Outcome | Local observed/source-supported coverage | Fresh live verdict |
|---|---|---|
| L1 | Real Argon2 login for both accounts; signed sessions/CSRF; allowed owned work and denied swapped run/result/conversation/cancel/grant; tenant/audience/signature/OID/delegation checks; model-hidden binding wrapper | **Blocked**: actual service tokens, hosted context and gateway binding not exercised |
| L2 | Bounded process/receipt validation and actual isolated Linux private-note UID/read/symlink checks; existing root supervisor reused | **Blocked**: useful hosted execution, Sandbox-origin egress denial and limit breach not freshly exercised |
| L3 | Transactional idempotency, single execution claim, restart fail-closed, cancellation cleanup and exact-run uncertain-create reconciliation in focused tests | **Blocked**: interruption/recovery with live task resources not exercised |
| L4 | Wrong phase answer and omitted safety provenance rejected alongside correct controls; code/input/marker/resource correlation implemented | **Blocked**: live hosted wrong-result/correlation path not exercised |
| L5 | One reserved run/customer, two total task slots and at most two workers; cleanup fencing; image/configuration versions and concrete revert instructions | **Blocked**: live fan-out, Sandbox/token usage and revert not exercised |

Each learner outcome has an action, observation, explanation and transfer question in the maintained learner guide. Instructional support is **partial** where required live capability remains unverified; no live outcome is evaluated as passed. Offline evaluator tests are labeled offline. Actual-created policy fields are recorded as `receipt.egress_policy.defaultAction` and `trafficInspection`; the UI does not expose a policy-specific traffic verdict, so full live egress enforcement is not established. Configured policies and mocked service identities are not live enforcement evidence.

## Validation evidence

| Check | Evidence and limit |
|---|---|
| Windows reactor unit/API checks | `python -B -m unittest discover -s tests -p 'test_reactor_*.py' -v`: **38 checks, 37 passed and one Linux-root skip** |
| Final Linux service-image checks | ACR run `ds5`, **38 passed, no skips**, including the actual private-note UID/read/symlink check; log retained in session artifact `reactor-services-ds5-20261107.log`; all 24 reactor source/test files matched the build context |
| Preserved supervisor regression | ACR run `ds3`, **10 passed, no skips**; log retained as `reactor-supervisor-ds3-20261107.log` |
| Genuine hosted image | ACR run `ds1` succeeded; pinned hosted module imported during Linux build |
| ARM | `az bicep build --file .\infra\reactor.bicep --stdout` succeeds; missing-preview-types warnings mean cloud property validation is not established |
| Deployment helper | PowerShell parser passed; three offline mocked cases verified omitted endpoint, retained HTTPS endpoint and HTTP rejection before deployment; no cloud write in these checks |
| Shared-registry follow-up | Verified `acateam`/`prodish-stuff`, imported both exact manifests under `lab722`, and fetched both manifests using anonymous pull tokens without Azure credentials; digests unchanged. Compiled ARM defaults omit registry credentials and condition image-pull roles on private mode; five offline helper cases passed |
| Native definitions | Both `setup-reactor-foundry.py hosted/toolbox --describe` serialize the supported SDK definitions offline; no cloud registration occurs |
| Whitespace | `git diff --check` |

Final component image candidates, not a live deployment:

- Services `acateam.azurecr.io/lab722/reactor-services:20261107-v3`, built in run `ds5`: `sha256:12edea1007a697b1adf902b7e69785799f398c8e7367d18307cb1c40d24b590e`.
- Hosted `acateam.azurecr.io/lab722/reactor-hosted:20261107-v1`: `sha256:29aecc979a793c5656a8272813c81f0e4f2f9e09d422f5272259a4cdccfc382d`.

The owner selected `acateam.azurecr.io/lab722` after the initial local delivery. Both images were imported unchanged from the build registry `lab722hg4qnurp4clywacr.azurecr.io`; the shared registry already had anonymous pulls enabled, and those pulls were independently verified. No registry access policy, tenant resources or application deployment was changed. Earlier service candidates `ds2` (30 checks) and `ds4` (36 checks) are superseded by `ds5`; the hosted component source is unchanged since `ds1`. The Windows CLI initially failed path resolution, then failed streaming Unicode build logs; registry task status and authenticated log retrieval independently verified the build results. Later builds used `--no-logs`. Those repairs were facilitator validation, not a passing literal learner run.

## Findings and corrections

| Location / outcome | Severity | Expected versus found; smallest correction | Verification |
|---|---|---|---|
| `execution.py` / L3 | Major | Concurrent owned cancellation escaped `/offload` as `CancelledError`; return explicit HTTP 409 only for the owned-cancel state and propagate other cancellation | Concurrent API test passed; targeted independent rereview found no issue |
| `main.py` / all outcomes | Blocker | Startup used `asyncio.run` inside the ASGI running loop; use a synchronous factory and asynchronous lifespan, close credentials and refuse missing-state orphans | Running-loop/orphan tests passed; targeted independent rereview found no issue |
| `main.py`, `frontend.py`, deployment helper / sequence | Major | Preparation required an endpoint from an agent learners had not created; allow an empty endpoint, disclose unconnected state and reject submission before reserving work | Startup and login/inspection/no-reservation tests passed; three offline helper cases passed |
| Learner sections 2 and 4 / L1 | Major | Expected OID/audience fields and execution-negative action were missing; supply literal configuration fields, independent values, offline swapped-binding fixture and separate live unbound-401 action | Fresh targeted B/C reread resolved; live foreign-grant proof remains unverified |
| Learner sections 3-5 / L4 | Major | Finding receipt fields did not compare them; supply trusted pins/source IDs and run/marker/code-digest comparisons for every receipt; move prediction before Run | Fresh final B/C reread resolved; wrong-answer and correct-control tests passed |
| Learner section 5 / L2 | Major | No numeric timeout comparison or precise egress verdict; supply field paths/bounds and actual-created policy fields; classify unavailable traffic verdict explicitly | Fresh final B/C reread resolved; full live enforcement remains unverified |
| Learner recovery / L3 | Major | Abandoned ephemeral state had no authorized cleanup handoff; supply exact task selector, facilitator deletion of confirmed IDs and ending criteria | Fresh targeted B/C reread resolved; local fail-closed and exact-cleanup tests passed |
| Learner section 6 / L5 | Major | Single-run inventory could not show aggregate capacity, and version/revert lookups were unspecified; supply aggregate selector, exact lookups and optional previous-reference labels | Fresh final B/C reread resolved; four-queued-task/two-physical-slot test passed |

These corrections are source/local or instructional evidence, not undocumented repairs to a completed live learner run. The final unconnected-preparation change received an informed coordinator check and focused tests, not a new blind implementation review.

## Walkthrough gate

**A:** independent implementation review completed, its cancellation finding was corrected, and targeted startup/cancellation rereview reported no concrete issue. **B-C:** eight initial instructional findings and three remaining targeted points were corrected; the final scoped reread found none remaining. This does not fill the disclosed live capability gaps.

**D:** blocked at the first required readiness prerequisite: no approved dedicated execution API audience/service grants. No Azure credential switch, substitute shared-key environment or later live checkpoint is represented as passed. Fresh reactor starting/final resource state was not changed by a deployment.

**E:** blind offline calibration detected **4/4 seeded defects, zero misses and zero false alarms**; all three correct controls were accepted. Defects covered the PowerShell prerequisite, successful-but-wrong answer, nonexistent Toolbox identity field and incorrect project-MI-to-demo-user explanation. Fixture retained as `reactor-review-calibration-20261107.json`.

The representative human comprehension and pacing check has **not occurred**. The 75-minute budget remains an unmeasured authoring target. Fresh Skillable permission/platform delivery, real hosted readiness and end-to-end gateway mapping remain unverified.

## Smallest remaining live action

Supply an approved **existing dedicated service API audience and its permitted service grants**, without new tenant resource creation. Then deploy the prepared services/connection and run the documented one-task Alice/Bob identity gate. Verify actual tokens and gateway argument mapping before progressing to two workers, live boundaries, recovery and capacity.

| Classification | Remaining boundary |
|---|---|
| Confirmed blocker | No dedicated execution API audience/app registration and permitted app-only grants have been supplied. Tenant resource creation was declined. |
| Unverified platform gate | Supported Foundry connection must request that dedicated audience using the actual outbound service identity; live token audience/OID and hosted activation are not yet verified. |
| Unverified gateway gate | Native Toolbox must advertise the operation and deliver all declared binding fields unchanged; metadata/grant privacy must hold across the actual hosted request. |
| Not-run acceptance | Fresh allowed/denied Alice/Bob runs, Sandbox execution/egress/limits, interruption/recovery, acceptance correlation, fan-out/usage and revert still require live rehearsal. |
| Resolved image delivery | Both reactor manifests are published under `acateam.azurecr.io/lab722` and anonymously readable; no private-registry grants are needed for their public-pull path. |
