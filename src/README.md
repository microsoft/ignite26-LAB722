# Source

This folder contains the lab-owned research portal and a prepared, genuinely incomplete developer baseline. The orchestrator and Sandbox gateway run outside worker clones.

## Research portal

`research-portal/` contains a FastAPI/Python backend, React/TypeScript frontend, and digest-pinned multi-stage container build. Direct Python and JavaScript dependencies are pinned, and the frontend has a generated lockfile.

The backend validates its DuckDB artifact and frontend build at startup. `/health` reports readiness and dataset identity, `/api/metadata` exposes provenance and candidate choices, and `/api/research` returns parameterized, read-only evidence queries. Unknown candidates return 404; unsupported conditions return 422. Trial condition filters do not incorrectly narrow candidate safety-report mentions.

The portal displays citations, synthetic-data warnings, report versions, responsible-use limitations, and explicit loading, error, empty-result, and unavailable states. The checked-in backend is fully implemented: `trial_feature.py` exports `query_trials(connection, candidate, condition)` and `safety_feature.py` exports `query_safety_reports(connection, candidate)`, sharing `queries.py` for record conversion.

`CALDOVA_PREVIEW_STATE=reference` exposes the reference research panel; `starter` exposes its visual unavailable state. Reference portal images retain both working feature implementations in either visual state. Build separate immutable portal images with the matching `PREVIEW_STATE` build argument rather than relying on a timely Express environment-only restart.

The container runs as a non-root user on port 8080 and includes the synthetic development artifact, not reviewed public data. Its Python import path includes `/app` so the Uvicorn console entry point can load the shared data package. Container validation starts that same entry point and runs nine focused pipeline/API checks, including the image's default starter/reference behavior. See [maintainer build and deployment commands](../scripts/README.md#research-preview).

### Local public-data integration

The reference portal also supports the separately frozen `caldova-public-lab-use-v1` artifact. Set `CALDOVA_DATA_DIR` to the external package directory and `CALDOVA_STATIC_DIR` to the built frontend, then start the existing Uvicorn application. This is a local reference check, not a public agent-built image or a deployment operation.

Startup verifies the database, original-source JSON and pipeline-source ZIP together, including full record fidelity. Public `/api/research` responses retain original condition/intervention/drug/reaction projections beside canonical fields, and `/api/source-records` returns the complete extraction with the subsequent source-use decision separately identified. The UI labels the data as a bounded public lab extract, displays coverage and source dates, and preserves an honest empty safety result instead of synthesizing evidence. Harmonized brand arrays are identified as metadata, not proof of products taken.

