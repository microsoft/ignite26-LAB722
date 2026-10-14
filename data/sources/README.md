# Data sources

## Approved scenario

- Clinical topic: diabetes and obesity, including a bounded GLP-1 research scenario.
- Trial-data format: curated AACT-derived relational data packaged as DuckDB.
- Safety-data format: cached openFDA-derived fixtures with an optional live request.
- Artifact distribution: versioned four-file lab bundle in the checkout, pinned by `data/lab-release.json`, then staged into the clean prepared VM snapshot.

## Intended public sources

- AACT: `https://aact.ctti-clinicaltrials.org/`
- User-supplied AACT-derived mirror: `https://huggingface.co/datasets/Nason/clinicaltrials-database`
- openFDA drug adverse events: `https://open.fda.gov/apis/drug/event/`

AACT describes its database as public, downloadable, and free to use, and asks users to acknowledge AACT and CTTI. openFDA states that its data is generally unrestricted and CC0 unless specific content is marked otherwise.

The application must preserve the openFDA disclaimer. Adverse-event reports are signals for investigation. They must not be presented as proof that a product caused an event, as incidence rates, or as comparative safety rankings.

## Raw AACT source cache

The supplied mirror is anonymously accessible. Its publisher identifies the pinned revision in `aact-mirror.json` as an AACT flat-file snapshot from **September 14, 2026**, converted to DuckDB. This is a third-party conversion, not an official CTTI-hosted release; the snapshot and CC0 label are publisher claims, not a completed source review. The database is **7,588,032,512 bytes (7.59 GB / 7.07 GiB)**. The pin records the immutable commit, expected size, and publisher's LFS SHA-256 rather than a mutable `main` URL or CDN ETag.

Run the maintainer-only standard-library script from the checkout. The check command performs a HEAD request and downloads no database bytes:

```powershell
python -m data.pipeline.download_aact --check
```

The following command actually downloads the full database into a cache outside the checkout:

```powershell
python -m data.pipeline.download_aact --cache-dir "$env:LOCALAPPDATA\Caldova\source-cache"
```

Without `--cache-dir`, the cache defaults to `%LOCALAPPDATA%\Caldova\source-cache` on Windows or `$XDG_CACHE_HOME/Caldova/source-cache` (otherwise `~/.cache/Caldova/source-cache`) on Linux. Repository-contained cache paths are rejected, including resolved paths through symlinks. Raw DuckDB files are also excluded from Git as a second guard.

The downloader checks free space, uses TLS-verified HTTPS with allowlisted Hugging Face/CDN redirects, streams bounded chunks, and verifies the complete byte count and SHA-256 before publishing a cache entry and acquisition receipt. Transient signed CDN URLs are not recorded. Interrupted `.partial` inputs are retained and resumed only when the server honors the exact byte range. Reuse rehashes the entire cached file without a network request; corrupt inputs, mismatched receipts, unexpected responses, and insufficient space fail explicitly without silently restarting or replacing an existing file. A concurrent downloader holds `.download.lock`; after a terminated process, inspect that lock's PID before manually removing a stale lock.

This script acquires raw maintainer input only. It does not execute the downloaded database, select candidates/aliases, approve privacy or reuse, build a public artifact, publish data, or change the deployed synthetic preview. Maintainers will extract and review only the required trial tables/fields; attendees will stage the smaller approved immutable lab artifact, not this full database.

On October 10, 2026 (UTC), the authorized full download completed in the external cache. Both the downloader and a separate read-only inspection verified the pinned 7,588,032,512-byte input and SHA-256. The actual schemas and types of `studies`, `conditions`, `interventions`, and `intervention_other_names` were checked, with 602,514, 1,083,005, 1,019,126, and 486,506 rows respectively. Seven inspected duplicate/ID/orphan/join-mismatch counts were zero. The database has 48 source tables plus two publisher metadata tables. This verifies the inspected input and relationships, not clinical accuracy or approval for attendee use.

Source inspection also found reasons not to infer aliases automatically: some `intervention_other_names` associations contain several different molecule names or generic class labels, and broader discovery includes studies with missing phases. The separately acquired openFDA shard contains combination/compound names and multi-brand harmonization arrays. The user-selected conservative extract below addresses these mapping risks. The project owner's subsequent October 10 instruction authorizes use of that selected slice for the lab; it does not claim an independent expert audit or authorize publication, live replacement or an attendee release.

## Conservative public review draft

The initial scope selection authorized conservative extraction; the subsequent source-use decision is recorded separately below. `python -m data.pipeline.extract_public` prepares a separate **`unreviewed-public`** draft in the data-aware Python environment. Unlike the standard-library downloader, this module uses the already declared DuckDB/Pydantic pipeline dependencies.

