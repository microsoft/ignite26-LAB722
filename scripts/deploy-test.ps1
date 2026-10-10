[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[a-zA-Z0-9-]+$')]
    [string] $EnvironmentName,

    [string] $ResourceGroup = $EnvironmentName,

    [string] $Subscription = 'Private Test Sub ACAPMS',

    [string] $Location = 'westus3',

    [string] $LabUserPrincipalId
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repositoryRoot

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
