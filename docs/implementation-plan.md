# Implementation plan

## Goal

Deliver a 75-minute guided and self-paced lab in which attendees configure a Foundry orchestrator, prepare and clone ACA Sandboxes, validate parallel agent work, and publish a Caldova research application to ACA Express.

The current project-owner request is to complete the presentation and participant instructions without covering Skillable-specific work. The recorded-evidence path is the default for this materials milestone; a new live participant run, platform integration and final video readiness remain separate.

## Confirmed decisions

| Area | Decision |
|---|---|
| Clinical topic | Diabetes and obesity with a bounded GLP-1 scenario |
| Trial data | Curated AACT-derived DuckDB artifact |
| Safety data | Frozen exact-name selection from one disclosed openFDA export shard; no live application query |
| Artifact storage | Full frozen package outside the checkout; reduced recorded evidence in `instructions/assets`; immutable data-release publication remains separate |
| Backend and agents | Python using Microsoft Agent Framework |
| Portal | React and TypeScript |
| Deployment scope | Harness supplies subscription/authentication and an existing resource group; only region and resource-group name are visible configuration |
| Attendee identity | Requires a separate explicit principal mapping; the exact current Skillable identity contract is not verified |
| Foundry resources | Deploy an API and Foundry endpoint for each attendee |
| GitHub access | Staged read-only repository source; the implemented controller does not require a portal-attached GitHub MCP connection |
| Sandbox authorization | Preassigned by the event platform |
| Presentation output | RevealJS source, PDF, and slide images |
| Video output | Seven segment videos and one combined cut on Microsoft Stream or SharePoint |
| Browser baseline | Current Microsoft Edge at 1440x900 or higher |
| Service fallback | Explicitly labelled recorded-evidence delivery, never a substitute approval, starter or successful live check |
| Resource cleanup | Requires explicit project-owner approval |

## Progress as of October 10, 2026

**Current state:** the public agent-built development preview is deployed and healthy; earlier synthetic images and resources remain retained. The project-owner-authorized public lab slice contains 60 trials, 20 reports and a 4,206,592-byte database, with original source projections and honest working-tree provenance. Public live run `9bbcce44-7e7b-4889-b7e4-4081ea9893dc` passes all three test-1 specialists, strict source/shared-record/ordering checks, the independent unchanged eight-test public suite, actual allowed HTTP 200/denied HTTP 403 egress and worker-schema checks with zero blockers. Prepared-baseline ACR run `dsk` and candidate-validation run `dsm` used `--no-push`. Subsequent separately approved publication run `dsn` passed the eight public tests in 4.025 seconds and produced digest `sha256:e219757d2f40dd83f5445ea661aa8f56e9ff53864d34127b74acc7570306bd38`, then received separate exact-run/dataset/image development-deployment approval. Attendee authorization, committed-source release provenance, fresh end-to-end startup, timed guidance and recording readiness remain pending. Earlier entries below retain development history.

The test-1 public baseline is `public-lab-development`, not attendee release. Its actual prepared-baseline SHA-256 is `b390a5059168e7c4aefba54f7ea613cf59cbff85a5c7abb87a3c0c37b30f630c`; all four new Sandboxes run as UID 10001 and inherit the exact frozen database, manifest, original JSON and pipeline ZIP. The initial two-input `Prepare` exited after a completed source import; scoped inspection and code-preserving recovery completed the resources without reimporting or deleting anything. Snapshot creation now omits resource overrides, and successful imports resolve only through their uniquely named scoped disk metadata. Sixty-six preparation checks and ten startup regression groups pass, but a fresh complete `Prepare` has not yet passed.

Actual test-1 Foundry data-plane access was denied. This maintainer run uses the already-authorized test-2 Foundry project with explicit test-1 Sandbox bindings, without changing IAM or model capacity; it does not validate per-attendee Foundry access. Workers now call the argument-free `verify_feature` MCP tool, whose command remains controller-bound instead of requiring model-generated shell quoting. It includes isolated fictional in-memory shared records and comma-containing terms. That extra software conformance guard prevents a homogeneous public slice from hiding narrowed arrays; it neither changes the public artifact nor substitutes synthetic tests for the eight original-source-derived public checks. Both actual implementation Sandboxes passed this real tool's public/source/conformance verification. The independent primary runs the same guard, and its public baseline identity is kept separate from iterated evidence records.