Set `$aactDatabase` to the verified external cached database and `$openFdaArchive` to the verified external drug-event ZIP. The AACT `acquisition-receipt.json` and openFDA `intake-receipt.json` must be adjacent to their respective inputs. The intake URL, export date, archive/member sizes, record count and SHA-256 are pinned in `openfda-intake.json`; the downloaded catalog order is not used to claim recency.

```powershell
python -m data.pipeline.extract_public `
    --aact-database $aactDatabase `
    --openfda-archive $openFdaArchive `
    --output "$env:LOCALAPPDATA\Caldova\review-drafts\new-review-version"
```

Both raw inputs and draft output must be outside the checkout; use paths native to the selected Python runtime. Existing output directories are never replaced. The command verifies the full source checksums and acquisition receipts before reading data, and publishes `public-review-draft.json` plus `draft-provenance.json` only after validation.

The fixed mapping uses trimmed, case-insensitive equality to **semaglutide, liraglutide and tirzepatide** primary intervention names, with `DRUG` interventions and `INTERVENTIONAL` studies. Source condition labels are exactly **Obesity**, **Diabetes Mellitus, Type 2**, **Type 2 Diabetes**, and **Type 2 Diabetes Mellitus**. It does not infer broad aliases from other-name associations, generic Diabetes/Overweight labels, brands, development codes, or compound-name substrings. Null/invalid required trial fields are excluded with recorded counts rather than invented defaults.

Safety matching uses an exact generic `medicinalproduct` or harmonized `generic_name`, excluding a matched drug object when `substance_name` lists additional substances. The latest report version is selected **within the complete acquired input before candidate filtering**, so an older matching version cannot replace an unmapped newer version. Conflicting complete raw copies of the same ID/version fail, even if the differing field would be excluded from the draft; identical copies are deduplicated. The existing normalization helper provides unique uppercase reaction terms, while original terms and matching source drug-name arrays remain separately available for review.

Stable ascending IDs and versioned strict budgets allow at most **10 trials per candidate/topic and 10 reports per candidate in v1**, or **30 trials per candidate/topic and 50 reports per candidate in v2**, measured against complete retained records. V1 validation still rejects larger counts; relabelling an expanded slice as v1 does not widen its policy. A shared record is retained whole or skipped when any represented bucket is full; its other mapped candidates, conditions, or reactions are never dropped to make a limit pass. Original source conditions and intervention labels, including original case/whitespace, remain separate from canonical topic categories. Harmonized brand arrays are metadata, not proof that every listed brand was taken.

The actual verified October 10 review draft contains **60 trials and 20 reports**, with **74,073 JSON bytes**. All six trial buckets contain 10 records; semaglutide/liraglutide each have 10 reports. Tirzepatide has a genuine empty safety result under this mapping in the disclosed single shard. This is a deliberately bounded software demonstration, neither complete nor representative clinical evidence. Four focused extraction tests and the four frozen-export regressions pass; an independent check compared every selected source field/collection, latest within-input version and actual limit with the original inputs.

The historical draft remains intentionally rejected by `DatasetInput` and cannot pass the synthetic baseline's public-data gate. Its false approval flags are retained as extraction-time evidence, not rewritten after the project owner's later instruction. The public-freeze path records that subsequent decision, preserves the exact source projections and limitations, and does not pause the same selected source use for another generic review.

## Freezing the authorized public lab slice

On **October 10, 2026 at 00:17 UTC-5**, Simon Jakesch instructed continued use of the selected publicly available datasets. The source-use record has scope `project-owner-selected-public-lab-use` and binds the **74,073-byte draft SHA-256 `db1e39943ee51d6cf8fe87628aff905b20e4f13e9af2c1812fa3af2f73814d5c`** plus its original provenance checksum. It explicitly records that no independent expert audit, publication, live replacement or attendee release is authorized.

For the already selected version, use that recorded decision rather than requesting it again. Future changed extracts need a decision bound to their own exact hashes. Set `$draftDirectory` to the verified external draft directory and `$sourceUseApproval` to the recorded JSON decision:

```powershell
python -m data.pipeline.freeze_public `
    --draft-directory $draftDirectory `
    --source-use-approval $sourceUseApproval `
    --output "$env:LOCALAPPDATA\Caldova\artifacts\new-public-version" `
    --dataset-version caldova-public-lab-use-v1
