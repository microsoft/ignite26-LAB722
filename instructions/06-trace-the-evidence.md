# Segment 6 - Trace the evidence (7 minutes)

Use the prepared telemetry view to trace the feature request through agent planning, Sandbox execution, validation, image publication, and the Express URL.

## Why this segment matters

Agent output is easier to trust when the source, data, execution environment, tests, approvals, and deployed artifact can be correlated.

## Services used

- Azure Monitor Application Insights
- Log Analytics
- Azure Container Registry
- Azure Container Apps Express

## Learning objectives

- Follow one correlation identifier across the complete workflow.
- Verify that the deployed image matches the tested candidate.
- Identify the evidence needed to investigate or reproduce the result.

## Starting state

- The Express application is running the approved image digest.
- Agent, Sandbox, test, and deployment telemetry has been emitted.

## Task 1 - Follow the workflow

1. Open the supplied telemetry workbook.
2. Filter by the feature-request correlation identifier.
3. Locate the orchestrator plan and approval events.
4. Locate the primary Sandbox, snapshot, and three clone identifiers.
5. Locate the egress, schema, acceptance, and responsible-use results.
6. Compare the approved image digest with the active Express revision.
7. Open the final application URL from the trace.

## Checkpoint

The trace contains:

- Feature-request identifier
- Source commit and data version
- Orchestrator and worker session identifiers
- Primary Sandbox, snapshot, and clone identifiers
- Allowed and denied egress results
- Acceptance and governance results
- Image digest
- Express URL and active revision

## Troubleshooting

| Symptom | Check | Recovery |
|---|---|---|
| One stage is missing | Check that all views use the same correlation identifier | Open the prepared recorded trace for comparison |
| Digest does not match | Compare the build and active revision timestamps | Return to Segment 5 and activate the approved digest |
| Live telemetry is delayed | Check the workbook time range | Use the prepared trace while ingestion completes |

## Segment outcome

You have a live application and an auditable chain from the request to the deployed artifact.
