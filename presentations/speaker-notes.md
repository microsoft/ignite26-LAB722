# LAB722 presenter notes

Operate secure, multi-tenant agentic apps on Azure Container Apps

Simon Jakesch · Microsoft Ignite 2026

Generated from the embedded notes in `index.html`; edit that source and rerun `npm run export`.
Deck SHA-256: `f3ec1ab35459474abd3d824227bccddb6d89a66e541f12fee9fcb7d7ec390a67`

## Delivery boundary

Facilitator-guided rehearsal with prepared resources. **Recorded Evidence is the default**; optional Live Exercise requires explicit facilitator authorization. No event release, measured 75-minute runtime, or final recording readiness is claimed. Videos do not yet exist. Skillable-specific integration is excluded from this material milestone.

## Target schedule

| Segment | Target | Planned window |
| --- | ---: | --- |
| 0 · Welcome/readiness | 5 min | 0:00–5:00 |
| 1 · Research portal | 4 min | 5:00–9:00 |
| 2 · Foundry orchestrator | 15 min | 9:00–24:00 |
| 3 · Sandbox baseline | 15 min | 24:00–39:00 |
| 4 · Agent team | 23 min | 39:00–62:00 |
| 5 · Build/publish receipts | 6 min | 62:00–68:00 |
| 6 · Trace evidence | 7 min | 68:00–75:00 |

These are activity allocations, not measurements. Segment 5 is a recorded-build walkthrough, not a six-minute full-build promise.

## Slide 01 · Operate secure, multi-tenant agentic apps on Azure Container Apps

Segment 0 · Slide target 0:30 · Planned window 0:00–0:30

Target: 0:30; segment 0, cumulative 0:30 of the planned 75:00.

Welcome. Caldova is fictional. This application previews public research records, not clinical decisions. We practice operational trust boundaries: agent orchestration, constrained workers, deterministic checks, and evidence-bound deployment.

Recorded Evidence is the default participant path. Optional Live Exercise requires explicit facilitator authorization and an eligible prepared environment. This is facilitator-guided rehearsal, not event authorization, a fresh attendee starter, or final recording readiness. The same guide supports guided and self-paced reading; videos have not been created.

Checkpoint: Everyone can open the shared guide. Transition: distinguish the usable rehearsal path from the remaining attendee startup work.

## Slide 02 · 0 · Welcome and readiness

Segment 0 · Slide target 1:00 · Planned window 0:30–1:30

Target: 1:00; cumulative 1:30. This is a five-minute segment target, not a measured duration.

Locate the guide, declared Python/PowerShell prerequisites, and selected path. Recorded Evidence requires no allocation or deployment. Live Exercise is optional and explicitly facilitator-authorized, not a generalized participant cloud workflow. Skillable-specific identity, authorization, trigger, and output adaptation are outside this milestone and do not block material creation.

Checkpoint: Participants can state which path they are following. Transition: examine the readiness ledger, not just a green application URL.

## Slide 03 · A green application is only one readiness fact

Segment 0 · Slide target 3:30 · Planned window 1:30–5:00

Target: 3:30; cumulative 5:00. Give about two minutes to reading segment 0 and selecting Recorded Evidence.

The startup shorthand on screen is not a complete command. scripts\start-lab.ps1 requires PowerShell 7.2+, a resource-group name, a separately authorized environment, and explicit Readiness mode. Use the guide’s current invocation only if authorized. Do not improvise names or switch to Provision/Prepare. This deck/exporter never invokes startup or Azure.

The 12:08 UTC−5 observation pinned application name/digest/state, four local files, Express/registry scope, full live manifest/original source, and a state sample. Thirteen offline PowerShell groups and seven Python tests passed. These are development validations, not an attendee-health claim.

Foundry is in maintainer test2 while Sandboxes are in test1. Both retained Sandbox groups are full; stopping does not free capacity. Do not delete retained resources, allocate replacements, or claim single-scope per-attendee authorization.

Checkpoint: Read infrastructure/application/frozen_data separately from baseline/data_release/attendee. Transition: inspect the portal as a development reference, not a distributed starter.

