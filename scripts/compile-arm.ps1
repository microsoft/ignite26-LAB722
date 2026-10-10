[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$bicepFile = Join-Path $repositoryRoot 'infra\main.bicep'
$outputDirectory = Join-Path $repositoryRoot 'infra\skillable'
$outputFile = Join-Path $outputDirectory 'azuredeploy.json'

New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null

az bicep build --file $bicepFile --outfile $outputFile
if ($LASTEXITCODE -ne 0) {
    throw 'Bicep compilation failed.'
}

Write-Output $outputFile
