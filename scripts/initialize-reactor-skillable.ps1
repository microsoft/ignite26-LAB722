#requires -Version 7.3
[CmdletBinding()]
param(
    [Parameter(Mandatory)][guid]$SubscriptionId,
    [Parameter(Mandatory)][guid]$TenantId,
    [Parameter(Mandatory)][string]$ResourceGroupName,
    [Parameter(Mandatory)][securestring]$AlicePassword,
    [Parameter(Mandatory)][securestring]$BobPassword,
    [Parameter(Mandatory)][string]$PythonExecutable
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
function Invoke-HarnessCommand {
    param([string]$Executable, [string[]]$Arguments)
    $text = & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Executable $($Arguments[0]) failed. Inspect the retained operation before retrying." }
    return ($text -join "`n")
}
$account = Invoke-HarnessCommand az @('account', 'show', '-o', 'json') | ConvertFrom-Json
if ($account.id -ine $SubscriptionId -or $account.tenantId -ine $TenantId -or $account.state -cne 'Enabled') {
    throw 'Sign into the intended enabled Skillable subscription before setup.'
}
$deployments = Invoke-HarnessCommand az @('deployment', 'group', 'list', '--subscription',
    $SubscriptionId, '--resource-group', $ResourceGroupName, '-o', 'json') | ConvertFrom-Json
$matches = @($deployments | Where-Object {
    $_.properties.provisioningState -ceq 'Succeeded' -and $_.properties.outputs -and
    $_.properties.outputs.PSObject.Properties.Name -contains 'REACTOR2_HARNESS_VERSION' -and
    $_.properties.outputs.REACTOR2_HARNESS_VERSION.value -ceq '1'
})
if ($matches.Count -ne 1) { throw 'Expected exactly one successful Reactor 2 foundation deployment.' }
$outputs = $matches[0].properties.outputs
if ($outputs.AZURE_SUBSCRIPTION_ID.value -ine $SubscriptionId -or
    $outputs.AZURE_TENANT_ID.value -ine $TenantId -or
    $outputs.AZURE_RESOURCE_GROUP.value -cne $ResourceGroupName) {
    throw 'Foundation outputs do not belong to this allocation.'
}
$apiName = "LAB722-Reactor2-$SubscriptionId-$ResourceGroupName"
$apiFilter = "displayName eq '$($apiName.Replace("'", "''"))'"
$applications = @(Invoke-HarnessCommand az @('ad', 'app', 'list', '--filter', $apiFilter,
    '-o', 'json') | ConvertFrom-Json)
if ($applications.Count -ne 1) { throw 'Expected exactly one allocation execution API from the blocking access LCA.' }
$application = $applications[0]
$audience = 'api://' + $application.appId
if ($application.displayName -cne $apiName -or
    $application.notes -cne "Skillable allocation /subscriptions/$SubscriptionId/resourceGroups/$ResourceGroupName" -or
    $application.signInAudience -cne 'AzureADMyOrg' -or $application.api.requestedAccessTokenVersion -ne 1 -or
    $audience -notmatch '^api://[a-fA-F0-9-]{36}$' -or
    @($application.identifierUris).Count -ne 1 -or $application.identifierUris[0] -cne $audience) {
    throw 'Allocation execution API ownership or audience differs from the lab contract.'
}
$principals = @(Invoke-HarnessCommand az @('ad', 'sp', 'list', '--filter',
    "appId eq '$($application.appId)'", '-o', 'json') | ConvertFrom-Json)
if ($principals.Count -ne 1 -or $principals[0].appId -cne $application.appId -or
    $principals[0].appRoleAssignmentRequired) {
    throw 'Allocation execution API service-principal policy differs from the lab contract.'
}
$stateDirectory = Join-Path $root ".build-contexts\skillable-$SubscriptionId-$ResourceGroupName"
$statePath = Join-Path $stateDirectory 'research-values.json'
$catalog = Get-Content (Join-Path $root 'data\reactor-research-images.json') -Raw | ConvertFrom-Json
$registryName = $outputs.AZURE_CONTAINER_REGISTRY_NAME.value
$registry = Invoke-HarnessCommand az @('acr', 'show', '--subscription', $SubscriptionId,
    '--resource-group', $ResourceGroupName, '--name', $registryName, '-o', 'json') | ConvertFrom-Json
$prefix = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroupName/providers/"
if ($registry.id -ine "${prefix}Microsoft.ContainerRegistry/registries/$registryName" -or
    $registry.tags.lab -cne 'LAB722' -or $registry.tags.purpose -cne 'reactor2-skillable') {
    throw 'Registry is not the allocation-local Reactor 2 registry.'
}
$digest = ($catalog.hosted_image -split '@')[1]
$repository = 'lab722/reactor-swarm-hosted'
$tag = 'release-' + $digest.Substring(7, 12)
$repositories = Invoke-HarnessCommand az @('acr', 'repository', 'list', '--subscription',
    $SubscriptionId, '--name', $registryName, '-o', 'json') | ConvertFrom-Json
$tags = if ($repositories -contains $repository) {
    Invoke-HarnessCommand az @('acr', 'repository', 'show-tags', '--subscription',
        $SubscriptionId, '--name', $registryName, '--repository', $repository, '-o', 'json') | ConvertFrom-Json
} else { @() }
if ($tags -notcontains $tag) {
    $null = Invoke-HarnessCommand az @('acr', 'import', '--subscription', $SubscriptionId,
        '--name', $registryName, '--source', $catalog.hosted_image,
        '--image', "${repository}:$tag")
}
$mirrored = Invoke-HarnessCommand az @('acr', 'repository', 'show', '--subscription',
    $SubscriptionId, '--name', $registryName, '--image', "${repository}:$tag", '-o', 'json') | ConvertFrom-Json
if ($mirrored.digest -cne $digest) { throw 'Allocation hosted-image digest differs; no overwrite was attempted.' }
$catalog.hosted_image = "$($registry.loginServer)/$repository@$digest"
$null = New-Item -ItemType Directory -Path $stateDirectory -Force
$catalogPath = Join-Path $stateDirectory 'research-images.json'
$catalog | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $catalogPath -Encoding utf8NoBOM
$projectId = "${prefix}Microsoft.CognitiveServices/accounts/$($outputs.FOUNDRY_ACCOUNT_NAME.value)/projects/$($outputs.FOUNDRY_PROJECT_NAME.value)"
$auth = Invoke-HarnessCommand az @('account', 'get-access-token', '--subscription', $SubscriptionId,
    '--resource', 'https://management.azure.com/', '-o', 'json') | ConvertFrom-Json
try {
    $headers = @{ Authorization = 'Bearer ' + $auth.accessToken }
    $uri = "https://management.azure.com$projectId/connections/reactor-allocated-registry?api-version=2025-06-01"
    $body = @{ properties = @{
        category = 'ContainerRegistry'; authType = 'ManagedIdentity'; target = $registry.loginServer
        isSharedToAll = $false; metadata = @{ ResourceId = $registry.id }
        credentials = @{ clientId = $outputs.REACTOR2_PROJECT_OBJECT_ID.value; resourceId = $registry.id }
    } } | ConvertTo-Json -Depth 10 -Compress
    $null = Invoke-RestMethod -Uri $uri -Method Put -Headers $headers -ContentType 'application/json' -Body $body
    $connection = Invoke-RestMethod -Uri $uri -Headers $headers
    if ($connection.properties.authType -cne 'ManagedIdentity' -or
        $connection.properties.target -cne $registry.loginServer -or
        $connection.properties.metadata.ResourceId -ine $registry.id) {
        throw 'Allocation registry connection read-back failed.'
    }
} finally { $auth = $null; $headers = $null; $body = $null }
$allocation = @{
    SubscriptionId = $SubscriptionId.ToString(); ResourceGroupName = $ResourceGroupName
    Region = $outputs.AZURE_LOCATION.value; SandboxGroupName = $outputs.SANDBOX_GROUP_NAME.value
    ProjectEndpoint = $outputs.FOUNDRY_PROJECT_ENDPOINT.value
    FoundryAccountName = $outputs.FOUNDRY_ACCOUNT_NAME.value
    FoundryProjectName = $outputs.FOUNDRY_PROJECT_NAME.value
    ExpressEnvironmentName = $outputs.EXPRESS_ENVIRONMENT_NAME.value
    ExecutionApiAudience = $audience; Model = $outputs.FOUNDRY_MODEL_DEPLOYMENT_NAME.value
}
$prepared = & (Join-Path $PSScriptRoot 'prepare-reactor-swarm.ps1') -AllocationValues $allocation `
    -PreparedStatePath $statePath -ImageCatalogPath $catalogPath -SkipRoleAssignments `
    -FrontendName $outputs.REACTOR2_FRONTEND_NAME.value -ExecutionName $outputs.REACTOR2_EXECUTION_NAME.value `
    -AlicePassword $AlicePassword -BobPassword $BobPassword -PythonExecutable $PythonExecutable
$null = Invoke-HarnessCommand $PythonExecutable @('-B', (Join-Path $PSScriptRoot 'wait-reactor-hosted.py'),
    '--project-endpoint', $prepared.ProjectEndpoint, '--name', $prepared.HostedName,
    '--version', $prepared.HostedVersion)
$session = Invoke-RestMethod -Uri "$($prepared.FrontendUrl)/api/session"
if (-not $session.hosted_configured) {
    $null = & (Join-Path $PSScriptRoot 'connect-reactor-frontend.ps1') -SubscriptionId $SubscriptionId `
        -ResourceGroupName $ResourceGroupName -FrontendName $prepared.FrontendName `
        -ProjectEndpoint $prepared.ProjectEndpoint -AgentName $prepared.HostedName `
        -HostedResponsesEndpoint $prepared.HostedEndpoint
}
$session = Invoke-RestMethod -Uri "$($prepared.FrontendUrl)/api/session"
if (-not $session.hosted_configured) { throw 'Frontend is not connected after exact hosted-version readiness.' }
$prepared.HostedConnected = $true
$prepared | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $statePath -Encoding utf8NoBOM
$prepared
