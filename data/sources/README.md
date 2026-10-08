# Data sources

## Approved scenario

- Clinical topic: diabetes and obesity, including a bounded GLP-1 research scenario.
- Trial-data format: curated AACT-derived relational data packaged as DuckDB.
- Safety-data format: cached openFDA-derived fixtures with an optional live request.
- Artifact distribution: GitHub release asset with a checked-in manifest and checksum.

## Intended public sources

- AACT: `https://aact.ctti-clinicaltrials.org/`
- openFDA drug adverse events: `https://open.fda.gov/apis/drug/event/`

AACT describes its database as public, downloadable, and free to use, and asks users to acknowledge AACT and CTTI. openFDA states that its data is generally unrestricted and CC0 unless specific content is marked otherwise.

The application must preserve the openFDA disclaimer. Adverse-event reports are signals for investigation. They must not be presented as proof that a product caused an event, as incidence rates, or as comparative safety rankings.

## Build placeholders

Use these values until a named data reviewer approves exact public URLs, releases, fields, and filters:

- `TODO_TRIAL_DATA_SOURCE`
- `TODO_SAFETY_DATA_SOURCE`
- `TODO_OPTIONAL_COMMERCIAL_DATA_SOURCE`

The source families are selected. Replace the placeholders only when the pipeline points to a fixed snapshot or endpoint and the manifest records the selection.

## Required approval record

Before generating the first release artifact, record:

- Source name and URL
- Release or retrieval date
- Included interventions and conditions
- Included and excluded fields
- Filtering and deduplication rules
- License and attribution requirements
- Responsible-use wording

The generated manifest must include the pipeline commit, schema version, record counts, and artifact checksum.
