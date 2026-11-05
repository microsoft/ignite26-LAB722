#requires -Version 7.2
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)] [string] $PrimaryDescriptorPath,
    [Parameter(Mandatory)] [ValidatePattern('^[0-9a-f]{64}$')] [string] $PrimaryDescriptorSha256,
    [guid] $SnapshotId = [guid]::Empty,
    [switch] $CatchUp,
    [switch] $AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:PortalWorkerRoot = Split-Path -Parent $PSScriptRoot

function Get-PortalPreparedPrimary {
    param([hashtable] $Options)
    $root = [IO.Path]::GetFullPath($script:PortalWorkerRoot).TrimEnd('\')
    $path = [IO.Path]::GetFullPath($Options.PrimaryDescriptorPath, $root)
    if (-not $path.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase) -or
        $Options.PrimaryDescriptorSha256 -cnotmatch '^[0-9a-f]{64}$' -or
        -not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw 'A pinned project-local prepared-primary descriptor is required.'
    }
    $bytes = [IO.File]::ReadAllBytes($path)
    if ([Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant() -cne
        $Options.PrimaryDescriptorSha256) {
        throw 'The prepared-primary descriptor changed. Do not register workspaces from edited metadata.'
    }
    $prepared = [Text.Encoding]::UTF8.GetString($bytes) | ConvertFrom-Json -AsHashtable
    if ($prepared -isnot [Collections.IDictionary] -or $prepared['schema_version'] -cne '1.0' -or
        $prepared['phase'] -cne 'primary-prepared' -or $prepared['mode'] -cne 'Provision' -or
        $prepared['scope'] -isnot [Collections.IDictionary] -or
        $prepared['frozen_identity'] -isnot [Collections.IDictionary] -or
        $prepared['workspace'] -cne '/opt/caldova-lab' -or $prepared['uid'] -ne 10001) {
        throw 'The descriptor does not identify a verified prepared primary.'
    }
    $scope = $prepared.scope
    $subscription = [guid]::Empty
    if (-not [guid]::TryParseExact([string] $scope['subscription'], 'D', [ref] $subscription) -or
        $subscription -eq [guid]::Empty -or
        $scope['resource_group'] -cnotmatch '^[A-Za-z0-9][A-Za-z0-9._()-]{0,89}$' -or
        $scope.resource_group.EndsWith('.') -or $scope['region'] -cnotmatch '^[a-z0-9]{1,30}$' -or
        $scope['group'] -cnotmatch '^[A-Za-z0-9][A-Za-z0-9._()-]{0,89}$' -or $scope.group.EndsWith('.')) {
        throw 'The prepared primary omits a valid explicit subscription, resource group, region or group.'
    }
    return @{ descriptor = $prepared; path = $path; subscription = $subscription }
}

function Invoke-ConnectLabWorkers {
    [CmdletBinding(SupportsShouldProcess)]
    param([hashtable] $Options)
    $record = Get-PortalPreparedPrimary $Options
    $prepared = $record.descriptor
    $path = $record.path
    $scope = $prepared.scope
    $subscription = $record.subscription
    if ($Options['CatchUp'] -and $Options['SnapshotId'] -and $Options.SnapshotId -ne [guid]::Empty) {
        throw 'CatchUp creates a replacement set; do not combine it with an existing SnapshotId.'
    }
    $primaryId = Assert-BaselineId @{ id = $prepared['primary_id'] }
    $diskId = Assert-BaselineId @{ id = $prepared['disk_id'] }
    $purpose = $prepared['acceptance_purpose']
    if ($purpose -cnotin @('synthetic-development', 'public-lab-development') -or
        $prepared['dataset_kind'] -cne $(if ($purpose -eq 'public-lab-development') {
            'reviewed-public'
        } else { 'synthetic-development' })) {
        throw 'The prepared primary has an unsupported dataset purpose.'
    }
    $expectedFields = @{
        ExpectedDatabaseSha256 = 'database_sha256'; ExpectedManifestSha256 = 'data_manifest_sha256'
        ExpectedBaselineSha256 = 'baseline_manifest_sha256'; ExpectedLogicalSha256 = 'logical_sha256'
    }
    if ($purpose -eq 'public-lab-development') {
        $expectedFields.ExpectedSourceRecordsSha256 = 'source_records_sha256'
        $expectedFields.ExpectedPipelineSourceSha256 = 'pipeline_source_sha256'
        $expectedFields.ExpectedSourceUseSha256 = 'source_use_sha256'
    }
    $baselineOptions = @{
        Mode = 'Reuse'; SubscriptionId = $subscription; ResourceGroup = $scope.resource_group
        Region = $scope.region; GroupName = $scope.group; Purpose = $purpose
        OutputDirectory = Join-Path (Split-Path -Parent $path) ('workers-' + [guid]::NewGuid().ToString('N'))
        DiskId = $diskId; PrimaryId = $primaryId; RequireStarters = $true
        AcaExecutable = 'aca'; AzExecutable = 'az'; PythonExecutable = 'python'
        OperationTimeoutSeconds = 900; CommandTimeoutSeconds = 60
    }
    foreach ($field in $expectedFields.Keys) {
        $hash = $prepared.frozen_identity[$expectedFields[$field]]
        if ($hash -cnotmatch '^[0-9a-f]{64}$') { throw 'A prepared-primary frozen identity checksum is missing.' }
        $baselineOptions[$field] = $hash
    }
    $action = if ($Options['CatchUp']) {
        'Create a replacement verified primary, snapshot and three clones; retain all attempted resources'
    } else { 'Verify and register the existing learner-created snapshot and three named clones; create no resources' }
    if (-not $PSCmdlet.ShouldProcess("$subscription/$($scope.resource_group)/$($scope.group)", $action)) { return }
    if ($Options['CatchUp']) {
        if ($env:AZURE_SUBSCRIPTION_ID -ine $subscription.ToString() -or
            $env:LAB_STARTUP_PURPOSE -cne $purpose -or
            $env:LAB_DATA_MANIFEST_SHA256 -cne $prepared.frozen_identity.data_manifest_sha256) {
            throw 'Catch-up requires the original allocated subscription, development purpose and manifest pin.'
        }
        $startup = Invoke-LabStartup -ResourceGroupName $scope.resource_group -Region $scope.region -Mode Prepare
        if (-not $startup.baseline_ready -or -not $startup.frozen_data_verified) {
            throw 'Catch-up did not produce a verified baseline; keep its diagnostics.'
        }
        $result = $startup.baseline
    }
    else {
        $snapshots = @()
        if ($Options['SnapshotId'] -and $Options.SnapshotId -ne [guid]::Empty) {
            $snapshots = @(@{ id = $Options.SnapshotId.ToString() })
        }
        else {
            $listed = ConvertFrom-BaselineNativeJson (Invoke-BaselineAca $baselineOptions @(
                'sandboxgroup', 'snapshot', 'list', '--group', $scope.group))
            if ($listed -is [Collections.IDictionary]) {
                if ($listed['nextLink'] -or -not $listed.Contains('value') -or
                    @($listed.Keys | Where-Object { $_ -notin @('value', 'nextLink') }).Count) {
                    throw 'Snapshot inventory is incomplete; specify the exact portal SnapshotId.'
                }
                $listed = $listed['value']
            }
            if ($listed -isnot [array] -or $listed.Count -gt 64) {
                throw 'Snapshot inventory is missing or too large; specify the exact portal SnapshotId.'
            }
            $snapshots = $listed
        }
        $matching = @()
        foreach ($snapshot in $snapshots) {
            $id = Assert-BaselineId $snapshot
            $metadata = ConvertFrom-BaselineNativeJson (Invoke-BaselineAca $baselineOptions @(
                'sandboxgroup', 'snapshot', 'get', '--group', $scope.group, '--id', $id.ToString()))
            [void] (Assert-BaselineId $metadata $id)
            if ([string] $metadata['sandboxId'] -ieq $primaryId.ToString()) { $matching += $id }
        }
        if ($matching.Count -ne 1) {
            throw 'Create exactly one snapshot of your prepared primary, or specify its exact SnapshotId. Nothing was created.'
        }
        $baselineOptions.SnapshotId = $matching[0]
        $inventory = Get-BaselineInventory $baselineOptions
        $roles = @{ 'clinical-trials' = 'ClinicalId'; 'drug-safety' = 'SafetyId'; 'quality-governance' = 'GovernanceId' }
        $workers = @{}
        foreach ($id in $inventory.ids) {
            $metadata = ConvertFrom-BaselineNativeJson (Invoke-BaselineAca $baselineOptions @(
                'sandbox', 'get', '--group', $scope.group, '--id', $id))
            [void] (Assert-BaselineId $metadata ([guid] $id))
            $source = $metadata['sourcesRef']
            $labels = $metadata['labels']
            if ($source -isnot [Collections.IDictionary] -or
                $source['snapshot'] -isnot [Collections.IDictionary] -or
                [string] $source.snapshot['id'] -ine $matching[0].ToString() -or
                $labels -isnot [Collections.IDictionary] -or
                [string] $labels['name'] -cnotin @($roles.Keys)) { continue }
            $role = [string] $labels['name']
            if ($workers.ContainsKey($role)) {
                throw "More than one clone from this snapshot is named '$role'. No ambiguous binding was published."
            }
            $workers[$role] = [guid] $id
        }
        foreach ($role in $roles.Keys) {
            if (-not $workers.ContainsKey($role)) {
                throw "Create a clone from your snapshot with Name label '$role'. Nothing was created."
            }
            $baselineOptions[$roles[$role]] = $workers[$role]
        }
        [Console]::Error.WriteLine('Verifying portal-created clone lineage, starter code, frozen data, UID and reviewed policies.')
        $result = Invoke-PrepareWorkerBaseline -Options $baselineOptions
    }
    $result['descriptor_sha256'] = (
        Get-FileHash -LiteralPath $result.descriptor -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    return $result
}

if ($MyInvocation.InvocationName -ne '.') {
    $options = @{
        PrimaryDescriptorPath = $PrimaryDescriptorPath; PrimaryDescriptorSha256 = $PrimaryDescriptorSha256
        SnapshotId = $SnapshotId; CatchUp = $CatchUp
    }
    $jsonOutput = $AsJson
    $whatIf = $WhatIfPreference
    $primaryRecord = Get-PortalPreparedPrimary $options
    $prepared = $primaryRecord.descriptor
    . (Join-Path $PSScriptRoot 'prepare-worker-baseline.ps1') -Mode Reuse `
        -SubscriptionId $prepared.scope.subscription -ResourceGroup $prepared.scope.resource_group `
        -Region $prepared.scope.region -GroupName $prepared.scope.group `
        -OutputDirectory (Join-Path (Split-Path -Parent $primaryRecord.path) 'workers')
    if ($options.CatchUp) {
        . (Join-Path $PSScriptRoot 'start-lab.ps1') `
            -ResourceGroupName $prepared.scope.resource_group -Region $prepared.scope.region -Mode Prepare
    }
    $result = Invoke-ConnectLabWorkers -Options $options -WhatIf:$whatIf
    if ($jsonOutput -and $null -ne $result) { ConvertTo-Json -InputObject $result -Depth 6 -Compress }
    elseif ($null -ne $result) { $result }
}