```

The command verifies draft/provenance hashes, pinned inputs, extraction-code identity and decision chronology, without redownloading the raw sources. It refuses an existing output directory or a checkout-contained draft/output. The original draft and acquisition receipts are never overwritten.

The actual local build contains **60 trials, 20 reports, and a 4,206,592-byte database**, SHA-256 `c9a7b0c8202bd19c360d020af81278476b8813f791b8902c398f87984d69b21b`. Its four-file package retains the exact original `source-records.json` and a bounded `pipeline-source.zip`, including canonical input, source-use decision, original provenance and actual allowlisted source bytes. `pipeline_commit=uncommitted-development` is honest working-tree provenance, not a fabricated clean commit. The manifest trust anchor is `22a6ef07b06bbb7e8829d51ea5d0612c2122ffab786d4edbbd75d3a80a4d8039`.

Validation independently compares every database record and complete canonical collection with the frozen extraction, preserves source identity/attribution, verifies auxiliary checksums and the ZIP's file inventory/checksums, and rejects unsafe archive entries. `data.pipeline.stage_dataset` stages all four files under the manifest trust anchor and preserves their bytes. Public API checks passed all nine actual candidate/condition combinations, complete original source projections, condition-independent safety results, true empty tirzepatide safety, and 404/422 errors. Twenty-six targeted tests, the original nine synthetic acceptance tests, and frontend type-check/build passed.

The portal displays a bounded-public-data banner, original source fields, dated provenance and exact source-use scope; its legacy `reviewed-public` label does not claim clinical validation or an expert audit. The later separately approved v1 agent-built development deployment is documented in [the script history](../../scripts/README.md); those image/run receipts do not apply to v2.

## Versioned v2 lab bundle

On October 14, 2026, the project owner approved a modest expansion of the same conservative selection, then explicitly confirmed distribution of the exact **168-trial, 38-report** slice in the fork and prepared Skillable VM. Its draft SHA-256 is `5c31dcd20478c1644b50eff7a7286b9c568094dd1e26427843afd23fc9dfe57c`; the original draft/provenance flags remain false. The separate source-use decision is frozen in the ZIP, while [the release record](../lab-release.json) records distribution authorization and pins the new manifest.

The v2 extractor uses `--mapping-version conservative-exact-generics-v2`. It reads the same pinned inputs, does not infer new names, and retains all 38 eligible reports (21 semaglutide and 17 liraglutide mentions). Tirzepatide still has no matching reports in this shard. Five candidate/topic trial buckets reach 30; tirzepatide/type-2-diabetes has 26. Whole shared trials make this 168 unique records rather than the sum of the buckets. Phase/status summaries and filters make the additional source coverage inspectable without changing complete record arrays or filtering safety reports.

The freeze uses `--pipeline-commit <full-commit-SHA>`. Every allowlisted pipeline/backend/frontend/test source is compared byte-for-byte with Git before the archive is labelled `git-commit`; a missing file, dirty allowlisted source or mismatched commit fails. The manifest and ZIP bind the same source revision. V1 is neither regenerated nor relabelled.

The four files under `data/lab-datasets/caldova-public-lab-use-v2` are the only dataset payload: database, manifest, original JSON and pipeline-source ZIP, totalling **4,468,808 bytes (4.26 MiB)**. `stage-lab-data.ps1` verifies them offline with the release pin, atomically stages a new destination, or checks an identical existing copy. The final bundle's native Windows local staging measured **0.37 seconds**, with an identical repeat verified as reused. No source download or extraction belongs in the attendee session. The measured local cached-input v2 extraction took 88.24 seconds; neither local measurement is Skillable timing, a remote build or a 75-minute rehearsal result.

Distribution authorization is not independent clinical/expert validation, live deployment approval, effective attendee permissions, or a successful fresh walkthrough. Existing source-use flags remain historical records rather than being edited to claim those later stages.

## Build placeholders

The original source-config example retains these placeholders for integrations not using the implemented pinned-source path:

- `TODO_TRIAL_DATA_SOURCE`
- `TODO_SAFETY_DATA_SOURCE`
- `TODO_OPTIONAL_COMMERCIAL_DATA_SOURCE`

The current AACT/openFDA public-freeze path uses `aact-mirror.json` and `openfda-intake.json`, with exact URLs, source dates, fields and mapping recorded in the frozen package; these example placeholders do not block it. Commercial context remains optional and unimplemented.

## Required approval record

Before generating the first release artifact, record:

- Source name and URL
- Release or retrieval date
- Included interventions and conditions
- Included and excluded fields
- Filtering and deduplication rules
- License and attribution requirements
- Responsible-use wording

The generated manifest must include schema version, counts, checksums, source-use scope and honest pipeline identity. The local public-freeze package captures its working-tree source ZIP; an attendee release additionally requires a committed pipeline and independent exact-image approval.
