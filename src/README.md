# Source

This folder will contain the lab-owned application and agent components.

## Planned components

```text
src/
|-- research-portal/
|-- orchestrator/
|-- sandbox-mcp/
|-- workers/
|   |-- clinical-trials/
|   |-- drug-safety/
|   `-- quality-governance/
`-- developer-image/
```

## Component responsibilities

- `research-portal/`: React and TypeScript starter and completed Caldova application states.
- `orchestrator/`: Python coordinator built with Microsoft Agent Framework and a structured release decision.
- `sandbox-mcp/`: Python service for authenticated operations that create, clone, and operate Sandboxes.
- `workers/`: Python-based bounded roles and structured output contracts using Microsoft Agent Framework.
- `developer-image/`: the prepared Python, Node.js, data, and validation environment used before snapshot creation.

## Implementation constraints

- Generated or repository-supplied code runs only inside ACA Sandboxes.
- Cached fixtures are authoritative for acceptance tests.
- Worker outputs must validate against checked-in schemas.
- The application must display source identifiers and responsible-use limitations.
- The release process uses an immutable image digest.
- Python packages and JavaScript dependencies must be pinned after the first runnable vertical slice identifies the minimum required set.
