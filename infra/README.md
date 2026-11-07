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

## Single-allocation generated analysis

The November 6 simplification adds `src\runtime`: a key-protected browser UI/API, Foundry-generated bounded Python, the `execute_python` MCP tool and actual execution receipts. It removes learner sign-in, partner accounts and app-local tenant/result ownership. The earlier fixed proof remains available in `runtimeMode=proof`; the new runtime uses `runtimeMode=analysis`. Runtime resources remain disabled by default, preserving `lab-ready-1`.

Preparation uses the existing core resources and four service grants. No extra Reader role is needed: the deployer verifies group identity removal, while the trusted execution supervisor probes the platform identity endpoint locally before starting untrusted Python.

1. Prepare the public-data seed/snapshot, then create A from that snapshot. A is the fixed application target and must exist before the app is deployed. Leave one slot for the learner to create B, used only for filesystem isolation.
2. Build/publish the approved runtime source in the allocated ACR using `src\runtime\Containerfile`. Stage only `src\runtime`, `src\sandbox_process.py` and `tests\test_runtime.py` into an explicit source context; do not upload local environments, secrets, caches or the entire working directory.
3. Deploy through the scoped helper below. It preserves existing assignment names, removes the Sandbox group's identity without changing its capacity, and supplies the access key to ARM in memory. It generates a key for a new app, or reuses the existing app key on updates. Explicit `-AppAccessKey` accepts a SecureString if rotation is required.
4. Configure the analysis Toolbox using `-RuntimeMode analysis`. Verify health, missing-key HTTP 401, one actual generated-code request and its correlated execution receipt before delivery.

```powershell
.\scripts\deploy-test.ps1 -DeployRuntimeApp -RuntimeMode analysis `
    -SubscriptionId $subscriptionId -ResourceGroup $resourceGroup -Location $region `
    -FoundryAccountName $foundryAccount -FoundryProjectName $project `
    -RegistryName $registry -ExpressEnvironmentName $expressEnvironment `
    -BaselineDescriptorPath $cleanSeedDescriptor -ExecutionSandboxId $sandboxA `
    -RuntimeImage $approvedImmutableImage -RuntimeRoleAssignmentNames $adoptedAssignments

.\scripts\deploy-test.ps1 -ConfigureRuntimeToolbox -RuntimeMode analysis `
    -SubscriptionId $subscriptionId -ResourceGroup $resourceGroup `
    -FoundryAccountName $foundryAccount -FoundryProjectName $project `
    -AuthorizeToolboxCreate
```

Do not put the access key in an `azd` environment file, parameter file, command literal or transcript. The facilitator retrieves the app's `proof-key` secret through the approved platform/portal channel and privately supplies it to that allocation's learner. The key is an endpoint capability, not a user identity. Browser code holds it only in tab memory.

For full `azd` preparation, set `ENABLE_RUNTIME_PROOF=true`, `RUNTIME_MODE=analysis`, `RUNTIME_PROOF_IMAGE`, `RUNTIME_SANDBOX_ID` and `RUNTIME_SNAPSHOT_ID`, supplying `RUNTIME_PROOF_KEY` through the approved secret channel. The full Bicep template disables the group identity in this mode; the runtime-only ARM references existing core resources and must be used through the helper or an equivalent provisioner that verifies that identity removal first.

The runtime exposes only one active server-created run and a fixed Sandbox, not model-selected Azure targets. Python has a 30-second remote wall limit, 15-second CPU limit, 256 MiB address-space limit and 128 KiB combined output limit. It runs as UID/GID 65534 with cleared environment, no-new-privileges and bounded processes/files. The supervisor kills detached analysis children and verifies the three frozen data hashes before/after. The image runs the new focused checks before publication.

`/api/analyze` follows Foundry/Toolbox/MCP; `/api/execute` is explicitly a direct edited-code action. Zero exit status is execution success, not answer correctness. There is no phase-count-specific result validator or durable user/result service.

Image publication and runtime execution in the ACAPMS test allocation are separate from Skillable VM/profile delivery. Do not claim a fresh Skillable run or measured 75-minute completion until those are observed.

## Optional runtime proof preparation

The runtime redesign is separate from the published `lab-ready-1` learner path. `main.bicep` defaults `enableRuntimeProof` to **false**. The opt-in module deploys the fixed maintainer proof, not learner sign-in, tenant authorization, generated Python or a chat application.

Prepare it outside the learner timer, in this order:

