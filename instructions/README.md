# Attendee instructions

## Caldova Research Preview Factory

In this 75-minute lab, a Microsoft Foundry orchestrator assigns bounded work to specialist agents running in isolated Azure Container Apps Sandboxes. The agents add a research panel to Caldova's application. You inspect the isolation and outbound controls, follow deterministic validation, and connect the accepted source to an approved image on Azure Container Apps Express.

The same seven segments support facilitator-guided delivery and self-paced study. Speaker notes and slides are in [the presentation package](../presentations/README.md). Narrated videos are not yet available.

**The core guide is platform-neutral.** The [Skillable panel manual](skillable.md) adds the profile's Windows login controls, the prepared VM checkout location and explicit controller/application interpreters. Its default remains recorded evidence; publishing the panel does not establish Azure authentication, starter/artifact distribution or live attendee readiness. Use the recorded-evidence path without a raw dataset download or resource allocation. The optional live path requires facilitator-prepared, explicitly authorized resources and a supported controller runtime; [the facilitator checklist](facilitator.md) defines the handoff. The maintainer public workflow and read-only application/data readiness are verified, but a fresh participant dry run and the proposed 75-minute schedule are not yet measured. A completed reference is not an untouched starter, and material availability is not attendee-release approval.

## Choose your path

| Path | What you do | What it proves |
|---|---|---|
| **Recorded evidence (default)** | Verify the bundled JSON/HTML checksums, follow all seven segments, inspect the recorded assignments/checks/image/approval/observation | You can explain and audit the verified development workflow; it is not a newly executed run |
| **Live exercise** | Use a facilitator-provided scope, starter, controller runtime and authorized baseline/build operations | New execution must produce its own evidence and exact-image approvals; the retained demo's receipts cannot approve it |

For recorded evidence, open PowerShell 7.2+ at the repository root. Run Segment 0's local checksum checks, then keep `$evidence` and `$evidenceDirectory` in that terminal across the following segments. The HTML viewer is self-contained and needs no network. A Python 3.12+ interpreter is needed only to run the full receipt inspector with the separately provided original files; the small bundled summary does not contain candidate code, raw execution logs or the four-file dataset.

The repository root is the directory containing `azure.yaml`, `instructions` and `scripts`. Do not run commands from the enclosing checkout folder. All commands below use Windows PowerShell paths. Linux controller execution uses the equivalent native paths, or the already-tested maintainer WSL launcher described in the facilitator checklist.

## What to retain

Use [the checkpoint worksheet](worksheet.md) to record the run, dataset, manifest/logical hashes, snapshot/worker/primary IDs, acceptance/egress evidence, immutable image, separate approval and observation time. Do not invent an issue number, committed source revision or Foundry session ID when the supplied evidence does not contain one. The bundled evidence manifest contains reproducible file hashes, not a digital signature.

## Lab schedule

| Segment | Time | Primary service | Outcome |
|---|---:|---|---|
| [0. Welcome and readiness](00-welcome-and-readiness.md) | 5 minutes | Supporting services | The execution path and pinned evidence/data identities are clear |
| [1. Open the research portal](01-open-research-portal.md) | 4 minutes | ACA Express | Starter and completed-reference states are distinguishable |
| [2. Configure the orchestrator](02-configure-orchestrator.md) | 15 minutes | Foundry Agent Service | The orchestrator has approved tools and a reviewed plan |
| [3. Prepare the Sandbox](03-prepare-sandbox.md) | 15 minutes | ACA Sandboxes | A tested baseline snapshot is available |
| [4. Run the agent team](04-run-agent-team.md) | 23 minutes | ACA Sandboxes | Three workers produce a validated release candidate |
| [5. Build and publish](05-build-and-publish.md) | 6 minutes | ACR and ACA Express | The approved image is live |
| [6. Trace the evidence](06-trace-the-evidence.md) | 7 minutes | Recorded workflow receipts | Recorded source-to-image-to-application identities are auditable |

## Service allocation

| Area | Minutes | Share |
|---|---:|---:|
| ACA Sandboxes | 38 | 50.7% |
| ACA Express | 7 | 9.3% |
| Foundry Agent Service | 15 | 20.0% |
| Other services | 15 | 20.0% |
| **Total** | **75** | **100%** |

## Lab environment

Use the dedicated product portals for the relevant exercises:

- ACA Sandboxes: `http://sandboxes.azure.com/`
- ACA Express: `https://containerapps.azure.com/`

The live path starts with prepared resources and explicitly supplied authentication. Platform-specific authentication/trigger/output configuration is intentionally outside these instructions. Use Segment 0's structured report, the facilitator handoff and actual data-plane checks rather than assuming that an elapsed wait establishes readiness. Never reuse the retained demo's Sandbox IDs for a fresh participant run.

## Data used in the lab

The lab uses one versioned, read-only dataset shared by all attendees. Your primary Sandbox stages the artifact once. The worker clones inherit it from the baseline snapshot.

The development preview uses the frozen `caldova-public-lab-use-v1` package: 60 trial records and 20 adverse-event reports across three exact-name candidate selections. Trial records come from the pinned September 14, 2026 AACT-derived DuckDB conversion by Nason; report records come from one disclosed openFDA 2026 Q2 export shard. Neither source is queried live by the application, and the report selection is not complete or representative.

The small package includes a database, manifest, original source-record JSON and frozen pipeline-source ZIP. Attendees must not download the full 7.07 GiB raw AACT-derived database into their checkout or Sandboxes. Trial conditions select trials only; they do not filter safety reports, link reports to trials or imply causation. The selected shard has no retained tirzepatide reports, which the portal displays honestly.

The project owner separately approved the exact development image. The historical dataset flags remain unchanged. Attendee distribution/release still needs committed pipeline provenance and a validated delivery contract; those decisions are not implied by the recorded-evidence materials. See [the data-source record](../data/sources/README.md) for pinned identities, coverage and the separate source-use decision.
