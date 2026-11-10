# Deployment and preparation scripts

Use the [root quickstart](../README.md#local-deployment-quickstart) for workstation deployment and the [lab instructions](../instructions/README.md) in Skillable.

| Script | Current responsibility |
| --- | --- |
| [prepare-local-reactor.ps1](prepare-local-reactor.ps1) | Root `azd` hooks: `Validate` checks the explicit environment; `Research` prepares the current Sandbox-agent research application, local registry mirror, API and hosted connection |
| [prepare-reactor-api.py](prepare-reactor-api.py) | Create/reuse the exact allocation-owned Entra execution API and service principal; reject foreign ownership or incompatible policy |
| [prepare-reactor-swarm.ps1](prepare-reactor-swarm.ps1) | Prepare the agent disk/seed/snapshot, two Express apps, managed execution connection, `runtime-research` Toolbox and hosted orchestrator |
| [prepare-reactor-agent-image.ps1](prepare-reactor-agent-image.ps1) | Prepare and verify the digest-pinned preloaded specialist image and teaching snapshot |
| [deploy-reactor.ps1](deploy-reactor.ps1) | Deploy the explicit service image and managed identities into an existing Express environment |
| [setup-reactor-foundry.py](setup-reactor-foundry.py) | Register the managed Toolbox and hosted agent version |
| [inspect-reactor-toolbox.py](inspect-reactor-toolbox.py) | Verify advertised specialist operations and required arguments |
| [wait-reactor-hosted.py](wait-reactor-hosted.py) | Wait for the exact saved hosted version; stop on failure rather than create a replacement |
| [connect-reactor-frontend.ps1](connect-reactor-frontend.ps1) | Configure the exact hosted Responses endpoint and refresh only the frontend |
| [run-reactor-skillable-vm.ps1](run-reactor-skillable-vm.ps1) | Allocated-user sign-in and VM handoff; requires preinstalled Python/SDK packages and installs nothing |
| [initialize-reactor-skillable.ps1](initialize-reactor-skillable.ps1) | Verify platform foundation/API outputs, mirror the hosted image to allocated ACR and prepare/connect the research application |
| [export-reactor-skillable.py](export-reactor-skillable.py) | Generate the pinned preparation archive and first-display action script |
| [skillable-reactor2-vm.ps1](skillable-reactor2-vm.ps1) | First-display source and allocation-specific launcher installation |
| [skillable-reactor2-access.ps1](skillable-reactor2-access.ps1) | Platform-owned API registration and eight scoped role assignments |
| [skillable-reactor2-teardown.ps1](skillable-reactor2-teardown.ps1) | Remove only the exact allocation-owned API registration/service principal |

Provisioning, role assignment and directory changes require the caller's authorized scope. Keep passwords in SecureString/private input channels. Do not log full token, session or grant responses.

The repository retains older developer-lab helpers for existing deployments and regression coverage. In particular, explicitly selected `Prepare`/`Connect` modes of `prepare-local-reactor.ps1` are legacy; the current root `azd` hook uses **Research**. They are not alternate learner instructions. Do not mix their prepared state, images or customer contract with the current research swarm.
