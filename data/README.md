# Data

This folder contains the source configuration, schemas, deterministic fixtures, manifests, and staging guidance for the shared Caldova research dataset.

All attendees use the same immutable data version. The primary Sandbox stages it once and records its checksum before creating the baseline snapshot. Worker clones inherit the staged artifact.

## Bundled v2 delivery

The new live-path checkout includes **`caldova-public-lab-use-v2`**, with **168 trials and 38 safety reports** across the same three candidates. Its four files total **4.26 MiB** and live in `lab-datasets/caldova-public-lab-use-v2`; [lab-release.json](lab-release.json) pins the manifest and records the project owner's exact-slice distribution confirmation. The frozen pipeline ZIP verifies allowlisted source bytes against its recorded full Git commit. V1 files and recorded development evidence remain unchanged.

Run `.\scripts\stage-lab-data.ps1 -ConfigureSession` from the repository root to verify and atomically stage/reuse the bundle offline. The helper uses only Python's standard library and sets the existing data pins in the current process; no raw download, Azure call, worker allocation or package installation occurs. Stage this checkout on the clean VM before capture, then configure each launched session explicitly. See [the full handoff](../scripts/README.md#portable-image-and-data-delivery).

The project owner approved selected-source use and fork/VM distribution, not independent clinical validation or a completed attendee walkthrough. The same disclosed shard still has no matching tirzepatide safety reports. Trial phase/status summaries and filters affect trials only. [lab-images.json](lab-images.json) now records the separately published v2 starter/reference digests, their exact source/data identities and independent container/anonymous-pull checks. It does not claim an allocated Express deployment or fresh Skillable acceptance. Old v1 image/run receipts cannot approve these assets.

## Implemented development slice

`fixtures/research-data.json` is an explicitly fictional `synthetic-development` fixture: three candidates, four trials, and five raw safety-report records that normalize to three distinct reports. It is not an AACT/openFDA extract and does not supply fabricated clinical citations. It remains the retained developer-image baseline; the separately authorized public lab artifact is described below.

The Python pipeline in `pipeline/` validates its Pydantic input contract, builds DuckDB and `data-manifest.json`, verifies artifact identity and counts, and stages a validated copy atomically. Safety normalization selects the latest report version, removes identical copies and duplicate reaction terms, and rejects conflicting copies.

Run these maintainer commands from the repository root in the prepared Python environment:

```powershell
python -m data.pipeline.build_dataset --input data\fixtures\research-data.json --output data\artifacts\development --schema-dir data\schemas
python -m data.pipeline.validate_dataset --manifest data\artifacts\development\data-manifest.json
python -m data.pipeline.stage_dataset --manifest data\artifacts\development\data-manifest.json --destination data\artifacts\staged-development
```

The builder and stager refuse to overwrite existing output directories. Remote staging requires an HTTPS manifest URL and `--manifest-sha256` containing the independently published manifest checksum. The validator checks database size, SHA-256, dataset identity, and the complete table-count contract; unsafe artifact filenames and symlinked database inputs are rejected.

Repeated builds preserve logical identity and query results, not necessarily identical database bytes or build timestamps. Freeze one artifact and its manifest rather than rebuilding it for each attendee. Public inputs require recorded source-use approval, source metadata and citations. `freeze_public --pipeline-commit` verifies every allowlisted source byte before recording committed provenance; the legacy no-commit path honestly retains a working-tree identity. Committed provenance alone does not pass the attendee-release gate.

## Frozen public lab slice

On October 10, 2026, the project owner directed continued use of the selected conservative public slice. `python -m data.pipeline.freeze_public` now binds that decision to the exact draft/provenance hashes and builds a new external **`caldova-public-lab-use-v1`** artifact: **60 trials, 20 reports, and a 4,206,592-byte DuckDB database**. This is project-owner lab-source authorization, not an independently performed expert audit, publication approval or an attendee image release.

The package includes `data-manifest.json`, `caldova-research.duckdb`, the byte-preserved `source-records.json`, and a checksum-bound `pipeline-source.zip` containing actual allowlisted working-tree code, canonical build input, original extraction provenance and the source-use decision. Validation compares every canonical database record with the frozen original projections, checks complete source identity/counts and archive contents, and rejects corruption or unsafe filenames. Staging preserves all four files byte for byte.

The portal exposes original condition/intervention/drug/reaction fields alongside the canonical query fields and provides `/api/source-records` for the complete frozen extraction. It distinguishes historical draft flags from the subsequent source-use decision, displays partial-coverage notes, and keeps the genuine empty tirzepatide safety result. An independent check passed all nine real candidate/condition combinations. Twenty-six targeted regressions, the nine unchanged synthetic acceptance tests, and frontend type-check/build passed.

This section preserves the initial v1 freeze history. Later separately approved public-worker and development-deployment evidence is recorded in [the script history](../scripts/README.md); it is not a v2 image or a fresh participant run. See [the public-freeze command and scope](sources/README.md#freezing-the-authorized-public-lab-slice).

## Release layout

```text
data/
|-- lab-images.json
|-- lab-release.json
|-- lab-datasets/
|   `-- caldova-public-lab-use-v2/
|-- sources/
|   |-- README.md
|   `-- source-config.example.json
|-- pipeline/
|-- schemas/
|-- fixtures/
|-- manifests/
`-- artifacts/
```

The approved relational artifact will use the implemented DuckDB pipeline. Its planned source content is:

- A bounded AACT-derived clinical-trial dataset covering diabetes and obesity.
- Cached openFDA-derived safety fixtures.
- An optional commercial-context dataset only if it fits the lab timing and approval requirements.

The bounded v2 bundle is distributed with the checkout after the project owner's explicit confirmation; a separate GitHub release-asset download is not required. Raw maintainer inputs remain outside the checkout. The ready-made v2 images have been published and anonymously pulled; clean VM capture, actual attendee access/deployment and the fresh live walkthrough remain separate operations.

## Source use

AACT is a public relational representation of ClinicalTrials.gov data and asks users to acknowledge AACT and CTTI. openFDA data is generally public domain and made available under CC0 unless the relevant documentation marks content as subject to additional rights.

The lab will use the public datasets directly to create a bounded artifact. Maintainers still need to select an immutable snapshot, document the included fields and filters, preserve attribution and disclaimers, and exclude any specifically marked third-party content.

See [sources/README.md](sources/README.md).

## Raw-source acquisition

The user-supplied AACT-derived Hugging Face mirror has a pinned **7.59 GB (7.07 GiB)** DuckDB input. Keep the full source outside Git and the checkout. `python -m data.pipeline.download_aact --check` verifies public availability and advertised size without downloading it; running the module without `--check` explicitly downloads to an external, checksum-verified maintainer cache. See [source cache commands and review boundaries](sources/README.md#raw-aact-source-cache).

Raw acquisition alone does not replace the synthetic fixture or authorize an attendee release. The separately authorized public lab artifact is the much smaller bounded extract above, with its own manifest and checksums.

The conservative draft extractor in `pipeline/extract_public.py` produced a separately labeled `unreviewed-public` package outside the checkout: 60 trials, 20 reports and a 74,073-byte JSON draft, with pinned input hashes, complete selected source projections, measured limits and provenance. Four focused extraction regressions and an independent full-selected-record comparison passed. The original draft remains unchanged and is not directly accepted by the generic artifact builder; `freeze_public` supplies the subsequent, explicitly bounded source-use decision.
