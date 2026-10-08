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
| Deployment scope | Skillable provides the resource group |
| Attendee identity | Skillable supplies the principal/object ID |
| Foundry model | Shared event deployment with per-attendee state |
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

- Approve exact AACT and openFDA source configuration.
- Build the bounded relational artifact and deterministic fixtures.
- Generate the manifest, schemas, counts, and checksums.
- Publish an immutable GitHub release asset.

### Application and agents

- Build the starter and completed research portal states.
- Implement the orchestrator and three structured worker contracts.
- Implement Sandbox operations and telemetry correlation.
- Add deterministic data, citation, policy, and application tests.

### Infrastructure

- Use `azd` as the maintainer deployment workflow.
- Keep Bicep as the infrastructure source of truth.
- Generate the Skillable ARM template from Bicep.
- Expose only deployment-specific parameters.
- Provide readiness and fallback paths.

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

- Name the data redistribution reviewer.
- Name the medical or responsible AI reviewer.
- Confirm write access to the canonical Microsoft repository.
- Obtain the exact Skillable parameter and startup contract.
- Obtain the shared Foundry endpoint, deployment name, API version, region, and capacity.
- Approve the exact data release, filters, interventions, and fields.
- Create the Microsoft Stream or SharePoint publishing location.