Bounded same-session repair now repeats the complete immutable worker identity and rejects mismatches before accepting blockers or executing feature validation. Exact mismatch fields are retained on stderr; report-only turns disable tools and share the existing three-attempt budget with feature repair. Fifty-nine combined Foundry/integration/full MCP regressions and seven public packaging regressions pass. The successful live run corrected safety's lexical reaction-term ordering and a genuine governance run-ID mismatch without rewriting the already-valid clinical feature. Result SHA-256 is `203d33acd34362a4b647cdd54e2a276c6da6a9199524f4880b518e85596d2538`; staged provenance SHA-256 is `d0745b58bbf37e2cf6d129dc4360611a21114e0d1165b6902e6b41bfc4974749`. The checksum-verified context is retained at `.build-contexts/public-agent-candidate-9bbcce44-20261010`; candidate execution occurred only in the remote Sandboxes and trusted container, never natively on the maintainer host.

The public development gate rejects missing approval and continues to reject attendee release with the frozen uncommitted pipeline. Digest-pinned deployment replaced the test-2 preview only after explicit human confirmation. All nine live candidate/topic combinations preserve complete canonical/original fields, condition-independent safety and honest empty tirzepatide report coverage; metadata/source identities and 404/422 errors pass. Native Windows gateway inspection verifies exact accepted source and all four artifact hashes, the matching embedded eight-test validation receipt, and application PID 1 UID 10001. WSL-launched Express inspection returned HTTP 404 without a confirmed cause; native Windows inspection succeeded without changing the app or credentials. The gateway inspection process uses UID 0, which is distinct from the verified non-root application. Build-time descriptors and historical source-use flags remain immutable; separate receipts record publication, later approval and live deployment.

Platform-neutral `Readiness` now supports complete opt-in harness pins for the existing application, immutable digest, expected starter/reference state and local frozen package. It verifies the derived app/Express/registry scope, running state, exact frozen bytes and live manifest/original-source/decision identity, then samples the expected preview state. The complete read-only entry point passed against retained test-2 on October 10, 2026: infrastructure/application/frozen-data verification is true, while worker-baseline and attendee-data/release readiness remain false. No allocation, image, credential, IAM or capacity change occurred. Thirteen offline startup groups pass. The first two instruction segments now contain executable report/API checks and explicit rejection of reference-as-starter, manifest fallback and unverified attendee release; their times remain unmeasured targets. Application provisioning/distribution, fresh complete preparation and the actual Skillable contract remain unfinished.

All seven [participant segments](../instructions/README.md), the [checkpoint worksheet](../instructions/worksheet.md) and [platform-neutral facilitator handoff](../instructions/facilitator.md) now cover the recorded path and explicitly authorized live alternatives. They describe the actual SDK/controller-owned stdio MCP, isolated baseline, independent primary, bounded repair, dataset-specific acceptance and separate publication/deployment approval; they do not promise portal connections or an unimplemented telemetry workbook. The static JSON/HTML evidence bundle reproduces byte for byte from the real pinned public result, baseline, frozen package, image, approval and October 10 application observation: three assignments, three workers, 11 recorded check categories and zero blockers. It contains neither executable candidate source nor raw logs, credentials or the full dataset.

The recorded participant checks have been executed in one PowerShell scope, all 16 documented PowerShell blocks parse, and 35 local navigation links/Markdown anchors resolve. The original-receipt inspector example verifies the actual workflow and correctly lists all three optional stages as absent when omitted. The optional read-only portal API recipe returned the expected 20 liraglutide trials and 10 reports at `2026-10-10T18:05:15.8956214Z`; this is a sample, not a new image-bound readiness check. The self-contained evidence viewer passed desktop and 390-pixel mobile overflow/11-check/no-script checks with no browser warnings or errors. Twenty focused evidence/application/public-packaging tests and all 13 offline startup groups pass. These checks establish usable recorded materials, not a measured 75-minute live exercise or attendee release.

