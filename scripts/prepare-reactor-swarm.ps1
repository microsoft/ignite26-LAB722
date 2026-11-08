#requires -Version 7.3
[CmdletBinding()]
param(
    [ValidateSet('Prepare', 'Values')][string]$Mode = 'Prepare',
    [securestring]$AlicePassword,
    [securestring]$BobPassword,
    [string]$PythonExecutable = 'python',
    [hashtable]$AllocationValues,
    [string]$PreparedStatePath,
    [string]$FrontendName = 'lab722-research-frontend',
    [string]$ExecutionName = 'lab722-research-execution',
    [string]$ExecutionConnectionName = 'reactor-swarm-execution',
    [string]$ToolboxName = 'runtime-research',
    [string]$HostedName = 'reactor-research-orchestrator'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if ($PreparedStatePath) {
    $PreparedStatePath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($PreparedStatePath)
}
$profile = Join-Path $root 'local-reactor'
$base = if ($null -ne $AllocationValues) { $AllocationValues } else {
    & (Join-Path $PSScriptRoot 'prepare-local-reactor.ps1') -Mode Values
}
foreach ($key in @('SubscriptionId', 'ResourceGroupName', 'Region', 'SandboxGroupName', 'ProjectEndpoint',
    'FoundryAccountName', 'FoundryProjectName', 'ExpressEnvironmentName', 'ExecutionApiAudience', 'Model')) {
    if (-not $base[$key]) { throw "Explicit research allocation is missing $key." }
}
$catalog = Get-Content -LiteralPath (Join-Path $root 'data\reactor-research-images.json') -Raw | ConvertFrom-Json
function Invoke-ResearchCommand {
    param([string]$Executable, [string[]]$Arguments)
    $text = & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Executable $($Arguments[0]) failed; inspect the existing operation before retrying." }
    return ($text -join "`n")
}
function Read-ResearchState {
    if ($PreparedStatePath) {
        if (Test-Path -LiteralPath $PreparedStatePath) {
            return (Get-Content -LiteralPath $PreparedStatePath -Raw | ConvertFrom-Json)
        }
        return $null
    }
    $text = Invoke-ResearchCommand azd @('-C', $profile, 'env', 'get-values')
    foreach ($line in $text -split "`n") {
        if ($line -match '^RESEARCH_PREPARED_STATE=(.*)$') {
            $value = $Matches[1].TrimEnd("`r")
            if ($value.StartsWith('"')) { $value = ConvertFrom-Json $value }
            return ($value | ConvertFrom-Json)
        }
    }
    return $null
}
$prepared = Read-ResearchState
if ($null -ne $prepared) {
    if ($prepared.SubscriptionId -cne $base.SubscriptionId -or $prepared.ResourceGroupName -cne $base.ResourceGroupName -or
            $prepared.ProjectEndpoint -cne $base.ProjectEndpoint) {
        throw 'Research preparation belongs to another allocation; no adoption or replacement was performed.'
    }
    if ($prepared.ServiceImage -cne $catalog.service_image -or $prepared.AgentImage -cne $catalog.agent_image) {
        throw 'Prepared images differ. Plan an explicit migration; do not redeploy an execution app with owned evidence.'
    }
    if ($prepared.FrontendName -cne $FrontendName -or $prepared.ExecutionName -cne $ExecutionName -or
            $prepared.HostedName -cne $HostedName) {
        throw 'Prepared app/agent names differ; use a separate state path for an explicit side-by-side variant.'
    }
    $prepared
    return
}
if ($Mode -eq 'Values') { throw 'Research preparation has not completed; no ready learner values were emitted.' }
if ($null -eq $AlicePassword) { $AlicePassword = Read-Host 'Alice demo password (12+ characters)' -AsSecureString }
if ($null -eq $BobPassword) { $BobPassword = Read-Host 'Bob demo password (different, 12+ characters)' -AsSecureString }
$seed = & (Join-Path $PSScriptRoot 'prepare-reactor-agent-image.ps1') `
    -SubscriptionId $base.SubscriptionId -ResourceGroupName $base.ResourceGroupName -Region $base.Region `
    -SandboxGroupName $base.SandboxGroupName -AgentImage $catalog.agent_image
$outputs = & (Join-Path $PSScriptRoot 'deploy-reactor.ps1') `
    -SubscriptionId $base.SubscriptionId -ResourceGroupName $base.ResourceGroupName `
    -ExpressEnvironmentName $base.ExpressEnvironmentName -FoundryAccountName $base.FoundryAccountName `
    -FoundryProjectName $base.FoundryProjectName -SandboxGroupName $base.SandboxGroupName `
    -SnapshotId $seed.snapshot_id -ServiceImage $catalog.service_image `
    -ExecutionApiAudience $base.ExecutionApiAudience -FrontendName $FrontendName `
    -ExecutionName $ExecutionName -EnableAgentSwarm -ModelDeployment $base.Model `
    -AlicePassword $AlicePassword -BobPassword $BobPassword
$AlicePassword = $null; $BobPassword = $null
$projectId = "/subscriptions/$($base.SubscriptionId)/resourceGroups/$($base.ResourceGroupName)/providers/Microsoft.CognitiveServices/accounts/$($base.FoundryAccountName)/projects/$($base.FoundryProjectName)"
$connectionId = "$projectId/connections/$ExecutionConnectionName"
$auth = Invoke-ResearchCommand az @('account', 'get-access-token', '--subscription', $base.SubscriptionId,
    '--resource', 'https://management.azure.com/', '-o', 'json') | ConvertFrom-Json
$headers = @{ Authorization = 'Bearer ' + $auth.accessToken }
$body = @{ properties = @{ category = 'OpenAPI'; authType = 'ProjectManagedIdentity';
    target = $outputs.executionEndpoint.value; audience = $base.ExecutionApiAudience;
    isSharedToAll = $false; metadata = @{ type = 'openapi' } } } | ConvertTo-Json -Depth 10
try {
    $uri = "https://management.azure.com${connectionId}?api-version=2025-06-01"
    $null = Invoke-RestMethod -Uri $uri -Method Put -Headers $headers -ContentType 'application/json' -Body $body
    $connection = Invoke-RestMethod -Uri $uri -Headers $headers
    if ($connection.properties.target -cne $outputs.executionEndpoint.value -or
            $connection.properties.audience -cne $base.ExecutionApiAudience -or
            $connection.properties.authType -cne 'ProjectManagedIdentity') {
        throw 'Research execution connection read-back failed.'
    }
} finally { $auth = $null; $headers = $null; $body = $null }
$setup = Join-Path $PSScriptRoot 'setup-reactor-foundry.py'
$toolboxEndpoint = "$($base.ProjectEndpoint)/toolboxes/$ToolboxName/mcp?api-version=v1"
$toolbox = Invoke-ResearchCommand $PythonExecutable @('-B', $setup, 'toolbox', '--project-endpoint',
    $base.ProjectEndpoint, '--name', $ToolboxName, '--execution-endpoint', $outputs.executionEndpoint.value,
    '--connection-id', $connectionId) | ConvertFrom-Json
$null = Invoke-ResearchCommand $PythonExecutable @('-B', (Join-Path $PSScriptRoot 'inspect-reactor-toolbox.py'),
    '--endpoint', $toolboxEndpoint)
$hosted = Invoke-ResearchCommand $PythonExecutable @('-B', $setup, 'hosted', '--project-endpoint',
    $base.ProjectEndpoint, '--name', $HostedName, '--image', $catalog.hosted_image,
    '--model', $base.Model, '--toolbox-endpoint', $toolboxEndpoint) | ConvertFrom-Json
$values = [ordered]@{
    SubscriptionId = $base.SubscriptionId; ResourceGroupName = $base.ResourceGroupName; Region = $base.Region
    SandboxGroupName = $base.SandboxGroupName; ProjectEndpoint = $base.ProjectEndpoint
    FoundryAccountName = $base.FoundryAccountName; FoundryProjectName = $base.FoundryProjectName
    FrontendUrl = $outputs.frontendEndpoint.value; ExecutionUrl = $outputs.executionEndpoint.value
    FrontendName = $FrontendName; ExecutionName = $ExecutionName
    FrontendObjectId = $outputs.frontendObjectId.value; ExecutionObjectId = $outputs.executionObjectId.value
    ProjectObjectId = $outputs.projectObjectId.value; ExecutionApiAudience = $base.ExecutionApiAudience
    AgentImage = $catalog.agent_image; ServiceImage = $catalog.service_image; HostedImage = $catalog.hosted_image
    AgentDiskId = $seed.disk_id; SeedId = $seed.seed_id; SnapshotId = $seed.snapshot_id
    HostedName = $HostedName; HostedVersion = $hosted.version
    HostedEndpoint = "$($base.ProjectEndpoint)/agents/$HostedName/endpoint/protocols/openai/responses?api-version=v1"
    ToolboxEndpoint = $toolboxEndpoint; ToolboxVersion = $toolbox.version; ExecutionConnectionId = $connectionId
    Model = $base.Model; HostedConnected = $false
}
$json = $values | ConvertTo-Json -Depth 10 -Compress
if ($PreparedStatePath) {
    $directory = Split-Path -Parent ([IO.Path]::GetFullPath($PreparedStatePath))
    $null = New-Item -ItemType Directory -Path $directory -Force
    [IO.File]::WriteAllText([IO.Path]::GetFullPath($PreparedStatePath), $json, [Text.UTF8Encoding]::new($false))
} else {
    $null = Invoke-ResearchCommand azd @('-C', $profile, 'env', 'set', 'RESEARCH_PREPARED_STATE', $json)
}
Write-Host 'Research services and tools prepared. Check the exact hosted version is active, then save its Responses endpoint on the research frontend and Stop/Start that frontend only.'
[pscustomobject]$values
