[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Split-Path -Parent $PSScriptRoot
$workspace = Join-Path $root ('.validation-workspaces\prepare-' + [guid]::NewGuid().ToString('N'))
[void] [IO.Directory]::CreateDirectory($workspace)
$script:passed = 0
$script:disk = [guid] '10000000-0000-0000-0000-000000000001'
$script:primary = [guid] '10000000-0000-0000-0000-000000000002'
$script:snapshot = [guid] '10000000-0000-0000-0000-000000000003'
$script:clinical = [guid] '10000000-0000-0000-0000-000000000004'
$script:safety = [guid] '10000000-0000-0000-0000-000000000005'
$script:governance = [guid] '10000000-0000-0000-0000-000000000006'
$script:other = [guid] '30000000-0000-0000-0000-000000000001'
$script:subscription = [guid] '40000000-0000-0000-0000-000000000001'
$script:baselineText = '{"source_revision":"stub-source","protected_files":{},"toolchains":{"python":"3.13.16","node":"v24.21.0"}}' + "`n"
$script:manifestText = '{"schema_version":"1.0","dataset_version":"stub-synthetic-v1","dataset_kind":"synthetic-development"}' + "`n"

function Get-TestHash([string] $Text) {
    return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData(
        [Text.Encoding]::UTF8.GetBytes($Text))).ToLowerInvariant()
}

function Assert-Test([bool] $Condition, [string] $Message) {
    if (-not $Condition) { throw $Message }
}

function New-TestOptions([string] $Name, [string] $Mode = 'Reuse') {
    return @{
        Mode = $Mode; SubscriptionId = $script:subscription; ResourceGroup = 'stub-resource-group'
        Region = 'westus3'; GroupName = 'stub-sandboxes'; OutputDirectory = Join-Path $workspace $Name
        AuthorizeProvisioning = $false; SourceContextDirectory = Join-Path $workspace "$Name-source"
        FrozenManifest = $null; FrozenManifestSha256 = $null
        Purpose = 'synthetic-development'
        DiskId = $script:disk; PrimaryId = $script:primary; SnapshotId = $script:snapshot
        ClinicalId = $script:clinical; SafetyId = $script:safety; GovernanceId = $script:governance
        ExpectedDatabaseSha256 = ('b' * 64); ExpectedManifestSha256 = Get-TestHash $script:manifestText
        ExpectedBaselineSha256 = Get-TestHash $script:baselineText; ExpectedLogicalSha256 = ('a' * 64)
        ExpectedSourceRecordsSha256 = ('d' * 64); ExpectedPipelineSourceSha256 = ('e' * 64)
        ExpectedSourceUseSha256 = ('f' * 64)
        AcaExecutable = 'aca-stub'; AzExecutable = 'az-stub'; PythonExecutable = 'python-stub'
        OperationTimeoutSeconds = 900; CommandTimeoutSeconds = 60
    }
}

$load = New-TestOptions 'load'
. (Join-Path $root 'scripts\prepare-worker-baseline.ps1') `
    -Mode Reuse -SubscriptionId $load.SubscriptionId -ResourceGroup $load.ResourceGroup `
    -Region $load.Region -GroupName $load.GroupName -OutputDirectory $load.OutputDirectory
