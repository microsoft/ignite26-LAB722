#requires -Version 7.3
[CmdletBinding()]
param(
    [Parameter(Mandatory)][guid]$SubscriptionId,
    [string]$ResourceGroupName = 'ig2026-lab-local2',
    [string]$Region = 'westus3',
    [string]$EnvironmentName = 'reactor2-local',
    [int]$ModelCapacity = 40,
    [Parameter(Mandatory)][string]$ExecutionApiAudience,
    [Parameter(Mandatory)][securestring]$AlicePassword,
    [Parameter(Mandatory)][securestring]$BobPassword,
    [string]$PythonExecutable = 'python'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$statePath = Join-Path $root ".build-contexts\reactor2-$EnvironmentName\research-values.json"
function Invoke-Reactor2Command {
    param([string]$Executable, [string[]]$Arguments)
    $text = & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Executable $($Arguments[0]) failed; inspect the owned operation before retrying." }
    return ($text -join "`n")
}
if ($ExecutionApiAudience -notmatch '^api://[a-fA-F0-9-]{36}$') {
    throw 'Supply the approved dedicated service API identifier, not a first-party audience.'
}
$account = Invoke-Reactor2Command az @('account', 'show', '-o', 'json') | ConvertFrom-Json
if ($account.id -ine $SubscriptionId -or $account.state -cne 'Enabled') {
    throw 'Sign into the intended enabled subscription before provisioning.'
}
$exists = Invoke-Reactor2Command az @('group', 'exists', '--subscription', $SubscriptionId,
    '--name', $ResourceGroupName) | ConvertFrom-Json
if ($exists) {
    $group = Invoke-Reactor2Command az @('group', 'show', '--subscription', $SubscriptionId,
        '--name', $ResourceGroupName, '-o', 'json') | ConvertFrom-Json
    if ($group.tags.lab -cne 'LAB722' -or $group.tags.purpose -cne 'reactor2') {
        throw 'Existing RG is not this variant allocation; no adoption or replacement was performed.'
    }
} else {
    $null = Invoke-Reactor2Command az @('group', 'create', '--subscription', $SubscriptionId,
        '--name', $ResourceGroupName, '--location', $Region, '--tags', 'lab=LAB722',
        'purpose=reactor2', "azd-env-name=$EnvironmentName", '-o', 'json')
}
$operator = Invoke-Reactor2Command az @('ad', 'signed-in-user', 'show', '--query', 'id', '-o', 'tsv')
$template = Join-Path $root 'infra\local-reactor\main.bicep'
$outputs = Invoke-Reactor2Command az @('deployment', 'group', 'create', '--subscription', $SubscriptionId,
    '--resource-group', $ResourceGroupName, '--name', "reactor2-$EnvironmentName", '--template-file', $template,
    '--parameters', "location=$Region", "environmentName=$EnvironmentName", "operatorObjectId=$operator",
    "modelCapacity=$ModelCapacity", '--query', 'properties.outputs', '-o', 'json') | ConvertFrom-Json
$scope = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroupName"
$accountId = "$scope/providers/Microsoft.CognitiveServices/accounts/$($outputs.FOUNDRY_ACCOUNT_NAME.value)"
$projectId = "$accountId/projects/$($outputs.FOUNDRY_PROJECT_NAME.value)"
$registryId = Invoke-Reactor2Command az @('acr', 'show', '--subscription', $SubscriptionId,
    '--name', 'acateam', '--query', 'id', '-o', 'tsv')
$auth = Invoke-Reactor2Command az @('account', 'get-access-token', '--subscription', $SubscriptionId,
    '--resource', 'https://management.azure.com/', '-o', 'json') | ConvertFrom-Json
function Invoke-Reactor2Arm {
    param([string]$Method, [string]$Id, [string]$Version, $Body)
    $request = @{ Uri = "https://management.azure.com${Id}?api-version=$Version";
        Method = $Method; Headers = @{ Authorization = 'Bearer ' + $auth.accessToken } }
    if ($Method -ne 'GET') { $request.ContentType = 'application/json' }
    if ($null -ne $Body) { $request.Body = $Body | ConvertTo-Json -Depth 100 -Compress }
    Invoke-RestMethod @request
}
try {
    $project = Invoke-Reactor2Arm GET $projectId '2025-06-01'
    foreach ($permission in @(
        @{ scope = $accountId; role = '53ca6127-db72-4b80-b1b0-d745d6d5456d' },
        @{ scope = $registryId; role = '7f951dda-4ed3-4680-a7ca-43fe172d538d' }
    )) {
        $roles = Invoke-Reactor2Command az @('role', 'assignment', 'list', '--subscription', $SubscriptionId,
            '--scope', $permission.scope, '-o', 'json') | ConvertFrom-Json
        if (@($roles | Where-Object {
            $_.scope -ieq $permission.scope -and $_.principalId -ieq $project.identity.principalId -and
            $_.roleDefinitionId.EndsWith('/' + $permission.role, [StringComparison]::OrdinalIgnoreCase)
        }).Count) { continue }
        $hash = [Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes(
            "$($permission.scope)/$($project.identity.principalId)/$($permission.role)"))
        $name = [guid]::new([byte[]]$hash[0..15])
        $null = Invoke-Reactor2Arm PUT "$($permission.scope)/providers/Microsoft.Authorization/roleAssignments/$name" `
            '2022-04-01' @{ properties = @{
                roleDefinitionId = "/subscriptions/$SubscriptionId/providers/Microsoft.Authorization/roleDefinitions/$($permission.role)"
                principalId = $project.identity.principalId; principalType = 'ServicePrincipal'
            } }
    }
    $connection = Invoke-Reactor2Arm PUT "$projectId/connections/reactor-acateam" '2025-06-01' @{
        properties = @{ category = 'ContainerRegistry'; authType = 'ManagedIdentity';
            target = 'acateam.azurecr.io'; isSharedToAll = $false; metadata = @{ ResourceId = $registryId };
            credentials = @{ clientId = $project.identity.principalId; resourceId = $registryId } }
    }
    if ($connection.properties.authType -cne 'ManagedIdentity') { throw 'Registry identity connection was not established.' }
} finally { $auth = $null }
$values = @{
    SubscriptionId = $SubscriptionId.ToString(); ResourceGroupName = $ResourceGroupName; Region = $Region
    SandboxGroupName = $outputs.SANDBOX_GROUP_NAME.value; ProjectEndpoint = $outputs.FOUNDRY_PROJECT_ENDPOINT.value
    FoundryAccountName = $outputs.FOUNDRY_ACCOUNT_NAME.value; FoundryProjectName = $outputs.FOUNDRY_PROJECT_NAME.value
    ExpressEnvironmentName = $outputs.EXPRESS_ENVIRONMENT_NAME.value; ExecutionApiAudience = $ExecutionApiAudience
    Model = $outputs.FOUNDRY_MODEL_DEPLOYMENT_NAME.value
}
$prepared = & (Join-Path $PSScriptRoot 'prepare-reactor-swarm.ps1') -AllocationValues $values `
    -PreparedStatePath $statePath -AlicePassword $AlicePassword -BobPassword $BobPassword `
    -PythonExecutable $PythonExecutable
$AlicePassword = $null; $BobPassword = $null
Write-Host "Services prepared in $ResourceGroupName. Exact hosted version: $($prepared.HostedName)/$($prepared.HostedVersion)."
$prepared
