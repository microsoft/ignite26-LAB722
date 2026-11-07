# Lab delivery and maintainer scripts

These scripts support repeatable development and rollout validation. The platform-neutral `start-lab.ps1 -Mode Readiness` is the read-only harness/facilitator check used in the first instruction segment. Authorized participants can publish into their allocated LAB722 registry using explicit scope; platform startup still does not silently build images or perform the participant's Sandbox preparation.

The repository's `.gitattributes` preserves authored bytes across Windows and Linux checkouts. Do not apply automatic line-ending conversion to checksummed source or evidence; changes require new validation and provenance, not replacement trust anchors.

**Verified development evidence:** public agent-built v1 run `9bbcce44-7e7b-4889-b7e4-4081ea9893dc` was approved and deployed as a development preview. All three specialist sessions, independent eight-test public acceptance, full-source/shared-record/ordering and real egress checks passed. After separate publication authorization, ACR run `dsn` passed eight public tests and published digest `sha256:e219757d2f40dd83f5445ea661aa8f56e9ff53864d34127b74acc7570306bd38`; subsequent exact-image deployment approval replaced the test-2 preview. Recorded API/source/runtime checks passed; this paragraph is not a new live-health observation. Earlier synthetic and rejected-candidate entries below are retained history. Separately, [the v2 image catalog](../data/lab-images.json) records newly published ready-made starter/reference images and container/anonymous-pull verification. It does not claim a new agent-accepted run, allocated Express deployment, Skillable access/source-data capture, fresh timed rehearsal or recording readiness.

| Script | Purpose |
|---|---|
| `export-skillable-instructions.ps1` | Generate the paged Skillable panel manual from the participant sources, with a separate welcome page and VM login controls |
| `initialize-lab-desktop.ps1` | During learner-VM preparation, create PowerShell 7 and Windows Terminal shortcuts that open the prepared checkout; requires both tools already installed |
| `compile-arm.ps1` | Compile the full Skillable ARM template, or the existing-resource runtime template with `-RuntimeOnly` |
| `start-lab.ps1` | Validate/provision infrastructure, inspect opt-in readiness, prepare only the primary for the portal exercise, or explicitly prepare a complete baseline |
| `stage-lab-data.ps1` | Verify or idempotently stage the versioned checkout dataset offline; optionally configure the current process for startup/Prepare |
| `deploy-test.ps1` | Create/update an `azd` test environment, explicitly deploy the simplified runtime into existing infrastructure, or verify/bootstrap its Toolbox |
| `validate-foundry.ps1` | Verify project-scoped agent access and a bounded live Responses inference contract |
| `validate-agent-workflow.ps1` | Validate planning/tool dispatch or run scoped implementors, independent integration, and governance against an explicit prepared baseline |
| `validate-sandbox.ps1` | Configure `aca`, create or reuse a Sandbox, and verify execution, egress, snapshot identity, and clone filesystem inheritance |
| `deploy-express-smoke.ps1` | Create a small Express application with bounded retry and verify its HTTPS endpoint |
| `deploy-lab-starter.ps1` | Pin the existing portal starter to its catalog digest; explicit Create mode is a one-time learner-authorized fallback in an existing Express environment |
| `build-research-image.ps1` | Run the nine containerized data/API checks in ACR, then build a Linux AMD64 starter or reference image and return its digest |
| `build-developer-image.ps1` | Build the genuine frozen-data Python/Node starter, or the separately selected tested reference; return the digest and source-context pin |
| `prepare-worker-baseline.ps1` | Read-only capacity/primary checks; explicit legacy preparation/reuse or a fresh verified public-data `RuntimeSeed` |
| `connect-lab-workers.ps1` | Verify and register portal-created snapshot/clones from a pinned prepared-primary descriptor; create replacement resources only with explicit `-CatchUp` |
| `build-agent-candidate.ps1` | Stage only the accepted specialist source and exact frozen artifact, then validate/build an unapproved digest-pinned candidate |
| `deploy-research-preview.ps1` | Configure repository-scoped image credentials, deploy a digest-pinned research preview, and verify its health and state |

The scripts do not remove resource groups, Sandboxes, snapshots, or applications. Cleanup requires explicit project-owner approval.

