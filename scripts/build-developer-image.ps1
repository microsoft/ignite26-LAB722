[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[a-z0-9]{5,50}$')]
    [string] $RegistryName,

    [Parameter(Mandatory)]
    [guid] $SubscriptionId,

    [Parameter(Mandatory)]
    [ValidatePattern('^[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*$')]
    [string] $Repository,

    [Parameter(Mandatory)]
    [ValidatePattern('^[a-z0-9][a-z0-9._-]{0,110}$')]
    [string] $Tag,

    [string] $SourceRevision,
    [string] $FrozenManifest,
    [ValidatePattern('^[0-9a-f]{64}$')] [string] $FrozenManifestSha256,
    [ValidateSet('synthetic-development', 'public-lab-development')]
    [string] $Purpose = 'synthetic-development'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if ([string]::IsNullOrWhiteSpace($SourceRevision)) {
    $SourceRevision = git rev-parse HEAD
    if ($LASTEXITCODE -ne 0) {
        throw 'Specify SourceRevision when building outside a Git checkout.'
    }
    if (git status --porcelain) {
        $SourceRevision = "$SourceRevision-working-tree"
    }
}

$root = $PWD.Path
$workspace = Join-Path $root ('.build-contexts\' + [guid]::NewGuid().ToString('N'))
$context = Join-Path $workspace 'source'
$archive = Join-Path $workspace 'archive'
$previousTemp = $env:TEMP
$previousTmp = $env:TMP
try {
    New-Item -ItemType Directory -Path $archive -Force | Out-Null
    $exportArguments = @((Join-Path $root 'src\developer-image\export_source.py'),
        '--destination', $context, '--source-revision', $SourceRevision, '--purpose', $Purpose)
    if ($FrozenManifest -or $FrozenManifestSha256) {
        if (-not $FrozenManifest -or -not $FrozenManifestSha256) { throw 'Frozen export requires both manifest and trust anchor.' }
        $exportArguments += @('--manifest', $FrozenManifest, '--manifest-sha256', $FrozenManifestSha256)
    }
    $export = & python @exportArguments
    if ($LASTEXITCODE -ne 0) { throw 'Pinned source export failed; no ACR build was queued.' }
    $exported = ($export -join "`n") | ConvertFrom-Json
    if ($exported.directory -ine $context) { throw 'The exporter returned an unexpected source directory.' }
    $env:TEMP = $archive
    $env:TMP = $archive
    # The release target depends on both reference acceptance and prepared-baseline validation.
    $run = az acr build `
        --registry $RegistryName --subscription $SubscriptionId `
        --image "${Repository}:$Tag" --file (Join-Path $context 'Dockerfile') `
        --build-arg "SOURCE_REVISION=$SourceRevision" `
        --target release --platform linux/amd64 `
        --timeout 1200 --no-logs --output json $context | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or $run.status -ne 'Succeeded') {
        if ($run) {
            Write-Warning "Existing ACR run: $($run.runId); status: $($run.status)"
        }
        throw 'The developer image build failed. Inspect its existing ACR run before retrying; do not queue a duplicate.'
    }
}
finally {
    $env:TEMP = $previousTemp
    $env:TMP = $previousTmp
    if (Test-Path -LiteralPath $workspace) {
        Remove-Item -LiteralPath $workspace -Recurse -Force
    }
}
[pscustomobject] @{
    Registry = $RegistryName
    Repository = $run.outputImages[0].repository
    Tag = $Tag
    Digest = $run.outputImages[0].digest
    RunId = $run.runId
    SourceRevision = $SourceRevision
    BaselineRoot = '/opt/caldova-lab'
    PreviewState = 'starter'
    AcceptancePurpose = $Purpose
}
