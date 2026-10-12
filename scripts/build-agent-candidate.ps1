<#
.SYNOPSIS
Stages an accepted run and optionally builds its unapproved, digest-pinned ACR candidate.
.DESCRIPTION
ApprovedRunId selects the independently accepted source run; it is NOT human release approval.
FrozenArtifactDirectory must contain the downloaded original database and data-manifest.json.
StageOnly performs no cloud operation and executes no candidate code. The candidate image target
depends on the dataset-specific suite (nine original synthetic or eight frozen-public checks),
against unchanged frozen runtime data and staged features. Public source JSON/ZIP are also protected.
No release, deployment, Sandbox allocation, credentials, or data rebuilding is performed.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)] [string] $ResultPath,
    [Parameter(Mandatory)] [ValidatePattern('^[0-9a-f]{64}$')] [string] $ResultSha256,
    [Parameter(Mandatory)] [string] $BaselineDescriptorPath,
    [Parameter(Mandatory)] [string] $FrozenArtifactDirectory,
    [Parameter(Mandatory)] [ValidatePattern('^[0-9a-f]{64}$')] [string] $ManifestSha256,
    [Parameter(Mandatory)] [guid] $ApprovedRunId,
    [Parameter(Mandatory)] [string] $Destination,
    [ValidateSet('synthetic-development', 'public-lab-development')]
    [string] $Purpose = 'synthetic-development',
    [Parameter(Mandatory)] [ValidateSet('lab7222tf3zuqwfs4huacr')] [string] $RegistryName,
    [Parameter(Mandatory)] [guid] $SubscriptionId,
    [ValidateSet('caldova/research-portal')] [string] $Repository = 'caldova/research-portal',
    [Parameter(Mandatory)] [ValidatePattern('^[a-z0-9][a-z0-9._-]{0,110}$')] [string] $Tag,
    [switch] $StageOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($SubscriptionId -ne [guid] '30501c6c-81f6-41ac-a388-d29cf43a020d') {
    throw 'Candidate packaging is restricted to the already authorized LAB722 subscription.'
}
$root = Split-Path -Parent $PSScriptRoot
$helper = Join-Path $root 'src\developer-image\stage_candidate.py'
Push-Location -LiteralPath $root
try {
    $stageText = & python $helper `
        --result $ResultPath --result-sha256 $ResultSha256 `
        --baseline-descriptor $BaselineDescriptorPath --frozen-artifact-directory $FrozenArtifactDirectory `
        --manifest-sha256 $ManifestSha256 --approved-run-id $ApprovedRunId.ToString() --destination $Destination --purpose $Purpose
    if ($LASTEXITCODE -ne 0) { throw 'Candidate staging failed; no build was queued.' }
    $stage = $stageText | ConvertFrom-Json
    if ($StageOnly -or -not $PSCmdlet.ShouldProcess(
        "$RegistryName/$Repository`:$Tag", 'Build an unapproved candidate with required container acceptance'
    )) {
        [pscustomobject] @{
            Directory = $stage.directory
            ProvenanceSha256 = $stage.provenance_sha256
            RunId = $stage.run_id
            Status = 'staged-awaiting-container-validation'
            HumanApproval = $false
            ReleaseApproved = $false
            Deployed = $false
        }
        return
    }
    $archive = Join-Path (Split-Path -Parent $stage.directory) ('.acr-transfer-' + [guid]::NewGuid().ToString('N'))
    $previousTemp = $env:TEMP
    $previousTmp = $env:TMP
    try {
        [void] [IO.Directory]::CreateDirectory($archive)
        $env:TEMP = $archive
        $env:TMP = $archive
        # An explicit read must succeed; an authentication or lookup failure is never "tag is new".
        $tagText = & az acr repository show-tags --name $RegistryName --subscription $SubscriptionId `
            --repository $Repository --only-show-errors --output json
        if ($LASTEXITCODE -ne 0) { throw 'Unable to verify that the candidate tag is new; no build was queued.' }
        $tags = ConvertFrom-Json -InputObject ($tagText -join "`n") -NoEnumerate
        if ($tags -isnot [array] -or @($tags | Where-Object { $_ -isnot [string] }).Count -gt 0) {
            throw 'ACR returned a malformed tag inventory; no build was queued.'
        }
        if ($Tag -cin $tags) { throw 'Refusing to overwrite an existing candidate tag.' }
        $verified = & python $helper --verify-context $stage.directory --provenance-sha256 $stage.provenance_sha256
        if ($LASTEXITCODE -ne 0) { throw 'Candidate context changed before the build; no build was queued.' }
        # An explicit ACR --file is resolved from cwd, not from the source-context directory.
        $dockerfile = Join-Path $stage.directory 'Dockerfile'
        if (-not (Test-Path -LiteralPath $dockerfile -PathType Leaf)) {
            throw 'The staged Dockerfile is missing; no build was queued.'
        }
        $runText = & az acr build --registry $RegistryName --subscription $SubscriptionId `
            --image "${Repository}:$Tag" --file $dockerfile --target candidate --platform linux/amd64 `
            --timeout 1200 --no-logs --only-show-errors --output json $stage.directory
        if ($LASTEXITCODE -ne 0) {
            throw 'Candidate ACR build failed. Inspect its existing run before retrying; no image descriptor was published.'
        }
        $run = $runText | ConvertFrom-Json
        if ($run.status -cne 'Succeeded' -or $run.runId -notmatch '^[a-zA-Z0-9-]{1,128}$' -or
            @($run.outputImages).Count -ne 1) {
            throw 'Candidate build did not return one successful, identifiable output image.'
        }
        $image = $run.outputImages[0]
        if ($image.repository -cne $Repository -or $image.tag -cne $Tag -or
            $image.registry -cne "$RegistryName.azurecr.io" -or $image.digest -cnotmatch '^sha256:[0-9a-f]{64}$') {
            throw 'ACR output image does not match the requested repository, tag, registry and immutable digest.'
        }
        $verified = & python $helper --verify-context $stage.directory --provenance-sha256 $stage.provenance_sha256
        if ($LASTEXITCODE -ne 0) { throw 'Candidate context changed during the build; no image descriptor was published.' }
        $report = [ordered] @{
            schema_version = '1.0'
            status = 'container-validated-unapproved-candidate'
            run_id = $stage.run_id
            dataset_version = $stage.dataset_version
            dataset_kind = $stage.dataset_kind
            logical_sha256 = $stage.logical_sha256
            frozen_identity = $stage.frozen_identity
            database = $stage.database
            candidate_sources = $stage.candidate_sources
            result_sha256 = $stage.result_sha256
            baseline_descriptor_sha256 = $stage.baseline_descriptor_sha256
            provenance_sha256 = $stage.provenance_sha256
            source_revision = $stage.source_revision
            image = [ordered] @{
                registry = $RegistryName; subscription = $SubscriptionId.ToString(); repository = $Repository
                tag = $Tag; digest = $image.digest; acr_run_id = $run.runId
                reference = "$RegistryName.azurecr.io/${Repository}@$($image.digest)"
                platform = 'linux/amd64'; target = 'candidate'
            }
            validation = $stage.validation_contract
            acceptance_purpose = $stage.acceptance_purpose
            human_approval = $false
            release_approved = $false
            deployed = $false
        }
        $descriptor = Join-Path $stage.directory 'candidate-image.json'
        $pending = Join-Path $stage.directory ('.image-' + [guid]::NewGuid().ToString('N') + '.json')
        try {
            $stream = [IO.File]::Open($pending, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
            try {
                $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($report | ConvertTo-Json -Depth 20) + "`n")
                $stream.Write($bytes, 0, $bytes.Length)
                $stream.Flush($true)
            }
            finally { $stream.Dispose() }
            [IO.File]::Move($pending, $descriptor, $false)
        }
        finally {
            if (Test-Path -LiteralPath $pending) { Remove-Item -LiteralPath $pending -Force }
        }
        [pscustomobject] @{
            Descriptor = $descriptor
            Image = $report.image.reference
            Digest = $image.digest
            AcrRunId = $run.runId
            RunId = $stage.run_id
            HumanApproval = $false
            ReleaseApproved = $false
            Deployed = $false
        }
    }
    finally {
        $env:TEMP = $previousTemp
        $env:TMP = $previousTmp
        if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive -Recurse -Force }
    }
}
finally { Pop-Location }
