# Infrastructure

This folder will contain the repeatable deployment for LAB722.

## Deployment rules

- `azd` is the primary maintainer workflow.
- Bicep is the infrastructure source of truth.
- The Skillable ARM template is generated from Bicep and is not maintained separately.
- Skillable provides the resource group and attendee principal ID.
- The event platform preassigns attendee access to the dedicated Sandbox and Express portals.
- Attendees do not run the infrastructure deployment during the 75-minute exercise.
- The deployment starts before or as the lab begins and should be ready within 5-10 minutes.

## Planned layout

```text
infra/
|-- main.bicep
|-- main.parameters.json
|-- modules/
|-- skillable/
|   |-- azuredeploy.json
|   `-- parameters.example.json
`-- tests/
    |-- ignite-lab-test-1.parameters.json
    `-- ignite-lab-test-2.parameters.json
```

## Skillable parameters

The final parameter names must come from the Skillable integration owner. The expected input categories are:

- Azure region, defaulting to westus3
- Resource-group name
- Short environment uniqueness token
- Attendee principal/object ID
- Shared data artifact URI, if not fixed by the template
- Shared Foundry deployment reference

Do not expose generated secrets, subscription IDs, tenant IDs, resource names, or derived endpoints as attendee inputs.

## Rollout requirement

Complete two fresh westus3 deployments using resource groups:

- `ignite-lab-test-1`
- `ignite-lab-test-2`

Retain both test environments until the project owner explicitly approves cleanup.
