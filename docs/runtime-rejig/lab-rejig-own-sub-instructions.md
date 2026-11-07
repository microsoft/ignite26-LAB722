# LAB722 outside Skillable

Use this file for **one-time preparation**, then follow `lab-rejig-learner-instructions.md` for the simplified runtime learner activities. Do not use the older developer-lab instruction segments for this runtime design.

## What is deployed

On November 6, 2026, deployment `core-learner-20261106` created the core resources below. GPT-5.2 is provisioned with capacity 40. Your current Azure user has project-scoped **Foundry User** and group-scoped **Container Apps SandboxGroup Data Owner** access; native Sandbox inventory access was verified.

| Setting | New learner allocation |
|---|---|
| Subscription | `30501c6c-81f6-41ac-a388-d29cf43a020d` / Private Test Sub ACAPMS |
| Resource group | `ig2026-lab-learner` |
| Region | `westus3` |
| Registry | `lab722hg4qnurp4clywacr` |
| Foundry account / project | `lab722-hg4qnurp4clyw-ai` / `caldova` |
| Express environment | `lab722-hg4qnurp4clyw-express` |
| Sandbox group | `lab722-hg4qnurp4clyw-sandboxes` |

**Core only is deployed.** There is no runtime app, Toolbox, image, clean seed, snapshot or execution Sandbox in this new RG yet. The existing `ig2026-lab-testing` app and workspaces were not copied or changed. Core infrastructure alone does not provide the browser learner experience.

Outside Skillable, you perform the facilitator preparation below yourself. It requires resource deployment and service-role assignment permission in this RG, in addition to the two learner data-plane roles. It requires no Entra app registration, directory administration, learner app sign-in or partner identity.

## 1. Set the new scope

Use the current checkout, which contains the uncommitted runtime implementation. Start in `ignite26-LAB722` with PowerShell 7.3+, Python, Azure CLI, azd and the prepared native ACA CLI. Do not use the earlier Microsoft-directory Cloud Shell device-login flow.

**Use PowerShell 7, not Windows PowerShell 5.1.** From the existing terminal on this machine, start the installed executable:

```powershell
& 'C:\Program Files\PowerShell\7\pwsh.exe' -NoProfile
$PSVersionTable.PSVersion
```

The version must be 7.3 or later. The new shell retains your working directory but not the old shell's variables, so run the following settings block again in that shell. On another machine, use its installed PowerShell 7 executable.

```powershell
$ErrorActionPreference = 'Stop'
$subscriptionId = '30501c6c-81f6-41ac-a388-d29cf43a020d'
$resourceGroup = 'ig2026-lab-learner'
$region = 'westus3'
$registry = 'lab722hg4qnurp4clywacr'
$foundryAccount = 'lab722-hg4qnurp4clyw-ai'
$project = 'caldova'
$expressEnvironment = 'lab722-hg4qnurp4clyw-express'
$sandboxGroup = 'lab722-hg4qnurp4clyw-sandboxes'
$aca = Join-Path $HOME '.aca\bin\aca.exe'
$scope = @('--subscription', $subscriptionId, '--resource-group', $resourceGroup,
    '--region', $region, '--group', $sandboxGroup)
& $aca --version
& $aca sandbox list @scope -o json
if ($LASTEXITCODE -ne 0) { throw 'Allocated Sandbox access is not ready.' }
```

An empty inventory is expected before preparation. Do not rerun the full core deployment to add the runtime: that can restore the group identity. Use the scoped runtime helper in section 4.

## 2. Prepare the clean seed and A once

The checked-out v2 data bundle is the source. Do not upload credentials or snapshot the old test workspace.

Run the following as one block. It preserves the resulting variables but stops before reading the descriptor or creating A if seed preparation fails.

```powershell
. {
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion -lt [version]'7.3') {
    throw 'Use PowerShell 7.3 or later; run section 1 again in that shell.'
}
$seedDirectory = '.build-contexts\runtime-learner-seed-20261106'
.\scripts\prepare-worker-baseline.ps1 -Mode RuntimeSeed `
    -SubscriptionId $subscriptionId -ResourceGroup $resourceGroup `
    -Region $region -GroupName $sandboxGroup `
    -OutputDirectory $seedDirectory -AcaExecutable $aca `
    -AuthorizeProvisioning -AsJson
$descriptorPath = Join-Path $seedDirectory 'runtime-seed.json'
$baseline = Get-Content -LiteralPath $descriptorPath -Raw | ConvertFrom-Json
if (-not $baseline.verified) { throw 'Clean seed verification did not complete.' }
$seed = $baseline.seed_id
$snapshot = $baseline.snapshot_id

& $aca sandbox create @scope --snapshot-id $snapshot `
    --label lab=LAB722 --label purpose=runtime-analysis-a `
    --egress-default Deny --traffic-inspection Full -o json
if ($LASTEXITCODE -ne 0) { throw 'A creation failed; inspect before retrying.' }
$a = Read-Host 'Copy Sandbox A id from the returned resource'
& $aca sandbox lifecycle set @scope --id $a --auto-suspend enable `
    --idle-timeout-seconds 900 --mode Memory --auto-delete disable -o json
