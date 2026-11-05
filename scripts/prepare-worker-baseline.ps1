[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
param(
    [Parameter(Mandatory)]
    [ValidateSet('Provision', 'Reuse', 'CheckCapacity', 'VerifyPrimary')]
    [string] $Mode,

    [Parameter(Mandatory)]
    [guid] $SubscriptionId,

    [Parameter(Mandatory)]
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._()-]{0,89}$')]
    [string] $ResourceGroup,

    [Parameter(Mandatory)]
    [ValidatePattern('^[a-z0-9]{1,30}$')]
    [string] $Region,

    [Parameter(Mandatory)]
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._()-]{0,89}$')]
    [string] $GroupName,

    [Parameter(Mandatory)]
    [string] $OutputDirectory,

    [switch] $AuthorizeProvisioning,
    [switch] $PrimaryOnly,
    [switch] $RequireStarters,
    [string] $SourceContextDirectory,
    [string] $SourceContextManifestSha256,
    [string] $FrozenManifest,
    [string] $FrozenManifestSha256,
    [ValidateSet('synthetic-development', 'public-lab-development')]
    [string] $Purpose = 'synthetic-development',
    [switch] $AsJson,
    [guid] $DiskId = [guid]::Empty,
    [guid] $PrimaryId = [guid]::Empty,
    [guid] $SnapshotId = [guid]::Empty,
    [guid] $ClinicalId = [guid]::Empty,
    [guid] $SafetyId = [guid]::Empty,
    [guid] $GovernanceId = [guid]::Empty,
    [string] $ExpectedDatabaseSha256,
    [string] $ExpectedManifestSha256,
    [string] $ExpectedBaselineSha256,
    [string] $ExpectedLogicalSha256,
    [string] $ExpectedSourceRecordsSha256,
    [string] $ExpectedPipelineSourceSha256,
    [string] $ExpectedSourceUseSha256,
    [string] $AcaExecutable = 'aca',
    [string] $AzExecutable = 'az',
    [string] $PythonExecutable = 'python',
    [ValidateRange(60, 1800)]
    [int] $OperationTimeoutSeconds = 900,
    [ValidateRange(1, 180)]
    [int] $CommandTimeoutSeconds = 60
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:BaselineRepositoryRoot = Split-Path -Parent $PSScriptRoot

function Invoke-BaselineNative {
    param([string] $Executable, [string[]] $Arguments, [int] $TimeoutSeconds)
    $executablePath = (Get-Command $Executable -CommandType Application -ErrorAction Stop |
        Select-Object -First 1).Source
    if ([IO.Path]::GetFileName($executablePath) -ieq 'az.cmd') {
        # Use the installed Azure CLI interpreter without introducing a command shell.
        $executablePath = Join-Path (Split-Path -Parent (Split-Path -Parent $executablePath)) 'python.exe'
        if (-not (Test-Path -LiteralPath $executablePath -PathType Leaf)) {
            throw 'The installed az.cmd launcher is missing its Azure CLI Python interpreter.'
        }
        $Arguments = @('-I', '-X', 'utf8', '-m', 'azure.cli') + $Arguments
    }
    $scratch = Get-BaselineNewDirectory ('.build-contexts\prepare-native-' + [guid]::NewGuid().ToString('N'))
    [void] [IO.Directory]::CreateDirectory($scratch)
    $process = [System.Diagnostics.Process]::new()
    try {
        $process.StartInfo.FileName = $executablePath
        $process.StartInfo.WorkingDirectory = $script:BaselineRepositoryRoot
        $process.StartInfo.UseShellExecute = $false
        $process.StartInfo.RedirectStandardOutput = $true
        $process.StartInfo.RedirectStandardError = $true
        $process.StartInfo.StandardOutputEncoding = [Text.Encoding]::UTF8
        $process.StartInfo.StandardErrorEncoding = [Text.Encoding]::UTF8
        foreach ($name in @('TEMP', 'TMP', 'TMPDIR')) { $process.StartInfo.Environment[$name] = $scratch }
        foreach ($argument in $Arguments) { $process.StartInfo.ArgumentList.Add($argument) }
        [void] $process.Start()
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            $process.Kill($true)
            $process.WaitForExit()
            throw 'The bounded native command timed out. Inspect existing operations before retrying.'
        }
        $out = $stdout.GetAwaiter().GetResult()
        $err = $stderr.GetAwaiter().GetResult()
        if ([Text.Encoding]::UTF8.GetByteCount($out + $err) -gt 1048576) {
            throw 'The native command exceeded the retained-output limit.'
        }
        return @{ exit_code = $process.ExitCode; stdout = $out; stderr = $err }
    }
    finally {
        $process.Dispose()
        Remove-Item -LiteralPath $scratch -Recurse -Force
    }
}

