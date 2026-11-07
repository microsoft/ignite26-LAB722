#requires -Version 7.3
[CmdletBinding(DefaultParameterSetName = 'Provision')]
param(
    [Parameter(Mandatory, ParameterSetName = 'Provision')]
    [ValidatePattern('^[a-zA-Z0-9-]+$')]
    [string] $EnvironmentName,

    [Parameter(Mandatory, ParameterSetName = 'RuntimeToolbox')]
    [Parameter(Mandatory, ParameterSetName = 'RuntimeApp')]
    [string] $ResourceGroup = $EnvironmentName,

    [string] $Subscription = 'Private Test Sub ACAPMS',

    [string] $Location = 'westus3',

    [string] $LabUserPrincipalId,

    [Parameter(Mandatory, ParameterSetName = 'RuntimeToolbox')]
    [switch] $ConfigureRuntimeToolbox,

    [Parameter(Mandatory, ParameterSetName = 'RuntimeToolbox')]
    [Parameter(Mandatory, ParameterSetName = 'RuntimeApp')]
    [guid] $SubscriptionId,

    [Parameter(Mandatory, ParameterSetName = 'RuntimeToolbox')]
    [Parameter(Mandatory, ParameterSetName = 'RuntimeApp')]
    [ValidatePattern('^[a-z0-9][a-z0-9-]{1,62}$')]
    [string] $FoundryAccountName,

    [Parameter(ParameterSetName = 'RuntimeToolbox')]
    [Parameter(ParameterSetName = 'RuntimeApp')]
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_-]{1,62}$')]
    [string] $FoundryProjectName = 'caldova',

    [Parameter(ParameterSetName = 'RuntimeToolbox')]
    [switch] $AuthorizeToolboxCreate,

    [Parameter(ParameterSetName = 'RuntimeToolbox')]
    [Parameter(ParameterSetName = 'RuntimeApp')]
    [ValidateSet('proof', 'analysis')]
    [string] $RuntimeMode = 'proof',

    [Parameter(Mandatory, ParameterSetName = 'RuntimeApp')]
    [switch] $DeployRuntimeApp,

    [Parameter(Mandatory, ParameterSetName = 'RuntimeApp')]
    [string] $RegistryName,

    [Parameter(Mandatory, ParameterSetName = 'RuntimeApp')]
    [string] $ExpressEnvironmentName,

    [Parameter(Mandatory, ParameterSetName = 'RuntimeApp')]
    [string] $BaselineDescriptorPath,

    [Parameter(Mandatory, ParameterSetName = 'RuntimeApp')]
    [guid] $ExecutionSandboxId,

    [Parameter(Mandatory, ParameterSetName = 'RuntimeApp')]
    [ValidatePattern('^[a-z0-9.-]+\.azurecr\.io/[a-z0-9/_.-]+@sha256:[a-f0-9]{64}$')]
    [string] $RuntimeImage,

    [Parameter(ParameterSetName = 'RuntimeApp')]
    [hashtable] $RuntimeRoleAssignmentNames = @{},

    [Parameter(ParameterSetName = 'RuntimeApp')]
    [string] $RuntimeIdentityName = 'lab722-runtime-proof-mi',

    [Parameter(ParameterSetName = 'RuntimeApp')]
    [string] $ModelDeployment = 'gpt-5.2',

    [Parameter(ParameterSetName = 'RuntimeApp')]
    [securestring] $AppAccessKey
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repositoryRoot

