# Implementation plan

## Goal

Deliver a 75-minute guided and self-paced lab in which attendees configure a Foundry orchestrator, prepare and clone ACA Sandboxes, validate parallel agent work, and publish a Caldova research application to ACA Express.

## Confirmed decisions

| Area | Decision |
|---|---|
| Clinical topic | Diabetes and obesity with a bounded GLP-1 scenario |
| Trial data | Curated AACT-derived DuckDB artifact |
| Safety data | Cached openFDA-derived fixtures plus an optional live request |
| Artifact storage | GitHub release asset with manifest and checksum in `/data` |
| Backend and agents | Python using Microsoft Agent Framework |
| Portal | React and TypeScript |
| Deployment scope | Skillable provides the resource group |
| Attendee identity | Skillable supplies the principal/object ID |
| Foundry resources | Deploy an API and Foundry endpoint for each attendee |
| GitHub access | Read-only connection with staged source fallback |
| Sandbox authorization | Preassigned by the event platform |
| Presentation output | RevealJS source, PDF, and slide images |
| Video output | Seven segment videos and one combined cut on Microsoft Stream or SharePoint |
| Browser baseline | Current Microsoft Edge at 1440x900 or higher |
| Service fallback | Prepared image, fixtures, recorded trace, and guided validation |
| Resource cleanup | Requires explicit project-owner approval |

## Workstreams

### Repository foundation

- Populate attendee-first session metadata.
- Establish instruction, architecture, data, infrastructure, presentation, and media locations.
- Keep unresolved service values and data sources explicit.

### Data pipeline

- Select an immutable AACT snapshot and a bounded set of diabetes and obesity records.
- Select the openFDA drug-event fields needed by the lab.
- Build the bounded relational artifact and deterministic fixtures.
- Generate the manifest, schemas, counts, and checksums.
- Publish an immutable GitHub release asset.
- Preserve AACT acknowledgement and openFDA attribution and disclaimer metadata.
- Exclude any field or content specifically marked as third-party or subject to additional rights.

### Application and agents

- Build the starter and completed research portal states.
- Use Python and Microsoft Agent Framework for the orchestrator, worker contracts, data access, and backend APIs.
- Use React and TypeScript for the attendee portal.
- Implement the orchestrator and three structured worker contracts.
- Implement Sandbox operations and telemetry correlation.
- Add deterministic data, citation, policy, and application tests.
- Prevent the portal and agents from presenting adverse-event reports as proof of causation, incidence, or comparative safety.

### Infrastructure

- Use `azd` and Azure CLI against the ACAPMS subscription as the current maintainer deployment workflow.
- Keep Bicep as the infrastructure source of truth.
- Generate the Skillable ARM template from Bicep.
- Deploy a Foundry project/API endpoint and model deployment for each attendee environment.
- Expose only deployment-specific parameters.
- Provide readiness and fallback paths.
- Add Skillable identity and attendee authorization only after the ARM template is complete and the deployment has passed repeatable rollout tests.

### Attendee content

- Complete and test the seven instruction segments.
- Capture current screenshots from the dedicated Sandbox and Express portals.
- Add expected results and local recovery steps.
- Complete a timed dry run with a new tester.

### Slides and video

- Build the RevealJS deck using `pamelafox/presentation-skills`.
- Explain the goal, reason, services, and outcome for each segment.
- Record narrated videos using slides and tested product captures.
- Publish captions and transcripts with the media.

### Rollout validation

Run two fresh deployments in westus3:

1. `ignite-lab-test-1`
2. `ignite-lab-test-2`

Retain the resources and deployment evidence until the project owner explicitly approves cleanup.

## Confirmations still required

- Select the exact AACT snapshot, filters, interventions, and tables used to generate the lab artifact.
- Select the exact openFDA drug-event fields and queries used by the lab.
- Confirm the per-attendee Foundry model, API version, and supported westus3 capacity during the first deployment test.
- Obtain the Skillable parameter, identity, and startup contract after the generated ARM template is available.
- Create the Microsoft Stream or SharePoint publishing location.
