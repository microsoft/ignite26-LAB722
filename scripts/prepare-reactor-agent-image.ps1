#requires -Version 7.3
[CmdletBinding()]
param(
    [Parameter(Mandatory)][guid]$SubscriptionId,
    [Parameter(Mandatory)][string]$ResourceGroupName,
    [Parameter(Mandatory)][string]$Region,
    [Parameter(Mandatory)][string]$SandboxGroupName,
    [Parameter(Mandatory)][string]$AgentImage
)
$ErrorActionPreference = 'Stop'
if ($AgentImage -notmatch '^acateam\.azurecr\.io/lab722/reactor-swarm-agents@sha256:([a-f0-9]{64})$') {
    throw 'Supply the published immutable research-agent image.'
}
$imageKey = $Matches[1].Substring(0, 12)
$scope = @('--subscription', $SubscriptionId, '--resource-group', $ResourceGroupName,
    '--region', $Region, '--group', $SandboxGroupName, '-o', 'json')
function Invoke-AgentNative {
    param([string[]]$Arguments)
    $text = & aca @Arguments @scope
    if ($LASTEXITCODE -ne 0) { throw "Native $($Arguments[0]) failed; inspect retained records before retrying." }
    return ($text -join "`n")
}
$disks = Invoke-AgentNative @('sandboxgroup', 'disk', 'list') | ConvertFrom-Json -NoEnumerate
$matching = @($disks | Where-Object { $_.image.base -ceq $AgentImage -and $_.labels.purpose -ceq 'reactor-agent-image' })
if ($matching.Count -gt 1) { throw 'Multiple owned agent disks match; no disk was selected.' }
if (-not $matching.Count) {
    $disk = Invoke-AgentNative @('sandboxgroup', 'disk', 'create', '--image', $AgentImage,
        '--name', "lab722-research-$imageKey", '--label', 'lab=LAB722', '--label', 'purpose=reactor-agent-image') |
        ConvertFrom-Json
} else { $disk = $matching[0] }
$disk = Invoke-AgentNative @('sandboxgroup', 'disk', 'get', '--id', $disk.id) | ConvertFrom-Json
if ($disk.status.state -cne 'Ready') { throw 'Agent disk is not Ready; no teaching seed was created.' }
$selector = "lab=LAB722,purpose=reactor-agent-seed,image=$imageKey"
$seeds = Invoke-AgentNative @('sandbox', 'list', '--selector', $selector) | ConvertFrom-Json -NoEnumerate
if (@($seeds).Count -gt 1) { throw 'Multiple teaching seeds match; no seed was selected.' }
if (-not @($seeds).Count) {
    $null = Invoke-AgentNative @('sandbox', 'create', '--disk-id', $disk.id, '--cpu', '2000m',
        '--memory', '4Gi', '--disk-size', '40Gi', '--label', 'lab=LAB722',
        '--label', 'purpose=reactor-agent-seed', '--label', "image=$imageKey",
        '--egress-default', 'Deny', '--traffic-inspection', 'Full')
}
$seed = Invoke-AgentNative @('sandbox', 'get', '--selector', $selector) | ConvertFrom-Json
if ($seed.sourcesRef.diskImage.id -cne $disk.id -or $seed.credentialRefs.Count -or $seed.volumes.Count) {
    throw 'Teaching seed does not match the identity-free custom-image contract.'
}
if ($seed.state -ceq 'Suspended') { $null = Invoke-AgentNative @('sandbox', 'resume', '--id', $seed.id) }
$program = @'
import hashlib,json,os
from pathlib import Path
from src.reactor.agent_runtime import VERSION,ROLES
from src.runtime.remote_runner import frozen_files
assert os.getuid()==0
print(json.dumps({'version':VERSION,'roles':list(ROLES),'agent_sha256':hashlib.sha256(Path('/opt/lab722-agent/src/reactor/agent_runtime.py').read_bytes()).hexdigest(),'files_sha256':frozen_files()}))
'@
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($program))
$command = 'env -i PATH=/opt/python/3/bin:/usr/bin:/bin PYTHONPATH=/opt/lab722-agent /opt/python/3/bin/python3 -B -c "import base64;exec(base64.b64decode(' + "'$encoded'" + '))"'
$inspection = Invoke-AgentNative @('sandbox', 'exec', '--id', $seed.id, '-c', $command) | ConvertFrom-Json
$expected = (Get-FileHash (Join-Path $PSScriptRoot '..\src\reactor\agent_runtime.py') -Algorithm SHA256).Hash.ToLowerInvariant()
if ($inspection.agent_sha256 -cne $expected) { throw 'Preloaded agent source differs from this checkout; no snapshot was accepted.' }
$snapshots = Invoke-AgentNative @('sandboxgroup', 'snapshot', 'list', '--selector',
    "lab=LAB722,purpose=reactor-agent-baseline,image=$imageKey") | ConvertFrom-Json -NoEnumerate
if (@($snapshots).Count -gt 1) { throw 'Multiple agent baselines match; no snapshot was selected.' }
if (-not @($snapshots).Count) {
    $snapshot = Invoke-AgentNative @('sandbox', 'snapshot', '--id', $seed.id, '--name', "lab722-research-$imageKey",
        '--label', 'lab=LAB722', '--label', 'purpose=reactor-agent-baseline', '--label', "image=$imageKey") |
        ConvertFrom-Json
} else { $snapshot = $snapshots[0] }
if ($snapshot.sandboxId -cne $seed.id) { throw 'Baseline does not belong to the inspected teaching seed.' }
[pscustomobject]@{ disk_id = $disk.id; seed_id = $seed.id; snapshot_id = $snapshot.id;
    image = $AgentImage; inspection = $inspection }
