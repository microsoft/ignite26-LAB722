# Data

This folder contains the source configuration, schemas, deterministic fixtures, manifests, and staging guidance for the shared Caldova research dataset.

All attendees use the same immutable data version. The primary Sandbox stages it once and records its checksum before creating the baseline snapshot. Worker clones inherit the staged artifact.

## Planned layout

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

The approved relational artifact will use DuckDB. Its planned content is:

- A bounded AACT-derived clinical-trial dataset covering diabetes and obesity.
- Cached openFDA-derived safety fixtures.
- An optional commercial-context dataset only if it fits the lab timing and approval requirements.

The large immutable artifact will be published as a GitHub release asset. Its manifest, schemas, pipeline source, fixtures, and checksum remain in this repository.

## Source status

The source choices are known, but exact releases, fields, filters, and redistribution approval are pending. See [sources/README.md](sources/README.md).
