# Infrastructure

This folder will contain the repeatable deployment for LAB722.

## Deployment rules

- `azd` is the primary maintainer workflow.
- Maintainers use Azure CLI and the ACAPMS subscription during development and rollout testing.
- Bicep is the infrastructure source of truth.
- The Skillable ARM template is generated from Bicep and is not maintained separately.
- Each attendee environment receives its own Foundry project/API endpoint and model deployment.
- Skillable identity, attendee authorization, and startup integration are added after the ARM template is complete and tested.
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

## Current `azd` deployment inputs

The first implementation targets repeatable maintainer deployments. Expected input categories are:

- Azure region, defaulting to westus3
- Resource-group name, including the required rollout names
- Short environment uniqueness token
- Shared data artifact URI, if not fixed by the template
- Per-attendee Foundry model selection and deployment capacity

Do not expose generated secrets, subscription IDs, tenant IDs, resource names, or derived endpoints as user inputs.

## Later Skillable integration

After the Bicep deployment has passed two fresh rollouts:

1. Compile Bicep to the Skillable ARM template.
2. Obtain Skillable's exact parameter, identity, startup, and output contract.
3. Add the attendee principal/object ID and required role assignments.
4. Confirm that deployment begins before or when the attendee enters the lab.
5. Confirm that the environment is normally usable within 5-10 minutes.

## Rollout requirement

Complete two fresh westus3 deployments using resource groups:

- `ignite-lab-test-1`
- `ignite-lab-test-2`

Retain both test environments until the project owner explicitly approves cleanup.
