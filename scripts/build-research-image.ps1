[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string] $EnvironmentName,

    [Parameter(Mandatory)]
    [ValidatePattern('^[a-z0-9][a-z0-9._-]{0,110}$')]
    [string] $Tag,

    [ValidateSet('starter', 'reference')]
    [string] $PreviewState = 'reference'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
azd env select $EnvironmentName | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Unable to select azd environment '$EnvironmentName'."
}
$values = azd env get-values --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read azd environment '$EnvironmentName'."
}

foreach ($target in @('validation', 'release')) {
    $imageTag = if ($target -eq 'validation') { "$Tag-validation" } else { $Tag }
    $run = az acr build `
        --registry $values.AZURE_CONTAINER_REGISTRY_NAME `
        --subscription $values.AZURE_SUBSCRIPTION_ID `
        --image "caldova/research-portal:$imageTag" `
        --file 'src\research-portal\Containerfile' `
        --build-arg "PREVIEW_STATE=$PreviewState" `
        --target $target --platform linux/amd64 `
        --timeout 900 --no-logs --output json . | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or $run.status -ne 'Succeeded') {
        throw "The '$target' image build failed. Inspect its existing ACR run before retrying."
    }
    if ($target -eq 'release') {
        [pscustomobject] @{
            Registry = $values.AZURE_CONTAINER_REGISTRY_NAME
            Repository = $run.outputImages[0].repository
            Tag = $imageTag
            Digest = $run.outputImages[0].digest
            RunId = $run.runId
            PreviewState = $PreviewState
        }
    }
}