For the user-supplied AACT mirror, the maintainer module `python -m data.pipeline.download_aact` downloads the pinned raw database into an external local cache, never the checkout. `--check` verifies availability and advertised size without downloading it. This is separate from staging the small approved attendee artifact; see [raw source cache commands and review boundaries](../data/sources/README.md#raw-aact-source-cache).

After acquisition, `python -m data.pipeline.extract_public` uses the existing data-aware runtime to prepare a bounded, checksum/provenance-bound **unreviewed** draft outside the checkout. Its conservative mapping, strict record limits and source fidelity are tested; it does not build an approved artifact, update startup or deploy the app. See [review draft commands and human approval requirements](../data/sources/README.md#conservative-public-review-draft).

`python -m data.pipeline.freeze_public` builds a public artifact using the project owner's recorded approval for the exact selected draft/provenance. It preserves original fields, validates complete records and stages four frozen files; the freeze command itself never publishes or deploys. `--pipeline-commit` additionally requires every allowlisted source byte to match that full Git commit. The retained v1 has 60 trials and 20 reports; the new v2 slice has 168 trials and 38 reports. See [versioned v2 delivery](../data/sources/README.md#versioned-v2-lab-bundle). Neither generation nor distribution rewrites historical source-use flags or proves attendee readiness.

## Simplified runtime deployment

The approved runtime is key-authenticated, single-allocation analysis with no learner sign-in or partner exercise. `deploy-test.ps1 -DeployRuntimeApp -RuntimeMode analysis` uses the current clean descriptor, fixed clone A and approved immutable image. It removes the Sandbox group identity, reuses the four existing scoped grant names supplied for adoption, and submits the access key directly to ARM in memory. Updates reuse the app's existing key unless an explicit SecureString replacement is supplied.

`-ConfigureRuntimeToolbox -RuntimeMode analysis` bootstraps or verifies the separate `runtime-analysis-toolbox`, exposing only `execute_python` through `runtime-analysis-backend`. Its default proof mode remains backward compatible and never updates an existing incompatible Toolbox. No automatic version churn, role broadening or production deployment is part of either action.

Prepare A before deployment; learners can create B from the clean snapshot if capacity is available. Do not bind the app to the clean seed, clone an active A, or let a model choose an Azure target. See [single-allocation deployment](../infra/README.md#single-allocation-generated-analysis) for the command sequence, secret channel and execution bounds.

## Clean runtime seed

`RuntimeSeed` prepares the runtime experiment, not the tagged manual-primary exercise. It creates one fresh public `python-3.13` instance, copies only the pinned v2 manifest, source-record JSON and DuckDB file, makes the data read-only to UID 65534, and verifies an empty writable `/workspace` before snapshot capture. The input verifier uses the already-prepared Python interpreter's standard library; it installs nothing.

From the repository root, with a prepared native ACA CLI and explicit provisioning authorization:

```powershell
.\scripts\prepare-worker-baseline.ps1 -Mode RuntimeSeed `
    -SubscriptionId $subscriptionId -ResourceGroup $resourceGroup `
    -Region $region -GroupName $sandboxGroup `
    -OutputDirectory '.build-contexts\runtime-seed-new' `
    -AcaExecutable $aca -AuthorizeProvisioning -AsJson
```

The helper checks actual group capacity before creating one retained seed. Success returns a `runtime-seed.json` descriptor with seed/snapshot IDs, three hashes, the fixed execution prefix and explicit unverified identity/tenant fields. Failure retains `seed-id.json`; it does not allocate a replacement on retry. To verify and capture that exact retained clean seed, add `-PrimaryId $retainedSeedId` and use a new output directory. Resume requires the `LAB722`/`runtime-clean-seed` labels, verifies the existing data/workspace/policies and does not recopy or clear files. It creates a snapshot only after those checks pass.

Use the descriptor's execution prefix:

```text
runuser -u nobody -- env -i PATH=/opt/python/3/bin:/usr/bin:/bin HOME=/workspace /opt/python/3/bin/python3 -I
```

`runuser` alone inherits Azure-injected identity variables. The cleared child environment prevents that inheritance; it is not a demonstrated denial of every discoverable platform identity mechanism. Do not expose credential values to learners. This seed verifies standard-library data inspection, not DuckDB query dependencies or generated code.

On November 6, the clean seed/snapshot and two separate clones passed live data-hash, writable-state separation, non-root write-denial, restored egress, exit-19 and explicit stop/resume checks in `ig2026-lab-testing`. All resources are retained and the group has four of four slots allocated; do not repeat fresh preparation there. The existing proof app still uses its original fixed Sandbox, not the new exercise clone.

For the optional app/identity/connections template and idempotent Toolbox setup, see [runtime proof preparation](../infra/README.md#optional-runtime-proof-preparation). Neither helper modifies the old learner instructions, enables runtime by default, publishes an image or configures learner sign-in.

## Portable image and data delivery

The normal image path is unchanged: agents implement the two application queries, independent validation accepts their source, and the candidate helper builds it in the participant's allocated ACR. Supplying `ResourceGroupName` opts into portable publication. Before any ACR build, the helper verifies the explicit subscription, exact registry resource ID, `lab=LAB722` tag, provisioning state and real login server. A successful empty repository inventory permits the first image; authentication/inventory failures never mean "repository absent." Existing tags are not overwritten. Omitting the group retains the original maintainer-only guard. `-StageOnly` and `-WhatIf` remain offline.

The candidate helper queues one build with `--no-wait`, prints its run ID and scoped log command immediately, and polls that same run with elapsed-time updates. Its bounded wait neither cancels the build nor retries publication. Run the printed `az acr task logs` command directly, without a pipe: some Windows Azure CLI installs fail to encode Unicode build logs when redirected. A descriptor is written only after the existing image/context checks and successful container acceptance.

ACR responses may expose run metadata directly or under `properties`; the helper handles both. If a previously queued build succeeded but local descriptor creation failed, follow the guide's recovery block with `-ResumeAcrRunId` and `-OriginalBuildContext`. Recovery verifies that original pinned context and existing run in a fresh staging directory; it never queues another build. Ship this helper with the guide in the captured attendee image, not just as an update to an already-running VM.

Clone the completed fork onto a **clean, credential-free VM**, stage the dataset, then capture that VM. The checkout ships the four-file v2 bundle and [release pin](../data/lab-release.json); the raw multi-GiB inputs stay outside it. Run from the repository root using the prepared Python interpreter:

```powershell
.\scripts\stage-lab-data.ps1 -ValidateOnly
$dataset = .\scripts\stage-lab-data.ps1 -ConfigureSession
$dataset | Format-List
```

This uses only Python's standard library, makes no network/Azure calls, verifies all four files and their original-source/provenance binding, stages atomically, and reuses only an already identical destination. Corrupt data fails without replacement. The default staging destination is `data\artifacts\lab-use-v2`; `-Destination` permits an explicit machine-local alternative. `-ConfigureSession` sets the existing `LAB_STARTUP_PURPOSE`, `LAB_DATA_MANIFEST`, `LAB_DATA_MANIFEST_SHA256` and `LAB_PYTHON_EXECUTABLE` in the current process only. A later PowerShell session or Skillable launch must call it again or receive the verified values from the harness.

Provision infrastructure separately with `azd up` or explicitly authorized `start-lab.ps1 -Mode Provision`, then use `Readiness` outputs for image scope. Learners deploy the public catalog starter themselves in the new Container Apps Express portal, using its versioned acateam tag and port 8080. The confirmed `deploy-lab-starter.ps1 -PinExisting` step then pins that same app to the catalog digest before readiness. Do not predeploy their `caldova-research` app. For maintainer image publication, the existing `build-developer-image.ps1` accepts the staged manifest, its release SHA and `public-lab-development` purpose. Its default `-PreviewState starter` retains the genuinely missing functions; explicit `-PreviewState reference` selects the separate reference-acceptance release target. Both return their exported source-context manifest SHA-256. The published v2 choices are pinned in [lab-images.json](../data/lab-images.json); old v1 starter/reference images cannot pass v2 data checks. Segment 3 exposes source export and native `aca.exe` disk/primary/lifecycle commands, then learners capture the snapshot and create the three clones in the portal. Staging the VM does not perform that learning exercise.

Use **West US 3** for the portal app, matching the allocated lab infrastructure. `-PinExisting` discovers only the existing same-scope app's actual healthy Express environment, accepts only the supplied starter tag/digest, and never creates another app. Readiness retains that actual target and `CALDOVA_APPLICATION_REGION` for later updates without changing the infrastructure region. If portal creation itself is blocked, the separate learner-authorized Create fallback verifies the allocated subscription, environment identity, `lab=LAB722` and Express mode before one create. Region is checked only when explicitly supplied. It refuses an existing app, never creates an environment or changes permissions, and does not retry failures. Inspect retained operations before retrying. This starter-only confirmation is not authorization for the later participant-built candidate; the learner separately reviews its digest and target.

After publication and a **separate approval of the exact image digest**, deployment no longer requires an azd environment:

```powershell
$imageTarget = @{
    SubscriptionId = [guid] $readiness.outputs.AZURE_SUBSCRIPTION_ID
    ResourceGroupName = $resourceGroupName
    RegistryName = $readiness.outputs.AZURE_CONTAINER_REGISTRY_NAME
    ExpressEnvironmentName = $readiness.outputs.EXPRESS_ENVIRONMENT_NAME
}
.\scripts\deploy-research-preview.ps1 @imageTarget -ImageDigest $approvedDigest `
    -PreviewState reference -AuthorizeDeployment
```

The optional known-working source is explicit, not a substitute for publishing the participant's accepted code:

```powershell
$sharedImages = Get-Content -LiteralPath '.\data\lab-images.json' -Raw | ConvertFrom-Json
if ($sharedImages.dataset.manifest_sha256 -cne $env:LAB_DATA_MANIFEST_SHA256) {
    throw 'The ready-made reference does not match the configured frozen dataset.'
}
# Obtain separate authorization for this exact catalog digest and allocated target.
$approvedReferenceDigest = $sharedImages.images.reference.digest
.\scripts\deploy-research-preview.ps1 @imageTarget -ImageDigest $approvedReferenceDigest `
    -ImageSource ReferenceRegistry -AppName $sharedImages.application_name `
    -ReferenceAnonymousPull -PreviewState reference -AuthorizeDeployment
```

The catalog distribution endpoint is **`acateam.azurecr.io/lab722/caldova-research`**. `ReferenceRegistry` uses this fixed repository and an immutable digest. The legacy `SimonRegistry` route remains available for explicitly selected historical images at `simon.azurecr.io/lab722-<app-name>`. Neither route creates scope maps/tokens, enables anonymous/admin access, or grants participant writes in the shared registry. For a private image, the facilitator supplies a verified repository-scoped read-only token through `LAB_REFERENCE_PULL_USERNAME` and `LAB_REFERENCE_PULL_PASSWORD` in memory; keep it out of the VM snapshot, arguments, transcripts and files. Remove those process variables after use. `-ReferenceAnonymousPull` is only for a separately approved, **already-public** image; it does not enable public access. There is no fallback from private pull failure.

The October 14 inventory predated publication. On October 20, ACR runs `cfay` and `cfax` published the genuine v2 starter and ready-made reference from clean source revision `e758f52d73970f6f22e9ceee9469cffb2c4953a1`. Independent runtime run `cfb0` checked 35 source/data files and all nine native API candidate/topic selections per image, exact supplied logo bytes, default commands and PID 1 UID 10001; the starter's protected missing functions and all eight reference acceptance tests passed. On October 21, run `cfb1` pulled both exact digests using an empty Docker credential configuration and source-registry authentication mode `None`. The registry already had anonymous pull enabled; no token or access-policy change was made. ACR anonymous access is registry-wide, not specific to these lab images.

On October 30, both original image digests were copied byte-for-byte to acateam under the catalog's readable versioned tags. The destination already allowed anonymous pulls; publication changed no access settings. Destination distribution verification is recorded separately in the catalog; original runtime receipts still describe the unchanged source image bytes.

Use `-ReferenceAnonymousPull` for these catalog images; no registry username/password is required. Do not set `LAB_REFERENCE_PULL_USERNAME` or `LAB_REFERENCE_PULL_PASSWORD` for that mode. The same path can deploy the separately approved catalog starter digest with `-PreviewState starter`; a completed reference is not a substitute.

These checks prove published container behavior and credential-free pull access, not an allocated Express deployment, participant-VM pull, fresh Skillable launch or effective learner roles. Deployment output identifies `ImageSource` and does not claim to verify participant-generated source. For catalog application readiness, set `LAB_APPLICATION_IMAGE_SOURCE=ReferenceRegistry`; its default is `LabRegistry`. Reset that source when returning to a participant-built image. All paths require the exact dataset pins and preserve `attendee_ready=false` until the separate delivery gates pass.

## Skillable instruction panel

The lab checkout source of truth is `main` in the private `simonjj/ignite26-LAB722` fork. A published feature branch alone does not update what a normal clone receives. Stage the completed checkout at `C:\Users\LabUser\code\ignite26-LAB722` using authorized GitHub access; preserve existing user work and fast-forward an existing clean checkout rather than cloning over it. Do not put GitHub credentials into the shared VM image.

Regenerate the versioned panel manual whenever its source instructions change:

```powershell
.\scripts\export-skillable-instructions.ps1
```

The export writes `instructions\skillable.md` as UTF-8 without a BOM. It adds a short welcome page with the VM login tokens exposed by LAB722 profile 224872's editor (`Win11-Pro-Base` is the instance's token name). The welcome is section 1; source H1-H3 headings continue the same hierarchy so learner help references match the panel and VM files. Keep `@lab.Title` as a token and never rename the lab profile while publishing instructions. Each source begins a page; `<!-- pagebreak -->` starts another logical page with its own level-one heading. The returned `Pages` count includes the welcome and all internal breaks. Commands, including the prepared native runtime paths and code inside the quoted `[+Help]` catch-up note, are preserved exactly from their sources rather than rewritten for Skillable.

Repository links become local VM file references; the panel must not request private repository documents as relative Skillable URLs. Relative images, missing references, repository-escaping links, unclosed fences, page breaks inside code, and pages without titles stop export.

In a running lab, use the tiny gear at the **top right of the instruction panel**, select **Edit Instructions**, and load the generated `instructions\skillable.md` as the editor's full Markdown content. Review any unexpected authored profile changes before replacing an older generated manual. Uploading a file attachment and leaving only a `[skillable.md](...)` hyperlink does not install the walkthrough inline. Save the changes, refresh the panel and inspect every page, Next/Previous navigation, code blocks and resolved VM login typing controls. Reopen the profile's editor to confirm the saved content matches the intended export. This updates instructions independently of a VM disk capture; when no lab is running, saved-editor inspection is not a substitute for the fresh rendered-panel check.

The participant guide leads with a hands-on sequence and assumes the prepared checkout, native environments, desktop shell shortcuts, allocated infrastructure and effective learner access. The participant creates the starter app in the Express portal. Verify the setup using the [facilitator checklist](../instructions/facilitator.md) before delivery. The recorded example is a comparison or catch-up activity, not the default exercise. Publishing the panel does not update the platform's ARM template or VM image, nor complete access, fresh-launch or timed-walkthrough checks. Source staged after a tools-only image capture still needs a separately verified future-launch delivery mechanism.

## Platform-neutral startup

The only visible deployment configuration is **region** and **resource-group name**. The entry point requires PowerShell 7.2 or later, Azure CLI, and the generated ARM template. Before invocation, the harness authenticates Azure CLI, supplies `AZURE_SUBSCRIPTION_ID`, and creates or allocates the resource group. The script never falls back to the maintainer subscription, selects an `azd` environment, changes the CLI account, or looks up the signed-in user in Microsoft Graph.

```powershell
.\scripts\start-lab.ps1 -Region westus3 -ResourceGroupName $resourceGroupName
.\scripts\start-lab.ps1 -Region westus3 -ResourceGroupName $resourceGroupName -Mode Readiness
```

The default `Validate` action checks the supplied scope and generated ARM template without provisioning. `Readiness` inspects authoritative successful deployment outputs and scoped resources; output names and endpoints are derived, not attendee inputs. `Provision` is an explicit operational choice for a genuinely fresh supplied scope:

```powershell
.\scripts\start-lab.ps1 -Region westus3 -ResourceGroupName $freshResourceGroupName -Mode Provision
```

Do not use this fresh-scope path to update retained environments. Existing LAB722 tags identify the explicit environment name for read-only checks, and conflicting names or reuse during provisioning are rejected rather than renaming resources or resetting the test-2 capacity overrides. Maintainers continue to use their existing `azd` configuration.

`-Region` selects the workload resource location, not the resource group's metadata-storage location. A harness-allocated group can validly have a different metadata location; existing tagged workload resources and deployment outputs must still match the requested region. `-TimeoutSeconds` is a bounded execution control, not another deployment input; its default is 900 seconds. A timeout does not cancel a submitted Azure deployment, so inspect its reported scope before retrying.

The optional harness-owned `LAB_USER_PRINCIPAL_ID` and `LAB_USER_PRINCIPAL_TYPE` provide an explicit principal mapping only. With no principal supplied, role assignments are skipped. Authentication as the deployment principal is not proof of attendee data-plane access. No Skillable replacement token or current identity/trigger contract is assumed.

Structured readiness deliberately distinguishes infrastructure from a usable attendee lab. The script verifies the current registry, Foundry account/project/model, Express environment, and Sandbox group by scoped resource ID and provisioning state; a historical successful deployment alone is insufficient. Application verification is now opt-in as described below, but application provisioning, attendee-releasable data, effective event capacity and the actual attendee identity/trigger/output adapter remain unresolved. A fresh complete `Prepare` has not passed end to end. Neither infrastructure nor development application readiness is an attendee-ready or recording-ready signal.

On October 9, 2026, eight focused offline regression groups passed, including missing harness context, conflicting scope, retained-scope provisioning refusal, native failures/timeouts, SDK output casing, distinct resource-group metadata location, and missing/failed current resources. Actual `Validate` and `Readiness` executions passed against `ignite-lab-test-2`, preserving its explicit names. Readiness reported `infrastructure_ready=true` while application/data/attendee readiness remained false, and emitted only allowlisted outputs. ARM validation of both the omitted environment-name default and preserved test-2 naming/capacity also passed without deploying. `Provision` is offline-tested only; fresh-scope startup still requires a separately authorized live validation.

### Pinned application readiness

`Readiness` retains its infrastructure-only behavior when no application settings are supplied. Any supplied application setting opts into the complete set below; partial, empty or malformed pins fail rather than selecting an observed image or ignoring the request. The harness owns these settings. A configured digest is an expected identity, not a new human release/deployment approval.

| Harness setting | Required application check |
|---|---|
| `LAB_APPLICATION_NAME` | Exact existing container app in the supplied subscription/resource group |
| `LAB_APPLICATION_IMAGE_DIGEST` | Lowercase `sha256:` digest expected in the explicitly selected image source |
| `LAB_APPLICATION_IMAGE_SOURCE` | `LabRegistry` (default: verified allocated ACR, `caldova/research-portal`), `ReferenceRegistry` (catalog at `acateam.azurecr.io/lab722/caldova-research`), or legacy `SimonRegistry` (`simon.azurecr.io/lab722-<app-name>`) |
| `LAB_APPLICATION_ENVIRONMENT_SOURCE` | `Allocated` (default: exact Bicep environment) or `Portal` (verify the exact app/environment share the allocated subscription/group and each other's region, with a healthy Express environment, then retain that actual target for updates) |
| `LAB_APPLICATION_PREVIEW_STATE` | Exactly `starter` or `reference`; a completed reference cannot pass a starter request |
| `LAB_STARTUP_PURPOSE` | Explicit `synthetic-development` or `public-lab-development`, never attendee release |
| `LAB_DATA_MANIFEST` | Locally staged frozen manifest with its adjacent database and, for public data, original JSON/pipeline ZIP |
| `LAB_DATA_MANIFEST_SHA256` | Independently trusted lowercase manifest SHA-256; do not derive it from an unverified live endpoint |
| `LAB_PYTHON_EXECUTABLE` | Optional supplied Python 3.12+ interpreter; the check uses only the standard library |

After the six infrastructure checks, startup reads only allowlisted app metadata: exact scoped ID/type/location, running/provisioning states, Express environment, one image and public ingress. It requests no registry secrets, environment variables, new credentials or role grants. `src/workers/check_application.py` reuses the frozen-contract checks, verifies exact local bytes without executing candidate code or importing DuckDB, and checks HTTPS health, full manifest, public original-source/decision identity, and one ready/unavailable sample. Redirects, cached/non-JSON/oversized responses, mismatches and network failures fail explicitly. The entire native check is deadline-bounded within startup; no failed operation is silently retried.

For the already-approved retained **development reference only**, the following reproduces the current local pins after the existing Azure sign-in and explicit subscription are supplied:

```powershell
$env:LAB_APPLICATION_NAME = 'caldova-research'
$env:LAB_APPLICATION_IMAGE_DIGEST = 'sha256:e219757d2f40dd83f5445ea661aa8f56e9ff53864d34127b74acc7570306bd38'
$env:LAB_APPLICATION_PREVIEW_STATE = 'reference'
$env:LAB_STARTUP_PURPOSE = 'public-lab-development'
$env:LAB_DATA_MANIFEST = Join-Path $env:LOCALAPPDATA 'Caldova\artifacts\public-lab-use-v1-20261010\data-manifest.json'
$env:LAB_DATA_MANIFEST_SHA256 = '22a6ef07b06bbb7e8829d51ea5d0612c2122ffab786d4edbbd75d3a80a4d8039'
$env:LAB_PYTHON_EXECUTABLE = (Resolve-Path '.\.venv\Scripts\python.exe').Path
.\scripts\start-lab.ps1 -Region westus3 -ResourceGroupName ignite-lab-test-2 -Mode Readiness
```

Successful checks publish `CALDOVA_APPLICATION_NAME`, `CALDOVA_APPLICATION_URL`, `CALDOVA_APPLICATION_IMAGE`, `CALDOVA_APPLICATION_REGION` and the nested `application` receipt. Portal checks also replace `EXPRESS_ENVIRONMENT_NAME` with the verified actual app environment, without replacing the infrastructure's `AZURE_LOCATION`. `application_ready`, `application_manifest_verified` and `frozen_data_verified` can be true. `baseline_ready` remains false because this read-only invocation did not inspect the worker baseline; `data_ready` and `attendee_ready` remain false because distribution, identity/authorization and event startup are separate gates. The receipt explicitly says no full functional acceptance suite was rerun. Existing image-bound approval and the earlier full live acceptance receipts remain separate evidence.

On October 10, 2026, the complete read-only entry point passed against retained test-2 with this public digest and all four frozen files, reporting verified infrastructure/application/data identity without attendee readiness. Thirteen offline startup groups passed, including incomplete pins, wrong scope/environment/image/ingress/state, malformed verification output, widened receipt scope and timeout paths. Seven application-checker tests cover local/live data drift, historical JSON types, source-use flags, synthetic disclosure, redirects, response limits and HTTP failures. No resources, images, IAM or credentials changed.

### Recorded evidence inspection

`src/workers/inspect_evidence.py` uses only the standard library and the existing trusted packaging/frozen-contract checks. Provide independently trusted SHA-256 pins for the accepted result, baseline descriptor and local frozen manifest; the adjacent prepared-baseline file and frozen database/original JSON/pipeline ZIP are checked too. Optional image, human-approval and timestamped startup receipts each need their own pin. Foreign run/Sandbox/data/source/image identities, failed checks and widened historical flags fail; missing optional stages remain explicit.

The inspector prints JSON or self-contained HTML (`--format html`), never imports candidate features or contacts Azure. It does not authenticate an approver, evaluate release authorization, replay raw logs, rerun acceptance or prove current live health. The baseline descriptor is recorded evidence, not a new remote missing-function/policy check. Six focused regressions pass, and the actual public chain joins all 11 categories, the `dsn` digest, separate image approval and timestamped startup observation with no missing supplied stages.

The reduced projection is bundled under `instructions/assets` for [platform-neutral participant rehearsal](../instructions/README.md). Its manifest pins the JSON/HTML and the original receipt hashes without copying candidate executable code, raw logs, data or credentials. The guide deliberately uses this instead of a nonexistent telemetry workbook; GitHub issue IDs, Foundry session IDs and detailed token/timing correlation are not stored by the current accepted-result contract.

<a id="pinned-synthetic-baseline-preparation"></a>

### Pinned development baseline preparation

The participant path exposes **native primary creation one command at a time**: learners read ARM capacity with `az rest` and the existing inventory with `aca.exe sandbox list`, inspect an allowlisted source/frozen-data export and its Dockerfile, run `aca.exe sandboxgroup disk create`, select the uniquely named Ready disk by its GUID, create the primary with explicit CPU/memory and egress settings, and separately set and inspect its lifecycle. Discovery/selection is separate from creation so an incorrect ID or timeout does not require resubmission. `prepare-worker-baseline.ps1 -Mode CheckCapacity` remains available, but the learner guide shows those read-only checks directly. Its final `-Mode VerifyPrimary` call requires the existing disk/primary IDs, original source-context directory/manifest SHA-256 and frozen manifest/pin. It checks unchanged context files, source revision, missing functions, UID, frozen identity and policies, then writes `primary-descriptor.json` and its original-byte SHA-256 without cloud mutation. The guide retains those paths for the unchanged portal-clone registration. The legacy `start-lab.ps1 -Mode PreparePrimary` remains available but is no longer the learner instruction.

Learners use the Sandbox portal to capture a Memory Snapshot, create clones with the exact Name labels `clinical-trials`, `drug-safety` and `quality-governance`, and demonstrate filesystem inheritance/isolation. Portal clone policies must be set explicitly: Full inspection, default Deny, only `open.fda.gov` allowed, 900-second Memory auto-suspend and auto-delete off. Do not rely on the create form's Allow/Partial defaults or assume policy inheritance.

`connect-lab-workers.ps1 -PrimaryDescriptorPath $primaryDescriptorPath -PrimaryDescriptorSha256 $primaryDescriptorSha256 -AsJson` discovers the primary-bound snapshot and named clones in the pinned allocation. Multiple snapshots require an explicit `-SnapshotId`; duplicate role names within the selected snapshot fail. It invokes strict Reuse verification with `-RequireStarters`, checking real snapshot lineage, all original frozen pins, UID, protected files and policy/lifecycle before publishing the standard baseline descriptor and bindings. Default registration creates or changes no cloud resources. Hash changes, missing/ambiguous workspaces and policy errors stop rather than trigger provisioning.

The end-of-segment **explicit** `-CatchUp` option invokes the legacy complete preparation path to create a replacement set, retaining every attempted resource and requiring four additional free slots. It requires the original allocated subscription, development purpose and manifest pin. Never invoke it implicitly after failed registration or repeatedly retry it on quota errors. The partial descriptor and accepted/failure evidence remain separate; neither primary preparation nor registration grants release approval or establishes fresh-launch readiness.

`Prepare` is an explicit allocation action against already provisioned, verified infrastructure. It does not deploy/update the infrastructure or application. The harness owns the immutable input configuration; attendees still supply only region and resource-group name.

| Harness setting | Meaning |
|---|---|
| `LAB_STARTUP_PURPOSE` | Exactly `synthetic-development` or `public-lab-development`; never image/deployment/attendee approval |
| `LAB_DATA_MANIFEST` | Local or credential-free HTTPS frozen artifact manifest |
| `LAB_DATA_MANIFEST_SHA256` | Required lowercase published/trusted manifest SHA-256 |
| `LAB_PYTHON_EXECUTABLE` | Optional existing Python interpreter; defaults to `python` |

The harness also provides authenticated Azure CLI, PowerShell, and `aca`. No package installation, account selection, role assignment, source approval, or registry credential creation occurs in this branch.

```powershell
.\scripts\start-lab.ps1 -Region westus3 -ResourceGroupName $resourceGroupName -Mode Prepare
```

Missing purpose or checksum fails before Azure calls. After current infrastructure checks pass, the entry point calls the existing bounded preparation helper with derived subscription/group/region, purpose and pinned artifact. The helper requires four free Sandbox slots before exporting/importing, validates the source trust anchor, checks the actual primary's full frozen identity before snapshotting, and verifies all three clones. The exact supplied files are staged, not regenerated. `-TimeoutSeconds` bounds the entire helper process; timeout does not cancel submitted Azure operations or authorize a retry.

Only successful remote UID, permissions, policy, lineage, starter, and frozen-data verification publishes controller paths as `CALDOVA_WORKER_BINDINGS_PATH`, `CALDOVA_DATA_MANIFEST_PATH`, `CALDOVA_BASELINE_DESCRIPTOR_PATH`, `CALDOVA_VALIDATION_SANDBOX_ID`, and `CALDOVA_BASELINE_SNAPSHOT_ID`. `baseline_ready` and `frozen_data_verified` may then be true, while `data_ready`, `application_ready`, and `attendee_ready` remain false. Here `data_ready` is the attendee-data release gate, not a claim that a verified development artifact is missing.

For `public-lab-development`, the manifest must bind the exact original JSON, pipeline ZIP and restricted project-owner source-use decision. Both files remain byte-preserved, protected and present in native source-import and candidate contexts. Startup independently checks the pinned manifest's database/logical/auxiliary/decision identities against the descriptor using a standard-library-only helper; it never silently downgrades to synthetic data. The report identifies `public_lab_development_only=true`, not expert audit, publication or readiness. Public `Reuse` requires its three additional trusted original-source/pipeline/decision hashes and does not alter retained synthetic resources.

The public build/controller/candidate branch selects eight source-derived `test_frozen_public_research.py` checks; the original nine synthetic tests are byte-unchanged and retain their separate acceptance path. The baseline still contains genuinely missing functions, and production UID/toolchain/read-only checks remain intact. Local regression validation passed 62 preparation checks, 10 startup groups, seven native public staging/legacy-reuse checks and four baseline checks (platform boundaries mocked only in unit tests). Eight checks passed against the actual public package. No new image, disk, Sandbox, worker run or deployment occurred; live import/worker/container receipts, exact-image approval and the real Skillable adapter remain required. See [the public branch contract](../src/README.md#frozen-public-development-branch).

Nine startup regression groups, 52 preparation-helper checks, four real frozen-export/staging tests, and the existing 17 packaging tests passed. A native Windows export preserved the retained approved database and manifest byte for byte. Local container validation stopped on the environment's Python CDN TLS handshake failure; TLS was not bypassed. Validation-only AMD64 ACR run `dsj` then passed the original nine tests in 3.740 seconds plus non-root prepared-baseline verification, with both query functions still missing and the exact frozen hashes retained. It used `--no-push`: no new release image, app deployment, or Sandbox allocation occurred. Fresh live `Prepare` validation remains separately required; test-2 has all nine Sandbox slots allocated.

## Sandbox validation

Use `-CreateSnapshot -CreateClone` to exercise the complete smoke workflow. `-CreateClone` without `-CreateSnapshot` is rejected. The source and clone both allow the host in `-AllowedUrl` and deny other egress, including the host in `-DeniedUrl`; both default to a 900-second idle suspension.

The current `aca` CLI prints a `Created sandbox:` confirmation even with JSON output selected. The script reads that success line for Sandbox IDs and parses the snapshot's JSON `id` separately from its source `sandboxId`. Clones are created using `--snapshot-id`, so repeated snapshot name labels do not select the wrong snapshot.

Snapshot clones inherit CPU, memory and disk resources from the primary. Only disk-based primary creation supplies resource requests; the service rejects resource overrides with a snapshot source. Egress and lifecycle settings remain explicit for every clone.

After a successful source import, preparation resolves the disk through scoped metadata using its freshly generated exact name. Build-log JSON cannot select a disk; missing, mismatched or duplicate results fail before primary allocation. A failed import is never silently retried or adopted.

The snapshot receives a filesystem marker that the clone must reproduce before its allowed and denied requests are tested. Egress is supplied explicitly during clone creation: the tested snapshot restore did not inherit the source Sandbox's egress policy.

See [infrastructure rollout results](../infra/README.md#verified-rollout-results) for the commands, retained resource IDs, and scope of the completed checks.

## Foundry and agent validation

The deployment grants the optional lab principal Foundry User at the `caldova` project scope, not the subscription or entire account. `deploy-test.ps1` preserves an existing assignment name before redeployment; a new environment uses a deterministic assignment name. The existing test-2 grant was adopted by Bicep, and Azure validation/deployment plus subsequent data-plane checks passed.

```powershell
.\scripts\validate-foundry.ps1 -EnvironmentName ignite-lab-test-2
.\scripts\validate-agent-workflow.ps1 -EnvironmentName ignite-lab-test-2 `
    -MetadataUrl $researchMetadataUrl -Mode plan -UseWsl
.\scripts\validate-agent-workflow.ps1 -EnvironmentName ignite-lab-test-2 `
    -MetadataUrl $researchMetadataUrl -Mode tool-smoke `
    -BindingsPath $ownedSmokeBindingsPath -UseWsl
.\scripts\validate-agent-workflow.ps1 -EnvironmentName ignite-lab-test-2 `
    -ManifestPath $preparedManifestPath -Mode workers `
    -BindingsPath $preparedWorkerBindingsPath `
    -ValidationSandboxId $preparedPrimaryId -ApprovePlan -UseWsl
```

`$researchMetadataUrl` is the deployed preview's HTTPS `/api/metadata` endpoint. Alternatively, `-ManifestPath` reads the actual imported baseline's manifest; the two input forms are mutually exclusive. Bindings are explicit JSON objects containing role, Sandbox UUID, snapshot UUID, and the fixed `/opt/caldova-lab` workspace. Diagnostic mode can use one retained smoke clone; full worker mode requires three distinct clones of one prepared baseline and a separate trusted primary. `-ApprovePlan` authorizes specialist execution, not source review, deployment, or release.

Worker mode verifies clone lineage and the default-deny policy before model-controlled execution. The trusted primary probes allowed HTTPS access and the expected HTTP 403 denial; generic timeouts or network failures cannot satisfy denial. The implementors run first, then the controller transfers only their two assigned feature modules into the primary and governance clone. Governance cannot start until frozen-data/source-fidelity validation and the dataset-specific suite pass in the independent primary: nine unchanged synthetic tests or eight frozen-public tests. Public worker checks also verify the complete protected original-source/source-use identity before querying. Failures retain role-specific blockers in structured stderr diagnostics and exit unsuccessfully. A completed worker exercise still requires complete deterministic release evidence, an immutable candidate image, and exact-image human approval.

Each specialist receives exact permitted source paths, the frozen database path, and the actual Python calling contract. A fresh interpreter verifies query calls and record shapes before accepting an implementor's result. Bounded repair turns return failed-check diagnostics to the same assigned worker session; tests, fixtures, and source scope are unchanged. Reported evidence identifiers must exist in the frozen database. A final independent primary check binds all three worker reports to the run, dataset, assigned Sandbox IDs, and source records. The output includes checksummed source text for only the two accepted feature files; generated code is never executed on the maintainer host.

On October 9, 2026, persistent `caldova-orchestrator` Agent Framework dispatch invoked the real assigned clone `674a7e8d-e107-4af6-8afd-6879086a6692`, returned the exact run-specific marker, and recorded exit code 0. The run ID was `c5835c78-48da-41af-95d6-06a14a1417b2`; captured-output SHA-256 was `eefd9e97454b3fda3ebd7e660d49b173d8b01d3a0c0e788ef38f4609c1332728`.

The SDK server owns tool declarations; matching local implementations perform only assigned remote operations. SDK warnings that per-run tool declarations are omitted are expected here: the declarations are already stored on the prompt agent version. An existing agent without the lab ownership marker is not overwritten.

The controller pins compatible SDK versions in `src/orchestrator/requirements.txt`; these differ from the isolated application's dependencies. Focused checks cover controller/credential/ownership/release contracts, real stdio MCP transport, lineage, remote exit status, independent integration, and fail-closed sequencing. The first live plan was schema-valid but drifted into clinical-analysis tasks; assignments now require the exact approved software tasks and deterministic check names. The revised live plan passed with run ID `d3ac2bb7-85c7-47bd-aa7f-07297bdaf480`, the frozen dataset identity, all three scoped assignments, and no release approval.

Windows ARM crypto compilation and Python CDN TLS blocked the native SDK installation. The existing Linux runtime successfully installed the pinned SDKs and passed `pip check`. `-UseWsl` hands a short-lived Foundry-only token from the already authenticated Windows CLI through stdin; it never copies refresh-token caches, writes token files, or places tokens in argv. The handoff cannot refresh or authorize non-Foundry scopes. Normal native execution uses Azure CLI credentials. Certificate validation remains enabled; requests negotiate uncompressed SDK responses because the observed default compressed response could not be decoded.

Test-2 originally enforced 1 request/minute and 1,000 tokens/minute and returned HTTP 429 for the larger planner request. A validated Bicep update configures capacity 20. ARM first reported 20 requests/minute and 20,000 tokens/minute while actual response headers still enforced 1/1,000; a later native inference check verified effective 20/20,000, after which the scoped planner passed. Do not infer usable capacity from ARM success alone. The template default remains 1 and attendee/event sizing remains pending.

## Prepared worker baseline

The secret-free native source import completed on October 9, 2026. The imported image and all three clones verified UID 10001, Python 3.13.16, Node v24.21.0, built frontend assets, read-only trusted files, frozen synthetic data, and genuinely missing query implementations. The test-2 Sandbox count override is 9 to retain five earlier diagnostic resources plus this primary and three workers; the template default remains 8. All nine slots are allocated.

| Retained resource | UUID |
|---|---|
| Prepared disk | `fba6f513-a8ba-4162-818c-08b16f4c7c5d` |
| Trusted primary | `73c54952-8c62-490d-9673-dd6a26f56c02` |
| Prepared snapshot | `5e032190-3587-4bc6-afc9-bc7847210d8e` |
| Clinical trials clone | `dd9b7b82-00f3-40e6-a4df-636a25e3fa59` |
| Drug safety clone | `91a0c929-ca0c-4578-b49b-1b59178c4483` |
| Governance clone | `2db5f93f-eca4-4d59-b6dc-405198e05d66` |

The actual imported database SHA-256 is `3e4459db5a22437c843921a006ca9fae66bbffa7bf539c76ef862b6b941ad3a1`, manifest SHA-256 is `0222e61a6c8e5687c318c60196afd4e78234a7a1ce343001de93313d6e870e08`, and logical identity is `3a95501abcdcd1dda93087a23f0904acb1a68e50fb87998943ec94b69e2b3a38`. Use the imported manifest, not a separately built image's timestamp-dependent manifest hash.

Early real implementation runs stopped on guessed schema paths, token throttling, an invented Python package import, a string condition treated as an enum, and missing result fields. These failures were not bypassed. Exact discovery/runtime contracts, bounded request-level SDK retries, and same-session query/shape repair resolved them without replacing trusted tests or seeding reference implementations.

On October 9, 2026, actual Foundry run `9b37caac-1498-46b2-802f-d9c731833885` completed clinical, safety, and governance sessions with no blockers. The two generated functions passed fresh-interpreter checks; their integrated candidate passed all nine original tests in the separate primary. Frozen identity, actual allowed/denied HTTPS probes, and grounded three-worker schema validation also passed. All eight required deterministic check names are present. Final regression validation passed 59 controller/MCP tests and 48 preparation-helper checks.

| Accepted candidate file | SHA-256 |
|---|---|
| `src/research-portal/backend/trial_feature.py` | `5cee376b0407b2c078f615d4047b2f71e27b33327a60945f90c1447ce2ad8f0a` |
| `src/research-portal/backend/safety_feature.py` | `80fd8f572e56289536f309d98eda2467342940ad192da7cc97e1356c6f057f2a` |

The code-preserving `Reuse` path also passed against the exact retained disk, primary, snapshot, and three clones. It published controller bindings, the frozen manifests, and a verified descriptor without allocation or resetting worker code. Use a new repository-contained output directory, all six explicit resource IDs, and the four known frozen hashes; see [the exact preparation examples](../src/README.md). `Provision` requires explicit authorization, checks capacity through the deployed `2026-02-01-preview` ARM API before allocation, and fails closed on unavailable capacity; the preparation helper's provisioning path is locally tested, not live-tested.

This recorded the first synthetic agent implementation/integration milestone, not an attendee release or recording-ready lab. Its accepted generated source remains preserved in the run result and retained Sandboxes. The later candidate failure, correction, fresh approval, and current agent-built deployment are recorded below. Reviewed AACT/openFDA publication, Skillable startup, timed attendee guidance, and the capture package remain pending.

## Agent-built candidate

`build-agent-candidate.ps1` requires the accepted result's SHA-256, approved run ID, verified baseline descriptor, and local byte-identical frozen artifact. It never executes generated source on the host or changes the repository's reference implementation. Supply the participant's explicit `ResourceGroupName`, `SubscriptionId` and `RegistryName` for the [portable path](#portable-image-and-data-delivery); without a group, only the original maintainer registry/subscription is accepted. The stager rejects foreign/failed/duplicate evidence, changed source/artifact bytes, unsupported schema, and existing destinations. `-StageOnly` and `-WhatIf` do not call ACR.

On October 9, 2026, ACR run `dsg` built `agent-9b37caac-20261009-191955`, using the exact two specialist modules and frozen database/manifest bytes. All nine original research tests passed as UID 10001 in 3.059 seconds, with frozen/source identity checked before and after validation. The candidate target depends on that validation stage and contains `candidate-validation.json`.

| Candidate property | Verified value |
|---|---|
| Accepted agent run | `9b37caac-1498-46b2-802f-d9c731833885` |
| ACR run | `dsg`, `Succeeded` |
| Immutable image digest | `sha256:eba0b2e0f4c57107bcc26d74afb2f97d088743028d2f0f334d96634d2349f791` |
| Accepted result SHA-256 | `8d10d77deaa6d39cd44531daa044919b61b5b726c1b4a5779300db9bfa85a4d3` |
| Candidate provenance SHA-256 | `7482e223ceabbfb1f8addcdcf606b7a223edee61a716c4ad50ef99ac0c3fae24` |
| Dataset | `caldova-synthetic-development-v1`; no public-source approval |
| Release/deployment | Approved for synthetic development, deployed, then restored to the reference after live source-fidelity failure |

The digest-bound descriptor is retained under `.build-contexts/candidate-9b37caac-live-20261009-191955/candidate-image.json`. Packaging regression checks passed 17 tests. The first submission failed before queuing an ACR run because an explicit relative `--file Dockerfile` resolved from the repository working directory; the helper now checks and submits the absolute staged Dockerfile path. Windows log streaming still required the bundled Azure CLI Python runtime with `-X utf8` to read Unicode build output; no build was repeated for that log-display failure.

Deployment requires explicit human approval bound to this run, logical dataset hash, and immutable image digest. Approval of this synthetic development preview is not review of AACT/openFDA sources or an attendee release.

Simon Jakesch explicitly approved this candidate for the synthetic preview. The deterministic gate accepted all 11 supplied receipts with that approval, blocked without it, and separately blocked an attendee release with synthetic data. Deployment reached `Succeeded` and `Running`, and native read-only execution verified the exact candidate source hashes and embedded validation receipt.

Live browser/API validation then exposed a gap in the original nine-test suite: `DEMO-REPORT-002` mentions both candidates A and B, but the generated SQL returned only the selected candidate in `candidate_ids`. The existing reference image was restored and both mentions were independently verified. The rejected candidate, original result, approval, deployment, failure, and rollback receipts remain retained; the original image descriptor records its build-time unapproved state, not current deployment history.

The controller now compares all returned fields and complete source collections against independent read-only table rows for every candidate/condition, both within the assigned worker's repair session and again on the integrated primary before the unchanged nine tests. Missing/duplicate records and narrowed candidate mentions, trial conditions, or reaction terms fail acceptance. A corrected run/image requires fresh human approval; the previous approval is not transferable.

All 25 focused controller/integration regressions passed, including shared-report, multi-candidate/multi-condition trial, duplicate/missing-record, changed-term, and independent-marker cases. A read-only live check rejected the exact defective safety module on its retained worker clone. The restored reference passed nine live candidate/condition combinations, normalized report versions/terms, complete shared mentions, citations, explicit 404/422 responses, security headers, and frontend asset checks. Its isolated browser displayed both shared mentions, expanded provenance, warnings, and a clean console.

### Corrected deployed candidate

Actual run `0e17d6ef-b6db-4380-959b-b73ab867488d` subsequently completed all three specialists with no blockers, full-source fidelity, the unchanged nine independent application tests, actual egress, and all eight required deterministic categories. A prior corrective attempt stopped on model token throttling after the safety worker had repaired its module; the successful retry preserved valid source rather than resetting worker files.

| Corrected property | Verified value |
|---|---|
| ACR run | `dsh`, `Succeeded`; original nine tests in 3.713 seconds |
| Immutable image | `sha256:f9a95fa8f157b717f556e52d3ce17996a6db9d977068d8733451b8bd733a7224` |
| Trial module SHA-256 | `7a9481a905de7e83b3fec72306d7e7ce782b3c9a2c59bb82368cb86cb27385dd` |
| Safety module SHA-256 | `ca2ecef327b32c2cb8afb9a181ff7ff7c5a4bdc6d3872518537c4767cf159012` |
| Accepted result SHA-256 | `4b29dacd1267e1b59fcd8b3155432663ce3047c978043db41745ce615bad52e4` |
| Release decision | Fresh approval from Simon Jakesch; `development-preview-approved` |
| Deployment | `caldova-research`, `Succeeded`, `Running`, healthy |
| Attendee/public-data release | Still not approved |

Fresh human approval was recorded for this exact corrected run, unchanged logical dataset hash, and new digest. The gate rejects both absent approval and the previous candidate's approval. The synthetic attendee-release guard still rejects this candidate.

Post-deployment checks verified the actual feature bytes, byte-identical database/manifest, matching embedded validation receipt, and Uvicorn process UID 10001. All nine candidate/condition API cases matched every trusted source field and full collection, with explicit empty results and 404/422 errors. The browser passed filtering, shared mentions, provenance, warnings, desktop/mobile layout, and empty results with a clean console. Final regressions passed 64 controller/MCP tests in the Linux SDK runtime and 17 packaging tests on Windows; packaging's native `pwsh` cases must not be run in WSL without PowerShell.

Native Express one-shot diagnostics should rediscover the current running replica and use short, explicit revision/replica/container commands. Longer and automatically targeted probes returned 404, and retained replica IDs became stale after scale changes; shorter probes against a freshly discovered replica succeeded. The exact payload/transport limit was not established. Transport success alone is insufficient: parse and verify the remote receipt. An exec command's UID is not the application's UID; inspect the Uvicorn process itself.

The build-time candidate descriptor remains immutable and unapproved; separate approval, decision, deployment, API/runtime, and browser receipts record the later approved deployment. No resources were deleted or changes committed. This completes the synthetic agent-to-image-to-live-preview milestone, not reviewed public data, Skillable attendee startup, or recording preparation.

## Research preview

Run from the repository root with Azure CLI and `azd` authenticated to the maintainer subscription:

```powershell
$release = .\scripts\build-research-image.ps1 -EnvironmentName ignite-lab-test-2 -Tag reference-20261009-state1 -PreviewState reference
.\scripts\deploy-research-preview.ps1 -EnvironmentName ignite-lab-test-2 -ImageDigest $release.Digest -PreviewState reference
```

Use a new release tag for each build. `-AppName` defaults to `caldova-research`. For the visual unavailable baseline, build a separate image with `-PreviewState starter` and deploy its digest with the same state. The image build bakes `CALDOVA_PREVIEW_STATE` into its defaults, and validation checks the default process's actual ready/unavailable API response. Neither state implements the remaining agent workflow.

Do not switch a running Express preview solely by changing environment variables on the same digest. The tested update reached `Succeeded` in ARM while `/health` continued reporting the previous state throughout the readiness window; the attempted latest-revision restart returned `InternalServerError`. Deploying a different, matching immutable image is the maintainer state transition, rather than depending on a timely environment-only restart.

Builds use ACR rather than the local WSL image engine, which encountered TLS handshake failures downloading Python packages. Certificate verification remains enabled. The helper uses `--no-logs` to avoid Windows Azure CLI Unicode log-streaming errors and stops if validation fails. Inspect the existing ACR run ID before queuing a retry.

Private-image access uses the approved ACR scope map and token `<AppName>-pull`, limited to `content/read` and `metadata/read` on `caldova/research-portal`. Each deployment generates password1 with a seven-day expiry and stores it as the application secret `caldova-acr-pull`; no registry admin credentials are enabled. Rerun deployment to rotate the credential before expiry or before a later image deployment. Do not print secret values or enable PowerShell request tracing.

The helper submits image, registry settings, and secrets together using ARM PUT with the tested app API `2025-10-02-preview`. It follows the returned Azure management operation before examining provisioning state: an immediate resource GET can still show the previous failed deployment. It checks the desired image reference and `/health` before reporting success, with bounded and explicitly logged startup retries.

On October 9, 2026, ACR runs `ds1` and `ds2` passed the initial eight checks and built the first release. The stored scoped token also passed an authenticated read of that release manifest. Two defects were then corrected: resource polling could report a previous failed state before the new ARM operation completed, and the Uvicorn console entry point could not import the shared `data` package without `/app` on its Python import path.

The revised validation run `ds3` passed all eight checks in 1.911 seconds using the release console entry point. Release run `ds4` built `reference-20261009-runtime1`, digest `sha256:57d9f0dd7ed3b0b7c58484eda86cbba657515c8458bf9a005228b2d0f46e5df8`. This digest served `/health` with HTTP 200 without the temporary diagnostic environment override, and the repaired deployment helper also completed successfully.

Live reference checks passed metadata, filtered trials, unchanged safety mentions across condition filters, the empty-result candidate, 404/422 errors, frontend assets, and response headers. Isolated Edge checks passed loading, filtered and empty states, offline error/retry recovery, keyboard skip navigation, and desktop/mobile layout, including expanded provenance at an actual 390x844 viewport. The browser form-field metadata issue was corrected and verified on the deployed image with no console errors, warnings, or issues. Follow-up ACR validation `ds5` passed all eight then-current tests in 2.614 seconds, and release `ds6` deployed successfully.

A ninth check now exercises the baked-in image default through a separately started API process. Both image variants passed all nine checks: reference validation `ds8` in 3.467 seconds and starter validation `dsa` in 3.374 seconds. The first starter attempt `ds7` caught missing propagation of the test's expected build state; that validation-only issue was corrected before publishing the starter release.

| Preview | Release run | Tag | Verified digest |
|---|---|---|---|
| Starter | `dsb` | `starter-20261009-state2` | `sha256:3c10382dcb5bfe59ff768f3a49041179c9aa0fa4857622a2b616e693b15e7423` |
| Reference | `ds9` | `reference-20261009-state1` | `sha256:ebde941149c8f9960d24d97c00463c3fd21746f565009aaad611b08791987c68` |

The starter digest passed HTTP 200 health, the explicit unavailable API contract, and the browser baseline with no evidence cards. The subsequent reference digest passed health, filtered evidence, and the browser reference panel with a clean console. `caldova-research` is left serving the reference digest. This completes the standalone synthetic preview validation, not the attendee agent exercise or recording preparation.

The original `reference-20261009` tag was locked against writes and deletion during diagnosis and remains retained. It is not the deployed release; the application uses an immutable digest. Unlocking or removing retained artifacts requires explicit owner approval. Screenshot export to the session-artifact folder was outside the browser tool's permitted workspace roots, so visual checks used returned screenshots; no recording capture package has been produced.

The maintainer `azd` installation was upgraded and verified at version `1.35.1`. Both retained environments remain available, with `ignite-lab-test-2` selected.