## Slide 04 · 1 · Open the research portal

Segment 1 · Slide target 1:00 · Planned window 5:00–6:00

Target: 1:00; cumulative 6:00.

The genuine portal starter is visual and its query features are unavailable. The completed development application is a presenter reference only; it cannot pass the starter check. Use Recorded Evidence when a starter has not been distributed. Do not present implemented retained work as a fresh editable starter.

Checkpoint: Identify the two query features without assuming they already exist in a starter. Transition: show expected behavior in the completed reference.

## Slide 05 · Preview records, not medical conclusions

Segment 1 · Slide target 3:00 · Planned window 6:00–9:00

Target: 3:00; cumulative 9:00. By default read the guide’s expected behavior and evidence. If separately permitted, inspect the existing development app read-only: select semaglutide, change a condition, inspect source fields, then select tirzepatide safety.

Describe trials and adverse-event reports independently. There is no patient-level trial/report linkage. Trial conditions never narrow safety reports. Conservative exact generic-name selection leaves tirzepatide safety empty; this is expected, not a fault to repair.

Do not infer incidence from counts, causality from reports, or comparative safety across drugs. No expert clinical audit is claimed. If the app is unavailable, use Recorded Evidence; do not claim a live success or perform a deployment.

Checkpoint: Ask why an empty result should remain empty. Transition: connect bounded portal features to the trusted orchestrator.

## Slide 06 · 2 · Configure the orchestrator

Segment 2 · Slide target 1:00 · Planned window 9:00–10:00

Target: 1:00; cumulative 10:00.

Follow the guide’s Recorded Evidence controller inspection. The implementation provisions or reuses caldova-orchestrator through the Foundry SDK. It is a persistent prompt agent, not portal-attached GitHub MCP, not a hosted HTTP Sandbox tool endpoint, and not a worker with cloud credentials.

Checkpoint: Identify the trusted Python controller before discussing portal configuration. Transition: walk the actual call path.

## Slide 07 · The controller owns the trust boundary

Segment 2 · Slide target 4:00 · Planned window 10:00–14:00

Target: 4:00; cumulative 14:00.

Walk each boundary. The SDK provisions/reuses the persistent Foundry prompt agent. The Python controller supplies bounded tools via a local stdio MCP bridge; trusted code performs remote ACA operations. Specialists receive no cloud credentials.

A read-only staged repository and immutable data form the baseline. Its snapshot supplies three role clones; the trusted primary is separate. Clinical and safety run separately. The primary integrates only permitted feature files and runs independent deterministic checks before governance sees the candidate.

Accepted source can progress toward a published ACR digest. Separate human approval bound to run, dataset, and image is required for authorized development deployment. The diagram does not imply attendee allocation or event release authority.

Checkpoint: Ask which component calls Azure and which cannot. Transition: inspect the small tool surface the model receives.

## Slide 08 · Small tools, exact identity, fixed verification

Segment 2 · Slide target 10:00 · Planned window 14:00–24:00

Target: 10:00; cumulative 24:00. Allocate about six minutes to segment 2’s Recorded Evidence inspection, two to the tool contract, and two to the checkpoint.

Inspect src\orchestrator\foundry.py, src\orchestrator\run.py, and src\sandbox-mcp\server.py using the guide. Read SDK creation/reuse instead of inventing a portal attachment. Any Live Exercise requires explicit facilitator authorization; the deck grants no execution authority.

Identity checks bind exact run ID, role, Sandbox, immutable dataset, and logical identity. Never accept another role/run/dataset’s report even if the narrative looks correct. verify_feature has no command arguments: trusted code fixes shell and scope so a worker cannot substitute its own passing command.

Staged source stays read-only; tests, shared modules, and frontend are protected. The code block is a contract summary, not a terminal command.

Checkpoint: Explain why a model-selected verifier command weakens the boundary. Transition: inspect persistent Sandbox state and controls.

## Slide 09 · 3 · Prepare the Sandbox baseline

Segment 3 · Slide target 1:00 · Planned window 24:00–25:00

Target: 1:00; cumulative 25:00.

