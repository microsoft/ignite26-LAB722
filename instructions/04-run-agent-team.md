# Segment 4 - Run the agent team (23 minutes)

Clone the prepared snapshot for three specialist agents, prove the egress policy, and combine only the outputs that pass deterministic validation.

## Why this segment matters

Parallel agents reduce delivery time, but their code and conclusions still need isolation, network boundaries, citations, and measurable acceptance criteria.

## Services used

- Azure Container Apps Sandboxes
- Microsoft Foundry Agent Service
- Sandbox MCP connection
- Shared clinical-trial and safety data

## Learning objectives

- Fan out specialist work from one prepared snapshot.
- Apply and test approved outbound destinations.
- Use tests and schemas instead of model confidence for release decisions.

## Starting state

- The primary snapshot exists.
- The orchestrator has three approved worker assignments.
- The acceptance suite and egress checks are available.

## Task 1 - Start specialist workers

1. Approve creation of three Sandbox clones from the baseline snapshot.
2. Assign the clinical-trials role to the first clone.
3. Assign the drug-safety role to the second clone.
4. Assign the quality/governance role to the third clone.
5. Confirm that all three clones report the same source commit, data version, and snapshot identifier.

## Task 2 - Prove outbound controls

1. Review the supplied egress allowlist.
2. Confirm that the approved data endpoint is present.
3. Run the allowed request.
4. Run the supplied request to an unapproved test destination.
5. Record the successful and blocked results.

## Task 3 - Validate and integrate

1. Collect each worker's structured output.
2. Validate each output against its schema.
3. Run the clinical-trial fixture assertions.
4. Run the safety normalization and deduplication assertions.
5. Run the citation and responsible-use assertions.
6. Integrate only the outputs that pass their checks.
7. Run the complete application acceptance suite.
8. Review the orchestrator's evidence-based release recommendation.

## Checkpoint

- Three worker clones started from the same snapshot.
- The approved request succeeded and the unapproved request was blocked.
- Every included worker output passes its schema and tests.
- The release candidate contains citations and required limitations.
- The application makes no treatment recommendation or unsupported safety claim.

## Troubleshooting

| Symptom | Check | Recovery |
|---|---|---|
| Worker reports a different version | Compare its snapshot identifier | Recreate that clone from the baseline snapshot |
| Live safety request fails | Check the recorded egress result | Use the authoritative cached fixture |
| A worker output fails its schema | Review the role's output contract | Rerun only that bounded task |
| Acceptance result differs between runs | Confirm fixture and source versions | Reset to the baseline snapshot and cached fixtures |

## Segment outcome

A release candidate has passed deterministic application, data, citation, and policy checks.
