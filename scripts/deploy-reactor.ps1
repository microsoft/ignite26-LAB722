#requires -Version 7.3
[CmdletBinding()]
param(
    [Parameter(Mandatory)][guid]$SubscriptionId,
    [Parameter(Mandatory)][string]$ResourceGroupName,
    [string]$RegistryName = 'acateam',
    [switch]$UsePrivateRegistry,
    [Parameter(Mandatory)][string]$ExpressEnvironmentName,
    [Parameter(Mandatory)][string]$FoundryAccountName,
    [string]$FoundryProjectName = 'caldova',
    [Parameter(Mandatory)][string]$SandboxGroupName,
    [Parameter(Mandatory)][guid]$SnapshotId,
    [Parameter(Mandatory)][string]$ServiceImage,
    [Parameter(Mandatory)][string]$ExecutionApiAudience,
    [uri]$HostedResponsesEndpoint,
    [Parameter(Mandatory)][securestring]$AlicePassword,
    [Parameter(Mandatory)][securestring]$BobPassword
)
$ErrorActionPreference = 'Stop'
if ($ExecutionApiAudience -in @('https://ai.azure.com', 'https://management.azure.com', 'https://cognitiveservices.azure.com')) {
    throw 'Supply the dedicated service API audience. First-party-audience substitution is not supported.'
}
if ($ServiceImage -notlike "$RegistryName.azurecr.io/*" -or
    $ServiceImage -notmatch '@sha256:[a-f0-9]{64}$' -or
    ($null -ne $HostedResponsesEndpoint -and $HostedResponsesEndpoint.Scheme -ne 'https')) {
    throw 'Use an immutable image from the selected registry and, when connecting the hosted agent, an HTTPS Responses endpoint.'
}
$templateText = & az bicep build --file (Join-Path $PSScriptRoot '..\infra\reactor.bicep') --stdout
if ($LASTEXITCODE -ne 0) { throw 'Reactor ARM compilation failed.' }
$values = @{
    registryName = $RegistryName; anonymousImagePull = -not $UsePrivateRegistry
    expressEnvironmentName = $ExpressEnvironmentName
    foundryAccountName = $FoundryAccountName; foundryProjectName = $FoundryProjectName
    sandboxGroupName = $SandboxGroupName; snapshotId = $SnapshotId.ToString()
    serviceImage = $ServiceImage; executionApiAudience = $ExecutionApiAudience
    hostedResponsesEndpoint = $(if ($null -eq $HostedResponsesEndpoint) { '' } else { $HostedResponsesEndpoint.AbsoluteUri })
    alicePassword = [System.Net.NetworkCredential]::new('', $AlicePassword).Password
    bobPassword = [System.Net.NetworkCredential]::new('', $BobPassword).Password
}
if ($values.alicePassword.Length -lt 12 -or $values.bobPassword.Length -lt 12 -or
    $values.alicePassword.Length -gt 1024 -or $values.bobPassword.Length -gt 1024 -or
    $values.alicePassword -ceq $values.bobPassword) {
    throw 'Supply two different demo passwords of 12-1024 characters.'
}
$parameters = @{}
foreach ($entry in $values.GetEnumerator()) { $parameters[$entry.Key] = @{ value = $entry.Value } }
$body = @{
    properties = @{
        mode = 'Incremental'
        template = ($templateText -join "`n" | ConvertFrom-Json -AsHashtable)
        parameters = $parameters
    }
} | ConvertTo-Json -Depth 100 -Compress
$auth = & az account get-access-token --subscription $SubscriptionId --resource 'https://management.azure.com/' -o json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Azure authentication failed.' }
$deployment = 'reactor-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$uri = "https://management.azure.com/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroupName/providers/Microsoft.Resources/deployments/${deployment}?api-version=2025-04-01"
try {
    $headers = @{ Authorization = 'Bearer ' + $auth.accessToken }
    $null = Invoke-RestMethod -Uri $uri -Method Put -Headers $headers -Body $body -ContentType 'application/json'
    $deadline = [DateTime]::UtcNow.AddMinutes(15)
    do {
        Start-Sleep -Seconds 10
        $result = Invoke-RestMethod -Uri $uri -Method Get -Headers $headers
        $state = $result.properties.provisioningState
        if ($state -in @('Failed', 'Canceled')) { throw "Deployment $deployment ended in $state. Inspect Azure deployment operations." }
    } until ($state -eq 'Succeeded' -or [DateTime]::UtcNow -gt $deadline)
    if ($state -ne 'Succeeded') { throw "Deployment $deployment is not ready; inspect its status before retrying." }
    $result.properties.outputs
} finally {
    $body = $null; $values = $null; $parameters = $null; $auth = $null; $headers = $null
}