if ($DeployRuntimeApp) {
    if ($RuntimeMode -ne 'analysis') { throw 'Runtime application deployment requires explicit -RuntimeMode analysis.' }
    $descriptor = Get-Content -LiteralPath $BaselineDescriptorPath -Raw | ConvertFrom-Json -AsHashtable
    if ($descriptor.purpose -cne 'runtime-clean-public-data' -or $descriptor.verified -ne $true -or
        $descriptor.subscription_id -ne $SubscriptionId.ToString() -or
        $descriptor.resource_group -ne $ResourceGroup -or $descriptor.region -ne $Location -or
        $ExecutionSandboxId -eq [guid]::Empty) { throw 'The clean baseline descriptor does not match this explicit allocation.' }
    $registryText = az acr show --subscription $SubscriptionId -g $ResourceGroup -n $RegistryName `
        --query '{server:loginServer,lab:tags.lab}' -o json
    if ($LASTEXITCODE -ne 0) { throw 'Runtime registry inspection failed.' }
    $registry = ($registryText -join "`n") | ConvertFrom-Json
    if ($registry.lab -cne 'LAB722' -or -not $RuntimeImage.StartsWith($registry.server + '/')) {
        throw 'The immutable runtime image must be in this allocated lab registry.'
    }
    az acr repository show --subscription $SubscriptionId --name $RegistryName `
        --image $RuntimeImage.Substring($registry.server.Length + 1) -o none
    if ($LASTEXITCODE -ne 0) { throw 'The supplied immutable runtime image is not available.' }
    & (Join-Path $PSScriptRoot 'compile-arm.ps1') -RuntimeOnly | Out-Null
    $tokenText = az account get-access-token --subscription $SubscriptionId --resource https://management.azure.com/ -o json
    if ($LASTEXITCODE -ne 0) { throw 'Runtime deployment authentication failed.' }
    $bearer = (($tokenText -join "`n") | ConvertFrom-Json).accessToken
    $headers = @{ Authorization = "Bearer $bearer" }
    $resourcePrefix = "https://management.azure.com/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup"
    $groupUri = "$resourcePrefix/providers/Microsoft.App/sandboxGroups/$($descriptor.group_name)?api-version=2026-02-01-preview"
    $group = Invoke-RestMethod -Uri $groupUri -Headers $headers -ErrorAction Stop
    if ($group.location -ne $Location -or $group.tags.lab -cne 'LAB722') { throw 'Runtime Sandbox scope does not match the lab allocation.' }
    $groupIdentity = $group.PSObject.Properties['identity']
    if ($groupIdentity -and $groupIdentity.Value -and $groupIdentity.Value.type -ne 'None') {
        [void](Invoke-RestMethod -Uri $groupUri -Headers $headers -Method Patch `
            -ContentType 'application/json' -Body '{"identity":{"type":"None"}}' -ErrorAction Stop)
        $deadline = [DateTimeOffset]::UtcNow.AddMinutes(2)
        do {
            $group = Invoke-RestMethod -Uri $groupUri -Headers $headers -ErrorAction Stop
            $groupIdentity = $group.PSObject.Properties['identity']
            if (-not $groupIdentity -or -not $groupIdentity.Value -or $groupIdentity.Value.type -eq 'None') { break }
            Start-Sleep -Seconds 3
        } while ([DateTimeOffset]::UtcNow -lt $deadline)
        if ($groupIdentity -and $groupIdentity.Value -and $groupIdentity.Value.type -ne 'None') { throw 'Sandbox identity removal did not complete; no app was deployed.' }
    }
    $appName = 'lab722-runtime-analysis'
    $appUri = "$resourcePrefix/providers/Microsoft.App/containerApps/$appName"
    $inventoryText = az containerapp list --subscription $SubscriptionId -g $ResourceGroup -o json
    if ($LASTEXITCODE -ne 0) { throw 'Runtime app inventory failed; no create was attempted.' }
    $existing = @(($inventoryText -join "`n" | ConvertFrom-Json) | Where-Object name -eq $appName)
    if ($existing.Count -gt 1) { throw 'Runtime app inventory is ambiguous.' }
    if ($AppAccessKey) {
        $key = [Net.NetworkCredential]::new('', $AppAccessKey).Password
    } elseif ($existing.Count -eq 1) {
        if ($existing[0].tags.lab -cne 'LAB722') { throw 'Existing runtime app is not tagged for this lab.' }
        $secrets = Invoke-RestMethod -Uri "$appUri/listSecrets?api-version=2026-03-02-preview" `
            -Headers $headers -Method Post -ContentType 'application/json' -Body '{}' -ErrorAction Stop
        $matches = @($secrets.value | Where-Object name -eq 'proof-key')
        if ($matches.Count -ne 1) { throw 'Existing runtime access key is missing or ambiguous; it was not replaced.' }
        $key = $matches[0].value
    } else {
        $key = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    }
    if ($key.Length -lt 32) { throw 'The runtime access key must be at least 32 characters.' }
    $values = @{
        location = $Location; tags = @{ lab = 'LAB722'; purpose = 'runtime-analysis' }
        registryName = $RegistryName; expressEnvironmentName = $ExpressEnvironmentName
        foundryAccountName = $FoundryAccountName; foundryProjectName = $FoundryProjectName
        sandboxGroupName = $descriptor.group_name; runtimeMode = 'analysis'
        image = $RuntimeImage; sandboxId = $ExecutionSandboxId.ToString()
        snapshotId = $descriptor.snapshot_id; proofKey = $key; appName = $appName
        identityName = $RuntimeIdentityName; modelDeployment = $ModelDeployment
        roleAssignmentNames = $RuntimeRoleAssignmentNames
    }
    $parameters = @{}
    foreach ($name in $values.Keys) { $parameters[$name] = @{ value = $values[$name] } }
    $template = Get-Content (Join-Path $repositoryRoot 'infra\skillable\runtime-proof.azuredeploy.json') -Raw |
        ConvertFrom-Json -AsHashtable
    $body = @{ properties = @{ mode = 'Incremental'; template = $template; parameters = $parameters } } |
        ConvertTo-Json -Depth 100 -Compress
    $deploymentName = 'runtime-analysis-' + [DateTimeOffset]::UtcNow.ToString('yyyyMMdd-HHmmss')
    $deploymentUri = "$resourcePrefix/providers/Microsoft.Resources/deployments/${deploymentName}?api-version=2022-09-01"
    [void](Invoke-RestMethod -Uri $deploymentUri -Headers $headers -Method Put `
        -ContentType 'application/json' -Body $body -ErrorAction Stop)
    $deadline = [DateTimeOffset]::UtcNow.AddMinutes(12)
    do {
        Start-Sleep -Seconds 5
        $result = Invoke-RestMethod -Uri $deploymentUri -Headers $headers -ErrorAction Stop
        $state = $result.properties.provisioningState
    } while ($state -in @('Accepted','Running') -and [DateTimeOffset]::UtcNow -lt $deadline)
    if ($state -ne 'Succeeded') { throw "Runtime deployment $deploymentName ended with state $state; inspect that operation before retrying." }
    [pscustomobject]@{
        status = $state; deployment = $deploymentName
        app = $appName; url = $result.properties.outputs.RUNTIME_APP_URL.value
        sandbox = $ExecutionSandboxId.ToString(); sandbox_group_identity = 'None'
        access_key = 'Stored in the app secret and backend connection; never printed or written locally.'
    }
    return
}

if ($ConfigureRuntimeToolbox) {
    if ($SubscriptionId -eq [guid]::Empty) { throw 'An explicit subscription ID is required.' }
    $analysis = $RuntimeMode -eq 'analysis'
    $toolboxName = if ($analysis) { 'runtime-analysis-toolbox' } else { 'runtime-stage1-proof' }
    $backendName = if ($analysis) { 'runtime-analysis-backend' } else { 'runtime-proof-backend' }
    $label = if ($analysis) { 'analysis' } else { 'proof' }
    $toolName = if ($analysis) { 'execute_python' } else { 'inspect_frozen_dataset' }
    $definitionName = if ($analysis) { 'runtime-analysis-toolbox.json' } else { 'runtime-proof-toolbox.json' }
    $endpoint = "https://$FoundryAccountName.services.ai.azure.com/api/projects/$FoundryProjectName"
    $projectId = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.CognitiveServices/accounts/$FoundryAccountName/projects/$FoundryProjectName"
    $connectionText = az rest --subscription $SubscriptionId --method get `
        --url "https://management.azure.com$projectId/connections/${backendName}?api-version=2025-06-01" `
        --query '{auth:properties.authType,target:properties.target}' -o json
    if ($LASTEXITCODE -ne 0) { throw 'Runtime backend connection lookup failed; no Toolbox change was attempted.' }
    $connection = ($connectionText -join "`n") | ConvertFrom-Json -ErrorAction Stop
    if ($connection.auth -cne 'CustomKeys' -or
        $connection.target -cnotmatch '^https://[a-z0-9.-]+\.azurecontainerapps\.io/mcp$') {
        throw 'The runtime backend connection is not the expected authenticated Express MCP endpoint.'
    }
    $listText = azd ai toolbox list --project-endpoint $endpoint -C $repositoryRoot --no-prompt -o json
    if ($LASTEXITCODE -ne 0) { throw 'Toolbox inventory failed; no create or retry was attempted.' }
    $inventory = ($listText -join "`n") | ConvertFrom-Json -ErrorAction Stop
    if (-not $inventory.PSObject.Properties['toolboxes']) { throw 'Toolbox inventory has an unexpected shape.' }
    $existing = @($inventory.toolboxes | Where-Object { $_.name -ceq $toolboxName })
    if ($existing.Count -gt 1) { throw 'Multiple runtime Toolboxes require operator review.' }
    if ($existing.Count -eq 0) {
        if (-not $AuthorizeToolboxCreate) { throw 'Missing runtime Toolbox; initial creation requires -AuthorizeToolboxCreate.' }
        $definition = Get-Content (Join-Path $repositoryRoot "infra\$definitionName") -Raw |
            ConvertFrom-Json -AsHashtable
        $definition.tools[0].server_url = $connection.target
        $temporary = Join-Path ([IO.Path]::GetTempPath()) ('lab722-toolbox-' + [guid]::NewGuid().ToString('N') + '.json')
        try {
            [IO.File]::WriteAllText($temporary, ($definition | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
            azd ai toolbox create $toolboxName --from-file $temporary `
                --project-endpoint $endpoint -C $repositoryRoot --no-prompt -o json | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'Toolbox creation failed; inspect the existing operation before retrying.' }
        } finally {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
    $showText = azd ai toolbox show $toolboxName --project-endpoint $endpoint `
        -C $repositoryRoot --no-prompt -o json
    if ($LASTEXITCODE -ne 0) { throw 'Runtime Toolbox read-back failed.' }
    $actual = ($showText -join "`n") | ConvertFrom-Json -ErrorAction Stop
    $tools = @($actual.version.tools)
    if ($tools.Count -ne 1 -or @($actual.version.skills).Count -ne 0 -or
        $tools[0].type -cne 'mcp' -or $tools[0].server_label -cne $label -or
        $tools[0].project_connection_id -cne $backendName -or
        $tools[0].server_url -cne $connection.target -or $tools[0].require_approval -cne 'never' -or
        @($tools[0].allowed_tools).Count -ne 1 -or $tools[0].allowed_tools[0] -cne $toolName) {
        throw 'Existing runtime Toolbox has a different tool surface; it was not overwritten.'
    }
    [pscustomobject]@{
        status = 'verified'
        toolbox = $toolboxName
        version = $actual.version.version
        reused = ($existing.Count -eq 1)
        endpoint = $actual.endpoint
    }
    return
}

az account set --subscription $Subscription
if ($LASTEXITCODE -ne 0) {
    throw "Unable to select Azure subscription '$Subscription'."
}

$subscriptionId = az account show --query id --output tsv
if ([string]::IsNullOrWhiteSpace($subscriptionId)) {
    throw 'Azure subscription ID is empty.'
}

if ([string]::IsNullOrWhiteSpace($LabUserPrincipalId)) {
    $LabUserPrincipalId = az ad signed-in-user show --query id --output tsv
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($LabUserPrincipalId)) {
        throw 'Unable to resolve the maintainer principal for data-plane access.'
    }
}

$environments = azd env list --output json 2>$null | ConvertFrom-Json
$environmentExists = $environments | Where-Object { $_.Name -eq $EnvironmentName }

if (-not $environmentExists) {
    azd env new $EnvironmentName `
        --subscription $subscriptionId `
        --location $Location `
        --no-prompt
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create azd environment '$EnvironmentName'."
    }
}

azd env select $EnvironmentName
azd env set AZURE_RESOURCE_GROUP $ResourceGroup
azd env set AZURE_LOCATION $Location
azd env set LAB_USER_PRINCIPAL_ID $LabUserPrincipalId
azd env set LAB_USER_PRINCIPAL_TYPE User

$values = azd env get-values --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to inspect the existing deployment outputs.'
}
$assignmentName = ''
if ($values.PSObject.Properties['FOUNDRY_ACCOUNT_NAME'] -and
    $values.PSObject.Properties['FOUNDRY_PROJECT_NAME']) {
    $projectId = '/subscriptions/{0}/resourceGroups/{1}/providers/Microsoft.CognitiveServices/accounts/{2}/projects/{3}' -f `
        $subscriptionId, $ResourceGroup, $values.FOUNDRY_ACCOUNT_NAME, $values.FOUNDRY_PROJECT_NAME
    $assignments = az role assignment list --assignee $LabUserPrincipalId `
        --scope $projectId --subscription $subscriptionId --output json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to inspect existing Foundry User access.'
    }
    $existing = @($assignments | Where-Object {
        $_.scope -eq $projectId -and
        $_.roleDefinitionId -like '*/53ca6127-db72-4b80-b1b0-d745d6d5456d'
    })
    if ($existing.Count -gt 1) {
        throw 'Multiple project-scoped Foundry User assignments need maintainer review.'
    }
    if ($existing.Count -eq 1) {
        $assignmentName = $existing[0].name
    }
}
azd env set FOUNDRY_USER_ROLE_ASSIGNMENT_NAME $assignmentName
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to preserve the Foundry role assignment name.'
}

& (Join-Path $PSScriptRoot 'compile-arm.ps1') | Out-Null

azd provision --no-prompt
if ($LASTEXITCODE -ne 0) {
    throw "Provisioning failed for azd environment '$EnvironmentName'."
}

azd env get-values