The prepared primary/clones contain implemented work. Code-preserving Reuse is not an untouched starter. A genuine worker baseline has missing query functions. With no allocation authority and full retained groups, default to descriptors and Recorded Evidence; do not create or reset Sandboxes.

Checkpoint: Label starter, snapshot, retained clone, and separate primary correctly. Transition: inspect enforced controls and real HTTP evidence.

## Slide 10 · Prove the controls without weakening them

Segment 3 · Slide target 6:00 · Planned window 25:00–31:00

Target: 6:00; cumulative 31:00. Give about three minutes to the policy/egress receipts in segment 3, then discuss the boundary.

Verified controls: default-deny egress, open.fda.gov allow with Full inspection, 900-second auto-suspend using Memory, auto-delete false, UID 10001. Actual approved HTTP returned 200; denied HTTP returned 403. DNS/TLS/timeout failures cannot substitute for a policy deny response.

Never disable TLS, widen egress, or install worker credentials. Stopped Sandboxes still consume capacity. Reuse preserves code; neither lifecycle controls nor a retained clone guarantee an untouched baseline.

Checkpoint: Distinguish policy-generated 403 from transport failure. Transition: the immutable dataset, not live network retrieval, is authoritative for acceptance.

## Slide 11 · One frozen public slice, explicit source limits

Segment 3 · Slide target 8:00 · Planned window 31:00–39:00

Target: 8:00; cumulative 39:00. Allow five minutes to inspect the four-file manifest and provenance in segment 3, three for discussion/checkpoint.

Ten trials per candidate/topic; at most ten safety reports per candidate. Conservative exact generics: semaglutide, liraglutide, tirzepatide. Tirzepatide safety is empty. Original-source JSON is 74,073 bytes; frozen pipeline ZIP is 62,813 bytes. Raw 7.07 GiB DB stays in external cache, never checkout/images/Sandboxes.

Trials came from an AACT-derived Nason Hugging Face DuckDB conversion pinned September 14, 2026: the publisher’s conversion, not a CTTI-hosted original. Safety uses one disclosed openFDA 2026 Q2 shard of 12,000 reports, not the full quarter/database. No live fetch is required for acceptance.

Frozen pipeline provenance is uncommitted-development; never relabel it with a later checkout HEAD. Historical expert-review, publication, live-demo, and attendee-use flags stay false; separate later operational approval does not rewrite source-use history. “reviewed-public” means project-owner selection, not expert clinical audit.

Checkpoint: Identify the four files and explain why condition cannot filter safety. Transition: assign just two feature implementations.

## Slide 12 · 4 · Run the agent team

Segment 4 · Slide target 1:00 · Planned window 39:00–40:00

Target: 1:00; cumulative 40:00.

Default to the accepted Recorded Evidence run. Live Exercise needs explicit facilitator authorization. Do not invoke new work automatically on implemented full-capacity resources. Governance inspects only after independent integration checks and never approves release.

Checkpoint: Name the two feature authors and separate governance reviewer. Transition: inspect each role’s file scope and function contract.

## Slide 13 · Two feature authors, one governance reviewer

Segment 4 · Slide target 5:00 · Planned window 40:00–45:00

Target: 5:00; cumulative 45:00. Inspect role templates and feature contracts with segment 4.

Assigned candidate modules are backend trial_feature.py and safety_feature.py; genuine missing-function versions are under src\workers\starter. Each author edits only its assigned module, never shared query dispatch, tests, frontend, or data. Clinical and safety sessions run separately.

query_trials accepts connection, candidate, condition; query_safety_reports accepts only connection and candidate. Its lack of condition reflects the data boundary, not an omission to repair.

Governance examines the integrated candidate and responsible-use evidence. It can identify blockers but cannot approve release.

Checkpoint: Which file may safety edit, and why not trial filtering? Transition: independent verification matters even after worker-reported success.

## Slide 14 · Integrate independently before governance

Segment 4 · Slide target 8:00 · Planned window 45:00–53:00

Target: 8:00; cumulative 53:00. Give about five minutes to reading independent integration/check order in segment 4, then discuss results.

