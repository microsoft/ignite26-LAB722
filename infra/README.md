# Infrastructure

This folder contains the repeatable infrastructure foundation for LAB722. A corrected agent-built Caldova synthetic preview is deployed separately; this template does not stage the application or reviewed data. The platform-neutral startup path uses two visible inputs and now has an explicitly authorized pinned-synthetic baseline preparation mode. The exact Skillable adapter remains unverified.

## Deployment rules

- `azd` is the primary maintainer workflow.
- Maintainers use Azure CLI and the ACAPMS subscription during development and rollout testing.
- Bicep is the infrastructure source of truth.
- The Skillable ARM template is generated from Bicep and is not maintained separately.
- Each attendee environment receives its own Foundry project/API endpoint and model deployment.
- Harness authentication and subscription context are separate from attendee authorization. Never infer the attendee from the deployment principal.
- Attendees do not run the infrastructure deployment during the 75-minute exercise.
- Complete attendee startup should begin before or as the lab begins and be usable within 5-10 minutes; that end-to-end timing has not yet been verified.

## Current layout

```text
infra/
|-- main.bicep
|-- main.parameters.json
|-- modules/
|   |-- core.bicep
|   |-- express.bicep
|   |-- foundry.bicep
|   `-- sandboxes.bicep
|-- skillable/
|   `-- azuredeploy.json
`-- README.md
```

## Current `azd` deployment inputs

The implementation targets repeatable maintainer deployments. `AZURE_RESOURCE_GROUP` selects the resource group in `azd`; subscription and resource-group scope are supplied by the deployment platform, not ARM template parameters.

| ARM parameter | Default |
|---|---|
| `environmentName` | `caldova-${uniqueString(resourceGroup().id)}` for a harness; `azd` still supplies its explicit 2-32 character environment name |
| `location` | `westus3` |
| `labUserPrincipalId` | Empty; skips the development Sandbox and project-scoped Foundry role assignments |
| `labUserPrincipalType` | `User` |
| `foundryUserRoleAssignmentName` | Empty; deterministic name for new assignments, or existing assignment name for adoption |
| `modelName` | `gpt-5.2` |
| `modelVersion` | `2025-12-11` |
| `modelFormat` | `OpenAI` |
| `modelSkuName` | `GlobalStandard` |
| `modelCapacity` | `40` |
| `sandboxMaxCount` | `8`; bounded 4-16 for primary/workers and retained development evidence |

The default requests `gpt-5.2` version `2025-12-11` on `GlobalStandard`, with capacity 40. Capacity is throughput allocation, not a different SKU. Confirm the model's actual TPM/RPM allocation and available model/SKU quota in the deployment region before delivery; capacity units are model-specific. Explicit `FOUNDRY_MODEL_NAME`, `FOUNDRY_MODEL_VERSION` and `FOUNDRY_MODEL_CAPACITY` values continue to override the `azd` defaults. Existing deployments do not change just because this template is regenerated.

The participant creates `caldova-research` from the public, digest-pinned starter in the new Container Apps portal. Bicep prepares the infrastructure, not that application. Portal-app readiness explicitly verifies the app's same-subscription/resource-group Express environment before returning it as the later deployment target. Resource-group name `LAB722` can be reused across separate subscriptions; every helper remains explicitly subscription-scoped.

Do not expose generated secrets, subscription IDs, tenant IDs, resource names, or derived endpoints as user inputs.

## Platform-neutral startup contract

Only **region** and **resource-group name** are visible deployment configuration. The harness must authenticate Azure CLI beforehand, supply `AZURE_SUBSCRIPTION_ID`, and provide an existing resource group. The startup script never selects a maintainer subscription, changes the active CLI account or `azd` environment, or creates a resource group.

The optional harness-owned `LAB_USER_PRINCIPAL_ID` and `LAB_USER_PRINCIPAL_TYPE` are an explicit authorization mapping, not another attendee input or a lookup of the deployment identity. Leaving the principal unset skips the role assignments; infrastructure success must not imply attendee access.

`main.bicep` derives the omitted environment name from resource-group scope. `main.parameters.json` continues to pass `${AZURE_ENV_NAME}` for maintainer deployments, and the resource-name seed is unchanged. Existing environments retain their explicit names rather than adopting a new harness default. The template returns `AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP`, `AZURE_LOCATION`, and `AZURE_ENV_NAME` alongside the registry, Foundry, Express, and Sandbox outputs.

The guarded entry point is `scripts\start-lab.ps1`; see [startup execution and readiness](../scripts/README.md#platform-neutral-startup). Its normal action validates rather than provisions. Explicit provisioning is limited to a fresh supplied scope; retained LAB722 environments must continue to use their existing maintainer configuration, including capacity and adopted-role overrides.

The entry point passed eight offline regression groups and actual read-only `Validate`/`Readiness` runs against test-2. Readiness checks six current resource identities and provisioning states, not only a past successful deployment. It verified the infrastructure while leaving application/data/attendee readiness false. The fresh-scope provisioning branch remains offline-tested only; the complete attendee startup has not been deployed or timed.

The later `Prepare` branch connects verified infrastructure to the primary/snapshot/three-clone preparation helper. A harness-owned manifest and SHA-256 pin the exact synthetic artifact; no data rebuild or public-source approval is inferred. This branch is allocation-capable only when explicitly selected and requires four available Sandbox slots. The container path passed the unchanged nine tests plus non-root/missing-query/frozen-byte baseline validation in validation-only, no-push ACR run `dsj`. Harness/helper orchestration is locally tested; no fresh Sandbox allocation or application update occurred. See [pinned preparation controls and remaining gates](../scripts/README.md#pinned-synthetic-baseline-preparation).

On October 9, 2026, the regenerated ARM template passed Azure validation with only `location=westus3` supplied. A separate read-only validation passed with the retained test-2 environment name, model capacity 20, and Sandbox count 9. A resource-ID-only what-if also resolved the explicit name to the retained resources without create/delete entries; it is not evidence that every property is unchanged. No startup deployment was performed, and the corrected preview was verified still running the approved immutable image with HTTP 200 health and Sandbox capacity 9. These checks validate the input/template contract, not a complete attendee startup or a confirmed Skillable substitution syntax.

## Maintainer rollout

Run these commands from the repository root with Azure CLI authenticated to the ACAPMS subscription:

```powershell
.\scripts\deploy-test.ps1 -EnvironmentName ignite-lab-test-1
.\scripts\deploy-express-smoke.ps1 -EnvironmentName ignite-lab-test-1 -AppName lab722-rollout1-smoke
.\scripts\validate-sandbox.ps1 -EnvironmentName ignite-lab-test-1 -CreateSnapshot -CreateClone

