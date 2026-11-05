# Architecture and trust boundaries

## Runtime flow

```text
Attendee browser
  |
  +--> Per-attendee Microsoft Foundry project and endpoint
  |      `--> Caldova orchestrator using Microsoft Agent Framework
  |
  +--> ACA Sandboxes portal
  |      +--> Primary development Sandbox
  |      |      `--> Baseline snapshot
  |      +--> Clinical-trials worker clone
  |      +--> Drug-safety worker clone
  |      `--> Quality/governance worker clone
  |
  +--> ACA Express portal
  |      `--> Caldova research application
  |
  `--> Azure Monitor workbook

GitHub or staged source bundle ---> primary Sandbox
Shared data artifact -----------> primary Sandbox
Validated source ---------------> ACR Task
Approved image digest ----------> ACA Express
```

## Agent boundary

The Python Foundry orchestrator uses Microsoft Agent Framework to plan and coordinate work. It does not execute repository code. The three specialist roles execute commands and manipulate files only inside their assigned Sandbox clones.

Planning uses a managed agent version with a strict `ImplementationPlan` output schema; Foundry rejects a per-request text-format override for a named agent. Tool-smoke and worker dispatch use an ordinary-text version of the same owned agent, so the planning schema does not constrain tool results. Strict validation still checks the exact run, immutable dataset identity, approved assignments and human-release requirement; Markdown-fenced or identity-changing output is rejected rather than repaired into an accepted plan.

Each worker receives a fresh structured-output schema whose role, run, Sandbox, dataset version and logical hash are constrained to the exact assigned identity. This prevents those report fields from competing with other hashes in the prompt. Local parsing, immutable-identity comparison, bounded report-only retries and independent acceptance remain separate checks; the controller never rewrites a returned identity into an accepted result.

The attendee configures one persistent orchestrator. Specialist roles are versioned templates started as separate sessions:

1. Clinical-trials worker
2. Drug-safety worker
3. Quality/governance worker

## Data boundary

All attendees use one immutable dataset version. A primary Sandbox stages the artifact, validates its checksum, and records the manifest before creating a snapshot. Worker clones inherit that state.

Live data access is optional and is used only to demonstrate controlled egress. Cached fixtures are authoritative for acceptance tests.

## Network boundary

Sandbox egress starts from a supplied restricted policy. The attendee confirms the approved destinations and runs:

- One request to an approved source.
- One request to an unapproved test destination.

The approved request must succeed. The unapproved request must fail.

## Release boundary

The orchestrator cannot approve a release based only on model confidence. The release candidate must pass:

- Worker-output schema validation
- Clinical-trial fixture assertions
- Safety normalization and deduplication assertions
- Citation checks
- Responsible-use checks
- Application acceptance tests
- Egress-policy checks

The final deployment uses the approved image digest rather than a mutable tag.

## Identity boundary

During development and rollout testing, maintainers deploy with `azd` and Azure CLI against the ACAPMS subscription. Each environment contains its own Foundry endpoint and model deployment so the lab can be completed independently.

Skillable identity and attendee authorization are added after the Bicep deployment has been compiled to ARM and validated. The event platform will provide the resource group and attendee principal ID and preassign the permissions needed for the dedicated Sandbox and Express portals. Attendees do not provide GitHub personal access tokens or infrastructure credentials.
