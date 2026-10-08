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

- `research-portal/`: starter and completed Caldova application states.
- `orchestrator/`: the Foundry-hosted coordinator and structured release decision.
- `sandbox-mcp/`: authenticated operations for creating, cloning, and operating Sandboxes.
- `workers/`: bounded role instructions and structured output contracts.
- `developer-image/`: the prepared Sandbox environment used before snapshot creation.

## Implementation constraints

- Generated or repository-supplied code runs only inside ACA Sandboxes.
- Cached fixtures are authoritative for acceptance tests.
- Worker outputs must validate against checked-in schemas.
- The application must display source identifiers and responsible-use limitations.
- The release process uses an immutable image digest.
- Runtime and package choices will be recorded only after the service contracts and application design are approved.
