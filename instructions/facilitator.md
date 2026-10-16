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

The default build path publishes the accepted agent source in the participant's allocated ACR. Supply explicit subscription, resource group and registry; the candidate helper verifies the current scoped LAB722 registry before building, permits a verified first repository and refuses tag overwrite. The old no-group form remains maintainer-only. Follow [portable image/data delivery](../scripts/README.md#portable-image-and-data-delivery), preserve ACR run/digest identities and record separate image-bound approval before deployment. Portable deployment requires `-AuthorizeDeployment` and the exact allocated Express environment. It may refresh a repository-scoped pull credential and mutate only that scoped app.

An explicitly labelled reference deployment can instead use `simon.azurecr.io/lab722-$AppName@sha256:...`. Supply an actually published, independently verified digest and legitimate read-only pull access; this is not a claim that the participant's generated source was deployed. The scripts neither grant participant writes in Simon's registry nor enable anonymous access. The reference repository/digest and cross-tenant pull path still need publication/live validation.

Before offering the [ready-made-image recovery path](05-build-and-publish.md#recovery---use-the-ready-made-reference-image), publish/test the v2 image, bind its digest to the bundled dataset, and verify pulling it from the actual attendee scope. Supply that digest as `$approvedReferenceDigest` and inject only repository-scoped read-only credentials after launch. Do not distribute an old v1 digest with v2 data pins. For an untouched ready-made starter, use its separately verified digest with `PreviewState=starter`; the completed reference is not a substitute for the starter exercise. Until these assets/access are verified, the honest fallback is recorded evidence, not a promised available image.

For VM delivery, clone the fork and stage the pinned v2 bundle on a **clean, credential-free VM before capturing it**. `stage-lab-data.ps1 -ConfigureSession` makes the same offline checked handoff available to a facilitator, Skillable harness or participant shell; it does not create Sandboxes or capture a VM. Repeat the session configuration after each launch. Do not snapshot the currently Azure-authenticated test instance or bake GitHub/registry credentials into the image. The v2 bundle contains 168 trials and 38 reports; its source-use/distribution confirmation is not proof of the still-pending live startup, IAM and timed walkthrough.

Supply a trusted baseline-descriptor pin for Segment 6 as `$baselineDescriptorSha256`; bind it to the original accepted run rather than reusing a later rewritten descriptor. Build-time false flags and historical source-use flags must remain unchanged. Use a new timestamped pinned startup observation for any claim about the current image.

## Delivery acceptance

Before calling a fresh live participant path ready, measure all seven segments with a new tester and available authorized resources. Resolve image/data distribution, committed pipeline provenance and effective model capacity independently of slides. The presentation and recorded-evidence guide can be reviewed now; final recording readiness additionally needs the agreed capture workflow and successful live delivery rehearsal.
