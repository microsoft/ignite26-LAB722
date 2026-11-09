[CmdletBinding()]
param(
    [switch] $RuntimeOnly,
    [switch] $Reactor2
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryRoot = Split-Path -Parent $PSScriptRoot
if ($RuntimeOnly -and $Reactor2) { throw 'Select RuntimeOnly or Reactor2, not both.' }
$bicepFile = Join-Path $repositoryRoot $(if ($Reactor2) { 'infra\reactor2-skillable.bicep' } elseif ($RuntimeOnly) { 'infra\modules\runtime-proof.bicep' } else { 'infra\main.bicep' })
$outputDirectory = Join-Path $repositoryRoot 'infra\skillable'
$outputFile = Join-Path $outputDirectory $(if ($Reactor2) { 'reactor2.azuredeploy.json' } elseif ($RuntimeOnly) { 'runtime-proof.azuredeploy.json' } else { 'azuredeploy.json' })

New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null

az bicep build --file $bicepFile --outfile $outputFile
if ($LASTEXITCODE -ne 0) {
    throw 'Bicep compilation failed.'
}

Write-Output $outputFile
