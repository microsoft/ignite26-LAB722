# Infrastructure

Start with the [requirements and quickstart](../README.md#local-deployment-quickstart). Bicep is the infrastructure source of truth.

| Entry point | Purpose |
| --- | --- |
| [Root azure.yaml](../azure.yaml) and [local-reactor/main.bicep](local-reactor/main.bicep) | Workstation-driven `azd up`: Foundry/model, Express, Sandboxes, environment-local ACR and shared supporting resources |
| [local-reactor/main.parameters.json](local-reactor/main.parameters.json) | Selected `azd` environment's location, name, operator ID, project and model capacity |
| [reactor2-skillable.bicep](reactor2-skillable.bicep) | Skillable foundation; platform lifecycle actions supply the dedicated API and scoped access |
| [Skillable ARM](skillable/reactor2.azuredeploy.json) | Compiled Reactor 2 foundation |
| [modules](modules) | Shared Foundry, Express, Sandbox, identity and service definitions |
| [reactor.bicep](reactor.bicep) | Existing-resource Express service deployment used by the runtime preparation helpers |
| [main.bicep](main.bicep) | Retained legacy foundation, not selected by root `azd` |

The local profile is now under `infra\local-reactor`; run `azd` from the repository root, not from an old `local-reactor` checkout. Environment state remains under ignored `.azure` directories and must not be committed.

The local template defaults to `westus3`, project `reactor`, `gpt-5.2` version `2025-12-11`, `GlobalStandard` capacity `40`, and a Sandbox-group limit of eight. Availability and quota must be checked for the authorized subscription. The role-assigning operator and attendee are not interchangeable identities.

For [detailed preparation and troubleshooting](../README.md#deployment-details), distinguish infrastructure provisioning, application/API registration, image pull, hosted-version readiness and a genuinely accepted research run. None of those checks implies the others.
