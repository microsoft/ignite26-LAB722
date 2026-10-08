# Segment 1 - Open the research portal (4 minutes)

Use the dedicated ACA Express portal to create or open the starter Caldova application and confirm that the requested research panel is not yet implemented.

## Why this segment matters

The starter application gives you a visible baseline. You will return to the same URL after the agents build and validate the new capability.

## Services used

- Azure Container Apps Express
- Azure Container Registry

## Learning objectives

- Locate the lab application in the Express portal.
- Identify its image and public endpoint.
- Reproduce the missing capability before making changes.

## Starting state

- The starter image and Express configuration are available.
- The readiness check from Segment 0 passes.

## Task 1 - Open the starter application

1. Open `https://containerapps.azure.com/`.
2. Select the lab's starter application.
3. Open its public URL.
4. Navigate to the research workspace.
5. Confirm that the requested evidence panel is marked as unavailable.

## Checkpoint

- The starter application loads successfully.
- You can reproduce the missing research panel.
- You have recorded the application URL and current image digest.

## Troubleshooting

| Symptom | Check | Recovery |
|---|---|---|
| Application is not listed | Confirm the expected resource group | Refresh after the readiness check passes |
| Public URL returns an error | Check the application status and revision | Use the prepared starter revision |
| Research workspace loads cached content | Confirm the image digest | Refresh with the supplied clean-session link |

## Segment outcome

You have a working baseline URL and a visible feature request to implement.
