# Segment 5 - Build and publish (6 minutes)

Approve the final image build, record its digest, and update the ACA Express application to the validated result.

## Why this segment matters

The image digest connects the tested source to the deployed application. Publishing by digest prevents a later tag change from replacing the approved artifact.

## Services used

- Azure Container Registry and ACR Tasks
- Azure Container Apps Express

## Learning objectives

- Approve a build only after acceptance checks pass.
- Record an immutable image digest.
- Update and verify an Express application.

## Starting state

- The release candidate passes all required checks.
- The ACR build task and Express application already exist.

## Task 1 - Build the image (3 minutes)

1. Review the source commit and acceptance summary attached to the build request.
2. Approve the ACR task.
3. Record the resulting image digest.

## Task 2 - Publish with Express (3 minutes)

1. Open `https://containerapps.azure.com/`.
2. Update the Caldova application to the approved image digest.
3. Open the public application URL.
4. Confirm that the evidence panel displays the expected fixture-backed result, citations, and limitations.

## Checkpoint

- The build source matches the validated commit.
- The Express application uses the approved digest.
- The completed research panel works at the original baseline URL.

## Troubleshooting

| Symptom | Check | Recovery |
|---|---|---|
| Build does not complete in the segment | Check the ACR task status | Use the prepared fallback digest tied to the same source |
| Express update shows the old version | Compare the active digest | Refresh after the new revision is active |
| Evidence panel cannot reach live data | Check the fallback state | Confirm the cached authoritative result is displayed |

## Segment outcome

The tested Caldova research application is live on ACA Express.