The primary does not trust worker test assertions. It independently integrates only assigned modules, checks strict source/shared-source protection and order, and runs public checks before governance inspects the candidate. Exact immutable run/role/Sandbox/dataset/logical identity binds reports.

Nine existing synthetic tests remain byte-for-byte unchanged. Eight public tests are separate, derived from original-source fields. Do not replace synthetic fixtures or weaken tests to fit public data. Honest empty safety is valid; trial/report linkage is not fabricated.

Checkpoint: Locate an independent test receipt rather than worker narrative. Transition: repair cannot reset that trail.

## Slide 15 · Repair within one shared three-attempt budget

Segment 4 · Slide target 5:00 · Planned window 53:00–58:00

Target: 5:00; cumulative 58:00. Read the bounded recovery path; do not corrupt retained prepared work for a demonstration.

Feature repair and report/schema repair share a three-attempt budget in one session with fixed identity. Report-only repair disables tools: correcting a structured report does not justify more code execution. No fresh session, reset, or weakened test can evade the limit.

The fixed zero-argument verifier remains the model’s verification path. Exhausted budget or unresolved blocker stops progression. Use real receipts, not destructive failure injection.

Checkpoint: Does report repair get a fresh budget? No. Transition: inspect the genuine accepted public run.

## Slide 16 · Accepted public run: three specialists, zero blockers

Segment 4 · Slide target 4:00 · Planned window 58:00–62:00

Target: 4:00; cumulative 62:00. Open the linked reduced bundle and use segment 4’s worksheet to inspect assignments, three worker identities, blockers, and checks.

Full accepted public run: 9bbcce44-7e7b-4889-b7e4-4081ea9893dc. All three specialists completed; zero blockers and eleven check categories. This is verified development evidence, not a fresh presentation/attendee run.

The reduced bundle excludes candidate source, raw logs, tokens, and full raw data. Do not invent token counts, per-agent latency, issue IDs, or Foundry session IDs; the accepted result does not store them. Offline joins do not rerun tests.

Checkpoint: Distinguish accepted candidate from publication/deployment authority. Transition: trace source to an immutable published image.

## Slide 17 · 5 · Build and publish

Segment 5 · Slide target 1:00 · Planned window 62:00–63:00

Target: 1:00; cumulative 63:00. Six minutes covers a recorded-run walkthrough, not a measured full build.

Default to prepared receipts. scripts\build-agent-candidate.ps1 is restricted to the maintainer registry/subscription; it is not a generalized participant publisher. Deployment helpers may refresh pull credentials. Do not invoke publication/deployment in this material walkthrough or treat it as harmless read-only work.

Checkpoint: Identify the immutable digest field rather than a mutable tag. Transition: read each separate stage’s evidence.

## Slide 18 · Publication and approval are separate steps

Segment 5 · Slide target 3:00 · Planned window 63:00–66:00

Target: 3:00; cumulative 66:00. Use segment 5 and the reduced evidence bundle to identify published image and separate approval.

Prepared ACR validation runs dsk/dsm used --no-push; their empty digest is nondeployable. Later separately authorized dsn ran eight public tests in 4.025 seconds and published sha256:e219757d2f40dd83f5445ea661aa8f56e9ff53864d34127b74acc7570306bd38.

Separate human approval tied full accepted run 9bbcce44-7e7b-4889-b7e4-4081ea9893dc, caldova-public-lab-use-v1, and this exact digest to development deployment only. The inspector checks joins/checksums; it does not authenticate the approver or evaluate release gates. Historical source-use flags remain unchanged.

Checkpoint: Which of dsk/dsm/dsn yielded a deployable digest? Transition: the application observation is another recorded stage, not permanent health proof.

## Slide 19 · Observe the deployed application honestly

Segment 5 · Slide target 2:00 · Planned window 66:00–68:00

Target: 2:00; cumulative 68:00.

The reference is caldova-research in test2 at the earlier development URL. Recorded checks covered all nine candidate/topic combinations, source/native hashes, PID 1 UID 10001, desktop/mobile, error states, and console. Diagnostic gateway exec UID 0 is not the application process identity.