if ($LASTEXITCODE -ne 0) { throw 'A lifecycle setup failed.' }
& $aca sandbox get @scope --id $a -o json
}
```

If you received `Cannot find an overload for GetFullPath ... argument count: 2` in Windows PowerShell, open PowerShell 7 and rerun section 1 before this block. The subsequent missing `runtime-seed.json` message is a consequence of the earlier failure, not a separate data issue. If an attempt did create resources, inspect them before retrying.

Keep the descriptor and A's ID. If seed preparation fails, inspect the retained `seed-id.json`; use the documented `-PrimaryId` recovery instead of allocating another seed. If A creation fails, inspect inventory before trying again.

Snapshot restores inherit CPU/memory resources; do not specify `--cpu` or `--memory` with `--snapshot-id`. If you received `'resources' cannot be set with snapshot source`, cancel the ID prompt and rerun only the corrected A creation and lifecycle commands, not seed preparation.

Leave B uncreated for the learner's snapshot exercise. After preparation there are two instances, seed and A, in an eight-slot group. B must be created from the clean snapshot, not from active A.

## 3. Import the tested runtime image

This copies the tested immutable image into your new registry; it does not rebuild code or copy application secrets. The command uses your existing Azure authorization to the source registry. Do not supply registry passwords.

```powershell
$digest = 'sha256:d4243b283746a7bf7af1549c223ef0d7dbdc2a54708f5cc25fcc7d87d0ad1101'
$sourceRegistryId = '/subscriptions/30501c6c-81f6-41ac-a388-d29cf43a020d/resourceGroups/ig2026-lab-testing/providers/Microsoft.ContainerRegistry/registries/lab7224fpje6f4ykpcgacr'
az acr import --subscription $subscriptionId --name $registry `
    --registry $sourceRegistryId --source "lab722/runtime-analysis@$digest" `
    --image 'lab722/runtime-analysis:learner-20261106'
if ($LASTEXITCODE -ne 0) { throw 'Image import failed; inspect before retrying.' }
$importedDigest = az acr repository show --subscription $subscriptionId `
    --name $registry --image 'lab722/runtime-analysis:learner-20261106' `
    --query digest -o tsv
if ($LASTEXITCODE -ne 0 -or $importedDigest -cne $digest) {
    throw 'Imported runtime digest does not match the tested image.'
}
$image = "$registry.azurecr.io/lab722/runtime-analysis@$digest"
```

For another subscription without source-registry access, build the current source in that subscription's registry using the source-only process in `infra\README.md`, **Single-allocation generated analysis**. Do not import an unrelated public starter image.

## 4. Deploy the runtime and Toolbox

```powershell
$deployment = .\scripts\deploy-test.ps1 -DeployRuntimeApp -RuntimeMode analysis `
    -SubscriptionId $subscriptionId -ResourceGroup $resourceGroup -Location $region `
    -FoundryAccountName $foundryAccount -FoundryProjectName $project `
    -RegistryName $registry -ExpressEnvironmentName $expressEnvironment `
    -BaselineDescriptorPath $descriptorPath -ExecutionSandboxId $a `
    -RuntimeImage $image
$url = $deployment.url
if ([string]::IsNullOrWhiteSpace($url)) { throw 'Runtime deployment did not return a URL.' }

.\scripts\deploy-test.ps1 -ConfigureRuntimeToolbox -RuntimeMode analysis `
    -SubscriptionId $subscriptionId -ResourceGroup $resourceGroup `
    -FoundryAccountName $foundryAccount -FoundryProjectName $project `
    -AuthorizeToolboxCreate
Invoke-RestMethod -Uri "$url/health"
$response = Invoke-WebRequest -Uri "$url/api/config" -SkipHttpErrorCheck
if ($response.StatusCode -ne 401) { throw 'Missing-key boundary did not return HTTP 401.' }
$url
```

This new allocation gets its own runtime service identity, four service grants and generated endpoint key. The helper disables the Sandbox group identity and binds the app to A. Do not supply the old allocation's assignment names or access key. Repeated Toolbox setup should reuse version 1.

Retrieve **proof-key** from the new runtime app's secrets through your approved Azure portal/platform channel. Enter it only in the application's key field. Do not put it in a URL, script, parameter file or transcript. The key is not an Azure user identity.

## 5. Start the learner activities

Open the new `$url`, select **Connect** with the new key, and follow `lab-rejig-learner-instructions.md` from section 1.

Use the new scope above and your newly returned `$seed`, `$snapshot` and `$a` values. In section 6, leave B's ID blank until you create B from the clean snapshot. Read back B's snapshot reference and apply its 900-second Memory/disabled-auto-delete policy as directed.

Follow the generated analysis, edited-code failure, filesystem/network and lifecycle activities. No Skillable substitutions or VM login controls are needed. The application uses key access; the portal/native CLI use your normal Azure user.

The commands in sections 2-4 are preparation instructions, not a claim that those resources already exist. Only the core deployment and current-user core access were executed for this allocation. A new allocation's runtime request and end-to-end timing must be checked after you prepare it.