$nativeRunner = ${function:Invoke-BaselineNative}
. (Join-Path $root 'scripts\connect-lab-workers.ps1') `
    -PrimaryDescriptorPath (Join-Path $workspace 'not-loaded.json') -PrimaryDescriptorSha256 ('a' * 64)

function Reset-TestNative([string] $Mode = 'Reuse', [string] $Fault = '') {
    $script:calls = [Collections.Generic.List[object]]::new()
    $script:fault = $Fault
    $script:inventory = [Collections.Generic.List[object]]::new()
    foreach ($index in 1..5) {
        $script:inventory.Add(@{ id = ('20000000-0000-0000-0000-{0:000000000000}' -f $index) })
    }
    if ($Mode -eq 'Reuse') {
        foreach ($id in @($script:primary, $script:clinical, $script:safety, $script:governance)) {
            $script:inventory.Add(@{ id = $id.ToString() })
        }
        if ($Fault -eq 'EmptyInventory') { $script:inventory.Clear() }
    }
    $script:created = 0
}

function Get-TestArgument([string[]] $Arguments, [string] $Flag) {
    $index = [array]::IndexOf($Arguments, $Flag)
    Assert-Test ($index -ge 0 -and $index + 1 -lt $Arguments.Count) "Missing native argument: $Flag"
    return $Arguments[$index + 1]
}

function New-TestManualPrimaryOptions([string] $Name, [switch] $Public) {
    $options = New-TestOptions $Name 'VerifyPrimary'
    foreach ($key in @('SnapshotId', 'ClinicalId', 'SafetyId', 'GovernanceId')) { $options[$key] = [guid]::Empty }
    $options.FrozenManifest = Join-Path $workspace "$Name-manifest.json"
    [IO.File]::WriteAllText($options.FrozenManifest, $script:manifestText, [Text.UTF8Encoding]::new($false))
    $options.FrozenManifestSha256 = Get-TestHash $script:manifestText
    [void] [IO.Directory]::CreateDirectory($options.SourceContextDirectory)
    [IO.File]::WriteAllText((Join-Path $options.SourceContextDirectory 'Dockerfile'), 'FROM scratch')
    $frozen = @{
        dataset_kind = 'synthetic-development'; database_sha256 = 'b' * 64
        data_manifest_sha256 = $options.FrozenManifestSha256; logical_sha256 = 'a' * 64
    }
    if ($Public) {
        $options.Purpose = 'public-lab-development'
        $frozen.dataset_kind = 'reviewed-public'
        $frozen.acceptance_purpose = $options.Purpose
        $frozen.source_records_sha256 = 'd' * 64
        $frozen.pipeline_source_sha256 = 'e' * 64
        $frozen.source_use_sha256 = 'f' * 64
    }
    $record = @{
        schema_version = '1.0'; source_revision = 'stub-source'; frozen_data = $frozen
        files = @{ Dockerfile = Get-TestHash 'FROM scratch' }
    } | ConvertTo-Json -Depth 6
    [IO.File]::WriteAllText((Join-Path $options.SourceContextDirectory 'source-context.json'),
        $record, [Text.UTF8Encoding]::new($false))
    $options.SourceContextManifestSha256 = Get-TestHash $record
    return $options
}

function Get-TestMetadata([guid] $Id) {
    $name = switch ($Id) {
        $script:clinical { 'clinical-trials' }
        $script:safety { 'drug-safety' }
        $script:governance { 'quality-governance' }
        default { 'unrelated' }
    }
    $metadata = @{
        id = $Id.ToString(); snapshotId = $script:snapshot.ToString()
        labels = @{ name = $name }
        sourcesRef = @{ snapshot = @{ id = $script:snapshot.ToString() } }
        egressPolicy = @{ defaultAction = 'Deny'; trafficInspection = 'Full'; rules = @(
            @{ name = 'reviewed'; match = @{ host = 'open.fda.gov' }; action = @{ type = 'Allow' } }) }
        lifecycle = @{
            autoSuspendPolicy = @{ enabled = $true; interval = 900; mode = 'Memory' }
            autoDeletePolicy = @{ enabled = $false }
        }
    }
    switch ($script:fault) {
        'MissingId' { $metadata.Remove('id') }
        'WrongId' { $metadata.id = $script:other.ToString() }
        'WrongLineage' { $metadata.sourcesRef.snapshot.id = $script:other.ToString() }
        'MissingLineage' { $metadata.Remove('sourcesRef') }
        'DuplicateWorkerName' { if ($Id -eq $script:governance) { $metadata.labels.name = 'clinical-trials' } }
        'MissingWorkerName' { if ($Id -eq $script:governance) { $metadata.labels.name = 'wrong-role' } }
        'BroadEgress' { $metadata.egressPolicy.rules[0].match.host = '*.fda.gov' }
        'AutoDelete' { $metadata.lifecycle.autoDeletePolicy.enabled = $true }
        'DiskSuspend' { $metadata.lifecycle.autoSuspendPolicy.mode = 'Disk' }
        'DocumentedSuspendMode' {
            $metadata.lifecycle.autoSuspendPolicy.Remove('mode')
            $metadata.lifecycle.autoSuspendPolicy.suspendMode = 'Memory'
        }
    }
    return $metadata
}

function Invoke-BaselineNative {
    param([string] $Executable, [string[]] $Arguments, [int] $TimeoutSeconds)
    $Executable = switch ($Executable) {
        'aca' { 'aca-stub' }; 'az' { 'az-stub' }; 'python' { 'python-stub' }; default { $Executable }
    }
    $script:calls.Add(@{ executable = $Executable; arguments = $Arguments; timeout = $TimeoutSeconds })
    if ($Executable -eq 'python-stub') {
        Assert-Test ($script:calls[$script:calls.Count - 2].executable -eq 'az-stub') 'Source export preceded the ARM capacity check.'
        $destination = Get-TestArgument $Arguments '--destination'
        [void] [IO.Directory]::CreateDirectory($destination)
        [IO.File]::WriteAllText((Join-Path $destination 'Dockerfile'), 'FROM scratch')
        $record = '{"schema_version":"1.0","source_revision":"stub-source","files":{}}'
        [IO.File]::WriteAllText((Join-Path $destination 'source-context.json'), $record, [Text.UTF8Encoding]::new($false))
        $result = @{ directory = $destination; source_revision = 'stub-source'; files = 1;
            source_context_manifest_sha256 = Get-TestHash $record }
        if ($Arguments -contains '--manifest') {
            Assert-Test ((Get-TestArgument $Arguments '--manifest') -eq 'stub-frozen-manifest.json') 'Pinned manifest was not passed to source export.'
            Assert-Test ((Get-TestArgument $Arguments '--manifest-sha256') -eq (Get-TestHash $script:manifestText)) 'Manifest trust anchor changed during export.'
            $result.frozen_data = @{
                dataset_kind = 'synthetic-development'; database_sha256 = ('b' * 64)
                data_manifest_sha256 = Get-TestHash $script:manifestText; logical_sha256 = ('a' * 64)
            }
            if ((Get-TestArgument $Arguments '--purpose') -ceq 'public-lab-development') {
                $result.frozen_data.dataset_kind = 'reviewed-public'
                $result.frozen_data.acceptance_purpose = 'public-lab-development'
                $result.frozen_data.source_records_sha256 = 'd' * 64
                $result.frozen_data.pipeline_source_sha256 = 'e' * 64
                $result.frozen_data.source_use_sha256 = 'f' * 64
            }
            if ($script:fault -eq 'FrozenAnchorMismatch') { $result.frozen_data.data_manifest_sha256 = 'c' * 64 }
        }
        $json = $result | ConvertTo-Json -Depth 6
        return @{ exit_code = 0; stdout = $json; stderr = '' }
    }
    if ($Executable -eq 'az-stub') {
        $expectedId = "/subscriptions/$script:subscription/resourceGroups/stub-resource-group/providers/Microsoft.App/sandboxGroups/stub-sandboxes"
        Assert-Test ($Arguments[0] -eq 'rest' -and (Get-TestArgument $Arguments '--method') -eq 'get') 'Capacity lookup was not read-only az rest.'
        Assert-Test ((Get-TestArgument $Arguments '--url') -ceq "https://management.azure.com${expectedId}?api-version=2026-02-01-preview") 'ARM scope or API version drift.'
        Assert-Test ((Get-TestArgument $Arguments '--subscription') -eq $script:subscription.ToString()) 'ARM subscription drift.'
        Assert-Test ((Get-TestArgument $Arguments '--query') -ceq '{id:id,maxSandboxCount:properties.maxSandboxCount,provisioningState:properties.provisioningState}') 'Capacity lookup unexpectedly returned unbounded metadata.'
        Assert-Test ((Get-TestArgument $Arguments '--output') -eq 'json' -and $Arguments -contains '--only-show-errors') 'ARM output/logging was not explicit.'
        Assert-Test ($TimeoutSeconds -eq 60) 'ARM capacity lookup is unbounded.'
        Assert-Test (-not @($Arguments | Where-Object {
            $_ -in @('--headers', '--token', '--credential', '--debug', '--verbose', 'delete', 'put', 'post', 'patch')
        }).Count) 'Credentials, broad logging or mutation appeared in ARM argv.'
        $resource = @{ id = $expectedId; maxSandboxCount = 9; provisioningState = 'Succeeded' }
        switch ($script:fault) {
            'MissingArmCapacity' { $resource.Remove('maxSandboxCount') }
            'StringArmCapacity' { $resource.maxSandboxCount = '9' }
            'ZeroArmCapacity' { $resource.maxSandboxCount = 0 }
            'WrongArmIdentity' { $resource.id += '-other' }
            'ArmNotReady' { $resource.provisioningState = 'Updating' }
            'ShrinkingArmCapacity' {
                if ($script:created -gt 0) { $resource.maxSandboxCount = $script:inventory.Count }
            }
            'AzCapacityFailure' { return @{ exit_code = 1; stdout = ''; stderr = 'untrusted diagnostic must not be logged' } }
        }
        $json = $resource | ConvertTo-Json
        if ($script:fault -eq 'MalformedArmCapacity') { $json = 'capacity metadata unavailable' }
        return @{ exit_code = 0; stdout = $json; stderr = '' }
    }
    Assert-Test ($Executable -eq 'aca-stub') 'Unexpected executable; tests must never invoke a live ACA CLI.'
    Assert-Test ((Get-TestArgument $Arguments '--subscription') -eq $script:subscription.ToString()) 'Subscription drift.'
    Assert-Test ((Get-TestArgument $Arguments '--resource-group') -eq 'stub-resource-group') 'Resource-group drift.'
    Assert-Test ((Get-TestArgument $Arguments '--region') -eq 'westus3') 'Region drift.'
    $expectedFormat = if ($Arguments[0] -eq 'sandbox' -and $Arguments[1] -eq 'exec') { 'table' } else { 'json' }
    Assert-Test ((Get-TestArgument $Arguments '--output') -eq $expectedFormat) 'Metadata JSON or raw remote output format was not explicit.'
    Assert-Test (-not @($Arguments | Where-Object {
        $_ -in @('--token', '--username', '--credential', '--debug', '--verbose', '--image', 'delete', 'resume')
    }).Count) 'Credentials, broad logging, cleanup, or implicit resume appeared in native argv.'
    $verb = $Arguments[0..([Math]::Min(2, $Arguments.Count - 1))] -join ' '
    if ($Arguments[0] -eq 'sandboxgroup' -and $Arguments[1] -eq 'get') {
        Assert-Test ((Get-TestArgument $Arguments '--name') -eq 'stub-sandboxes') 'Group-name drift.'
        # Native group get returns endpoint/state, not allocation capacity.
        $group = @{ id = "/subscriptions/$script:subscription/resourceGroups/stub-resource-group/providers/Microsoft.App/sandboxGroups/stub-sandboxes";
            name = 'stub-sandboxes'; location = 'westus3'; tags = @{ lab = 'LAB722' }
            properties = @{ managementEndpoint = 'https://stub-sandboxes.example.invalid'; provisioningState = 'Succeeded' } }
        if ($script:fault -eq 'WrongScope') { $group.location = 'eastus2' }
        if ($script:fault -eq 'MisleadingNativeCapacity') { $group.properties.maxSandboxCount = 999 }
        return @{ exit_code = 0; stdout = ($group | ConvertTo-Json -Depth 8); stderr = '' }
    }
    Assert-Test ((Get-TestArgument $Arguments '--group') -eq 'stub-sandboxes') 'Sandbox-group drift.'
    if ($Arguments[0] -eq 'sandbox' -and $Arguments[1] -eq 'list') {
        $value = $script:inventory.ToArray()
        if ($script:fault -eq 'MissingInventory') { $value = @($value | Where-Object { $_.id -ne $script:clinical.ToString() }) }
        $json = ConvertTo-Json -InputObject @{ value = $value; nextLink = $null } -Depth 6
        if ($script:fault -in @('ArrayInventory', 'EmptyInventory')) {
            $json = ConvertTo-Json -InputObject $value -Depth 6
        }
    }
    elseif ($verb -eq 'sandboxgroup disk create') {
        Assert-Test ((Get-TestArgument $Arguments '--wait-timeout') -eq '900' -and $TimeoutSeconds -eq 930) 'Import wait is unbounded.'
        Assert-Test (Test-Path -LiteralPath (Join-Path (Get-TestArgument $Arguments '--source') 'Dockerfile')) 'Missing source Dockerfile.'
        $script:diskName = Get-TestArgument $Arguments '--name'
        if ($script:fault -eq 'ImportFailure') {
            return @{ exit_code = 1; stdout = ''; stderr = 'untrusted import diagnostic must not be logged' }
        }
        $json = "Uploading source...`n" + (@{ id = $script:disk.ToString(); status = @{ state = 'Ready' } } | ConvertTo-Json -Depth 4)
        if ($script:fault -eq 'ImportBuildJson') {
            $json = '{"build":{"id":"untrusted-progress"}}' + "`n" + $json
        }
    }
    elseif ($verb -eq 'sandboxgroup disk list') {
        Assert-Test ((Get-TestArgument $Arguments '--selector') -ceq "name=$script:diskName") 'Imported disk lookup is not bound to its unique name.'
        $disks = @(@{ id = $script:disk.ToString(); name = $script:diskName; labels = @{ name = $script:diskName } })
        if ($script:fault -eq 'ImportWrongName') { $disks[0].name = 'another-disk' }
        if ($script:fault -eq 'ImportDuplicate') { $disks += $disks[0] }
        $json = ConvertTo-Json -InputObject $disks -Depth 4
    }
    elseif ($verb -eq 'sandboxgroup disk get') {
        $id = Get-TestArgument $Arguments '--id'
        $disk = @{
            id = $id; name = 'caldova-prepared-20261009'; image = @{ base = '' }
            status = @{
                state = 'Ready'; errorMessage = ''
                createdAt = '2026-10-09T22:06:43.2732307+00:00'
                updatedAt = '2026-10-09T22:06:47.4928386+00:00'
            }
        }
        switch ($script:fault) {
            'MissingDiskStatus' { $disk.Remove('status') }
            'MissingDiskState' { $disk.status.Remove('state') }
            'DiskNotReady' { $disk.status.state = 'Failed' }
            'FlatDiskStatus' { $disk.status = 'Ready' }
        }
        $json = $disk | ConvertTo-Json -Depth 4
    }
    elseif ($Arguments[0] -eq 'sandbox' -and $Arguments[1] -eq 'create') {
        Assert-Test ($script:calls[$script:calls.Count - 2].executable -eq 'az-stub') 'Allocation preceded the latest ARM capacity check.'
        Assert-Test ((Get-TestArgument $Arguments '--wait-timeout') -eq '900' -and $TimeoutSeconds -eq 930) 'Create wait is unbounded.'
        Assert-Test ((Get-TestArgument $Arguments '--egress-default') -eq 'Deny') 'New Sandbox lacks default Deny.'
        Assert-Test ((Get-TestArgument $Arguments '--egress-rule') -eq 'open.fda.gov:Allow') 'New Sandbox lacks the exact reviewed host.'
        Assert-Test ((Get-TestArgument $Arguments '--traffic-inspection') -eq 'Full') 'New Sandbox lacks Full inspection.'
        $id = @($script:primary, $script:clinical, $script:safety, $script:governance)[$script:created]
        if ($script:created -eq 0) {
            Assert-Test ((Get-TestArgument $Arguments '--disk-id') -eq $script:disk.ToString()) 'Primary disk mismatch.'
            Assert-Test ((Get-TestArgument $Arguments '--cpu') -eq '2000m' -and
                (Get-TestArgument $Arguments '--memory') -eq '4096Mi') 'Primary resource requests changed.'
        }
        else {
            Assert-Test ((Get-TestArgument $Arguments '--snapshot-id') -eq $script:snapshot.ToString()) 'Clone source mismatch.'
            Assert-Test ('--cpu' -notin $Arguments -and '--memory' -notin $Arguments -and
                '--disk-size' -notin $Arguments) 'Snapshot clones must inherit resources without create-time overrides.'
        }
        $script:created++
        $script:inventory.Add(@{ id = $id.ToString() })
        $json = "Created sandbox: $script:other`n" + (@{ id = $id.ToString(); note = 'JSON {identity} wins over progress.' } | ConvertTo-Json)
        if ($script:fault -eq 'MissingCreateId') { $json = "Created sandbox: $id`n" + '{"status":"Ready"}' }
        if ($script:fault -eq 'ProgressOnly') { $json = "Created sandbox: $id`n" }
    }
    elseif ($Arguments[0] -eq 'sandbox' -and $Arguments[1] -eq 'snapshot') {
        Assert-Test ((Get-TestArgument $Arguments '--wait-timeout') -eq '900' -and $TimeoutSeconds -eq 930) 'Snapshot wait is unbounded.'
        Assert-Test ((Get-TestArgument $Arguments '--id') -eq $script:primary.ToString()) 'Snapshot primary mismatch.'
        $json = "Snapshot operation: $script:other`n" +
            (@{ id = $script:snapshot.ToString(); sandboxId = $script:primary.ToString() } | ConvertTo-Json)
    }
    elseif ($verb -eq 'sandboxgroup snapshot list') {
        $snapshots = @(@{ id = $script:snapshot.ToString() })
        if ($script:fault -eq 'DuplicateSnapshots') { $snapshots += $snapshots[0] }
        $json = ConvertTo-Json -InputObject $snapshots
    }
    elseif ($verb -eq 'sandboxgroup snapshot get') {
        $parent = $script:primary.ToString()
        if ($script:fault -eq 'WrongSnapshotParent') { $parent = $script:other.ToString() }
        $json = @{ id = $script:snapshot.ToString(); sandboxId = $parent } | ConvertTo-Json
    }
    elseif ($verb -eq 'sandbox lifecycle set') {
        Assert-Test ((Get-TestArgument $Arguments '--auto-suspend') -eq 'enable') 'Missing auto-suspend.'
        Assert-Test ((Get-TestArgument $Arguments '--idle-timeout-seconds') -eq '900') 'Idle interval drift.'
        Assert-Test ((Get-TestArgument $Arguments '--mode') -eq 'Memory') 'Suspend-mode drift.'
        Assert-Test ((Get-TestArgument $Arguments '--auto-delete') -eq 'disable') 'Automatic deletion was not explicitly disabled.'
        $json = '{}'
    }
    elseif ($Arguments[0] -eq 'sandbox' -and $Arguments[1] -eq 'get') {
        $json = Get-TestMetadata ([guid] (Get-TestArgument $Arguments '--id')) | ConvertTo-Json -Depth 10
    }
    elseif ($Arguments[0] -eq 'sandbox' -and $Arguments[1] -eq 'exec') {
        Assert-Test ((Get-TestArgument $Arguments '--working-directory') -eq '/opt/caldova-lab') 'Workspace drift.'
        Assert-Test ($TimeoutSeconds -eq 60) 'Remote verification is unbounded.'
        $command = Get-TestArgument $Arguments '--command'
        Assert-Test ($command.Contains('python -I -B -c')) 'Frozen verification must isolate Python environment and bytecode writes.'
        $payloadMarker = [regex]::Match($command, 'CALDOVA_FROZEN_[0-9a-f]{32}=').Value
        $statusMarker = [regex]::Match($command, 'CALDOVA_STATUS_[0-9a-f]{32}=').Value
        Assert-Test ($payloadMarker -and $statusMarker) 'The remote command lacks nonce-bound receipts.'
        $receipt = @{
            uid = 10001; workspace = '/opt/caldova-lab'; dataset_kind = 'synthetic-development'
            dataset_version = 'stub-synthetic-v1'; source_revision = 'stub-source'; logical_sha256 = ('a' * 64)
            database_sha256 = ('b' * 64); data_manifest_sha256 = Get-TestHash $script:manifestText
            baseline_manifest_sha256 = Get-TestHash $script:baselineText; frontend_assets = 2
            starters_checked = $command.Contains('REQUIRE_STARTERS = True')
            data_manifest_json = $script:manifestText; prepared_baseline_json = $script:baselineText
            toolchains = @{ python = '3.13.16'; node = 'v24.21.0' }
        }
        if ([regex]::IsMatch($command, 'PURPOSE = [^\r\n]{0,80}public-lab-development')) {
            Assert-Test ($command.Contains('baseline.check_data_contract()') -and
                $command.Contains('record["public_identity"]')) 'Public remote source-use/identity verification is missing.'
            $receipt.dataset_kind = 'reviewed-public'
            $receipt.acceptance_purpose = 'public-lab-development'
            $receipt.source_records_sha256 = 'd' * 64
            $receipt.pipeline_source_sha256 = 'e' * 64
            $receipt.source_use_sha256 = 'f' * 64
            switch ($script:fault) {
                'PublicOriginalMismatch' { $receipt.source_records_sha256 = 'c' * 64 }
                'PublicZipMismatch' { $receipt.pipeline_source_sha256 = 'c' * 64 }
                'PublicDecisionMismatch' { $receipt.source_use_sha256 = 'c' * 64 }
                'PublicPurposeMismatch' { $receipt.acceptance_purpose = 'synthetic-development' }
                'PublicCloneMismatch' {
                    if ((Get-TestArgument $Arguments '--id') -ceq $script:governance.ToString()) {
                        $receipt.source_records_sha256 = 'c' * 64
                    }
                }
            }
        }
        if ($script:fault -in @('WrongFrozenData', 'FrozenPrimaryMismatch')) { $receipt.database_sha256 = ('c' * 64) }
        if ($script:fault -eq 'WrongSourceRevision') { $receipt.source_revision = 'another-source' }
        if ($script:fault -eq 'RootUser') { $receipt.uid = 0 }
        $status = if ($script:fault -eq 'RemoteFailure') { '7' } else { '0' }
        $json = "Native progress...`n" + $payloadMarker +
            (ConvertTo-Json -InputObject $receipt -Depth 6 -Compress) + "`n" + $statusMarker + $status + "`n"
        if ($script:fault -eq 'MissingRemoteStatus') {
            $json = $payloadMarker + (ConvertTo-Json -InputObject $receipt -Depth 6 -Compress) + "`n"
        }
    }
    else { throw "Unexpected stub-native operation: $verb" }
    return @{ exit_code = 0; stdout = $json; stderr = '' }
}