function ConvertFrom-BaselineNativeJson {
    param([string] $Text, [switch] $AllowMissing)
    $text = [regex]::Replace($Text, '\x1b\[[0-?]*[ -/]*[@-~]', '')
    $documents = [Collections.Generic.List[object]]::new()
    for ($start = 0; $start -lt $text.Length; $start++) {
        if ($text[$start] -notin @('{', '[')) { continue }
        $stack = [Collections.Generic.Stack[char]]::new()
        $quoted = $false
        $escaped = $false
        for ($end = $start; $end -lt $text.Length; $end++) {
            $character = $text[$end]
            if ($quoted) {
                if ($escaped) { $escaped = $false }
                elseif ($character -eq '\') { $escaped = $true }
                elseif ($character -eq '"') { $quoted = $false }
                continue
            }
            if ($character -eq '"') { $quoted = $true; continue }
            if ($character -in @('{', '[')) { $stack.Push($character); continue }
            if ($character -notin @('}', ']')) { continue }
            if ($stack.Count -eq 0) { break }
            $opening = $stack.Pop()
            if (($opening -eq '{' -and $character -ne '}') -or
                ($opening -eq '[' -and $character -ne ']')) { break }
            if ($stack.Count -eq 0) {
                try {
                    $document = ConvertFrom-Json -InputObject $text.Substring($start, $end - $start + 1) `
                        -AsHashtable -NoEnumerate -ErrorAction Stop
                    $documents.Add($document)
                    $start = $end
                }
                catch { }
                break
            }
        }
    }
    if ($documents.Count -eq 0 -and $AllowMissing) { return $null }
    if ($documents.Count -ne 1) { throw 'Native output must contain exactly one complete JSON resource document.' }
    return ,$documents[0]
}

function Assert-BaselineId {
    param($Resource, [guid] $Expected = [guid]::Empty)
    $id = [guid]::Empty
    if ($Resource -isnot [Collections.IDictionary] -or
        -not [guid]::TryParse([string] $Resource['id'], [ref] $id) -or $id -eq [guid]::Empty) {
        throw 'Resource metadata is missing a valid resource identity.'
    }
    if ($Expected -ne [guid]::Empty -and $id -ne $Expected) {
        throw 'Resource metadata does not match the explicitly bound resource identity.'
    }
    return $id
}

function Get-BaselineNewDirectory {
    param([string] $Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { throw 'A new project-local directory is required.' }
    $root = [IO.Path]::GetFullPath($script:BaselineRepositoryRoot).TrimEnd('\')
    $full = [IO.Path]::GetFullPath($Path, $root)
    if (-not $full.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Preparation artifacts must stay inside the repository.'
    }
    $relative = [IO.Path]::GetRelativePath($root, $full)
    if (($relative.Split('\'))[0] -in @('.azure', '.git', '.venv', '.venv-linux')) {
        throw 'Credential, Git and virtualenv directories are not preparation destinations.'
    }
    if (Test-Path -LiteralPath $full) { throw 'Refusing to replace an existing output directory or file.' }
    for ($parent = Split-Path -Parent $full; $parent -ne $root; $parent = Split-Path -Parent $parent) {
        if (Test-Path -LiteralPath $parent) {
            if ((Get-Item -LiteralPath $parent).LinkType -in @('SymbolicLink', 'Junction')) {
                throw 'Preparation output must not pass through symbolic links.'
            }
        }
    }
    return $full
}

function Get-BaselineSourceContext {
    param([hashtable] $Options)
    if ($Options['SourceContextManifestSha256'] -cnotmatch '^[0-9a-f]{64}$' -or
        [string]::IsNullOrWhiteSpace($Options['SourceContextDirectory'])) {
        throw 'VerifyPrimary requires the original source context and its manifest SHA-256.'
    }
    $root = [IO.Path]::GetFullPath($script:BaselineRepositoryRoot).TrimEnd('\')
    $path = [IO.Path]::GetFullPath($Options.SourceContextDirectory, $root)
    if (-not $path.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase) -or
        -not (Test-Path -LiteralPath $path -PathType Container)) {
        throw 'The verified source context must be an existing project-local directory.'
    }
    for ($parent = $path; $parent -ne $root; $parent = Split-Path -Parent $parent) {
        if ((Get-Item -LiteralPath $parent -Force).LinkType -in @('SymbolicLink', 'Junction')) {
            throw 'The source context must not pass through links.'
        }
    }
    $entries = @(Get-ChildItem -LiteralPath $path -Recurse -Force)
    if (@($entries | Where-Object { $_.LinkType -in @('SymbolicLink', 'Junction') }).Count) {
        throw 'The source context must not contain links.'
    }
    $manifestPath = Join-Path $path 'source-context.json'
    if ((Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne
        $Options.SourceContextManifestSha256) {
        throw 'The original source-context manifest changed.'
    }
    $record = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json -AsHashtable
    if ($record['schema_version'] -cne '1.0' -or
        $record['source_revision'] -isnot [string] -or [string]::IsNullOrWhiteSpace($record.source_revision) -or
        $record['files'] -isnot [Collections.IDictionary] -or -not $record.files.Contains('Dockerfile') -or
        @($entries | Where-Object { -not $_.PSIsContainer }).Count -ne $record.files.Count + 1) {
        throw 'The original source context has an invalid or changed file inventory.'
    }
    foreach ($name in $record.files.Keys) {
        $file = [IO.Path]::GetFullPath((Join-Path $path $name))
        if (-not $file.StartsWith($path + '\', [StringComparison]::OrdinalIgnoreCase) -or
            $record.files[$name] -cnotmatch '^[0-9a-f]{64}$' -or
            (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -cne $record.files[$name]) {
            throw 'An original source-context file changed.'
        }
    }
    if ((Get-FileHash -LiteralPath $Options.FrozenManifest -Algorithm SHA256).Hash.ToLowerInvariant() -cne
        $Options.FrozenManifestSha256) {
        throw 'The local frozen manifest no longer matches its trust anchor.'
    }
    return @{
        directory = $path; source_revision = $record.source_revision; files = $record.files.Count
        source_context_manifest_sha256 = $Options.SourceContextManifestSha256; frozen_data = $record['frozen_data']
    }
}

function Set-BaselineFrozenInputs {
    param([hashtable] $Options, [hashtable] $SourceContext)
    $inputIdentity = $SourceContext['frozen_data']
    if ($inputIdentity -isnot [Collections.IDictionary] -or
        $inputIdentity['dataset_kind'] -cne $(if ($Options.Purpose -eq 'public-lab-development') { 'reviewed-public' } else { 'synthetic-development' }) -or
        ($Options.Purpose -eq 'public-lab-development' -and $inputIdentity['acceptance_purpose'] -cne $Options.Purpose) -or
        $inputIdentity['data_manifest_sha256'] -cne $Options.FrozenManifestSha256) {
        throw 'Source export did not verify the explicitly pinned development artifact and purpose.'
    }
    $pairs = @(@('ExpectedDatabaseSha256', 'database_sha256'),
        @('ExpectedManifestSha256', 'data_manifest_sha256'), @('ExpectedLogicalSha256', 'logical_sha256'))
    if ($Options.Purpose -eq 'public-lab-development') {
        $pairs += @(@('ExpectedSourceRecordsSha256', 'source_records_sha256'),
            @('ExpectedPipelineSourceSha256', 'pipeline_source_sha256'), @('ExpectedSourceUseSha256', 'source_use_sha256'))
    }
    foreach ($pair in $pairs) {
        $hash = $inputIdentity[$pair[1]]
        if ($hash -cnotmatch '^[0-9a-f]{64}$' -or ($Options[$pair[0]] -and $Options[$pair[0]] -cne $hash)) {
            throw 'The pinned artifact disagrees with a required frozen checksum.'
        }
        $Options[$pair[0]] = $hash
    }
}

function Assert-BaselinePolicies {
    param([hashtable] $Sandbox)
    $policy = $Sandbox['egressPolicy']
    if ($policy -isnot [Collections.IDictionary] -or $policy['defaultAction'] -cne 'Deny' -or
        $policy['trafficInspection'] -cne 'Full' -or @($policy['rules']).Count -ne 1 -or
        @($policy.Keys | Where-Object { $_ -notin @('defaultAction', 'trafficInspection', 'rules') }).Count) {
        throw 'Every Sandbox must have default Deny, Full inspection and one reviewed host rule.'
    }
    $rule = @($policy['rules'])[0]
    if ($rule['match']['host'] -cne 'open.fda.gov' -or $rule['match'].Count -ne 1 -or
        $rule['action']['type'] -cne 'Allow' -or $rule['action'].Count -ne 1 -or
        @($rule.Keys | Where-Object { $_ -notin @('name', 'match', 'action') }).Count) {
        throw 'The only allowed egress destination must be the exact host open.fda.gov.'
    }
    $lifecycle = $Sandbox['lifecycle']
    if ($lifecycle -isnot [Collections.IDictionary]) { throw 'Sandbox lifecycle metadata is missing.' }
    $suspend = $lifecycle['autoSuspendPolicy']
    $delete = $lifecycle['autoDeletePolicy']
    if ($suspend -isnot [Collections.IDictionary] -or $delete -isnot [Collections.IDictionary] -or
        $suspend['enabled'] -isnot [bool] -or -not $suspend['enabled'] -or
        $delete['enabled'] -isnot [bool] -or $delete['enabled'] -or $suspend['interval'] -ne 900) {
        throw 'Every Sandbox must suspend after 900 idle seconds and have auto-delete disabled.'
    }
    $modes = @($suspend['mode'], $suspend['suspendMode']) | Where-Object { $null -ne $_ }
    if (@($modes).Count -ne 1 -or @($modes)[0] -cne 'Memory') {
        throw 'Every Sandbox must use the explicitly verified Memory suspend mode.'
    }
}

function Invoke-BaselineAca {
    param([hashtable] $Options, [string[]] $Arguments, [switch] $LongOperation, [switch] $RawOutput)
    $format = if ($RawOutput) { 'table' } else { 'json' }
    $scope = @('--subscription', $Options.SubscriptionId.ToString(),
        '--resource-group', $Options.ResourceGroup, '--region', $Options.Region, '--output', $format)
    $timeout = $Options.CommandTimeoutSeconds
    if ($LongOperation) {
        $Arguments += @('--wait-timeout', [string] $Options.OperationTimeoutSeconds, '--wait-interval', '5')
        $timeout = $Options.OperationTimeoutSeconds + 30
    }
    $result = Invoke-BaselineNative $Options.AcaExecutable ($Arguments + $scope) $timeout
    if ($result.exit_code -ne 0) {
        $operation = $Arguments[0..([Math]::Min(2, $Arguments.Count - 1))] -join ' '
        throw "Native ACA $operation failed. No cleanup or retry was performed; inspect the existing operation."
    }
    return $result.stdout
}

function Get-BaselineCapacity {
    param([hashtable] $Options, [string] $ExpectedGroupId)
    $groupPath = "/subscriptions/$($Options.SubscriptionId)/resourceGroups/$([uri]::EscapeDataString($Options.ResourceGroup))/providers/Microsoft.App/sandboxGroups/$([uri]::EscapeDataString($Options.GroupName))"
    $url = "https://management.azure.com${groupPath}?api-version=2026-02-01-preview"
    $result = Invoke-BaselineNative $Options.AzExecutable @(
        'rest', '--method', 'get', '--url', $url,
        '--query', '{id:id,maxSandboxCount:properties.maxSandboxCount,provisioningState:properties.provisioningState}',
        '--subscription', $Options.SubscriptionId.ToString(), '--output', 'json', '--only-show-errors'
    ) $Options.CommandTimeoutSeconds
    if ($result.exit_code -ne 0) {
        throw 'Read-only ARM capacity lookup failed. No source export, allocation, cleanup or retry was attempted by this check.'
    }
    $resource = ConvertFrom-BaselineNativeJson $result.stdout
    if ($resource -isnot [Collections.IDictionary] -or $resource['id'] -ine $ExpectedGroupId) {
        throw 'ARM capacity metadata does not match the explicitly scoped Sandbox group.'
    }
    $capacity = $resource['maxSandboxCount']
    if (($capacity -isnot [int] -and $capacity -isnot [long]) -or $capacity -lt 1) {
        throw 'The explicit ARM API response is missing a positive integer maxSandboxCount capacity.'
    }
    if ($resource['provisioningState'] -cne 'Succeeded') {
        throw 'The explicitly scoped Sandbox group is not in Succeeded provisioning state.'
    }
    return $capacity
}

function Get-BaselineInventory {
    param([hashtable] $Options, [ValidateRange(0, 2147483647)] [int] $RequiredSlots = 0)
    $group = ConvertFrom-BaselineNativeJson (Invoke-BaselineAca $Options @(
        'sandboxgroup', 'get', '--name', $Options.GroupName))
    $expected = "/subscriptions/$($Options.SubscriptionId)/resourceGroups/$($Options.ResourceGroup)/providers/Microsoft.App/sandboxGroups/$($Options.GroupName)"
    if ($group['id'] -ine $expected -or $group['name'] -ine $Options.GroupName -or
        $group['location'] -ine $Options.Region) {
        throw 'Sandbox group identity or region does not match the explicit preparation scope.'
    }
    $inventory = ConvertFrom-BaselineNativeJson (Invoke-BaselineAca $Options @(
        'sandbox', 'list', '--group', $Options.GroupName))
    if ($inventory -is [Collections.IDictionary]) {
        if ($inventory['nextLink'] -or -not $inventory.Contains('value') -or
            @($inventory.Keys | Where-Object { $_ -notin @('value', 'nextLink') }).Count) {
            throw 'Sandbox inventory is incomplete or paged; capacity cannot safely be established.'
        }
        $inventory = $inventory['value']
    }
    if ($inventory -isnot [array]) { throw 'Sandbox inventory must be a complete JSON array.' }
    $ids = @($inventory | ForEach-Object { (Assert-BaselineId $_).ToString() })
    if (@($ids | Select-Object -Unique).Count -ne $ids.Count) {
        throw 'Sandbox inventory contains ambiguous resource identities.'
    }
    $capacity = $null
    if ($RequiredSlots -gt 0) {
        $capacity = Get-BaselineCapacity $Options $expected
        if ($capacity - $ids.Count -lt $RequiredSlots) {
            throw "Sandbox capacity is insufficient: $($ids.Count)/$capacity allocated; $RequiredSlots additional slots required. No capacity or resource cleanup changes were made."
        }
    }
    return @{ capacity = $capacity; allocated = $ids.Count; ids = $ids }
}

function Get-BaselineSandbox {
    param([hashtable] $Options, [guid] $Id, [guid] $SourceSnapshot = [guid]::Empty)
    $metadata = ConvertFrom-BaselineNativeJson (Invoke-BaselineAca $Options @(
        'sandbox', 'get', '--group', $Options.GroupName, '--id', $Id.ToString()))
    [void] (Assert-BaselineId $metadata $Id)
    Assert-BaselinePolicies $metadata
    if ($SourceSnapshot -ne [guid]::Empty) {
        $source = $metadata['sourcesRef']
        if ($source -isnot [Collections.IDictionary] -or $source['snapshot'] -isnot [Collections.IDictionary] -or
            [string] $source['snapshot']['id'] -ine $SourceSnapshot.ToString()) {
            throw 'Worker sourcesRef.snapshot.id does not match the explicitly bound baseline snapshot.'
        }
    }
    return $metadata
}

function Quote-BaselineShell {
    param([string] $Text)
    $quote = [string] [char] 39
    $replacement = $quote + [char] 34 + $quote + [char] 34 + $quote
    return $quote + $Text.Replace($quote, $replacement) + $quote
}

function Get-BaselineFrozenData {
    param([hashtable] $Options, [guid] $Id, [switch] $RequireStarters)
    $nonce = [guid]::NewGuid().ToString('N')
    $python = @'
import hashlib, importlib.util, json, os, sys
from pathlib import Path
root = Path("/opt/caldova-lab")
sys.path.insert(0, str(root))
assert os.geteuid() == 10001, "The verified workspace must run as UID 10001."
assert Path.cwd() == root, "The native working directory must be the fixed lab workspace."
baseline_path = root / "prepared-baseline.json"
manifest_path = root / "data/artifacts/development/data-manifest.json"
baseline_bytes = baseline_path.read_bytes()
manifest_bytes = manifest_path.read_bytes()
record = json.loads(baseline_bytes)
for relative, expected in record["protected_files"].items():
    path = root / relative
    path.resolve().relative_to(root)
    assert not path.is_symlink()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    assert path.stat().st_uid == 0
    assert not os.access(path, os.W_OK) and not os.access(path.parent, os.W_OK)
    parent = path.parent
    while parent.is_relative_to(root):
        assert parent.stat().st_uid == 0 and not os.access(parent, os.W_OK)
        parent = parent.parent
assert baseline_path.stat().st_uid == 0 and root.stat().st_uid == 0
assert not os.access(baseline_path, os.W_OK) and not os.access(root, os.W_OK)
spec = importlib.util.spec_from_file_location("caldova_baseline", root / "src/developer-image/baseline.py")
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
assert record["protected_files"] == baseline.protected_files()
assert record["editable_modules"] == baseline.EDITABLE_MODULES
assert record["toolchains"] == baseline.toolchains()
for relative in baseline.EDITABLE_MODULES.values():
    path = root / relative
    assert path.stat().st_uid == 10001 and os.access(path, os.W_OK)
manifest = baseline.validate_artifact(manifest_path)
os.environ["CALDOVA_ACCEPTANCE_PURPOSE"] = PURPOSE
if PURPOSE == "public-lab-development":
    os.environ["CALDOVA_DATA_MANIFEST_SHA256"] = record["data_manifest_sha256"]
    manifest, raw_manifest, verified_purpose = baseline.check_data_contract()
    assert verified_purpose == PURPOSE
else:
    assert manifest.dataset_kind == "synthetic-development" and manifest.review is None
assert record.get("acceptance_purpose", "synthetic-development") == PURPOSE
assert record["dataset_kind"] == manifest.dataset_kind
if PURPOSE == "public-lab-development":
    assert record["public_identity"] == baseline.public_identity(raw_manifest)
manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
assert record["database_sha256"] == manifest.database.sha256
assert record["data_manifest_sha256"] == manifest_sha
assert record["dataset_version"] == manifest.dataset_version
assets = baseline.BuiltAssets()
assets.feed((baseline.FRONTEND / "dist/index.html").read_text())
assert assets.paths and all((baseline.FRONTEND / "dist" / path).is_file() for path in assets.paths)
assert (baseline.FRONTEND / "node_modules/typescript/bin/tsc").is_file()
if REQUIRE_STARTERS:
    baseline.verify_baseline()
result = {
    "uid": os.geteuid(), "workspace": str(root),
    "dataset_version": manifest.dataset_version, "dataset_kind": manifest.dataset_kind,
    "logical_sha256": manifest.logical_sha256, "database_sha256": manifest.database.sha256,
    "data_manifest_sha256": manifest_sha,
    "baseline_manifest_sha256": hashlib.sha256(baseline_bytes).hexdigest(),
    "source_revision": record["source_revision"], "toolchains": record["toolchains"],
    "frontend_assets": len(assets.paths), "starters_checked": REQUIRE_STARTERS,
    "data_manifest_json": manifest_bytes.decode("utf-8"),
    "prepared_baseline_json": baseline_bytes.decode("utf-8")
}
if PURPOSE == "public-lab-development":
    result.update(acceptance_purpose=PURPOSE, **baseline.public_identity(raw_manifest))
print("PAYLOAD_MARKER" + json.dumps(result, separators=(",", ":")))
'@
    $payloadMarker = "CALDOVA_FROZEN_${nonce}="
    $statusMarker = "CALDOVA_STATUS_${nonce}="
    $purpose = if ($Options['Purpose']) { $Options.Purpose } else { 'synthetic-development' }
    $python = "PURPOSE = '$purpose'`n" +
        'REQUIRE_STARTERS = ' + $(if ($RequireStarters) { 'True' } else { 'False' }) + "`n" +
        $python.Replace('PAYLOAD_MARKER', $payloadMarker)
    $inner = 'python -I -B -c ' + (Quote-BaselineShell $python)
    $command = 'sh -c ' + (Quote-BaselineShell $inner) + '; caldova_status=$?; printf ' +
        (Quote-BaselineShell ("\n" + $statusMarker + "%s\n")) + ' "$caldova_status"; exit "$caldova_status"'
    $stdout = Invoke-BaselineAca $Options @('sandbox', 'exec', '--group', $Options.GroupName,
        '--id', $Id.ToString(), '--working-directory', '/opt/caldova-lab', '--command', $command) -RawOutput
    $statuses = [regex]::Matches($stdout, '(?m)^' + [regex]::Escape($statusMarker) + '([0-9]{1,3})\r?$')
    $payloads = [regex]::Matches($stdout, '(?m)^' + [regex]::Escape($payloadMarker) + '([^\r\n]+)\r?$')
    if ($statuses.Count -ne 1 -or $statuses[0].Groups[1].Value -cne '0' -or $payloads.Count -ne 1) {
        throw 'Frozen baseline verification did not return one successful remote status and identity receipt.'
    }
    $receipt = ConvertFrom-Json -InputObject $payloads[0].Groups[1].Value -AsHashtable
    if ($receipt['uid'] -ne 10001 -or $receipt['workspace'] -cne '/opt/caldova-lab' -or
        $receipt['dataset_kind'] -cne $(if ($purpose -eq 'public-lab-development') { 'reviewed-public' } else { 'synthetic-development' }) -or
        ($purpose -eq 'public-lab-development' -and $receipt['acceptance_purpose'] -cne $purpose) -or
        $receipt['frontend_assets'] -lt 1 -or
        $receipt['starters_checked'] -isnot [bool] -or $receipt['starters_checked'] -ne $RequireStarters.IsPresent) {
        throw 'The remote receipt does not prove the required workspace, UID, dataset purpose and verification mode.'
    }
    foreach ($pair in @(
        @('data_manifest_json', 'data_manifest_sha256'),
        @('prepared_baseline_json', 'baseline_manifest_sha256')
    )) {
        $bytes = [Text.Encoding]::UTF8.GetBytes([string] $receipt[$pair[0]])
        $hash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
        if ($hash -cne $receipt[$pair[1]]) { throw 'A returned manifest does not match its frozen SHA-256.' }
    }
    return $receipt
}

function Assert-BaselineFrozenMatch {
    param([hashtable] $Receipt, [hashtable] $Expected)
    foreach ($field in $Expected.Keys) {
        if ($Receipt[$field] -cnotmatch '^[0-9a-f]{64}$' -or $Receipt[$field] -cne $Expected[$field]) {
            throw "Frozen baseline identity does not match the trusted $field."
        }
    }
}

function New-BaselineSandbox {
    param([hashtable] $Options, [string] $SourceFlag, [guid] $SourceId, [string] $Role, [int] $RequiredSlots)
    [void] (Get-BaselineInventory $Options $RequiredSlots)
    $arguments = @('sandbox', 'create', '--group', $Options.GroupName, $SourceFlag, $SourceId.ToString())
    if ($SourceFlag -eq '--disk-id') { $arguments += @('--cpu', '2000m', '--memory', '4096Mi') }
    $arguments += @(
        '--label', 'lab=LAB722', '--label', "role=$Role", '--egress-default', 'Deny',
        '--egress-rule', 'open.fda.gov:Allow', '--traffic-inspection', 'Full')
    $text = Invoke-BaselineAca $Options $arguments -LongOperation
    $resource = ConvertFrom-BaselineNativeJson $text -AllowMissing
    if ($null -eq $resource) {
        $matches = [regex]::Matches($text, '(?m)^Created sandbox:\s*([0-9a-fA-F-]{36})\s*$')
        if ($matches.Count -ne 1) { throw 'Sandbox creation did not return an unambiguous resource identity.' }
        $resource = @{ id = $matches[0].Groups[1].Value }
    }
    $id = Assert-BaselineId $resource
    $actual = ConvertFrom-BaselineNativeJson (Invoke-BaselineAca $Options @(
        'sandbox', 'get', '--group', $Options.GroupName, '--id', $id.ToString()))
    [void] (Assert-BaselineId $actual $id)
    [void] (Invoke-BaselineAca $Options @('sandbox', 'lifecycle', 'set', '--group', $Options.GroupName,
        '--id', $id.ToString(), '--auto-suspend', 'enable', '--idle-timeout-seconds', '900',
        '--mode', 'Memory', '--auto-delete', 'disable'))
    return $id
}

function Write-BaselineArtifact {
    param([string] $Path, [string] $Text)
    $stream = [IO.FileStream]::new($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $bytes = [Text.UTF8Encoding]::new($false).GetBytes($Text)
        $stream.Write($bytes, 0, $bytes.Length)
    }
    finally { $stream.Dispose() }
}

function Invoke-PrepareWorkerBaseline {
    [CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
    param([hashtable] $Options)
    $output = Get-BaselineNewDirectory $Options.OutputDirectory
    if ($Options.SubscriptionId -eq [guid]::Empty) { throw 'An explicit nonempty subscription UUID is required.' }
    if ($Options.Mode -notin @('Provision', 'Reuse', 'CheckCapacity', 'VerifyPrimary')) {
        throw 'Choose explicit Provision, Reuse, CheckCapacity or VerifyPrimary mode.'
    }
    if ($Options['PrimaryOnly'] -and $Options.Mode -ne 'Provision') {
        throw 'PrimaryOnly requires explicitly authorized Provision mode.'
    }
    if (-not $Options['Purpose']) { $Options['Purpose'] = 'synthetic-development' }
    if ($Options.Purpose -notin @('synthetic-development', 'public-lab-development')) {
        throw 'Preparation requires an explicit supported development purpose; not attendee release.'
    }
    $frozen = -not [string]::IsNullOrWhiteSpace($Options['FrozenManifest'])
    if ($frozen -ne (-not [string]::IsNullOrWhiteSpace($Options['FrozenManifestSha256'])) -or
        ($frozen -and $Options['FrozenManifestSha256'] -cnotmatch '^[0-9a-f]{64}$')) {
        throw 'Frozen preparation requires both a manifest and its lowercase SHA-256 trust anchor.'
    }
    if ($frozen -and $Options.Mode -notin @('Provision', 'VerifyPrimary')) {
        throw 'Frozen source inputs belong in Provision; Reuse requires its existing resource and checksum bindings.'
    }
    $verifyPrimary = $Options.Mode -eq 'VerifyPrimary'
    if (($verifyPrimary -or ($Options.Purpose -eq 'public-lab-development' -and $Options.Mode -eq 'Provision')) -and -not $frozen) {
        throw 'Public development preparation requires the exact frozen manifest and trust anchor.'
    }
    if ($WhatIfPreference) {
        [void] $PSCmdlet.ShouldProcess("$($Options.SubscriptionId)/$($Options.ResourceGroup)/$($Options.Region)/$($Options.GroupName)",
            "$($Options.Mode) prepared baseline; publish controller artifacts only after verification")
        return
    }
    $ids = @{}
    $sourceContext = $null
    if ($Options.Mode -eq 'CheckCapacity') {
        return Get-BaselineInventory $Options 4
    }
    if ($verifyPrimary) {
        foreach ($pair in @(@('disk', 'DiskId'), @('primary', 'PrimaryId'))) {
            if ($null -eq $Options[$pair[1]] -or $Options[$pair[1]] -eq [guid]::Empty) {
                throw "VerifyPrimary requires an explicit $($pair[1])."
            }
            $ids[$pair[0]] = $Options[$pair[1]]
        }
        foreach ($name in @('SnapshotId', 'ClinicalId', 'SafetyId', 'GovernanceId')) {
            if ($Options[$name] -and $Options[$name] -ne [guid]::Empty) {
                throw 'VerifyPrimary accepts only the existing disk and primary, not snapshots or workers.'
            }
        }
        $sourceContext = Get-BaselineSourceContext $Options
        Set-BaselineFrozenInputs $Options $sourceContext
        $inventory = Get-BaselineInventory $Options
        if ($ids.primary.ToString() -notin $inventory.ids) {
            throw 'The explicitly bound primary is missing from scoped inventory.'
        }
    }
    elseif ($Options.Mode -eq 'Provision') {
        if (-not $Options.AuthorizeProvisioning) { throw 'Provision mode requires explicit -AuthorizeProvisioning.' }
        foreach ($name in @('DiskId', 'PrimaryId', 'SnapshotId', 'ClinicalId', 'SafetyId', 'GovernanceId')) {
            if ($null -ne $Options[$name] -and $Options[$name] -ne [guid]::Empty) {
                throw 'Existing resource bindings belong in Reuse mode, not Provision.'
            }
        }
        $contextDirectory = Get-BaselineNewDirectory $Options.SourceContextDirectory
        if ($contextDirectory -eq $output -or $contextDirectory.StartsWith($output + '\') -or $output.StartsWith($contextDirectory + '\')) {
            throw 'Source context and final artifacts must use separate, non-nested directories.'
        }
        $action = if ($Options['PrimaryOnly']) {
            'Import a source disk and prepare only the primary; leave snapshot and clone creation to the learner'
        } else { 'Import a source disk, create one primary and three clones, and snapshot; retain all resources' }
        if (-not $PSCmdlet.ShouldProcess("$($Options.SubscriptionId)/$($Options.ResourceGroup)/$($Options.GroupName)",
            $action)) { return }
        [void] (Get-BaselineInventory $Options 4)
        $exportArguments = @(
            (Join-Path $script:BaselineRepositoryRoot 'src\developer-image\export_source.py'),
            '--destination', $contextDirectory)
        if ($frozen) { $exportArguments += @('--manifest', $Options.FrozenManifest, '--manifest-sha256', $Options.FrozenManifestSha256) }
        $exportArguments += @('--purpose', $Options.Purpose)
        $export = Invoke-BaselineNative $Options.PythonExecutable $exportArguments $Options.CommandTimeoutSeconds
        if ($export.exit_code -ne 0) { throw 'Secret-free source export failed; no import was attempted.' }
        $sourceContext = ConvertFrom-BaselineNativeJson $export.stdout
        $contextPath = [string] $sourceContext['directory']
        if ($contextPath -ine $contextDirectory) { throw 'The source exporter returned a different preparation directory.' }
        $contextManifest = Join-Path $contextPath 'source-context.json'
        if (-not (Test-Path -LiteralPath (Join-Path $contextPath 'Dockerfile')) -or
            (Get-FileHash -LiteralPath $contextManifest -Algorithm SHA256).Hash.ToLowerInvariant() -cne
            $sourceContext['source_context_manifest_sha256']) {
            throw 'The exported source context identity or root Dockerfile is invalid.'
        }
        if ($frozen) {
            Set-BaselineFrozenInputs $Options $sourceContext
        }
        $diskName = 'lab722-developer-' + [guid]::NewGuid().ToString('N')
        [void] (Invoke-BaselineAca $Options @(
            'sandboxgroup', 'disk', 'create', '--group', $Options.GroupName, '--source', $contextPath,
            '--name', $diskName) -LongOperation)
        $disks = ConvertFrom-BaselineNativeJson (Invoke-BaselineAca $Options @(
            'sandboxgroup', 'disk', 'list', '--group', $Options.GroupName, '--selector', "name=$diskName"))
        if ($disks -isnot [array] -or $disks.Count -ne 1 -or
            $disks[0] -isnot [Collections.IDictionary] -or
            $disks[0]['labels'] -isnot [Collections.IDictionary] -or
            $disks[0]['name'] -cne $diskName -or $disks[0]['labels']['name'] -cne $diskName) {
            throw 'Source import did not yield exactly one scoped disk with the requested unique name.'
        }
        $ids.disk = Assert-BaselineId $disks[0]
    }
    else {
        foreach ($pair in @(@('disk', 'DiskId'), @('primary', 'PrimaryId'), @('snapshot', 'SnapshotId'),
            @('clinical-trials', 'ClinicalId'), @('drug-safety', 'SafetyId'), @('quality-governance', 'GovernanceId'))) {
            if ($null -eq $Options[$pair[1]] -or $Options[$pair[1]] -eq [guid]::Empty) {
                throw "Reuse requires an explicit $($pair[1])."
            }
            $ids[$pair[0]] = $Options[$pair[1]]
        }
        foreach ($name in @('ExpectedDatabaseSha256', 'ExpectedManifestSha256', 'ExpectedBaselineSha256', 'ExpectedLogicalSha256')) {
            if ($Options[$name] -cnotmatch '^[0-9a-f]{64}$') { throw "Reuse requires trusted $name." }
        }
        if ($Options.Purpose -eq 'public-lab-development') {
            foreach ($name in @('ExpectedSourceRecordsSha256', 'ExpectedPipelineSourceSha256', 'ExpectedSourceUseSha256')) {
                if ($Options[$name] -cnotmatch '^[0-9a-f]{64}$') { throw "Public Reuse requires trusted $name." }
            }
        }
        if (@(@($ids.primary, $ids['clinical-trials'], $ids['drug-safety'], $ids['quality-governance']) |
            Select-Object -Unique).Count -ne 4) { throw 'Primary and all three workers must be distinct Sandboxes.' }
        $inventory = Get-BaselineInventory $Options
        foreach ($id in @($ids.primary, $ids['clinical-trials'], $ids['drug-safety'], $ids['quality-governance'])) {
            if ($id.ToString() -notin $inventory.ids) { throw 'An explicitly bound Sandbox is missing from scoped inventory.' }
        }
    }
    $disk = ConvertFrom-BaselineNativeJson (Invoke-BaselineAca $Options @(
        'sandboxgroup', 'disk', 'get', '--group', $Options.GroupName, '--id', $ids.disk.ToString()))
    [void] (Assert-BaselineId $disk $ids.disk)
    $status = $disk['status']
    if ($status -isnot [Collections.IDictionary] -or $status['state'] -cne 'Ready') {
        throw 'The explicitly bound developer disk must report status.state Ready.'
    }
    $fresh = $Options.Mode -eq 'Provision'
    if ($fresh) { $ids.primary = New-BaselineSandbox $Options '--disk-id' $ids.disk 'primary' 4 }
    [void] (Get-BaselineSandbox $Options $ids.primary)
    $checkStarters = $fresh -or $verifyPrimary -or [bool] $Options['RequireStarters']
    $primary = Get-BaselineFrozenData $Options $ids.primary -RequireStarters:$checkStarters
    $expected = @{
        database_sha256 = $Options.ExpectedDatabaseSha256
        data_manifest_sha256 = $Options.ExpectedManifestSha256
        baseline_manifest_sha256 = $Options.ExpectedBaselineSha256
        logical_sha256 = $Options.ExpectedLogicalSha256
    }
    if ($Options.Purpose -eq 'public-lab-development') {
        $expected.source_records_sha256 = $Options.ExpectedSourceRecordsSha256
        $expected.pipeline_source_sha256 = $Options.ExpectedPipelineSourceSha256
        $expected.source_use_sha256 = $Options.ExpectedSourceUseSha256
    }
    if ($fresh -or $verifyPrimary) {
        $fields = @($expected.Keys)
        $expected = @{}
        foreach ($field in $fields) {
            $expected[$field] = $primary[$field]
        }
        if ($Options.Purpose -eq 'public-lab-development') {
            foreach ($pair in @(@('ExpectedSourceRecordsSha256', 'source_records_sha256'),
                @('ExpectedPipelineSourceSha256', 'pipeline_source_sha256'), @('ExpectedSourceUseSha256', 'source_use_sha256'))) {
                if ($Options[$pair[0]] -cne $expected[$pair[1]]) {
                    throw 'The imported primary changed the frozen public original sources or source-use decision.'
                }
            }
        }
        foreach ($pair in @(@('ExpectedDatabaseSha256', 'database_sha256'),
            @('ExpectedManifestSha256', 'data_manifest_sha256'), @('ExpectedBaselineSha256', 'baseline_manifest_sha256'),
            @('ExpectedLogicalSha256', 'logical_sha256'))) {
            if ($Options[$pair[0]] -and $Options[$pair[0]] -cne $expected[$pair[1]]) {
                throw 'The newly imported primary differs from an explicitly supplied frozen checksum.'
            }
        }
        Assert-BaselineFrozenMatch $primary $expected
        if ($primary['source_revision'] -cne $sourceContext['source_revision']) {
            throw 'The imported primary does not match the exported source revision.'
        }
        if ($Options['PrimaryOnly'] -or $verifyPrimary) {
            $descriptor = @{
                schema_version = '1.0'; phase = 'primary-prepared'; mode = 'Provision'
                verified_at = [DateTimeOffset]::UtcNow.ToString('o')
                scope = @{ subscription = $Options.SubscriptionId.ToString(); resource_group = $Options.ResourceGroup
                    region = $Options.Region; group = $Options.GroupName }
                disk_id = $ids.disk.ToString(); primary_id = $ids.primary.ToString()
                workspace = '/opt/caldova-lab'; uid = 10001
                dataset_version = $primary.dataset_version; dataset_kind = $primary.dataset_kind
                acceptance_purpose = $Options.Purpose; source_revision = $primary.source_revision
                frozen_identity = $expected; source_context = $sourceContext
                artifacts = @{ manifest = 'data-manifest.json'; baseline = 'prepared-baseline.json' }
            }
            if (Test-Path -LiteralPath $output) { throw 'Primary output appeared during verification; refusing to replace it.' }
            [void] [IO.Directory]::CreateDirectory($output)
            Write-BaselineArtifact (Join-Path $output 'data-manifest.json') $primary.data_manifest_json
            Write-BaselineArtifact (Join-Path $output 'prepared-baseline.json') $primary.prepared_baseline_json
            $descriptorPath = Join-Path $output 'primary-descriptor.json'
            Write-BaselineArtifact $descriptorPath (ConvertTo-Json -InputObject $descriptor -Depth 12)
            return @{
                descriptor = $descriptorPath
                descriptor_sha256 = (Get-FileHash -LiteralPath $descriptorPath -Algorithm SHA256).Hash.ToLowerInvariant()
                manifest = (Join-Path $output 'data-manifest.json')
                primary_id = $ids.primary.ToString(); disk_id = $ids.disk.ToString()
                phase = 'primary-prepared'
            }
        }
        $snapshot = ConvertFrom-BaselineNativeJson (Invoke-BaselineAca $Options @(
            'sandbox', 'snapshot', '--group', $Options.GroupName, '--id', $ids.primary.ToString(),
            '--name', ('lab722-baseline-' + [guid]::NewGuid().ToString('N'))) -LongOperation)
        $ids.snapshot = Assert-BaselineId $snapshot
    }
    Assert-BaselineFrozenMatch $primary $expected
    $snapshot = ConvertFrom-BaselineNativeJson (Invoke-BaselineAca $Options @(
        'sandboxgroup', 'snapshot', 'get', '--group', $Options.GroupName, '--id', $ids.snapshot.ToString()))
    [void] (Assert-BaselineId $snapshot $ids.snapshot)
    if ([string] $snapshot['sandboxId'] -ine $ids.primary.ToString()) {
        throw 'The baseline snapshot does not belong to the explicitly bound primary.'
    }
    $bindings = @()
    $receipts = @{}
    $remaining = 3
    foreach ($role in @('clinical-trials', 'drug-safety', 'quality-governance')) {
        if ($fresh) { $ids[$role] = New-BaselineSandbox $Options '--snapshot-id' $ids.snapshot $role $remaining }
        [void] (Get-BaselineSandbox $Options $ids[$role] $ids.snapshot)
        $receipt = Get-BaselineFrozenData $Options $ids[$role] -RequireStarters:$checkStarters
        Assert-BaselineFrozenMatch $receipt $expected
        $receipts[$role] = @{ sandbox_id = $ids[$role].ToString(); uid = $receipt.uid;
            starters_checked = $receipt.starters_checked; frontend_assets = $receipt.frontend_assets }
        $bindings += @{ role = $role; sandbox_id = $ids[$role].ToString();
            snapshot_id = $ids.snapshot.ToString(); workspace = '/opt/caldova-lab' }
        $remaining--
    }
    if (@(@($ids.primary, $ids['clinical-trials'], $ids['drug-safety'], $ids['quality-governance']) |
        Select-Object -Unique).Count -ne 4) { throw 'Primary and all three workers must be distinct Sandboxes.' }
    $inventory = Get-BaselineInventory $Options
    foreach ($id in @($ids.primary, $ids['clinical-trials'], $ids['drug-safety'], $ids['quality-governance'])) {
        if ($id.ToString() -notin $inventory.ids) { throw 'A verified Sandbox is missing from final scoped inventory.' }
    }
    $descriptor = @{
        schema_version = '1.0'; mode = $Options.Mode; verified_at = [DateTimeOffset]::UtcNow.ToString('o')
        scope = @{ subscription = $Options.SubscriptionId.ToString(); resource_group = $Options.ResourceGroup;
            region = $Options.Region; group = $Options.GroupName }
        disk_id = $ids.disk.ToString(); primary_id = $ids.primary.ToString(); snapshot_id = $ids.snapshot.ToString()
        workspace = '/opt/caldova-lab'; uid = 10001; bindings = $bindings
        dataset_version = $primary.dataset_version; dataset_kind = $primary.dataset_kind
        acceptance_purpose = $Options.Purpose
        source_revision = $primary.source_revision; frozen_identity = $expected; worker_verification = $receipts
        policies = @{ defaultAction = 'Deny'; trafficInspection = 'Full'; allowed_hosts = @('open.fda.gov');
            auto_suspend_seconds = 900; suspend_mode = 'Memory'; auto_delete = $false }
        source_context = $sourceContext
        artifacts = @{ bindings = 'bindings.json'; manifest = 'data-manifest.json'; baseline = 'prepared-baseline.json' }
    }
    if (Test-Path -LiteralPath $output) { throw 'Output appeared during verification; refusing to replace it.' }
    [void] [IO.Directory]::CreateDirectory($output)
    Write-BaselineArtifact (Join-Path $output 'bindings.json') (ConvertTo-Json -InputObject $bindings -Depth 6)
    Write-BaselineArtifact (Join-Path $output 'data-manifest.json') $primary.data_manifest_json
    Write-BaselineArtifact (Join-Path $output 'prepared-baseline.json') $primary.prepared_baseline_json
    Write-BaselineArtifact (Join-Path $output 'baseline-descriptor.json') (ConvertTo-Json -InputObject $descriptor -Depth 12)
    return @{ descriptor = (Join-Path $output 'baseline-descriptor.json');
        bindings = (Join-Path $output 'bindings.json'); manifest = (Join-Path $output 'data-manifest.json');
        primary_id = $ids.primary.ToString(); snapshot_id = $ids.snapshot.ToString() }
}

if ($MyInvocation.InvocationName -ne '.') {
    $options = @{
        Mode = $Mode; SubscriptionId = $SubscriptionId; ResourceGroup = $ResourceGroup; Region = $Region
        GroupName = $GroupName; OutputDirectory = $OutputDirectory; AuthorizeProvisioning = $AuthorizeProvisioning
        PrimaryOnly = $PrimaryOnly; RequireStarters = $RequireStarters
        SourceContextDirectory = $SourceContextDirectory; SourceContextManifestSha256 = $SourceContextManifestSha256
        FrozenManifest = $FrozenManifest
        FrozenManifestSha256 = $FrozenManifestSha256; DiskId = $DiskId; PrimaryId = $PrimaryId
        Purpose = $Purpose
        SnapshotId = $SnapshotId; ClinicalId = $ClinicalId; SafetyId = $SafetyId; GovernanceId = $GovernanceId
        ExpectedDatabaseSha256 = $ExpectedDatabaseSha256; ExpectedManifestSha256 = $ExpectedManifestSha256
        ExpectedBaselineSha256 = $ExpectedBaselineSha256; ExpectedLogicalSha256 = $ExpectedLogicalSha256
        ExpectedSourceRecordsSha256 = $ExpectedSourceRecordsSha256
        ExpectedPipelineSourceSha256 = $ExpectedPipelineSourceSha256; ExpectedSourceUseSha256 = $ExpectedSourceUseSha256
        AcaExecutable = $AcaExecutable; AzExecutable = $AzExecutable; PythonExecutable = $PythonExecutable
        OperationTimeoutSeconds = $OperationTimeoutSeconds; CommandTimeoutSeconds = $CommandTimeoutSeconds
    }
    $result = Invoke-PrepareWorkerBaseline -Options $options -WhatIf:$WhatIfPreference
    if ($AsJson -and $null -ne $result) { ConvertTo-Json -InputObject $result -Depth 6 -Compress }
    elseif ($null -ne $result) { $result }
}
