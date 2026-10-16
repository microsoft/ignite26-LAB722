#requires -Version 7.2
[CmdletBinding(DefaultParameterSetName = 'Stage')]
param(
    [string] $PythonExecutable = 'python',
    [Parameter(ParameterSetName = 'Stage')] [string] $Destination,
    [Parameter(ParameterSetName = 'Stage')] [switch] $ConfigureSession,
    [Parameter(Mandatory, ParameterSetName = 'Validate')] [switch] $ValidateOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Split-Path -Parent $PSScriptRoot
$arguments = @('-m', 'data.pipeline.lab_bundle')
if ($ValidateOnly) { $arguments += '--validate-only' }
elseif ($Destination) { $arguments += @('--destination', $Destination) }
Push-Location -LiteralPath $root
try {
    $text = & $PythonExecutable @arguments
    if ($LASTEXITCODE -ne 0) { throw 'The pinned lab dataset was not verified/staged; session configuration is unchanged.' }
    $receipt = ($text -join "`n") | ConvertFrom-Json -ErrorAction Stop
    if (-not $receipt.frozen_files_verified -or
        $receipt.manifest_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
        $receipt.purpose -cne 'public-lab-development' -or
        $receipt.full_functional_acceptance_rerun -or $receipt.attendee_ready -or
        (-not $ValidateOnly -and -not $receipt.staged)) {
        throw 'The lab dataset handoff returned an unexpected receipt; session configuration is unchanged.'
    }
    if ($ConfigureSession) {
        $env:LAB_STARTUP_PURPOSE = $receipt.purpose
        $env:LAB_DATA_MANIFEST = $receipt.manifest
        $env:LAB_DATA_MANIFEST_SHA256 = $receipt.manifest_sha256
        $env:LAB_PYTHON_EXECUTABLE = $PythonExecutable
    }
    $receipt
}
finally { Pop-Location }
