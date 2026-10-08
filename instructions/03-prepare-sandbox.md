# Segment 3 - Prepare the Sandbox (15 minutes)

Create the primary development Sandbox, stage the shared source and data, reproduce the missing feature, and snapshot the prepared workspace.

## Why this segment matters

Preparing dependencies and data once gives every worker an identical starting point. The snapshot also records the source and data versions used to produce the result.

## Services used

- Azure Container Apps Sandboxes
- Shared GitHub release data artifact
- Approved package and source endpoints

## Learning objectives

- Create and inspect a development Sandbox.
- Stage and verify a versioned shared dataset.
- Create a reusable snapshot after reproducing the baseline.

## Starting state

- The Sandbox Group and prepared developer image are available.
- The orchestrator's plan is approved.
- The dataset manifest and checksum are available.

## Task 1 - Prepare the workspace

1. Open `http://sandboxes.azure.com/`.
2. Create the primary Sandbox from the prepared developer image.
3. Stage the supplied source bundle or approved repository content.
4. Stage the shared data artifact.
5. Verify the data checksum and manifest version.
6. Restore the supplied project dependencies from approved endpoints.

## Task 2 - Reproduce and snapshot

1. Run the supplied baseline check.
2. Confirm that the requested research panel is missing.
3. Record the runtime, source commit, and data version.
4. Create a snapshot of the prepared workspace.
5. Record the snapshot identifier.

## Checkpoint

- The primary Sandbox is healthy.
- Source and data checksums match the manifest.
- The baseline check reproduces the missing capability.
- A snapshot exists for the correct source and data versions.

## Troubleshooting

| Symptom | Check | Recovery |
|---|---|---|
| Data checksum differs | Compare the manifest version | Restage the immutable artifact |
| Dependency restore cannot reach a source | Review the approved destinations | Use the prepared dependency cache |
| Snapshot action is unavailable | Confirm the attendee's preassigned role | Use the facilitator identity-recovery path |

## Segment outcome

An immutable prepared baseline is ready for parallel specialist work.
