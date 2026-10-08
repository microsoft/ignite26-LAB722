# Attendee instructions

## Caldova Research Preview Factory

In this 75-minute lab, you configure a Microsoft Foundry orchestrator that assigns work to specialist agents running in isolated Azure Container Apps Sandboxes. The agents add an evidence-backed research panel to Caldova's application. You verify network controls and deterministic tests before publishing the approved result to Azure Container Apps Express.

The same instructions support the guided Ignite session and self-paced completion. Each segment will include a short narrated video before the final lab release.

## Lab schedule

| Segment | Time | Primary service | Outcome |
|---|---:|---|---|
| [0. Welcome and readiness](00-welcome-and-readiness.md) | 5 minutes | Supporting services | The environment and data version are ready |
| [1. Open the research portal](01-open-research-portal.md) | 4 minutes | ACA Express | The starter application is available |
| [2. Configure the orchestrator](02-configure-orchestrator.md) | 15 minutes | Foundry Agent Service | The orchestrator has approved tools and a reviewed plan |
| [3. Prepare the Sandbox](03-prepare-sandbox.md) | 15 minutes | ACA Sandboxes | A tested baseline snapshot is available |
| [4. Run the agent team](04-run-agent-team.md) | 23 minutes | ACA Sandboxes | Three workers produce a validated release candidate |
| [5. Build and publish](05-build-and-publish.md) | 6 minutes | ACR and ACA Express | The approved image is live |
| [6. Trace the evidence](06-trace-the-evidence.md) | 7 minutes | Azure Monitor | The complete workflow is auditable |

## Service allocation

| Area | Minutes | Share |
|---|---:|---:|
| ACA Sandboxes | 38 | 50.7% |
| ACA Express | 7 | 9.3% |
| Foundry Agent Service | 15 | 20.0% |
| Other services | 15 | 20.0% |
| **Total** | **75** | **100%** |

## Lab environment

Use the dedicated product portals for the relevant exercises:

- ACA Sandboxes: `http://sandboxes.azure.com/`
- ACA Express: `https://containerapps.azure.com/`

The event platform starts the infrastructure deployment before or when you enter the lab. Sign in immediately, then complete Segment 0 while deployment finishes. The environment should normally be ready within 5-10 minutes.

## Data used in the lab

The lab uses one versioned, read-only dataset shared by all attendees. Your primary Sandbox stages the artifact once. The worker clones inherit it from the baseline snapshot.

The approved source locations are still being finalized:

- `TODO_TRIAL_DATA_SOURCE`
- `TODO_SAFETY_DATA_SOURCE`
- `TODO_OPTIONAL_COMMERCIAL_DATA_SOURCE`

See [the data-source record](../data/sources/README.md) for ownership and approval requirements.