Preserve observed_at in the receipt. A historical observation is not a current-live-health guarantee, event release, or attendee starter.

Checkpoint: Distinguish app runtime from diagnostic tooling identity. Transition: inspect the complete offline receipt chain.

## Slide 20 · 6 · Trace the evidence

Segment 6 · Slide target 1:00 · Planned window 68:00–69:00

Target: 1:00; cumulative 69:00.

No telemetry workbook exists. The actual tool is src\workers\inspect_evidence.py: offline stdlib checksums/cross-receipt joins, emitting JSON or static HTML with no network, candidate-code execution, or external assets.

Checkpoint: Locate the actual inspector, not a fictional workbook/issue. Transition: follow identity joins in order.

## Slide 21 · Follow one identity through every receipt

Segment 6 · Slide target 2:00 · Planned window 69:00–71:00

Target: 2:00; cumulative 71:00. Trace run/dataset/worker/check/image/approval/observed_at fields in the reduced bundle and segment 6 worksheet.

The full inspector joins accepted result, baseline/prepared descriptor, pinned manifest/frozen files, optional image, separate human approval, and startup receipt. Missing optional stages remain visible; the supplied public chain included them and passed eleven checks with zero missing stages. Six focused inspector tests passed.

The reduced summary is a verified teaching extract, not a replacement for full receipt provenance or an authenticated approver. Preserve timestamped observation; this is history, not a live replay.

Checkpoint: Point to one cross-stage identity and observed_at. Transition: make the proof boundary explicit.

## Slide 22 · Integrity verified does not mean release approved

Segment 6 · Slide target 2:00 · Planned window 71:00–73:00

Target: 2:00; cumulative 73:00. The displayed help command is safe locally from repository root with declared Python.

Use the guide’s complete pinned command. Required: result, baseline-descriptor, and manifest paths, their SHA-256 values, and purpose. Optional image-descriptor, approval, startup-receipt each need a hash when present. --format html emits static HTML. Never guess purpose or paste abbreviated slide hashes into commands.

The inspector never authenticates the approver, reruns tests, evaluates release gates, executes candidate code, uses network, or certifies current health/attendee readiness. The reduced bundle has no candidate source/raw logs/tokens/full raw data. Do not invent missing issue/session/token/timing details.

Checkpoint: State one thing proved and two not proved. Transition: retain the separate execution gaps.

## Slide 23 · Usable rehearsal material, separate execution gaps

Segment 6 · Slide target 1:00 · Planned window 73:00–74:00

Target: 1:00; cumulative 74:00.

This material supports facilitator-guided rehearsal using Recorded Evidence by default. Shared guide supports self-paced reading; narrated videos do not exist. A 75-minute target is not a measured rehearsal or cloud-operation duration guarantee.

Full event authorization/startup, starter distribution, committed provenance, and fresh dry run remain separate gaps. Skillable identity/auth/trigger/output is deliberately excluded. A future adapter must preserve infrastructure/application/frozen_data versus baseline/data_release/attendee and never reinterpret development approval as event approval.

Checkpoint: Explain why successful development evidence is not attendee readiness. Transition: close with three reusable operational practices.

## Slide 24 · Keep authority outside the model

Segment 6 · Slide target 1:00 · Planned window 74:00–75:00

Target: 1:00; cumulative 75:00 of the planned schedule.

Who controls cloud operations, who verifies integration, and who separately authorizes deployment? Trusted controller owns operations; separate primary checks deterministically; model/governance cannot approve release.

Bound work to two feature modules, retain frozen public provenance/responsible-use limitations, and carry exact identity through image/approval/observation. The lesson is operational trust, not agent confidence.

Checkpoint: Reopen the shared guide and select a separately authorized next step. Transition: end without event-release, measured-timing, or recording-readiness claims.

## Presenter controls

Serve with `npm run present`; open the printed loopback URL. Arrow keys/Page Up/Page Down navigate; Home/End jump; `S` opens the local speaker view. Allow the local popup. `Esc` opens overview. The PDF and slide images intentionally omit speaker notes. Relative guide links are served as readable source files; open the Markdown guide in your editor or repository viewer for rendered navigation.
