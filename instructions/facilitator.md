# Platform-neutral facilitator handoff

This checklist supports the presentation and participant instructions. The [Skillable panel manual](skillable.md) adds the existing profile's Windows login tokens, prepared checkout path and separate native SDK environments; [its export and publishing procedure](../scripts/README.md#skillable-instruction-panel) keeps the panel derived from the same seven segments. Azure authentication, live startup triggers and output adapters remain separate handoff work. The recorded-evidence path is available independently of those decisions. A new live participant run needs explicit scope/access and its own evidence; the current materials are not proof of a measured event dry run.

## Recorded-evidence delivery

Provide the repository and [presentation package](../presentations/README.md). Participants need PowerShell 7.2+ for local checksum/JSON examples and a browser for the static evidence viewer; they need no Azure account or raw dataset download for this path. The three files in `instructions\assets` preserve a reduced recorded chain, checksums and observation time, not original executable worker code or a fresh remote result.

Each opener gives the goal, why it matters, services and expected outcome. Keep timings as targets and explicitly say when you switch from live demonstration to recorded evidence. Missing identity/session/token telemetry is not an invitation to fabricate worksheet entries.

## Before a live exercise

| Handoff | Required proof |
|---|---|
| Authentication/scope | Facilitator supplies authenticated Azure CLI and explicit `AZURE_SUBSCRIPTION_ID`, allocated resource group and workload region |
| Permissions | Actual project-scoped Foundry agent/inference access and authorized ACA operations; management ownership alone is insufficient |
| Runtime | Working Python controller environment with `src\orchestrator\requirements.txt` dependencies and `aca` on `PATH`; no installs during the exercise |
| Frozen data | Trusted manifest SHA-256 and adjacent exact database/original JSON/pipeline ZIP; no live rebuild or full raw-source download |
| Application | Separately approved genuine starter image and exact scoped image/state readiness; the retained development reference is not a starter |
| Worker baseline | Explicitly authorized available group with four free slots, protected prebuilt source/toolchains and genuine missing-function verification |
| Execution | Facilitator confirmation for planning, new allocation and bounded worker execution; separate publication and exact-image deployment authorization |
| Evidence | Accepted result plus its original-byte hash, baseline descriptor/prepared manifest and independent pins, optional image/approval/observation receipts |

The startup application pins are documented in [maintainer startup settings](../scripts/README.md#pinned-application-readiness). Region and resource-group name remain the only visible deployment configuration. The harness/facilitator owns immutable dataset/image settings; do not expose secrets in command arguments, files or screenshots.

Retained test-1 and test-2 groups are full. Their verified public workflow used test-2 Foundry with explicitly bound test-1 Sandboxes, a maintainer-only arrangement that is not proof of attendee single-scope access. Do not copy those IDs into a new exercise or implicitly authorize deletion/capacity changes.

## Maintainer controller execution

`validate-agent-workflow.ps1` is an existing azd-based launcher. It selects one named environment and derives both Foundry and Sandbox scope from that environment:

```powershell
.\scripts\validate-agent-workflow.ps1 -EnvironmentName $authorizedEnvironmentName `
    -ManifestPath $preparedManifestPath -Mode plan -UseWsl
```

Worker mode additionally needs explicit bindings, separate validation primary and `-ApprovePlan`. `-UseWsl` passes a short-lived Foundry-only token through stdin, never a token file or command argument. It uses the existing `.venv-linux` interpreter; do not claim the Windows ARM stdlib environment can run Agent Framework. The deliberate mixed-scope retained run used the direct controller entry point instead, not this one-environment wrapper.

The participant live snippets use a supplied supported native controller runtime on `PATH` and Azure CLI credentials. Choose and verify the delivery runtime before the session, not in front of participants. The planning command provisions/reuses a persistent agent; it is not read-only.

## Build/deployment handoff

The current candidate build helper is restricted to the authorized maintainer registry/subscription/repository. Do not promise it as a generalized participant publisher. Follow [accepted candidate packaging](../scripts/README.md#agent-built-candidate), preserve ACR output/log identities and record separate image-bound human approval before deployment. The deployment helper may refresh a scoped pull credential and mutate the app; run it only with explicit authorization.

Supply a trusted baseline-descriptor pin for Segment 6 as `$baselineDescriptorSha256`; bind it to the original accepted run rather than reusing a later rewritten descriptor. Build-time false flags and historical source-use flags must remain unchanged. Use a new timestamped pinned startup observation for any claim about the current image.

## Delivery acceptance

Before calling a fresh live participant path ready, measure all seven segments with a new tester and available authorized resources. Resolve image/data distribution, committed pipeline provenance and effective model capacity independently of slides. The presentation and recorded-evidence guide can be reviewed now; final recording readiness additionally needs the agreed capture workflow and successful live delivery rehearsal.
