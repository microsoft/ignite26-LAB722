# Data sources

## Approved scenario

- Clinical topic: diabetes and obesity, including a bounded GLP-1 research scenario.
- Trial-data format: curated AACT-derived relational data packaged as DuckDB.
- Safety-data format: cached openFDA-derived fixtures with an optional live request.
- Artifact distribution: GitHub release asset with a checked-in manifest and checksum.

## Source placeholders

Use these values until a named data reviewer approves exact public URLs, releases, fields, and filters:

- `TODO_TRIAL_DATA_SOURCE`
- `TODO_SAFETY_DATA_SOURCE`
- `TODO_OPTIONAL_COMMERCIAL_DATA_SOURCE`

Do not replace a placeholder with an unreviewed URL.

## Required approval record

Before generating the first release artifact, record:

- Data licensing and redistribution reviewer
- Medical or responsible AI reviewer
- Source name and URL
- Release or retrieval date
- Included interventions and conditions
- Included and excluded fields
- Filtering and deduplication rules
- License and attribution requirements
- Privacy review result
- Responsible-use wording

The generated manifest must include the pipeline commit, schema version, record counts, and artifact checksum.
