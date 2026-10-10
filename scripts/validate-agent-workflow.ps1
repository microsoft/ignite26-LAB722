[CmdletBinding(DefaultParameterSetName = 'Metadata')]
param(
    [Parameter(Mandatory)]
    [string] $EnvironmentName,

    [Parameter(Mandatory, ParameterSetName = 'Metadata')]
    [uri] $MetadataUrl,

    [Parameter(Mandatory, ParameterSetName = 'Manifest')]
    [string] $ManifestPath,

    [ValidateSet('plan', 'tool-smoke', 'workers')]
    [string] $Mode = 'plan',

    [string] $BindingsPath,

    [guid] $ValidationSandboxId = [guid]::Empty,

    [ValidateSet('clinical-trials', 'drug-safety', 'quality-governance')]
    [string] $Role = 'clinical-trials',

    [switch] $ApprovePlan,

    [switch] $UseWsl
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$repositoryRoot = (Get-Location).Path
azd env select $EnvironmentName | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Unable to select azd environment '$EnvironmentName'."
}
$values = azd env get-values --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to read Foundry and Sandbox outputs.'
}
$aca = (Get-Command aca -ErrorAction Stop).Source
$arguments = @(
    '-m', 'src.orchestrator.run',
    '--mode', $Mode,
    '--project-endpoint', $values.FOUNDRY_PROJECT_ENDPOINT,
    '--model', $values.FOUNDRY_MODEL_DEPLOYMENT_NAME,
    '--subscription', $values.AZURE_SUBSCRIPTION_ID,
    '--resource-group', $values.AZURE_RESOURCE_GROUP,
    '--region', $values.SANDBOX_REGION,
    '--group', $values.SANDBOX_GROUP_NAME,
    '--role', $Role
)
if ($PSCmdlet.ParameterSetName -eq 'Manifest') {
    $ManifestPath = (Resolve-Path -LiteralPath $ManifestPath).Path
}
else {
    $arguments += @('--metadata-url', $MetadataUrl.AbsoluteUri)
}
if ($ApprovePlan) {
    $arguments += '--approve-plan'
}
if ($Mode -ne 'plan' -and [string]::IsNullOrWhiteSpace($BindingsPath)) {
    throw 'Worker and tool-smoke modes require an explicit binding file.'
}
if ($Mode -eq 'workers' -and (-not $ApprovePlan -or $ValidationSandboxId -eq [guid]::Empty)) {
    throw 'Worker mode requires -ApprovePlan and a separate trusted -ValidationSandboxId.'
}
if ($ValidationSandboxId -ne [guid]::Empty) {
    $arguments += @('--validation-sandbox-id', $ValidationSandboxId.ToString())
}
if (-not [string]::IsNullOrWhiteSpace($BindingsPath)) {
    $BindingsPath = (Resolve-Path -LiteralPath $BindingsPath).Path
}
if ($UseWsl) {
    $aca = (wsl --exec wslpath -a $aca).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to resolve the ACA executable in the Linux runtime.'
    }
    if ($BindingsPath) {
        $BindingsPath = (wsl --exec wslpath -a $BindingsPath).Trim()
        if ($LASTEXITCODE -ne 0) {
            throw 'Unable to resolve the worker binding file in the Linux runtime.'
        }
    }
    if ($ManifestPath) {
        $ManifestPath = (wsl --exec wslpath -a $ManifestPath).Trim()
        if ($LASTEXITCODE -ne 0) {
            throw 'Unable to resolve the prepared data manifest in the Linux runtime.'
        }
    }
}
$arguments += @('--aca', $aca)
if ($BindingsPath) {
    $arguments += @('--bindings', $BindingsPath)
}
if ($ManifestPath) {
    $arguments += @('--manifest', $ManifestPath)
}
if ($UseWsl) {
    $tokenJson = az account get-access-token --subscription $values.AZURE_SUBSCRIPTION_ID `
        --resource https://ai.azure.com --output json | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to acquire the short-lived Foundry credential.'
    }
    try {
        $output = $tokenJson | wsl --cd $repositoryRoot --exec .venv-linux/bin/python @arguments --token-stdin
        if ($LASTEXITCODE -ne 0) {
            throw 'Agent Framework validation failed in the Linux runtime.'
        }
    }
    finally {
        $tokenJson = $null
    }
}
else {
    $python = Join-Path $repositoryRoot '.venv\Scripts\python.exe'
    $output = & $python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw 'Agent Framework validation failed.'
    }
}
($output -join "`n") | ConvertFrom-Json