Twenty-six targeted data/API/release-gate regressions passed, as did all nine unchanged synthetic acceptance tests and frontend type-check/build. Independent checks compared all nine real candidate/condition responses with the complete frozen extraction and verified exact-byte staging. The actual local public artifact and source-use record are described in [the data-source notes](../data/sources/README.md#freezing-the-authorized-public-lab-slice).

The test-2 Azure preview now serves the approved **public-lab-development** candidate; earlier synthetic images, disks and clones remain retained. Public live run `9bbcce44-7e7b-4889-b7e4-4081ea9893dc` completed all three specialists in the authorized test-1 clones, strict full-source/shared-record/ordering checks, independent eight-test API acceptance, and actual allowed/denied egress checks with no blockers. Prepared-baseline ACR run `dsk` and exact-candidate run `dsm` used `--no-push`. Separate owner-authorized ACR run `dsn` published the same accepted source, passed all eight public tests in 4.025 seconds, and produced digest `sha256:e219757d2f40dd83f5445ea661aa8f56e9ff53864d34127b74acc7570306bd38`.

The project owner separately approved this exact run/dataset/image for development-preview deployment. The deterministic gate passes with that approval, fails without it, and still rejects attendee release because pipeline provenance is uncommitted. The live app is healthy in `reference` state; all nine candidate/topic API combinations match complete frozen original projections, metadata/source fields and 404/422 errors. Native read-only inspection verifies the two accepted feature hashes, all four frozen artifact hashes, matching embedded eight-test receipt and application PID 1 UID 10001. The inspection shell itself uses the native gateway's UID 0; it is not the application process. Attendee startup and recording readiness remain incomplete; the original nine synthetic test bytes and historical artifact approval flags are unchanged.

The platform-neutral startup's opt-in application check is `workers/check_application.py`. It uses only the standard library and the existing frozen-contract verifier: no candidate execution, DuckDB import or data regeneration occurs on the host. The complete read-only `start-lab.ps1 -Mode Readiness` path has verified the retained public app's scoped immutable image, frozen files, live manifest/original sources and expected reference state. It reports development application/data identity separately from worker-baseline and attendee release. See [harness pins, outputs and limits](../scripts/README.md#pinned-application-readiness).

`workers/inspect_evidence.py` joins independently pinned accepted-result/baseline/frozen inputs with optional image, human-approval and timestamped startup receipts. It reuses the stdlib packaging checks and renders JSON or a self-contained HTML projection without executing candidate code or contacting Azure. The participant guide bundles a reduced projection of the actual public development chain. Integrity checks and recorded approval are not approver authentication, a fresh live observation, a release decision or an Azure Monitor workbook.

## Prepared developer image

`developer-image/Containerfile` reuses the portal's pinned Python 3.13 and Node 24 base-image digests. Its release target contains:

- The needed portal and pipeline source at `/opt/caldova-lab`, installed application dependencies, and frontend dependencies restored from the checked-in lockfile.
- The built frontend at `src/research-portal/frontend/dist`.
- Trusted, root-owned acceptance tests: the byte-unchanged original nine synthetic checks at `tests/test_research.py` and the separate eight public checks at `tests/test_frozen_public_research.py`.
- A DuckDB artifact and authoritative pipeline manifest at `data/artifacts/development`, built once for synthetic images or staged byte-for-byte from an explicit frozen input, then inherited unchanged by snapshot clones. The public branch also protects the original source JSON and pipeline ZIP.
- `prepared-baseline.json`, recording the source revision, toolchain versions, database and data-manifest checksums, and hashes of protected source, tests, and bundled assets.
- Active feature modules replaced with the checked-in `workers/starter/` equivalents. Both functions explicitly raise `NotImplementedError`; the final image contains no reference feature implementations, even in its ancestor layers.

The default UI is unavailable, but setting `CALDOVA_PREVIEW_STATE=reference` does **not** implement the missing queries. Both role modules must be completed before reference acceptance can pass. The container runs as UID 10001; only the two feature slots and the `.runtime` scratch directory are writable within the lab workspace. The gateway/controller must additionally enforce each worker's exact file allowlist: clinical trials may change only `trial_feature.py`, drug safety only `safety_feature.py`, and quality/governance no files. Do not grant worker code root access.

The image excludes control-plane Agent Framework SDKs. Its application/data dependencies use Pydantic 2.14.0; keep the controller's separately pinned environment isolated. No model, management, or registry credentials belong in images, source bundles, commands, files, or snapshots.

Build one immutable baseline from the repository root, choosing the repository and a new tag explicitly:

```powershell
.\scripts\build-developer-image.ps1 `
  -RegistryName '<registry-name>' `
  -SubscriptionId '<subscription-id>' `
  -Repository 'caldova/research-portal' `
  -Tag '<unique-developer-tag>'
```

The helper uses the same allowlisted native exporter in a unique project-local workspace, keeps archive scratch files there, and cleans up its own workspace afterward. This avoids Azure CLI traversing excluded credential caches or Windows-inaccessible virtualenv symlinks. It uses an AMD64 ACR build with no log streaming. The release target depends on the dataset-specific reference suite and prepared-baseline checks; it does not deploy, import a disk, allocate a Sandbox, or change permissions. Optional paired `-FrozenManifest`/`-FrozenManifestSha256` and explicit `-Purpose public-lab-development` select the frozen public branch. If a build call fails, inspect its existing run before retrying. A different repository requires existing pull authorization for that repository; scoped `caldova/research-portal` pull credentials do not grant registry-wide access.

For a native source-built disk, export an explicit credential-free context with a root `Dockerfile`:

```powershell
python .\src\developer-image\export_source.py `
  --destination .build-contexts\caldova-developer-source
```

The exporter uses only Python's standard library, refuses existing output directories, excludes caches and unrelated files by allowlist, and records source checksums in `source-context.json`. Use its returned directory for the native `aca sandboxgroup disk create --source` option with the parent's approved resource parameters. Exporting the directory does not import a disk or allocate resources.

To preserve an existing immutable synthetic artifact rather than rebuilding its timestamp-dependent manifest/database bytes, supply the pinned manifest explicitly:

```powershell
python .\src\developer-image\export_source.py `
  --destination .build-contexts\caldova-frozen-developer-source `
  --manifest $frozenManifest `
  --manifest-sha256 $trustedManifestSha256
```

Both inputs are required together, including for local files. The exporter reuses the packaging schema/byte checks and bounded HTTPS downloader using only the standard library. It checks the exact manifest SHA-256, database size/SHA-256, synthetic-data boundary, and canonical paths, then includes only those frozen files in the allowlisted context. The generated root Dockerfile stages and validates those exact bytes in the trusted container instead of running the synthetic builder. Database identity/count checks, the unchanged nine reference tests, and prepared-baseline verification remain mandatory container stages. Default export without frozen inputs retains the existing development builder; it is not a fallback for a failed or missing pin.

This is a **trusted image-builder context**, not a worker source bundle: it includes reference modules needed by the build's dataset-specific preflight. The final image replaces those modules with starters and excludes their reference layers. Never copy this build context into worker clones. Default source builds create new timestamp-dependent artifact/manifest bytes; frozen-input builds preserve the supplied artifact and still produce a new source/toolchain baseline record. Retain the actual `BASELINE_VERIFIED` checksums before snapshotting. Preserve the non-root UID 10001 execution boundary when staging or cloning.

### Frozen public development branch

The public branch is opt-in and requires the exact source-use-bound artifact, not merely a `reviewed-public` label or a named reviewer:

```powershell
python .\src\developer-image\export_source.py `
  --destination .build-contexts\caldova-public-developer-source `
  --purpose public-lab-development `
  --manifest $publicManifest `
  --manifest-sha256 $trustedPublicManifestSha256
```

The standard-library-only exporter checks all four frozen file identities, the ZIP's bounded inventory/member hashes, canonical input identity, exact project-owner decision/review identity, original false draft flags and coverage metadata. It compares the frozen pipeline bytes with the actual packaging source without extracting or executing archived code. The generated Dockerfile stages the original files and runs `test_frozen_public_research.py`; the original nine synthetic tests remain packaged and byte-identical, not rewritten or run against real IDs.

Eight public runtime checks derive every expected selected record from the original extraction, not current query output or hard-coded real records. They verify all candidate/topic selections, full canonical and original collections, citations, metadata/coverage/limitations, honest empty safety coverage, condition-independent safety, the source-record endpoint, errors and image-default starter/reference behavior. Existing worker checks still verify complete canonical table projections; public workers and the independent primary first bind those tables to the original JSON/ZIP and protected baseline. All source-use/publication/live-replacement/attendee restrictions remain explicit.

Workers call the argument-free `verify_feature` MCP tool and receive its controller-bound success marker, also on bounded same-session repair. The bridge owns the exact verifier command; models never need to reconstruct its shell quoting or choose another Sandbox. It checks the assigned function without requiring the other worker's implementation. Separate isolated fictional in-memory conformance cases exercise shared candidate/topic arrays, empty results and comma-containing reaction terms even when the frozen slice has only single associations. These cases are software checks, not public evidence, and never modify the frozen database. Record-selection predicates must not narrow the association rows used for returned arrays. The independent primary repeats these checks before the dataset-specific API suite.

Every initial and repair prompt repeats the immutable role/run/Sandbox/dataset identity. A mismatched report is rejected before feature execution or blocker acceptance, with exact expected/received fields recorded on stderr. Report-only repair reuses the same session with tool calls disabled, preserving existing source; it shares the three-attempt budget with feature repair. The controller independently verifies any corrected report and implementation. Persistent mismatches cannot become accepted results or reach integration.

The public prepared record additionally binds original-source, pipeline-source and canonical source-use decision hashes. Verification probes both starter functions for every frozen candidate/topic and confirms that reference mode genuinely raises `NotImplementedError`. A matching file containing a working empty query cannot satisfy the missing-function check. Production Python 3.13/Node 24, UID 10001 and read-only ownership checks are unchanged; local baseline unit tests mock those platform boundaries, not claim an imported-image receipt.

Use the same harness-owned purpose for preparation and candidate packaging. Public `Reuse` additionally requires `-ExpectedSourceRecordsSha256`, `-ExpectedPipelineSourceSha256` and `-ExpectedSourceUseSha256`; it never converts or resets retained synthetic clones. Candidate staging carries all four files and all public identities, executes no candidate code natively, and selects the public suite only after matching the prepared purpose. The final container validation target remains mandatory.

For local public reference acceptance in the declared data-aware runtime, set `CALDOVA_DATA_DIR`, `CALDOVA_ACCEPTANCE_PURPOSE=public-lab-development` and `CALDOVA_DATA_MANIFEST_SHA256` to the pinned package, then run:

```text
CALDOVA_PREVIEW_STATE=reference CALDOVA_EXPECTED_PREVIEW_STATE=reference python -m unittest discover -s tests -p test_frozen_public_research.py -v
```

The October 10 local public checks passed without Azure calls. No public worker run, new image, disk import, clone allocation or deployment is implied. `HumanApproval` still binds the exact run/dataset/image; an uncommitted public pipeline snapshot still fails the final attendee release gate even with a reviewed-public evidence flag.

Before creating a snapshot, run from `/opt/caldova-lab`:

```text
python src/developer-image/baseline.py
```

This verifies cached-data checksums and counts through `data/pipeline`, protected-file hashes, Python/Node versions, built local frontend assets, read-only trusted files, and both missing implementations. It also forces reference state and confirms the query remains unimplemented. Retain its `BASELINE_VERIFIED` output, immutable image digest, and source revision with snapshot lineage. The baseline checker intentionally stops passing after workers implement the features.

After integrating both approved modules, validate the candidate explicitly in reference state:

```text
CALDOVA_PREVIEW_STATE=reference CALDOVA_EXPECTED_PREVIEW_STATE=reference python -m unittest discover -s tests -p test_research.py -v
```

The command above is the original synthetic suite only; use the separate public command for an explicitly pinned public development baseline. Freeze one image's complete artifact and manifest for all clones; separate builds need not have identical database bytes. Image import, primary snapshot/clone staging, exact-image approval and attendee release remain separate prerequisites.

## Repeatable worker baseline

`scripts/prepare-worker-baseline.ps1` provides explicit `Provision` and `Reuse` paths. Its native flags were checked against `aca 1.0.0-preview.4` (`6d679be`, build `20260916.1`). Supply subscription, resource group, region, and existing Sandbox group explicitly; the helper does not select an azd environment, change CLI configuration, grant roles, or read credential caches.

- **Provision:** requires `-AuthorizeProvisioning` and `ShouldProcess` approval. It confirms group scope through native ACA metadata and checks complete inventory plus actual `maxSandboxCount` through bounded, read-only `az rest --method get` using the explicit `2026-02-01-preview` ARM API before exporting or importing. It requires four free Sandbox slots and rechecks ARM capacity before each allocation; missing, invalid or mismatched capacity fails without a fallback. It exports a new secret-free source context, imports with native `sandboxgroup disk create --source`, creates a primary, snapshots it, and creates the three role clones. Each new Sandbox receives default-deny egress allowing only `open.fda.gov`, Full traffic inspection, 900-second Memory suspension, and explicitly disabled auto-delete. Native operation waits default to 900 seconds, with a bounded host timeout; other commands default to 60 seconds.
- **Reuse:** requires explicit disk, primary, snapshot, and three distinct role IDs, plus trusted database, data-manifest, prepared-baseline, and logical SHA-256 values. It verifies group scope and complete inventory, Ready disk identity, snapshot-to-primary identity, each clone's actual `sourcesRef.snapshot.id`, configured policies, UID 10001, protected-file hashes, built frontend assets, and the authoritative pipeline's frozen-data checks. Native group metadata omits allocation capacity, so this non-allocating path neither requires `maxSandboxCount` nor invokes Azure CLI capacity queries. It does not create, resume, reconfigure, or reset resources or worker files. Completed feature modules are permitted: reuse checks protected baseline contents without importing worker implementations or requiring the active modules to remain starters.
- **WhatIf:** makes no native calls, exports no source, and writes no artifacts. Native archive scratch stays in unique project-local directories and only that owned scratch is removed. No path provides resource cleanup or automatic retry. Failed or timed-out provisioning can leave retained resources; inspect the existing operation and scoped inventory before another attempt.

Provision optionally accepts the paired `-FrozenManifest` and `-FrozenManifestSha256`; public development requires them plus `-Purpose public-lab-development`. It passes them to the trusted exporter and rejects mismatched export/primary hashes, including public auxiliary/decision pins, before any snapshot can be created. Every clone must match the same full frozen identity. `Reuse` rejects source-import arguments rather than ignoring them; its explicit retained-resource/checksum bindings remain required. `-AsJson` provides a compact machine-readable result for the startup harness without changing the default maintainer output. The harness calls this pinned Provision path through `start-lab.ps1 -Mode Prepare`, with the whole child process bounded by the startup deadline; see [harness configuration and outputs](../scripts/README.md#pinned-synthetic-baseline-preparation).

Use the **actual native-import checksums**, not an earlier ACR build's manifest checksums. The retained test-2 group currently has all nine slots allocated, so use `Reuse`; another four-Sandbox preparation must fail until the maintainer separately addresses capacity.

Set an explicit scope. The retained test-2 group uses these values; supply the appropriate existing group for another environment:

```powershell
$scope = @{
  SubscriptionId = '30501c6c-81f6-41ac-a388-d29cf43a020d'
  ResourceGroup = 'ignite-lab-test-2'
  Region = 'westus3'
  GroupName = 'lab722-2tf3zuqwfs4hu-sandboxes'
}
```

Validate the retained primary/snapshot/clones without replacing their worker code. The output directory must be new.

All six resource IDs, including `-DiskId`, are required in `Reuse` mode even though the script's shared parameter list permits omission for `Provision`. Missing or null bindings fail before native calls; the helper never discovers or substitutes another disk automatically.

```powershell
.\scripts\prepare-worker-baseline.ps1 @scope -Mode Reuse `
  -DiskId 'fba6f513-a8ba-4162-818c-08b16f4c7c5d' `
  -PrimaryId '73c54952-8c62-490d-9673-dd6a26f56c02' `
  -SnapshotId '5e032190-3587-4bc6-afc9-bc7847210d8e' `
  -ClinicalId 'dd9b7b82-00f3-40e6-a4df-636a25e3fa59' `
  -SafetyId '91a0c929-ca0c-4578-b49b-1b59178c4483' `
  -GovernanceId '2db5f93f-eca4-4d59-b6dc-405198e05d66' `
  -ExpectedDatabaseSha256 '3e4459db5a22437c843921a006ca9fae66bbffa7bf539c76ef862b6b941ad3a1' `
  -ExpectedManifestSha256 '0222e61a6c8e5687c318c60196afd4e78234a7a1ce343001de93313d6e870e08' `
  -ExpectedBaselineSha256 'df3e549189a62ea0da30d6d75d41ed011762068220412217043e7a7951253d2a' `
  -ExpectedLogicalSha256 '3a95501abcdcd1dda93087a23f0904acb1a68e50fb87998943ec94b69e2b3a38' `
  -OutputDirectory '.build-contexts\verified-existing-baseline'
```

Preview a future preparation without running a build/import or allocating resources:

```powershell
.\scripts\prepare-worker-baseline.ps1 @scope -Mode Provision `
  -SourceContextDirectory '.build-contexts\developer-source-next' `
  -OutputDirectory '.build-contexts\worker-baseline-next' `
  -WhatIf
```

Only after separate capacity approval and at least four verified free slots, use the same command with `-AuthorizeProvisioning` **instead of** `-WhatIf`. Both destination directories must be new, separate project-local paths. Optional `-PythonExecutable`, `-AcaExecutable` and `-AzExecutable` select already installed tools; Provision requires an already authenticated Azure CLI. No dependencies or credentials are provisioned, and credentials never enter command arguments.

After all four Sandbox checks succeed, the helper publishes:

- `bindings.json`: the exact three-role `SandboxBinding` array accepted by the controller's `--bindings`.
- `data-manifest.json`: byte-preserved frozen data metadata for `--manifest`, with the original SHA-256.
- `prepared-baseline.json`: byte-preserved protected-file and toolchain record.
- `baseline-descriptor.json`: verified scope, disk/primary/snapshot IDs, role bindings, frozen identities, policy configuration, verification mode, and controller artifact filenames.

Use the descriptor's `primary_id` for the controller's separate `--validation-sandbox-id`. Remote verification requires a nonce-bound success receipt as well as native transport success, so a native CLI exit code of zero cannot hide a failed Sandbox command. Artifacts are refused if output already exists or any identity, lineage, policy, permission, or checksum check fails. Reuse preserves the frozen baseline, but does not replace functional acceptance, runtime egress receipts, or human release approval.

Run the focused local helper checks without live ACA operations:

```powershell
.\tests\test_prepare_baseline.ps1
```

## Component layout

```text
src/
|-- research-portal/
|-- orchestrator/
|-- sandbox-mcp/
|-- workers/
|   |-- templates.json
|   `-- starter/
`-- developer-image/
```

## Component responsibilities

- `research-portal/`: fully implemented reference source, React/TypeScript visual states, and a Python data API with two isolated feature modules.
- `orchestrator/`: Python coordinator built with Microsoft Agent Framework and a structured release decision.
- `sandbox-mcp/`: Python service for authenticated operations that create, clone, and operate Sandboxes.
- `workers/`: bounded role templates and genuinely unimplemented starter modules.
- `developer-image/`: prepared Python/Node, frozen synthetic or explicitly pinned public lab data, protected validation and candidate packaging.

## Implementation constraints

- Generated or repository-supplied code runs only inside ACA Sandboxes.
- Synthetic fixtures or the exactly frozen public original extraction are authoritative for their separate acceptance suites.
- Worker outputs must validate against checked-in schemas.
- The application must display source identifiers and responsible-use limitations.
- The release process uses an immutable image digest.
- Python packages and JavaScript dependencies must be pinned after the first runnable vertical slice identifies the minimum required set.