.\scripts\deploy-test.ps1 -EnvironmentName ignite-lab-test-2
.\scripts\deploy-express-smoke.ps1 -EnvironmentName ignite-lab-test-2 -AppName lab722-rollout2-smoke
.\scripts\validate-sandbox.ps1 -EnvironmentName ignite-lab-test-2 -CreateSnapshot -CreateClone
```

`deploy-test.ps1` compiles the Skillable ARM template before provisioning. Existing environments are updated, not recreated; use an unused resource group to test a fresh rollout. Sandbox validation creates retained resources unless `-SandboxId` is supplied to reuse a source Sandbox.

## Verified rollout results

Validation recorded on October 9, 2026. Deployment timestamps below are UTC.

| Check | `ignite-lab-test-1` | `ignite-lab-test-2` |
|---|---|---|
| Region | `westus3` | `westus3` |
| Successful top-level ARM deployment | October 9, 00:10:57 UTC | October 9, 13:34:21 UTC |
| Foundry account, project, and model deployment | Provisioned | Provisioned |
| Foundry agent API and bounded Responses inference | Not tested | HTTP 200 |
| Persistent Agent Framework assigned-Sandbox tool dispatch | Not tested | Passed; diagnostic scope only |
| Express environment mode | `Express` | `Express` |
| Express smoke app HTTPS | HTTP 200 | HTTP 200 |
| Source Sandbox command execution | Passed | Passed |
| Source and clone egress | `open.fda.gov` allowed; `example.com` blocked | `open.fda.gov` allowed; `example.com` blocked |
| Snapshot filesystem marker restored in clone | Passed | Passed |
| Clone references the returned snapshot ID | Passed | Passed |
| Clone default-deny policy and 900-second idle suspension | Verified | Verified |

The first environment passed after development fixes and deployment retries. The second resource group did not exist before this run and provisioned successfully on the first attempt with the corrected template; `azd` reported 2 minutes 5 seconds.

The generated `infra\skillable\azuredeploy.json` also passed `az deployment group validate` against `ignite-lab-test-2`. Bicep compilation reports missing type definitions for the Express and Sandbox preview API versions; Azure accepted and provisioned both resource types.

The corrected validation run produced these retained resources:

| Environment | Source Sandbox ID | Snapshot ID | Clone Sandbox ID |
|---|---|---|---|
| `ignite-lab-test-1` | `6e7dd779-d7cd-4ab6-ae07-ff9b4b46acca` | `75385ffc-7f75-4080-b816-9b526164be7d` | `aec3a044-2da6-45a8-81c0-a572062b57fa` |
| `ignite-lab-test-2` | `1c64b303-c8ff-4133-be92-8ba505b6081a` | `85d35016-2f4a-400d-bc43-30cf36fe1ba5` | `674a7e8d-e107-4af6-8afd-6879086a6692` |

These are infrastructure and smoke checks, not a completed attendee exercise. The original Express smoke apps serve nginx and the retained rollout snapshot contains a test marker rather than the clinical dataset. A later prepared source/data snapshot and three distinct specialist clones now pass actual Foundry implementation, independent nine-test integration, and governance validation using synthetic data; see [prepared worker evidence](../scripts/README.md#prepared-worker-baseline). The separate `caldova-research` preview now runs the corrected agent-built image `sha256:f9a95fa8f157b717f556e52d3ce17996a6db9d977068d8733451b8bd733a7224`, with fresh image-bound approval for synthetic development and verified full-source API fidelity. Its earlier defective candidate and rollback remain retained as evidence. Application deployment is still a maintainer script, not part of this Bicep or Skillable startup template; public-data and attendee-release approval remain pending.

Foundry User access is scoped to the project and uses built-in role ID `53ca6127-db72-4b80-b1b0-d745d6d5456d`. The existing manual test-2 assignment was adopted, not deleted or duplicated; `caldova-foundry-access-20261009` passed Azure deployment validation and deployment, and subsequent agent/inference checks still returned HTTP 200. A freshly granted role may require several minutes of propagation.

The initial test-2 deployment's capacity 1 was sufficient for a small smoke request, not the larger implementation planner. After measured HTTP 429 failures, `caldova-agent-capacity-20261009` configured test-2 capacity 20 through Bicep and persisted the `FOUNDRY_MODEL_CAPACITY` environment override. Actual response headers initially lagged ARM, then verified effective 20 requests/minute and 20,000 tokens/minute; the scoped software planner subsequently passed. Effective readiness must be measured rather than inferred from ARM success. Those are historical GPT-4.1-mini measurements, not throughput or acceptance evidence for the new GPT-5.2/capacity-40 defaults; event-scale quota and capacity review is still required.

The development-only `SANDBOX_MAX_COUNT=9` override was deployed to retain five earlier diagnostic Sandboxes plus the prepared primary and three workers; all nine slots are allocated. The attendee/template default remains 8. The native group GET does not return capacity: the explicit Bicep API `2026-02-01-preview` ARM GET verified `maxSandboxCount=9`. Preparation checks use that exact API before new allocation, not an assumed default or the native response's missing field. Reuse allocates nothing and verifies the existing scoped inventory and bindings.

## Later Skillable integration

The generated template, both resource-group rollouts, and the neutral two-input startup contract are available. Remaining integration work:

1. Obtain Skillable's exact authentication/subscription channel, parameter, identity, startup trigger, and output contract; no guessed platform replacement tokens are used.
2. Map the actual attendee identity to the required Sandbox and Foundry permissions; the current Sandbox role assignment is a maintainer test path.
3. Add the application images, data staging, and readiness checks.
4. Confirm that deployment begins before or when the attendee enters the lab and the complete exercise is usable within 5-10 minutes.

## Rollout requirement

Complete two fresh westus3 deployments using resource groups:

- `ignite-lab-test-1`
- `ignite-lab-test-2`

Retain both test environments until the project owner explicitly approves cleanup.