1. Provision the existing registry, Express environment, Foundry project/model and Sandbox group. Do not run the default fresh deployment against a retained environment with different capacity or model settings.
2. Prepare a clean public-data seed with `prepare-worker-baseline.ps1 -Mode RuntimeSeed`; see [the runtime seed contract](../scripts/README.md#clean-runtime-seed). Supply one free Sandbox slot. The helper retains the seed on failure and writes its ID before verification. Learners later create their separate execution instances from the verified snapshot; never clone an active user's workspace.
3. Make the separately approved, immutable proof image available in the **target registry**. The current test-registry image is not a published attendee release. This module neither builds nor copies an image.
4. Supply a fixed execution Sandbox ID and a fresh proof key through the approved deployment secret channel. Deploy the runtime module and its connections using a provisioner authorized to assign the four scoped service roles. Learners do not perform these assignments.
5. Run `deploy-test.ps1 -ConfigureRuntimeToolbox` after ARM succeeds. It verifies and reuses the matching default Toolbox version, or creates the initial version only with explicit authorization and a successful inventory confirming absence.
6. A facilitator verifies app health, HTTP 401 without the proof key, then the authenticated `/proof` request. The current proof lazily creates its saved agent on that first request; a successful ARM deployment alone does not establish inference or Sandbox execution readiness.

### Template choices

```powershell
# Existing full infrastructure template, with runtime disabled by default.
.\scripts\compile-arm.ps1

# Runtime-only template referencing already-provisioned core resources.
.\scripts\compile-arm.ps1 -RuntimeOnly
```

The outputs are `infra\skillable\azuredeploy.json` and `infra\skillable\runtime-proof.azuredeploy.json`. Both are generated from Bicep; do not edit the ARM JSON by hand. Use the runtime-only template to adopt the retained proof without resetting core infrastructure.

| Runtime-only parameter | Supplied by the provisioner |
|---|---|
| `location`, `tags` | Allocated workload region and existing lab tags |
| `registryName`, `expressEnvironmentName` | Existing same-allocation resources |
| `foundryAccountName`, `foundryProjectName`, `sandboxGroupName` | Existing project and execution group |
| `image` | Approved target-registry image with `@sha256:` digest |
| `sandboxId` | Verified fixed execution instance, never an argument selected by the model |
| `proofKey` | Secure parameter; at least 32 characters |
| `appName`, `identityName` | Optional; defaults match the current maintainer proof |
| `roleAssignmentNames` | Existing assignment names for adoption; omit only for genuinely new grants |

The full `azd` template accepts `ENABLE_RUNTIME_PROOF`, `RUNTIME_PROOF_IMAGE`, `RUNTIME_SANDBOX_ID` and `RUNTIME_PROOF_KEY`. Keep the key out of `azd env set`, `.azure` files, source, transcripts and recorded commands. The harness must provide its approved secret-injection mechanism; this change does not invent that platform mechanism.

For the retained `ig2026-lab-testing` proof, preserve these existing assignment names rather than asking ARM to create duplicates:

| `roleAssignmentNames` key | Existing assignment name |
|---|---|
| `runtimeFoundry` | `718374f5-e7c9-4340-be96-669fc4123e68` |
| `runtimeSandbox` | `fe0b77e6-ac4f-4129-850f-ef7072b16762` |
| `runtimeAcr` | `d6fc006a-627d-4c88-adb6-67a0d7bd89e6` |
| `projectToolbox` | `41f70c9d-7286-42a2-8d06-01fd1bcadb9d` |

The runtime identity receives Foundry User on the project, SandboxGroup Data Owner on the group, and AcrPull on the registry. The project managed identity receives Foundry User on its own project for Toolbox authentication. No runtime subscription-wide grant or learner directory assignment is added.

### Toolbox setup and verification

Run from the repository root with existing Azure CLI and `azd` authentication:

```powershell
.\scripts\deploy-test.ps1 -ConfigureRuntimeToolbox `
    -SubscriptionId 30501c6c-81f6-41ac-a388-d29cf43a020d `
    -ResourceGroup ig2026-lab-testing `
    -FoundryAccountName lab722-4fpje6f4ykpcg-ai `
    -FoundryProjectName caldova
```

For a new allocation, substitute its actual scope and add `-AuthorizeToolboxCreate` for the initial creation. The helper reads only the backend connection's authentication type and target, never its key. It resolves the versioned definition in `runtime-proof-toolbox.json` to that target and exposes only `inspect_frozen_dataset`. Inventory, authentication, mismatched tools or read-back failures stop with an error; they do not trigger replacement or a second create. After an uncertain create, inspect the same operation before retrying. Do not use `azd ai toolbox deploy` as a repeatable bootstrap: it creates a new immutable version.

On November 6, 2026, both templates compiled and Azure provider validation of the standalone runtime template succeeded using a dummy validation-only key. **The template was not deployed.** The Toolbox helper reused and verified the existing version 1 without changing it. Bicep reports missing preview resource types (BCP081); narrow connection-field suppressions document the older local catalog's missing `ProjectManagedIdentity`/`audience` definitions. Provider validation does not replace an actual deployment and end-to-end proof request.

The clean seed and two snapshot-derived workspaces passed live filesystem, non-root environment, egress, remote-exit and stop/resume checks. This baseline contains Python and frozen public data; it does not install the DuckDB Python package or establish generated-analysis execution. Azure platform identity variables are stripped from the analysis child environment, not proven absent from the platform. Test the remaining identity-access boundary before enabling untrusted code.

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
