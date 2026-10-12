# Data

This folder contains the source configuration, schemas, deterministic fixtures, manifests, and staging guidance for the shared Caldova research dataset.

All attendees use the same immutable data version. The primary Sandbox stages it once and records its checksum before creating the baseline snapshot. Worker clones inherit the staged artifact.

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

Repeated builds preserve logical identity and query results, not necessarily identical database bytes or build timestamps. Freeze one artifact and its manifest for an attendee release, rather than rebuilding it independently for each attendee. Public inputs require recorded source-use approval, source metadata and citations. The local public-freeze path captures an exact source ZIP rather than falsely assigning an old commit to uncommitted implementation; the attendee release gate still requires a full pipeline commit.

## Frozen public lab slice

On October 10, 2026, the project owner directed continued use of the selected conservative public slice. `python -m data.pipeline.freeze_public` now binds that decision to the exact draft/provenance hashes and builds a new external **`caldova-public-lab-use-v1`** artifact: **60 trials, 20 reports, and a 4,206,592-byte DuckDB database**. This is project-owner lab-source authorization, not an independently performed expert audit, publication approval or an attendee image release.

The package includes `data-manifest.json`, `caldova-research.duckdb`, the byte-preserved `source-records.json`, and a checksum-bound `pipeline-source.zip` containing actual allowlisted working-tree code, canonical build input, original extraction provenance and the source-use decision. Validation compares every canonical database record with the frozen original projections, checks complete source identity/counts and archive contents, and rejects corruption or unsafe filenames. Staging preserves all four files byte for byte.

The portal exposes original condition/intervention/drug/reaction fields alongside the canonical query fields and provides `/api/source-records` for the complete frozen extraction. It distinguishes historical draft flags from the subsequent source-use decision, displays partial-coverage notes, and keeps the genuine empty tirzepatide safety result. An independent check passed all nine real candidate/condition combinations. Twenty-six targeted regressions, the nine unchanged synthetic acceptance tests, and frontend type-check/build passed.

See [the public-freeze command and scope](sources/README.md#freezing-the-authorized-public-lab-slice). The public package is local and unpublished. The existing synthetic Azure preview, original fixture tests, and synthetic-only worker-baseline/candidate packaging path remain unchanged; public worker acceptance and attendee startup integration are still required.

## Release layout

```text
data/
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

The bounded immutable attendee artifact is planned for a GitHub release asset after explicit publication authorization. Raw maintainer inputs remain outside the checkout. The local public artifact has not been published.

## Source use

AACT is a public relational representation of ClinicalTrials.gov data and asks users to acknowledge AACT and CTTI. openFDA data is generally public domain and made available under CC0 unless the relevant documentation marks content as subject to additional rights.

The lab will use the public datasets directly to create a bounded artifact. Maintainers still need to select an immutable snapshot, document the included fields and filters, preserve attribution and disclaimers, and exclude any specifically marked third-party content.

See [sources/README.md](sources/README.md).

## Raw-source acquisition

The user-supplied AACT-derived Hugging Face mirror has a pinned **7.59 GB (7.07 GiB)** DuckDB input. Keep the full source outside Git and the checkout. `python -m data.pipeline.download_aact --check` verifies public availability and advertised size without downloading it; running the module without `--check` explicitly downloads to an external, checksum-verified maintainer cache. See [source cache commands and review boundaries](sources/README.md#raw-aact-source-cache).

Raw acquisition alone does not replace the synthetic fixture or authorize an attendee release. The separately authorized public lab artifact is the much smaller bounded extract above, with its own manifest and checksums.

The conservative draft extractor in `pipeline/extract_public.py` produced a separately labeled `unreviewed-public` package outside the checkout: 60 trials, 20 reports and a 74,073-byte JSON draft, with pinned input hashes, complete selected source projections, measured limits and provenance. Four focused extraction regressions and an independent full-selected-record comparison passed. The original draft remains unchanged and is not directly accepted by the generic artifact builder; `freeze_public` supplies the subsequent, explicitly bounded source-use decision.