function Invoke-Test([string] $Name, [scriptblock] $Body) {
    & $Body
    $script:passed++
    Write-Host "PASS $Name"
}

function Assert-PreparationFails([hashtable] $Options) {
    $caught = $false
    try { Invoke-PrepareWorkerBaseline -Options $Options | Out-Null }
    catch { $caught = $true }
    Assert-Test $caught 'Preparation unexpectedly succeeded.'
    Assert-Test (-not (Test-Path -LiteralPath $Options.OutputDirectory)) 'Failure published controller artifacts.'
}

try {
    Invoke-Test 'manual preflight only reads scope inventory and four-slot capacity' {
        Reset-TestNative 'Provision'
        $options = New-TestOptions 'manual-preflight' 'CheckCapacity'
        $result = Invoke-PrepareWorkerBaseline -Options $options
        Assert-Test ($result.capacity -eq 9 -and $result.allocated -eq 5 -and $script:calls.Count -eq 3 -and
            $script:created -eq 0 -and -not (Test-Path -LiteralPath $options.OutputDirectory) -and
            -not (Test-Path -LiteralPath $options.SourceContextDirectory)) 'Preflight allocated, exported or published artifacts.'
    }
    foreach ($public in @($false, $true)) {
        Invoke-Test "manual primary verifies and exports a compatible handoff without cloud mutation: public=$public" {
            Reset-TestNative
            $options = New-TestManualPrimaryOptions "manual-primary-$public" -Public:$public
            $result = Invoke-PrepareWorkerBaseline -Options $options
            $descriptor = Get-Content -LiteralPath $result.descriptor -Raw | ConvertFrom-Json
            Assert-Test ($descriptor.phase -ceq 'primary-prepared' -and $descriptor.mode -ceq 'Provision' -and
                $descriptor.source_context.source_context_manifest_sha256 -ceq $options.SourceContextManifestSha256 -and
                $result.descriptor_sha256 -ceq (Get-TestHash ([IO.File]::ReadAllText($result.descriptor)))) 'Manual handoff lost its original-byte pins.'
            Assert-Test ($script:created -eq 0 -and -not @($script:calls | Where-Object {
                $_.arguments -contains 'create' -or $_.arguments -contains 'set' -or
                $_.executable -in @('python-stub', 'az-stub') -or
                ($_.arguments[0] -eq 'sandbox' -and $_.arguments[1] -eq 'snapshot')
            }).Count) 'VerifyPrimary mutated resources, imported source or queried allocation capacity.'
            $checks = @($script:calls | Where-Object { $_.arguments[1] -eq 'exec' })
            Assert-Test ($checks.Count -eq 1 -and
                (Get-TestArgument $checks[0].arguments '--command').Contains('REQUIRE_STARTERS = True')) 'Manual verification did not require genuinely missing starter functions.'
            $registered = Invoke-ConnectLabWorkers -Options @{
                PrimaryDescriptorPath = $result.descriptor; PrimaryDescriptorSha256 = $result.descriptor_sha256
            }
            Assert-Test ((Test-Path -LiteralPath $registered.bindings) -and $script:created -eq 0) 'Manual handoff could not register existing portal clones.'
        }
    }
    foreach ($sourceFault in @('ManifestHash', 'SourceFile', 'ExtraFile', 'FrozenManifest')) {
        Invoke-Test "changed manual source is rejected before Azure: $sourceFault" {
            Reset-TestNative
            $options = New-TestManualPrimaryOptions "manual-source-$sourceFault"
            switch ($sourceFault) {
                'ManifestHash' { $options.SourceContextManifestSha256 = '0' * 64 }
                'SourceFile' { [IO.File]::WriteAllText((Join-Path $options.SourceContextDirectory 'Dockerfile'), 'changed') }
                'ExtraFile' { [IO.File]::WriteAllText((Join-Path $options.SourceContextDirectory 'extra.txt'), 'unexpected') }
                'FrozenManifest' { [IO.File]::WriteAllText($options.FrozenManifest, '{}') }
            }
            Assert-PreparationFails $options
            Assert-Test ($script:calls.Count -eq 0) 'Changed manual source reached Azure.'
        }
    }
    foreach ($fault in @('WrongFrozenData', 'WrongSourceRevision', 'BroadEgress', 'RootUser', 'DiskNotReady')) {
        Invoke-Test "manual primary rejects an invalid existing workspace: $fault" {
            Reset-TestNative 'Reuse' $fault
            $options = New-TestManualPrimaryOptions "manual-invalid-$fault" -Public
            Assert-PreparationFails $options
            Assert-Test ($script:created -eq 0 -and -not @($script:calls | Where-Object {
                $_.arguments -contains 'create' -or $_.arguments -contains 'set'
            }).Count) 'Manual verification tried to repair or replace invalid resources.'
        }
    }
    Invoke-Test 'primary-only preparation leaves snapshot and clones to the learner' {
        Reset-TestNative 'Provision'
        $options = New-TestOptions 'portal-primary' 'Provision'
        $options.AuthorizeProvisioning = $true
        $options.PrimaryOnly = $true
        foreach ($key in @('DiskId', 'PrimaryId', 'SnapshotId', 'ClinicalId', 'SafetyId', 'GovernanceId')) {
            $options[$key] = [guid]::Empty
        }
        $script:preparedPrimary = Invoke-PrepareWorkerBaseline -Options $options
        $descriptor = Get-Content -LiteralPath $script:preparedPrimary.descriptor -Raw | ConvertFrom-Json
        Assert-Test ($script:created -eq 1 -and $descriptor.phase -ceq 'primary-prepared' -and
            $script:preparedPrimary.descriptor_sha256 -ceq (Get-TestHash (
                [IO.File]::ReadAllText($script:preparedPrimary.descriptor)))) 'Primary-only preparation lost its phase or byte pin.'
        Assert-Test (-not (Test-Path (Join-Path $options.OutputDirectory 'bindings.json')) -and
            -not @($script:calls | Where-Object {
                $_.arguments[0] -eq 'sandbox' -and $_.arguments[1] -eq 'snapshot'
            }).Count) 'Primary-only preparation created a snapshot or published worker bindings.'
    }
    Invoke-Test 'portal registration verifies the existing workers without creating or changing resources' {
        Reset-TestNative
        $result = Invoke-ConnectLabWorkers -Options @{
            PrimaryDescriptorPath = $script:preparedPrimary.descriptor
            PrimaryDescriptorSha256 = $script:preparedPrimary.descriptor_sha256
        }
        $descriptor = Get-Content -LiteralPath $result.descriptor -Raw | ConvertFrom-Json
        Assert-Test ($descriptor.mode -ceq 'Reuse' -and $descriptor.bindings.Count -eq 3 -and
            $result.descriptor_sha256 -ceq (Get-TestHash ([IO.File]::ReadAllText($result.descriptor)))) 'Portal registration did not return a pinned reusable baseline.'
        Assert-Test ($script:created -eq 0 -and -not @($script:calls | Where-Object {
            $_.arguments -contains 'create' -or $_.arguments -contains 'set' -or
            ($_.arguments[0] -eq 'sandbox' -and $_.arguments[1] -eq 'snapshot')
        }).Count) 'Default portal registration mutated resources.'
        $checks = @($script:calls | Where-Object {
            $_.arguments[0] -eq 'sandbox' -and $_.arguments[1] -eq 'exec'
        })
        Assert-Test ($checks.Count -eq 4 -and @($checks | Where-Object {
            -not (Get-TestArgument $_.arguments '--command').Contains('REQUIRE_STARTERS = True')
        }).Count -eq 0) 'All four portal workspaces must retain genuinely missing functions.'
    }
    foreach ($fault in @('WrongSnapshotParent', 'DuplicateSnapshots', 'WrongLineage', 'DuplicateWorkerName',
        'MissingWorkerName', 'BroadEgress', 'AutoDelete', 'RootUser', 'WrongFrozenData')) {
        Invoke-Test "portal registration refuses invalid learner resources: $fault" {
            Reset-TestNative 'Reuse' $fault
            $caught = $false
            $parent = Split-Path -Parent $script:preparedPrimary.descriptor
            $before = @(Get-ChildItem -LiteralPath $parent -Directory).Count
            try {
                Invoke-ConnectLabWorkers -Options @{
                    PrimaryDescriptorPath = $script:preparedPrimary.descriptor
                    PrimaryDescriptorSha256 = $script:preparedPrimary.descriptor_sha256
                } | Out-Null
            } catch { $caught = $true }
            Assert-Test ($caught -and $script:created -eq 0 -and
                @(Get-ChildItem -LiteralPath $parent -Directory).Count -eq $before) 'Invalid portal resources published bindings or triggered fallback creation.'
        }
    }
    Invoke-Test 'an explicit snapshot resolves ambiguous capture history without creating resources' {
        Reset-TestNative 'Reuse' 'DuplicateSnapshots'
        $result = Invoke-ConnectLabWorkers -Options @{
            PrimaryDescriptorPath = $script:preparedPrimary.descriptor
            PrimaryDescriptorSha256 = $script:preparedPrimary.descriptor_sha256
            SnapshotId = $script:snapshot
        }
        Assert-Test ($result.snapshot_id -ceq $script:snapshot.ToString() -and $script:created -eq 0 -and
            -not @($script:calls | Where-Object {
                ($_.arguments[0..2] -join ' ') -eq 'sandboxgroup snapshot list'
            }).Count) 'Explicit snapshot selection did not bind the intended capture.'
    }
    Invoke-Test 'edited primary metadata fails before native discovery' {
        Reset-TestNative
        $caught = $false
        try {
            Invoke-ConnectLabWorkers -Options @{
                PrimaryDescriptorPath = $script:preparedPrimary.descriptor
                PrimaryDescriptorSha256 = ('0' * 64)
            } | Out-Null
        } catch { $caught = $_.Exception.Message.Contains('descriptor changed') }
        Assert-Test ($caught -and $script:calls.Count -eq 0) 'Changed primary metadata reached Azure.'
    }
    Invoke-Test 'public portal WhatIf does not invoke Azure or publish a registration' {
        $path = Join-Path $root 'scripts\connect-lab-workers.ps1'
        $output = & $path -PrimaryDescriptorPath $script:preparedPrimary.descriptor `
            -PrimaryDescriptorSha256 $script:preparedPrimary.descriptor_sha256 -SnapshotId $script:snapshot -WhatIf -AsJson
        Assert-Test ($null -eq $output) 'WhatIf must not publish a success-shaped registration.'
    }
    Invoke-Test 'bounded native process runner' {
        $result = & $nativeRunner 'pwsh' @('-NoProfile', '-Command', "'local-native-ok'") 10
        Assert-Test ($result.exit_code -eq 0 -and $result.stdout.Trim() -eq 'local-native-ok') 'Local runner output mismatch.'
        $timedOut = $false
        try { & $nativeRunner 'pwsh' @('-NoProfile', '-Command', 'Start-Sleep -Seconds 5') 1 | Out-Null }
        catch { $timedOut = $_.Exception.Message.Contains('timed out') }
        Assert-Test $timedOut 'Native process timeout was not enforced.'
    }
    Invoke-Test 'JSON resource identity wins over progress and escaped braces' {
        $text = "[1/2] waiting`nCreated sandbox: $script:other`n" +
            (@{ id = $script:primary.ToString(); note = 'a "quoted" {value}' } | ConvertTo-Json) + "`nReady"
        $parsed = ConvertFrom-BaselineNativeJson $text
        Assert-Test ((Assert-BaselineId $parsed) -eq $script:primary) 'Progress UUID replaced authoritative JSON identity.'
        $caught = $false
        try { ConvertFrom-BaselineNativeJson '{"id":"one"}{"id":"two"}' | Out-Null } catch { $caught = $true }
        Assert-Test $caught 'Ambiguous JSON resources were accepted.'
    }
    Invoke-Test 'WhatIf performs no native calls or output writes' {
        Reset-TestNative
        $options = New-TestOptions 'whatif' 'Provision'
        Invoke-PrepareWorkerBaseline -Options $options -WhatIf | Out-Null
        Assert-Test ($script:calls.Count -eq 0 -and -not (Test-Path $options.OutputDirectory)) 'WhatIf changed state.'
    }
    Invoke-Test 'provisioning requires explicit authorization before any native call' {
        Reset-TestNative
        Assert-PreparationFails (New-TestOptions 'unauthorized' 'Provision')
        Assert-Test ($script:calls.Count -eq 0) 'Unauthorized mode invoked native commands.'
    }
    Invoke-Test 'partial pinned source inputs fail before any native call' {
        Reset-TestNative 'Provision'
        $options = New-TestOptions 'partial-frozen' 'Provision'
        $options.FrozenManifest = 'stub-frozen-manifest.json'
        Assert-PreparationFails $options
        Assert-Test ($script:calls.Count -eq 0) 'An incomplete frozen trust anchor reached native execution.'
    }
    foreach ($fault in @('', 'FrozenAnchorMismatch', 'FrozenPrimaryMismatch')) {
        Invoke-Test "frozen source stays bound to export and primary before any snapshot: $fault" {
            Reset-TestNative 'Provision' $fault
            $options = New-TestOptions ("frozen-" + $(if ($fault) { $fault } else { 'valid' })) 'Provision'
            $options.AuthorizeProvisioning = $true
            $options.FrozenManifest = 'stub-frozen-manifest.json'
            $options.FrozenManifestSha256 = Get-TestHash $script:manifestText
            foreach ($key in @('DiskId', 'PrimaryId', 'SnapshotId', 'ClinicalId', 'SafetyId', 'GovernanceId')) { $options[$key] = [guid]::Empty }
            if ($fault) {
                Assert-PreparationFails $options
                Assert-Test (-not @($script:calls | Where-Object {
                    $_.arguments[0] -eq 'sandbox' -and $_.arguments[1] -eq 'snapshot'
                }).Count) 'An unpinned artifact reached snapshot or clone preparation.'
            }
            else {
                $result = Invoke-PrepareWorkerBaseline -Options $options
                Assert-Test ($script:created -eq 4 -and (Test-Path -LiteralPath $result.descriptor)) 'Pinned artifact did not reach all four verified Sandboxes.'
                $descriptor = Get-Content -LiteralPath $result.descriptor -Raw | ConvertFrom-Json
                Assert-Test ($descriptor.frozen_identity.data_manifest_sha256 -ceq $options.FrozenManifestSha256) 'Pinned manifest identity was not published.'
            }
        }
    }
    foreach ($missing in @('DiskId', 'PrimaryId', 'SnapshotId', 'ClinicalId', 'SafetyId', 'GovernanceId')) {
        Invoke-Test "public Reuse rejects omitted $missing before native invocation" {
            Reset-TestNative
            $parameters = New-TestOptions "public-missing-$missing"
            $parameters.Remove($missing)
            $parameters.AcaExecutable = Join-Path $workspace 'native-must-not-run.exe'
            $parameters.AzExecutable = $parameters.AcaExecutable
            $parameters.PythonExecutable = $parameters.AcaExecutable
            $message = $null
            try { & (Join-Path $root 'scripts\prepare-worker-baseline.ps1') @parameters | Out-Null }
            catch { $message = $_.Exception.Message }
            Assert-Test ($message -ceq "Reuse requires an explicit $missing.") "Public script did not reject missing $missing before native access: $message"
            Assert-Test (-not (Test-Path -LiteralPath $parameters.OutputDirectory) -and
                $script:calls.Count -eq 0) 'Missing public binding published output or invoked a test native command.'
        }
    }
        Invoke-Test 'public Provision requires exact frozen input before native calls' {
            Reset-TestNative 'Provision'
            $options = New-TestOptions 'public-without-pin' 'Provision'
            $options.Purpose = 'public-lab-development'
            Assert-PreparationFails $options
            Assert-Test ($script:calls.Count -eq 0) 'Unpinned public preparation reached native commands.'
        }
        foreach ($fault in @('', 'PublicOriginalMismatch', 'PublicZipMismatch', 'PublicDecisionMismatch',
            'PublicPurposeMismatch', 'PublicCloneMismatch')) {
            Invoke-Test "public source-use and all frozen pins bind primary and each clone: $fault" {
                Reset-TestNative 'Provision' $fault
                $options = New-TestOptions ("public-" + $(if ($fault) { $fault } else { 'valid' })) 'Provision'
                $options.Purpose = 'public-lab-development'
                $options.AuthorizeProvisioning = $true
                $options.FrozenManifest = 'stub-frozen-manifest.json'
                $options.FrozenManifestSha256 = Get-TestHash $script:manifestText
                foreach ($key in @('DiskId', 'PrimaryId', 'SnapshotId', 'ClinicalId', 'SafetyId', 'GovernanceId')) { $options[$key] = [guid]::Empty }
                if ($fault) {
                    Assert-PreparationFails $options
                    if ($fault -ne 'PublicCloneMismatch') {
                        Assert-Test (-not @($script:calls | Where-Object {
                            $_.arguments[0] -eq 'sandbox' -and $_.arguments[1] -eq 'snapshot'
                        }).Count) 'An unbound public artifact reached snapshot.'
                    }
                }
                else {
                    $result = Invoke-PrepareWorkerBaseline -Options $options
                    $descriptor = Get-Content -LiteralPath $result.descriptor -Raw | ConvertFrom-Json
                    Assert-Test ($script:created -eq 4 -and $descriptor.dataset_kind -ceq 'reviewed-public' -and
                        $descriptor.acceptance_purpose -ceq 'public-lab-development') 'Public preparation identity was lost.'
                    Assert-Test ($descriptor.frozen_identity.source_records_sha256 -ceq ('d' * 64) -and
                        $descriptor.frozen_identity.pipeline_source_sha256 -ceq ('e' * 64) -and
                        $descriptor.frozen_identity.source_use_sha256 -ceq ('f' * 64)) 'Public original-source pins were not published.'
                }
            }
        }
        foreach ($missing in @('ExpectedSourceRecordsSha256', 'ExpectedPipelineSourceSha256', 'ExpectedSourceUseSha256')) {
            Invoke-Test "public Reuse requires trusted $missing before native invocation" {
                Reset-TestNative
                $options = New-TestOptions "public-missing-$missing"
                $options.Purpose = 'public-lab-development'
                $options.Remove($missing)
                Assert-PreparationFails $options
                Assert-Test ($script:calls.Count -eq 0) 'Incomplete public reuse identity reached native commands.'
            }
        }
    Invoke-Test 'internal Reuse rejects null disk binding before native invocation' {
        Reset-TestNative
        $options = New-TestOptions 'null-disk'
        $options.DiskId = $null
        $message = $null
        try { Invoke-PrepareWorkerBaseline -Options $options | Out-Null }
        catch { $message = $_.Exception.Message }
        Assert-Test ($message -ceq 'Reuse requires an explicit DiskId.' -and $script:calls.Count -eq 0 -and
            -not (Test-Path -LiteralPath $options.OutputDirectory)) 'A null disk binding passed required-identity validation.'
    }
    Invoke-Test 'full allocated capacity refuses import and allocation' {
        Reset-TestNative
        $options = New-TestOptions 'full' 'Provision'
        $options.AuthorizeProvisioning = $true
        foreach ($key in @('DiskId', 'PrimaryId', 'SnapshotId', 'ClinicalId', 'SafetyId', 'GovernanceId')) { $options[$key] = [guid]::Empty }
        Assert-PreparationFails $options
        Assert-Test ($script:calls.Count -eq 3 -and $script:calls[2].executable -eq 'az-stub' -and
            -not (Test-Path $options.SourceContextDirectory)) 'Full capacity proceeded to source export or skipped explicit ARM capacity.'
    }
    Invoke-Test 'reuse publishes exact controller artifacts without resetting worker code' {
        Reset-TestNative
        $options = New-TestOptions 'reuse'
        $result = Invoke-PrepareWorkerBaseline -Options $options
        $bindings = Get-Content -LiteralPath $result.bindings -Raw | ConvertFrom-Json
        Assert-Test ($bindings.Count -eq 3 -and $bindings[0].workspace -eq '/opt/caldova-lab') 'Controller bindings shape mismatch.'
        Assert-Test ((Get-FileHash -LiteralPath $result.manifest).Hash.ToLowerInvariant() -eq $options.ExpectedManifestSha256) 'Manifest bytes changed.'
        $descriptor = Get-Content -LiteralPath $result.descriptor -Raw | ConvertFrom-Json
        Assert-Test ($descriptor.snapshot_id -eq $script:snapshot.ToString() -and $descriptor.uid -eq 10001) 'Descriptor identity mismatch.'
        Assert-Test (-not @($script:calls | Where-Object { $_.arguments -contains 'create' -or $_.arguments -contains 'set' -or $_.executable -eq 'python-stub' }).Count) 'Reuse provisioned or reset resources.'
        Assert-Test (-not @($script:calls | Where-Object { $_.executable -eq 'az-stub' }).Count) 'Reuse depended on allocation capacity.'
        Assert-Test (@($script:calls | Where-Object { $_.arguments[0] -eq 'sandbox' -and $_.arguments[1] -eq 'exec' }).Count -eq 4) 'Reuse did not verify all four frozen baselines.'
        foreach ($call in $script:calls | Where-Object { $_.arguments[1] -eq 'exec' }) {
            Assert-Test ((Get-TestArgument $call.arguments '--command').Contains('REQUIRE_STARTERS = False')) 'Reuse required unchanged worker implementations.'
        }
    }
    Invoke-Test 'reuse accepts real native schema even when ARM capacity lookup is unavailable' {
        Reset-TestNative 'Reuse' 'AzCapacityFailure'
        $result = Invoke-PrepareWorkerBaseline -Options (New-TestOptions 'reuse-no-capacity')
        Assert-Test ((Test-Path -LiteralPath $result.descriptor) -and
            -not @($script:calls | Where-Object { $_.executable -eq 'az-stub' }).Count) 'Reuse queried or required allocation capacity.'
    }
    foreach ($fault in @('MissingDiskStatus', 'MissingDiskState', 'DiskNotReady', 'FlatDiskStatus')) {
        Invoke-Test "reuse rejects unverified nested disk readiness: $fault" {
            Reset-TestNative 'Reuse' $fault
            Assert-PreparationFails (New-TestOptions "disk-$fault")
            Assert-Test ($script:calls.Count -eq 3 -and $script:created -eq 0) 'Invalid disk readiness proceeded to Sandbox verification or allocation.'
        }
    }
    foreach ($fault in @('MissingArmCapacity', 'StringArmCapacity', 'ZeroArmCapacity', 'WrongArmIdentity',
        'ArmNotReady', 'AzCapacityFailure', 'MalformedArmCapacity')) {
        Invoke-Test "provisioning fails before export or allocation: $fault" {
            Reset-TestNative 'Provision' $fault
            $options = New-TestOptions "capacity-$fault" 'Provision'
            $options.AuthorizeProvisioning = $true
            foreach ($key in @('DiskId', 'PrimaryId', 'SnapshotId', 'ClinicalId', 'SafetyId', 'GovernanceId')) { $options[$key] = [guid]::Empty }
            Assert-PreparationFails $options
            Assert-Test ($script:calls.Count -eq 3 -and $script:created -eq 0 -and
                -not (Test-Path $options.SourceContextDirectory)) 'Unverified ARM capacity proceeded to export or allocation.'
        }
    }
    Invoke-Test 'native capacity is never a fallback for explicit ARM capacity' {
        Reset-TestNative 'Reuse' 'MisleadingNativeCapacity'
        $options = New-TestOptions 'no-native-capacity-fallback' 'Provision'
        $options.AuthorizeProvisioning = $true
        foreach ($key in @('DiskId', 'PrimaryId', 'SnapshotId', 'ClinicalId', 'SafetyId', 'GovernanceId')) { $options[$key] = [guid]::Empty }
        Assert-PreparationFails $options
        Assert-Test ($script:calls.Count -eq 3 -and $script:created -eq 0 -and
            -not (Test-Path $options.SourceContextDirectory)) 'Provisioning trusted a native capacity fallback.'
    }
    Invoke-Test 'capacity is rechecked before subsequent allocations' {
        Reset-TestNative 'Provision' 'ShrinkingArmCapacity'
        $options = New-TestOptions 'shrinking-capacity' 'Provision'
        $options.AuthorizeProvisioning = $true
        foreach ($key in @('DiskId', 'PrimaryId', 'SnapshotId', 'ClinicalId', 'SafetyId', 'GovernanceId')) { $options[$key] = [guid]::Empty }
        Assert-PreparationFails $options
        Assert-Test ($script:created -eq 1 -and
            @($script:calls | Where-Object { $_.executable -eq 'az-stub' }).Count -eq 3) 'Capacity was not rechecked before the first clone.'
    }
    foreach ($fault in @('WrongScope', 'MissingInventory', 'MissingId', 'WrongId', 'WrongLineage',
        'MissingLineage', 'WrongSnapshotParent', 'BroadEgress', 'AutoDelete', 'DiskSuspend',
        'WrongFrozenData', 'RootUser', 'RemoteFailure', 'MissingRemoteStatus')) {
        Invoke-Test "reuse fails closed: $fault" {
            Reset-TestNative 'Reuse' $fault
            Assert-PreparationFails (New-TestOptions "fail-$fault")
        }
    }
    Invoke-Test 'documented suspendMode response remains verified as Memory' {
        Reset-TestNative 'Reuse' 'DocumentedSuspendMode'
        $result = Invoke-PrepareWorkerBaseline -Options (New-TestOptions 'suspend-alias')
        Assert-Test (Test-Path -LiteralPath $result.descriptor) 'Documented lifecycle representation failed.'
    }
    Invoke-Test 'plain JSON array inventory preserves scoped resource identity' {
        Reset-TestNative 'Reuse' 'ArrayInventory'
        $result = Invoke-PrepareWorkerBaseline -Options (New-TestOptions 'array-inventory')
        Assert-Test (Test-Path -LiteralPath $result.descriptor) 'Native array inventory failed.'
    }
    Invoke-Test 'existing output file is never overwritten' {
        Reset-TestNative
        $options = New-TestOptions 'existing-file'
        [IO.File]::WriteAllText($options.OutputDirectory, 'retain')
        $caught = $false
        try { Invoke-PrepareWorkerBaseline -Options $options | Out-Null } catch { $caught = $true }
        Assert-Test ($caught -and [IO.File]::ReadAllText($options.OutputDirectory) -eq 'retain' -and $script:calls.Count -eq 0) 'Existing output was modified.'
    }
    foreach ($fault in @('', 'ProgressOnly', 'EmptyInventory', 'ImportBuildJson')) {
        Invoke-Test "authorized source provisioning passes exact scoped native contract: $fault" {
            Reset-TestNative 'Provision' $fault
            $options = New-TestOptions ("provision-" + $(if ($fault) { $fault } else { 'json' })) 'Provision'
            $options.AuthorizeProvisioning = $true
            foreach ($key in @('DiskId', 'PrimaryId', 'SnapshotId', 'ClinicalId', 'SafetyId', 'GovernanceId')) { $options[$key] = [guid]::Empty }
            $result = Invoke-PrepareWorkerBaseline -Options $options
            Assert-Test ($script:created -eq 4 -and (Test-Path -LiteralPath $result.descriptor)) 'Provisioning did not validate exactly four Sandboxes.'
            Assert-Test (@($script:calls | Where-Object { $_.arguments[0] -eq 'sandbox' -and $_.arguments[1] -eq 'exec' }).Count -eq 4) 'All four frozen baselines were not checked.'
            Assert-Test (@($script:calls | Where-Object { $_.executable -eq 'az-stub' }).Count -eq 5) 'Provisioning did not check ARM capacity before export and each of four allocations.'
        }
    }
    foreach ($fault in @('ImportFailure', 'ImportWrongName', 'ImportDuplicate')) {
        Invoke-Test "source import identity fails before primary allocation: $fault" {
            Reset-TestNative 'Provision' $fault
            $options = New-TestOptions ("import-" + $fault) 'Provision'
            $options.AuthorizeProvisioning = $true
            foreach ($key in @('DiskId', 'PrimaryId', 'SnapshotId', 'ClinicalId', 'SafetyId', 'GovernanceId')) { $options[$key] = [guid]::Empty }
            Assert-PreparationFails $options
            Assert-Test ($script:created -eq 0) 'Unverified import reached primary allocation.'
            if ($fault -eq 'ImportFailure') {
                Assert-Test (-not @($script:calls | Where-Object {
                    ($_.arguments[0..2] -join ' ') -eq 'sandboxgroup disk list'
                }).Count) 'Failed import was silently recovered through disk lookup.'
            }
        }
    }
    Invoke-Test 'missing create JSON identity cannot fall back to progress UUID' {
        Reset-TestNative 'Provision' 'MissingCreateId'
        $options = New-TestOptions 'missing-created-id' 'Provision'
        $options.AuthorizeProvisioning = $true
        foreach ($key in @('DiskId', 'PrimaryId', 'SnapshotId', 'ClinicalId', 'SafetyId', 'GovernanceId')) { $options[$key] = [guid]::Empty }
        Assert-PreparationFails $options
    }
    Write-Host "$script:passed focused preparation checks passed; no live ACA operations."
}
finally {
    Remove-Item -LiteralPath $workspace -Recurse -Force
}