The requested presentation-and-instructions milestone is complete. The [presentation package](../presentations/README.md) contains 24 RevealJS slides, detailed [speaker notes](../presentations/speaker-notes.md), a [24-page PDF](../presentations/outputs/lab722-caldova.pdf), 24 slide PNGs at 1280x720, locked local rendering dependencies and a source/artifact-bound export receipt. Local isolated Edge validation covered all slide notes and segment openers, keyboard navigation, speaker view, nine participant links, slide/print overflow, nonblank PDF pages and absence of failed/external requests or console errors. Independent `npm run verify` passed against the persistent exports at `2026-10-10T18:14:42.4764436Z`; all nine linked participant-file hashes match the completed guide. No cloud resources or credentials changed. Skillable-specific work is excluded; timings are unmeasured targets and final product captures, videos and recording readiness remain unfinished.

The infrastructure foundation has successful `azd` deployments in both required westus3 resource groups, `ignite-lab-test-1` and `ignite-lab-test-2`. Each has its own Foundry account/project/model deployment, Express environment, Sandbox group, registry, managed identity, and monitoring resources. The second rollout started with an absent resource group and provisioned in 2 minutes 5 seconds.

Both environments passed Express HTTP 200 and Sandbox execution, allowed/denied egress, snapshot file inheritance, clone lineage, and clone policy/lifecycle checks. The generated Skillable ARM template passed Azure deployment validation. See [the retained rollout evidence](../infra/README.md#verified-rollout-results).

The checks also identified and corrected two smoke-script issues: snapshot IDs were incorrectly read from progress text, and worker clones lacked the source's egress policy. Snapshot JSON now supplies the actual ID, and clones receive default-deny egress during creation.

The synthetic development data pipeline and Python/React research portal are now implemented. The initial ACR validation passed eight focused checks, and a release image was built. The data builder, validator, and atomic stager enforce provenance, checksums, count contracts, and explicit public-source review. Actual AACT/openFDA extraction, approval, and immutable release publication remain pending.

The dedicated `caldova-research` Express reference preview now serves its immutable private-image digest with HTTP 200 health. The build and deployment helpers have both run successfully end to end. Validation starts the same Uvicorn console entry point as the release; its eight checks passed again in ACR run `ds3`. Runtime startup now includes the shared data package on the Python import path, and deployment polling follows the returned ARM operation instead of reporting stale resource failure.

Live API checks and isolated Edge browser checks passed filtering, explicit empty results, offline error/retry recovery, keyboard skip navigation, and desktop/mobile layout. The small browser metadata fix is deployed and verified with a clean console. An environment-only starter update did not reach the running process within the readiness window, and revision restart failed; the maintainer workflow now builds matching immutable starter/reference image defaults instead.

Both variants passed nine container checks, including a separately started process that validates the image's default ready/unavailable response. The starter-to-reference digest deployment round trip passed live API and browser checks. The standalone synthetic application/data milestone is complete, and the retained app is left serving the reference image. See [maintainer preview commands and evidence](../scripts/README.md#research-preview).

Foundry project-scoped access and live Responses inference now pass. The optional project role is in Bicep, and the existing manual test-2 grant was adopted without deletion or duplication. One persistent `caldova-orchestrator` now performs an actual Agent Framework function call in its assigned retained Sandbox clone; this is a diagnostic, not the full three-worker exercise.

Structured plans, worker results, and the deterministic release gate are implemented with focused controller, credential, ownership, remote-status, real-stdio MCP, lineage, and integration tests passing. A first schema-valid model plan drifted into clinical analysis; the plan now preserves exact approved query-function/governance tasks and check names and has passed live validation. Test-2 Bicep configures capacity 20, and actual response headers eventually verified 20 requests/minute and 20,000 tokens/minute. Event sizing is not validated.

The requested developer-baseline sub-agent completed a real starter and a prepared Python 3.13/Node 24 image. Refactored reference validation passed all nine checks in ACR run `dsd`; developer run `dsf` passed nine reference checks plus baseline verification, including genuinely missing query functions, built frontend, read-only trusted files, and frozen synthetic data. The MCP sub-agent completed the real stdio adapter and bounded remote-status/lineage verification.

Secret-free native source import, prepared primary, snapshot, and three clones have now passed live UID/toolchain/frozen-data/starter checks. Actual clone metadata confirms the same prepared snapshot, explicit default-deny egress, and bounded lifecycle. The test-2-only Sandbox count override is deployed at 9; the template default stays 8 and all retained slots are allocated. The primary's allowed request returned HTTP 200 and denied request HTTP 403 with TLS verification intact. Native telemetry reported the allowed request but not a denied entry; denial validation therefore also verifies authoritative policy and requires the specific HTTP 403 outcome, never a generic connection failure.

The first real specialist runs exposed guessed schema filenames, token throttling, invalid package imports, string arguments mistaken for enums, and incomplete result fields. Exact MCP discovery, the actual runtime/data contracts, bounded SDK retries, and deterministic same-session repair now resolve those failures without bypassing tests. The repeatable wrapper accepts the imported manifest and separate primary ID. Governance cannot run against an untouched starter.

Actual Foundry run `9b37caac-1498-46b2-802f-d9c731833885` completed all three specialist sessions with no blockers. Both generated query functions passed fresh-interpreter checks, their integrated candidate passed the original nine acceptance tests on the trusted primary, and all eight deterministic check categories passed, including actual egress and grounded worker identities/source records. The candidate's two source modules and checksums are preserved in the result. Final controller/MCP regression validation passed 59 tests.

The repeatable baseline helper passed 48 focused local checks and a live code-preserving reuse verification against all retained resources. It checks actual clone lineage, UID, policies, permissions, frontend assets, and frozen hashes before publishing controller artifacts. Its authorized provisioning path is locally tested; no new resources were allocated during reuse. The deployed Express preview is still the previously verified reference image, not a built worker-generated candidate.

Human release approval, reviewed public data, Skillable startup, timed attendee validation, slides, screenshots, presenter scripts, and narrated videos are incomplete, so the lab is not ready for recording. Changes remain uncommitted and resources retained; `azd` is verified at version `1.35.1`.

The exact independently accepted source and frozen artifact are now packaged in candidate image `sha256:eba0b2e0f4c57107bcc26d74afb2f97d088743028d2f0f334d96634d2349f791`. ACR run `dsg` succeeded; all nine unchanged tests passed in the non-root packaged runtime in 3.059 seconds, with source and frozen-artifact checks before and after testing. Seventeen packaging regression checks passed. The descriptor binds the agent run, source/result/provenance hashes, frozen identity, and immutable image.

Simon Jakesch approved this exact run/dataset/image for a synthetic development preview. The deterministic gate passed with that approval, remained blocked without approval, and still blocked an attendee release with synthetic data. Digest-pinned deployment succeeded, and live native inspection confirmed the exact accepted source hashes and packaged validation receipt.

Independent live validation then found a source-fidelity defect missed by the original nine tests: the generated safety SQL dropped other candidate mentions from a shared report. The verified reference image was restored, and both A/B mentions passed live verification. The candidate and its original approval/evidence are retained but must not be treated as an accepted live preview.

The worker and independent-primary checks now compare complete source records against the frozen tables for every candidate and condition, rejecting narrowed collections, missing/duplicate records, and changed metadata before the unchanged nine tests. The next milestone is a corrected specialist run and newly pinned candidate image, followed by fresh image-bound human approval. Public-data review, attendee release, and recording readiness remain separate.

The stronger guard passed 25 focused regressions and rejected the actual defective source in its retained Sandbox without modifying the frozen data or original nine tests. The restored reference passed all nine candidate/condition combinations plus report normalization, full mentions, citations, error responses, headers, assets, and an isolated-browser provenance/clean-console check.

Corrected actual run `0e17d6ef-b6db-4380-959b-b73ab867488d` then passed all three workers, full-source fidelity, independent original-nine-test acceptance, actual egress, and all required deterministic categories. ACR run `dsh` passed the nine packaged tests in 3.713 seconds and published `sha256:f9a95fa8f157b717f556e52d3ce17996a6db9d977068d8733451b8bd733a7224`.

Simon Jakesch provided fresh approval bound to this exact corrected run, dataset, and image. The deterministic gate rejects missing or old approval and still blocks a synthetic attendee release. The corrected image is now deployed and healthy. Live checks verified actual source/database/manifest hashes, the embedded validation receipt, Uvicorn UID 10001, complete evidence for all nine API filter combinations, desktop/mobile provenance and shared mentions, explicit empty/error states, and a clean browser console. Final checks passed 64 controller/MCP regressions and 17 Windows-native packaging tests.

The synthetic end-to-end agent-to-live-preview milestone is complete. Public-source intake research is an unapproved proposal only: exact AACT snapshot/access/schema/reuse metadata, candidate mapping, minimal fields, source freshness, privacy review, and release publication remain separate. Skillable startup, timed attendee instructions, and the recording package remain incomplete. All changes are uncommitted; resources and earlier failure evidence are retained.

The user selected a platform-neutral startup entry point with only region and resource-group name as visible configuration. The harness supplies subscription/authentication; attendee identity must be supplied separately rather than inferred from the deployment account. Bicep now has a deterministic scope-derived environment-name default while the explicit `azd` parameter mapping and resource-name seed are preserved. The regenerated ARM template passed read-only Azure validation both with only a region parameter and with the existing test-2 name/capacity overrides; the approved preview remains unchanged. The exact Skillable trigger, identity mapping, substitution syntax, and output adapter are still unverified.

`scripts\start-lab.ps1` now validates by default, explicitly provisions only a fresh harness-supplied scope, or checks infrastructure readiness. Eight focused offline regression groups passed. Actual test-2 `Validate` and `Readiness` executions passed after fixing native Windows launcher resolution and handling Azure CLI output casing and location display names. Readiness verifies six current output-derived resource IDs and provisioning states, rejects absent/failed resources, preserves the explicit environment name, and keeps application/data/attendee gates false. The resource group's metadata location is independent of the requested workload region. No startup provisioning occurred; app/data/baseline wiring, the real Skillable adapter, effective event capacity, and end-to-end startup timing remain pending.

The synthetic baseline leg is now wired as explicit `Prepare` mode. Harness-owned purpose/manifest/checksum configuration is separate from the two visible region/resource-group inputs. The trusted exporter can stage the existing database and manifest byte for byte; preparation checks those pinned hashes on the primary before snapshotting and verifies all three clones before emitting controller bindings. The source export remains standard-library-only; database/count/acceptance validation stays in the trusted container and remote baselines. Nine startup regression groups, 52 preparation checks, four frozen-export tests, and 17 packaging tests pass. Validation-only AMD64 ACR run `dsj` passed the original nine tests in 3.740 seconds and verified the exact retained frozen hashes, non-root execution, readonly trusted files, and genuinely missing query functions. No image was pushed or app/Sandbox provisioned. Default read-only readiness still passes and the approved preview is unchanged. Fresh live allocation/timing, approved app-image startup, reviewed public data, and the real attendee harness adapter remain incomplete.

The user supplied the publicly accessible `Nason/clinicaltrials-database` AACT-derived mirror. Its publisher identifies revision `11b858f5f39519b92ee9a7a98129997f694c7833` as a September 14, 2026 snapshot; HEAD and a bounded 64-byte range request verified availability of the 7,588,032,512-byte DuckDB file. This resolves anonymous source-path discovery, not schema/rights/privacy/extract approval. `data.pipeline.download_aact` now acquires that pinned input into an external maintainer cache with bounded resumable streaming, full-size/SHA-256 verification, verified offline reuse, and explicit failure handling. The full database has not been downloaded or checksum-verified. The separately authorized openFDA intake acquired its catalog/schema and one 4,960,888-byte drug-event ZIP from the latest-listed quarter (2026 Q2, export date October 5, 2026); CRC/JSON and 12,000 records were verified. That single shard is neither a complete endpoint mirror nor a representative clinical sample. Raw input acquisition does not replace the synthetic artifact or approve attendee release.

Nine focused downloader regressions pass on native Windows without DuckDB installed and on Linux; the four existing frozen-export/staging regressions also pass. The actual module's `--check` mode verified HTTP 200 and the pinned size without downloading database bytes. Its repository-contained cache invocation failed with exit code 1 before creating a directory, and Git ignores raw DuckDB/partial files as an additional guard. Validation used tiny fictional transfer payloads, not a full live 7.59 GB download. The approved preview and retained resources are unchanged.

The explicitly authorized full AACT download subsequently completed on October 10, 2026 at 04:52:49 UTC, outside the checkout. The downloader and independent read-only DuckDB inspection both verified the complete pinned size/SHA-256. Actual required schemas and row counts match the four inspected source tables; seven inspected duplicate/ID/orphan/join-mismatch counts are zero. The file contains 48 source tables plus two publisher metadata tables. A source-derived conservative proposal uses exact generic intervention names and four explicit condition labels, excludes invalid required fields, and deterministically selects up to 10 trials per candidate/topic (60 unique trial IDs in the current proposal) plus up to 10 reports per candidate from the disclosed openFDA shard. Exact generic safety matching finds 21 semaglutide reports, 17 liraglutide reports, and no tirzepatide reports in that shard; the wider discovery's two tirzepatide matches were compound-name strings. These are technical extraction counts, not clinical claims. Mapping choices and source/privacy/reuse review remain unapproved; aliases are not inferred from broad other-name associations, no empty clinical records are fabricated, and the synthetic preview is unchanged.

The user then selected the conservative exact-name draft scope. `data.pipeline.extract_public` is implemented and ran on the complete checksum-verified external inputs. The final external review package contains 60 trials and 20 reports in 74,073 JSON bytes, SHA-256 `db1e39943ee51d6cf8fe87628aff905b20e4f13e9af2c1812fa3af2f73814d5c`. It is explicitly `unreviewed-public`, preserves original selected source labels/conditions/reactions separately from normalized categories/terms, and enforces actual per-bucket limits without narrowing shared records. Raw latest-version selection precedes candidate filtering, and conflicting raw same-version copies fail even when differing excluded fields would not appear in the draft. Four focused extraction and four existing frozen-export tests passed; independent actual-source validation passed for every selected field/collection, original case/whitespace, within-input latest versions and all measured bounds. Source/reuse/privacy review, acceptance as a reviewed artifact, publication and attendee release remain unapproved. The current synthetic preview, retained resources and original nine acceptance tests are unchanged.

The project owner subsequently instructed continued selected public-source use on October 10 at 00:17 UTC-5, without another generic review pause. A new source-use decision binds the exact draft/provenance hashes and expressly distinguishes project-owner lab authorization from an independent expert audit, publication, live replacement or attendee release. `data.pipeline.freeze_public` now builds the external `caldova-public-lab-use-v1` package: 60 trials, 20 reports and a 4,206,592-byte database, SHA-256 `c9a7b0c8202bd19c360d020af81278476b8813f791b8902c398f87984d69b21b`. The original extraction JSON remains byte-preserved; its historical false approval flags are not rewritten.

The manifest binds the original-source JSON and a ZIP of actual allowlisted working-tree code, canonical input, extraction provenance and source-use decision. Validation checks archive inventory/file hashes and every complete database record against frozen original projections; staging preserves all four files. The portal retains original source fields, displays partial coverage/dates/approval scope, preserves truly empty tirzepatide safety, and keeps safety independent of trial condition filters. Independent actual-source checks passed all nine candidate/condition combinations, original fields, citations, errors and exact-byte staging. Twenty-six targeted regressions, all nine unchanged synthetic acceptance tests, and frontend type-check/build passed. The local portal is responsive; no public package or image was published, no app or Sandbox was changed. At that milestone the baseline/candidate branch was still synthetic-only.

The remaining local acceptance branch now requires explicit harness-owned `public-lab-development` purpose and a pinned source-use-bound manifest across native export, developer baseline, every worker/independent-primary check, candidate staging/container selection and startup `Prepare`. It protects and carries all four frozen files and source-use identities without relabeling public data or changing the nine original tests. Eight separate public checks derive expected complete records from frozen original JSON, verify metadata/citations/source arrays/coverage/limitations, preserve empty safety and condition independence, and check genuinely unavailable starter versus completed reference state. The baseline probes every frozen candidate/topic and rejects a working empty function even if active/starter bytes match.

Sixty-two preparation checks, ten startup groups, seven native public packaging/legacy-reuse checks, four baseline unit checks and the actual public eight-check runtime suite passed locally. The existing synthetic packaging/export/controller gates remain separate. Production Python 3.13/Node 24/UID 10001/read-only boundaries are unchanged; baseline unit checks mock those boundaries and are not image-import receipts. No Azure operation, new image, reset, allocation, publication or deployment was performed. Exact-image `HumanApproval` and the uncommitted-source attendee restriction remain intact. Live public Foundry/ACA/container validation, a separately approved immutable image, the real Skillable identity/trigger/output adapter, timed guidance and recording readiness remain outstanding.

## Workstreams

### Repository foundation

- Populate attendee-first session metadata.
- Establish instruction, architecture, data, infrastructure, presentation, and media locations.
- Keep unresolved service values and data sources explicit.

### Data pipeline

- Select an immutable AACT snapshot and a bounded set of diabetes and obesity records.
- Select the openFDA drug-event fields needed by the lab.
- Build the bounded relational artifact and deterministic fixtures.
- Generate the manifest, schemas, counts, and checksums.
- Publish an immutable GitHub release asset.
- Preserve AACT acknowledgement and openFDA attribution and disclaimer metadata.
- Exclude any field or content specifically marked as third-party or subject to additional rights.

### Application and agents

- Build the starter and completed research portal states.
- Use Python and Microsoft Agent Framework for the orchestrator, worker contracts, data access, and backend APIs.
- Use React and TypeScript for the attendee portal.
- Implement the orchestrator and three structured worker contracts.
- Implement Sandbox operations and telemetry correlation.
- Add deterministic data, citation, policy, and application tests.
- Prevent the portal and agents from presenting adverse-event reports as proof of causation, incidence, or comparative safety.

### Infrastructure

- Use `azd` and Azure CLI against the ACAPMS subscription as the current maintainer deployment workflow.
- Keep Bicep as the infrastructure source of truth.
- Generate the Skillable ARM template from Bicep.
- Deploy a Foundry project/API endpoint and model deployment for each attendee environment.
- Expose only deployment-specific parameters.
- Provide readiness and fallback paths.
- Add Skillable identity and attendee authorization only after the ARM template is complete and the deployment has passed repeatable rollout tests.

### Attendee content

- Complete and test the seven instruction segments.
- Capture current screenshots from the dedicated Sandbox and Express portals.
- Add expected results and local recovery steps.
- Complete a timed dry run with a new tester.

### Slides and video

- Build the RevealJS deck using `pamelafox/presentation-skills`.
- Explain the goal, reason, services, and outcome for each segment.
- Record narrated videos using slides and tested product captures.
- Publish captions and transcripts with the media.

### Rollout validation

Run two fresh deployments in westus3:

1. `ignite-lab-test-1`
2. `ignite-lab-test-2`

Retain the resources and deployment evidence until the project owner explicitly approves cleanup.

## Confirmations still required

- Authorize and validate a genuine public attendee starter image/distribution and a fresh complete startup in an available scope. The public specialist/candidate workflow and separate exact-image development publication/deployment approvals are complete; neither those approvals nor the read-only readiness check authorize attendee release.
- Preserve genuinely committed pipeline provenance for attendee release; the current public artifact honestly records its frozen uncommitted working-tree snapshot.
- Finish event-scale Foundry sizing. Test-2 agent/inference access, scoped planning, and SDK remote-tool dispatch pass using API `v1`. Both initial rollouts provisioned `gpt-4.1-mini`, version `2025-04-14`, with `GlobalStandard` capacity `1`; test-2 now configures capacity `20`, and effective response headers confirm `20`/`20,000`.
- Obtain the Skillable parameter, identity, and startup contract after the generated ARM template is available.
- Create the Microsoft Stream or SharePoint publishing location.
