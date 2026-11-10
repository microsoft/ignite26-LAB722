#requires -Version 7.3
[CmdletBinding()]
param(
    [ValidateSet('Validate', 'Research', 'Prepare', 'Connect', 'Values')]
    [string] $Mode = 'Research',
    [uri] $HostedResponsesEndpoint,
    [securestring] $ServiceManagementReference = $(if ($env:LAB722_SERVICE_MANAGEMENT_REFERENCE) {
        ConvertTo-SecureString $env:LAB722_SERVICE_MANAGEMENT_REFERENCE -AsPlainText -Force
    }),
    [securestring] $AlicePassword = $(if ($env:LAB722_ALICE_PASSWORD) {
        ConvertTo-SecureString $env:LAB722_ALICE_PASSWORD -AsPlainText -Force
    }),
    [securestring] $BobPassword = $(if ($env:LAB722_BOB_PASSWORD) {
        ConvertTo-SecureString $env:LAB722_BOB_PASSWORD -AsPlainText -Force
    })
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Split-Path -Parent $PSScriptRoot
$profile = $root

function Invoke-LocalNative {
    param([string] $Executable, [string[]] $Arguments)
    $text = & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable $($Arguments[0]) failed. Inspect the existing operation before retrying."
    }
    return ($text -join "`n")
}

function Read-LocalEnvironment {
    $text = Invoke-LocalNative azd @('-C', $profile, 'env', 'get-values')
    $values = @{}
    foreach ($line in $text -split "`n") {
        if ($line -match '^([A-Z][A-Z0-9_]*)=(.*)$') {
            $name = $Matches[1]
            $value = $Matches[2].TrimEnd("`r")
            if ($value.StartsWith('"')) { $value = ConvertFrom-Json $value }
            $values[$name] = $value
        }
    }
    return $values
}

function Set-LocalValue {
    param([string] $Name, [string] $Value)
    $null = Invoke-LocalNative azd @('-C', $profile, 'env', 'set', $Name, $Value)
    $config[$Name] = $Value
    [Environment]::SetEnvironmentVariable($Name, $Value, 'Process')
}

function Invoke-ReactorArm {
    param([string] $Method, [string] $ResourceId, [string] $Version, $Body)
    $auth = Invoke-LocalNative az @('account', 'get-access-token', '--subscription',
        $config.AZURE_SUBSCRIPTION_ID, '--resource', 'https://management.azure.com/', '-o', 'json') |
        ConvertFrom-Json
    $request = @{
        Uri = "https://management.azure.com${ResourceId}?api-version=$Version"
        Method = $Method
        Headers = @{ Authorization = 'Bearer ' + $auth.accessToken }
    }
    if ($Method -ne 'GET') { $request.ContentType = 'application/json' }
    if ($null -ne $Body) {
        $request.Body = ConvertTo-Json -InputObject $Body -Depth 100 -Compress
    }
    try { Invoke-RestMethod @request }
    finally { $auth = $null; $request = $null }
}

function Ensure-ReactorRole {
    param([string] $Scope, [string] $Principal, [string] $Role, [string] $PrincipalType = 'ServicePrincipal')
    $assignments = Invoke-LocalNative az @('role', 'assignment', 'list', '--scope', $Scope,
        '--subscription', $config.AZURE_SUBSCRIPTION_ID, '-o', 'json') | ConvertFrom-Json
    if (@($assignments | Where-Object {
        $_.scope -ieq $Scope -and $_.principalId -ieq $Principal -and
        $_.roleDefinitionId.EndsWith("/$Role", [StringComparison]::OrdinalIgnoreCase)
    }).Count) { return }
    $bytes = [Security.Cryptography.SHA256]::HashData(
        [Text.Encoding]::UTF8.GetBytes("$Scope/$Principal/$Role"))
    $name = [guid]::new([byte[]] $bytes[0..15]).ToString()
    $null = Invoke-ReactorArm PUT "$Scope/providers/Microsoft.Authorization/roleAssignments/$name" `
        '2022-04-01' @{ properties = @{
            roleDefinitionId = "/subscriptions/$($config.AZURE_SUBSCRIPTION_ID)/providers/Microsoft.Authorization/roleDefinitions/$Role"
            principalId = $Principal
            principalType = $PrincipalType
        } }
}

function New-ReactorConnectionBody {
    param([string] $Target, [string] $Audience, [string] $RegistryResourceId, [string] $ProjectObjectId)
    if ($RegistryResourceId) {
        if (-not $ProjectObjectId) { throw 'Registry identity connection requires the actual project principal.' }
        return @{ properties = @{
            category = 'ContainerRegistry'; authType = 'ManagedIdentity'
            target = $Target; isSharedToAll = $false
            metadata = @{ ResourceId = $RegistryResourceId }
            # The verified registry connection contract names this principal-ID field clientId.
            credentials = @{ clientId = $ProjectObjectId; resourceId = $RegistryResourceId }
        } }
    }
    return @{ properties = @{
        category = 'OpenAPI'; authType = 'ProjectManagedIdentity'
        target = $Target; audience = $Audience; isSharedToAll = $false
        metadata = @{ type = 'openapi' }
    } }
}

function Normalize-ReactorEndpoint {
    param([uri] $Endpoint, [string] $ProjectEndpoint, [string] $AgentName)
    $expected = "$ProjectEndpoint/agents/$AgentName/endpoint/protocols/openai/responses"
    if ($null -eq $Endpoint -or $Endpoint.GetLeftPart([UriPartial]::Path) -cne $expected) {
        throw 'Copy the Responses endpoint for this exact project and prepared agent.'
    }
    $builder = [UriBuilder]::new($Endpoint)
    if ($builder.Query -notmatch '(^\?|&)api-version=') {
        $query = $builder.Query.TrimStart('?')
        $builder.Query = $(if ($query) { "$query&api-version=v1" } else { 'api-version=v1' })
    }
    return $builder.Uri.AbsoluteUri
}

function Wait-LocalHosted {
    param([string] $Name, [string] $Version)
    $program = @'
import asyncio, sys, time
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import AzureCliCredential
async def run():
    async with AzureCliCredential() as credential, AIProjectClient(endpoint=sys.argv[1], credential=credential, allow_preview=True) as project:
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            version = await project.agents.get_version(sys.argv[2], sys.argv[3])
            if version.status == "active":
                print("Exact hosted version active.")
                return
            if version.status == "failed":
                raise RuntimeError("Exact hosted version failed. Preserve it and inspect Foundry build/identity diagnostics; do not modify platform-owned groups or automatically create another version.")
            await asyncio.sleep(10)
        raise RuntimeError("Hosted readiness timed out. Inspect the retained exact version before retrying.")
asyncio.run(run())
'@
    $null = Invoke-LocalNative $python @('-B', '-c', $program, $config.FOUNDRY_PROJECT_ENDPOINT, $Name, $Version)
}

function Assert-NoReactorTasks {
    $tasks = Invoke-LocalNative aca @('sandbox', 'list', '--subscription', $config.AZURE_SUBSCRIPTION_ID,
        '--resource-group', $config.AZURE_RESOURCE_GROUP, '--region', $config.AZURE_LOCATION,
        '--group', $config.SANDBOX_GROUP_NAME, '--selector', 'lab=LAB722,purpose=reactor-task', '-o', 'json') |
        ConvertFrom-Json -NoEnumerate
    if (@($tasks).Count) { throw 'Reconcile existing owned tasks before setup or frontend connection. No task was deleted.' }
}

function Get-LocalLearnerValues {
    return @{
        SubscriptionId = $config.AZURE_SUBSCRIPTION_ID; ResourceGroupName = $config.AZURE_RESOURCE_GROUP
        Region = $config.AZURE_LOCATION; SandboxGroupName = $config.SANDBOX_GROUP_NAME
        FoundryAccountName = $config.FOUNDRY_ACCOUNT_NAME; FoundryProjectName = $config.FOUNDRY_PROJECT_NAME
        ExpressEnvironmentName = $config.EXPRESS_ENVIRONMENT_NAME; ProjectEndpoint = $config.FOUNDRY_PROJECT_ENDPOINT
        ProjectObjectId = $config.REACTOR_PROJECT_OBJECT_ID; ExecutionApiAudience = $config.REACTOR_API_AUDIENCE
        FrontendObjectId = $config.REACTOR_FRONTEND_OBJECT_ID; ExecutionObjectId = $config.REACTOR_EXECUTION_OBJECT_ID
        FrontendUrl = $config.REACTOR_FRONTEND_URL; ExecutionUrl = $config.REACTOR_EXECUTION_URL
        HostedName = 'reactor-orchestrator'; HostedImage = $config.REACTOR_HOSTED_IMAGE
        Model = $config.FOUNDRY_MODEL_DEPLOYMENT_NAME; ServiceImage = $config.REACTOR_SERVICE_IMAGE
        ToolboxEndpoint = "$($config.FOUNDRY_PROJECT_ENDPOINT)/toolboxes/runtime-reactor/mcp?api-version=v1"
        ToolboxOperation = 'reactor___reactor_execute'; ToolboxVersion = $config.REACTOR_TOOLBOX_VERSION
        ExecutionConnectionId = "$projectId/connections/reactor-execution"
        SnapshotId = $config.REACTOR_SNAPSHOT_ID; SeedId = $config.REACTOR_SEED_ID
        PreparedHostedVersion = $config.REACTOR_STARTER_VERSION
        PreviousHostedVersion = $null; PreviousHostedImage = $null
        PreviousToolboxVersion = $null; PreviousServiceImage = $null
    }
}

$config = Read-LocalEnvironment
foreach ($key in @('AZURE_ENV_NAME', 'AZURE_SUBSCRIPTION_ID', 'AZURE_RESOURCE_GROUP', 'AZURE_LOCATION')) {
    if (-not $config[$key]) { throw "Set $key in the repository-root azd environment before continuing." }
}
if ($config.AZURE_RESOURCE_GROUP -notmatch '^[A-Za-z0-9][A-Za-z0-9._()-]{0,89}$' -or
    $config.AZURE_ENV_NAME -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{1,31}$' -or
    [guid]::Parse($config.AZURE_SUBSCRIPTION_ID) -eq [guid]::Empty) {
    throw 'Invalid explicit local allocation scope.'
}
$python = if ($config['REACTOR_PYTHON']) { $config.REACTOR_PYTHON } else { 'python' }
if ($Mode -ne 'Values') {
    $account = Invoke-LocalNative az @('account', 'show', '-o', 'json') | ConvertFrom-Json
    if ($account.id -ine $config.AZURE_SUBSCRIPTION_ID -or $account.state -cne 'Enabled') {
        throw 'Sign Azure CLI into the selected enabled subscription before continuing.'
    }
}

if ($Mode -eq 'Validate') {
    foreach ($tool in @('azd', 'az', 'aca', $python)) { $null = Get-Command $tool -ErrorAction Stop }
    $null = Invoke-LocalNative $python @('-B', '-c', 'import azure.ai.projects, azure.identity, requests, duckdb')
    $operator = Invoke-LocalNative az @('ad', 'signed-in-user', 'show', '--query', 'id', '-o', 'tsv')
    Set-LocalValue LAB_USER_PRINCIPAL_ID $operator
    $exists = Invoke-LocalNative az @('group', 'exists', '--name', $config.AZURE_RESOURCE_GROUP,
        '--subscription', $config.AZURE_SUBSCRIPTION_ID) | ConvertFrom-Json
    if ($exists) {
        $inventory = Invoke-LocalNative az @('resource', 'list', '--resource-group', $config.AZURE_RESOURCE_GROUP,
            '--subscription', $config.AZURE_SUBSCRIPTION_ID, '--query', '[].{id:id,tags:tags}', '-o', 'json') |
            ConvertFrom-Json -AsHashtable -NoEnumerate
        $owned = @($inventory | Where-Object {
            $_.tags -and $_.tags['lab'] -ceq 'LAB722' -and
            $_.tags['azd-env-name'] -ceq $config.AZURE_ENV_NAME
        })
        foreach ($resource in $inventory) {
            if (@($owned | Where-Object {
                $resource.id -ieq $_.id -or $resource.id.StartsWith($_.id + '/', [StringComparison]::OrdinalIgnoreCase)
            }).Count -eq 0 -and -not $config['FOUNDRY_ACCOUNT_NAME']) {
                throw 'Existing RG has resources outside this recorded local environment; no adoption or deployment was performed.'
            }
        }
    }
    Write-Host "Local allocation: $($config.AZURE_SUBSCRIPTION_ID)/$($config.AZURE_RESOURCE_GROUP). The post-provision hook prepares the research swarm."
    return
}

if ($Mode -eq 'Prepare') {
    if (-not $config['REACTOR_REGISTRY_ID']) { throw 'Set the authorized shared acateam registry resource ID for legacy preparation.' }
    if (-not $config['REACTOR_SERVICE_IMAGE']) {
        Set-LocalValue REACTOR_SERVICE_IMAGE 'acateam.azurecr.io/lab722/reactor-services@sha256:48d6a42cd9d7bc87a551f2f05264fb8de6de0efef10bf3ec31e947ca96ff355a'
    }
    if (-not $config['REACTOR_HOSTED_IMAGE']) {
        Set-LocalValue REACTOR_HOSTED_IMAGE 'acateam.azurecr.io/lab722/reactor-hosted@sha256:2b3ef7ec815035dd5cbfe2c9905cbc5307efd46364bb2b149c91d6e2cb3cb289'
    }
}

foreach ($key in @('FOUNDRY_ACCOUNT_NAME', 'FOUNDRY_PROJECT_NAME', 'FOUNDRY_PROJECT_ENDPOINT',
    'FOUNDRY_MODEL_DEPLOYMENT_NAME', 'EXPRESS_ENVIRONMENT_NAME', 'SANDBOX_GROUP_NAME')) {
    if (-not $config[$key]) { throw "Provision the local infrastructure first; missing $key." }
}
$groupId = "/subscriptions/$($config.AZURE_SUBSCRIPTION_ID)/resourceGroups/$($config.AZURE_RESOURCE_GROUP)"
$accountId = "$groupId/providers/Microsoft.CognitiveServices/accounts/$($config.FOUNDRY_ACCOUNT_NAME)"
$projectId = "$accountId/projects/$($config.FOUNDRY_PROJECT_NAME)"
if ($config.FOUNDRY_PROJECT_ENDPOINT -cne
    "https://$($config.FOUNDRY_ACCOUNT_NAME).services.ai.azure.com/api/projects/$($config.FOUNDRY_PROJECT_NAME)") {
    throw 'Project endpoint and recorded account/project differ; reprovision the selected profile before continuing.'
}
if ($config['REACTOR_PREPARED'] -eq 'true' -and $config['REACTOR_PREPARED_PROJECT'] -ine $projectId) {
    throw 'The prepared marker belongs to a different project. Inspect and explicitly authorize recovery before clearing it.'
}
if ($Mode -eq 'Values') {
    if ($config['REACTOR_PREPARED'] -ne 'true') { throw 'The local preparation has not completed; no learner values were emitted.' }
    Get-LocalLearnerValues
    return
}
if ($Mode -eq 'Connect' -and $config['REACTOR_PREPARED'] -ne 'true') {
    throw 'Finish exact starter/service preparation before connecting a learner version.'
}
Assert-NoReactorTasks

if ($Mode -eq 'Research') {
    if (-not $config['AZURE_CONTAINER_REGISTRY_NAME']) { throw 'Provision the local registry before research preparation.' }
    $project = Invoke-ReactorArm GET $projectId '2025-06-01'
    $registryId = "$groupId/providers/Microsoft.ContainerRegistry/registries/$($config.AZURE_CONTAINER_REGISTRY_NAME)"
    $registry = Invoke-ReactorArm GET $registryId '2023-07-01'
    if ($registry.tags.lab -cne 'LAB722' -or
        $registry.tags.'azd-env-name' -cne $config.AZURE_ENV_NAME) {
        throw 'Registry does not belong to this local environment.'
    }
    Ensure-ReactorRole $projectId $config.LAB_USER_PRINCIPAL_ID '53ca6127-db72-4b80-b1b0-d745d6d5456d' 'User'
    Ensure-ReactorRole $registryId $project.identity.principalId '7f951dda-4ed3-4680-a7ca-43fe172d538d'
    Ensure-ReactorRole $accountId $project.identity.principalId '53ca6127-db72-4b80-b1b0-d745d6d5456d'
    $catalog = Get-Content (Join-Path $root 'data\reactor-research-images.json') -Raw | ConvertFrom-Json
    $digest = ($catalog.hosted_image -split '@')[1]
    $repository = 'lab722/reactor-swarm-hosted'
    $tag = 'release-' + $digest.Substring(7, 12)
    $repositories = Invoke-LocalNative az @('acr', 'repository', 'list', '--subscription',
        $config.AZURE_SUBSCRIPTION_ID, '--name', $registry.name, '-o', 'json') | ConvertFrom-Json
    $tags = if ($repositories -contains $repository) {
        Invoke-LocalNative az @('acr', 'repository', 'show-tags', '--subscription',
            $config.AZURE_SUBSCRIPTION_ID, '--name', $registry.name, '--repository', $repository, '-o', 'json') | ConvertFrom-Json
    } else { @() }
    if ($tags -notcontains $tag) {
        $null = Invoke-LocalNative az @('acr', 'import', '--subscription', $config.AZURE_SUBSCRIPTION_ID,
            '--name', $registry.name, '--source', $catalog.hosted_image, '--image', "${repository}:$tag")
    }
    $mirror = Invoke-LocalNative az @('acr', 'repository', 'show', '--subscription',
        $config.AZURE_SUBSCRIPTION_ID, '--name', $registry.name, '--image', "${repository}:$tag", '-o', 'json') | ConvertFrom-Json
    if ($mirror.digest -cne $digest) { throw 'Local hosted-image digest differs; no overwrite was attempted.' }
    $catalog.hosted_image = "$($registry.properties.loginServer)/$repository@$digest"
    $directory = Join-Path $root ".build-contexts\research-$($config.AZURE_ENV_NAME)"
    $null = New-Item -ItemType Directory -Path $directory -Force
    $catalogPath = Join-Path $directory 'research-images.json'
    $catalog | ConvertTo-Json -Depth 20 | Set-Content $catalogPath -Encoding utf8NoBOM
    $body = New-ReactorConnectionBody $registry.properties.loginServer '' $registryId $project.identity.principalId
    $null = Invoke-ReactorArm PUT "$projectId/connections/reactor-allocated-registry" '2025-06-01' $body
    $connection = Invoke-ReactorArm GET "$projectId/connections/reactor-allocated-registry" '2025-06-01'
    if ($connection.properties.authType -cne 'ManagedIdentity' -or
        $connection.properties.target -cne $registry.properties.loginServer -or
        $connection.properties.metadata.ResourceId -ine $registryId) {
        throw 'Local registry connection read-back failed.'
    }
    $private = $ServiceManagementReference
    if ($null -eq $private) {
        $private = Read-Host 'Private serviceManagementReference (Enter if your tenant does not require it)' -AsSecureString
    }
    $inputJson = @{ service_management_reference = [Net.NetworkCredential]::new('', $private).Password } |
        ConvertTo-Json -Compress
    try {
        $apiText = $inputJson | & $python -B (Join-Path $PSScriptRoot 'prepare-reactor-api.py') `
            --subscription $config.AZURE_SUBSCRIPTION_ID --resource-group $config.AZURE_RESOURCE_GROUP
        if ($LASTEXITCODE -ne 0) { throw 'Dedicated execution API preparation failed; inspect the retained registration.' }
        $api = ($apiText -join "`n") | ConvertFrom-Json
    } finally { $private = $null; $inputJson = $null }
    $allocation = @{
        SubscriptionId = $config.AZURE_SUBSCRIPTION_ID; ResourceGroupName = $config.AZURE_RESOURCE_GROUP
        Region = $config.AZURE_LOCATION; SandboxGroupName = $config.SANDBOX_GROUP_NAME
        ProjectEndpoint = $config.FOUNDRY_PROJECT_ENDPOINT; FoundryAccountName = $config.FOUNDRY_ACCOUNT_NAME
        FoundryProjectName = $config.FOUNDRY_PROJECT_NAME; ExpressEnvironmentName = $config.EXPRESS_ENVIRONMENT_NAME
        ExecutionApiAudience = $api.audience; Model = $config.FOUNDRY_MODEL_DEPLOYMENT_NAME
    }
    $prepared = & (Join-Path $PSScriptRoot 'prepare-reactor-swarm.ps1') -AllocationValues $allocation `
        -ImageCatalogPath $catalogPath -PythonExecutable $python -AlicePassword $AlicePassword -BobPassword $BobPassword
    Wait-LocalHosted $prepared.HostedName $prepared.HostedVersion
    $session = Invoke-RestMethod "$($prepared.FrontendUrl)/api/session"
    if (-not $session.hosted_configured) {
        $null = & (Join-Path $PSScriptRoot 'connect-reactor-frontend.ps1') `
            -SubscriptionId $prepared.SubscriptionId -ResourceGroupName $prepared.ResourceGroupName `
            -FrontendName $prepared.FrontendName -ProjectEndpoint $prepared.ProjectEndpoint `
            -AgentName $prepared.HostedName -HostedResponsesEndpoint $prepared.HostedEndpoint
    }
    $session = Invoke-RestMethod "$($prepared.FrontendUrl)/api/session"
    if (-not $session.hosted_configured) { throw 'Research frontend is not connected after hosted readiness.' }
    $prepared.HostedConnected = $true
    $prepared | ConvertTo-Json -Depth 20 | Set-Content (Join-Path $directory 'learner-values.json') -Encoding utf8NoBOM
    $json = $prepared | ConvertTo-Json -Depth 20 -Compress
    $null = Invoke-LocalNative azd @('-C', $profile, 'env', 'set', 'RESEARCH_PREPARED_STATE', $json)
    Write-Host "Research frontend: $($prepared.FrontendUrl)"
    Write-Host "Learner values: $(Join-Path $directory 'learner-values.json')"
    Write-Host 'Services and exact hosted version are ready. Verify a real accepted research run in the browser.'
    return
}

if ($Mode -eq 'Connect') {
    $endpoint = Normalize-ReactorEndpoint $HostedResponsesEndpoint $config.FOUNDRY_PROJECT_ENDPOINT 'reactor-orchestrator'
    $frontendId = "$groupId/providers/Microsoft.App/containerApps/lab722-reactor-frontend"
    $app = Invoke-ReactorArm GET $frontendId '2026-03-02-preview'
    $container = $app.properties.template.containers[0]
    if ($container.image -cne $config.REACTOR_SERVICE_IMAGE) { throw 'Frontend image differs from the prepared immutable image.' }
    $container.env = @($container.env | Where-Object { $_.name -cne 'HOSTED_RESPONSES_ENDPOINT' }) +
        @([pscustomobject] @{ name = 'HOSTED_RESPONSES_ENDPOINT'; value = $endpoint })
    $null = Invoke-ReactorArm PATCH $frontendId '2026-03-02-preview' @{
        properties = @{ template = $app.properties.template }
    }
    $deadline = [DateTime]::UtcNow.AddMinutes(3)
    do {
        Start-Sleep -Seconds 5
        $state = (Invoke-ReactorArm GET $frontendId '2026-03-02-preview').properties.provisioningState
        if ($state -in @('Failed', 'Canceled')) { throw 'Frontend configuration failed; inspect the retained operation.' }
        if ([DateTime]::UtcNow -gt $deadline) { throw 'Frontend configuration timed out; inspect before retrying.' }
    } until ($state -eq 'Succeeded')
    try {
        $null = Invoke-ReactorArm POST "$frontendId/stop" '2026-03-02-preview'
        $deadline = [DateTime]::UtcNow.AddMinutes(2)
        do {
            Start-Sleep -Seconds 5
            $state = (Invoke-ReactorArm GET $frontendId '2026-03-02-preview').properties.runningStatus
            if ([DateTime]::UtcNow -gt $deadline) { throw 'Frontend Stop timed out.' }
        } until ($state -eq 'Stopped')
    } finally {
        $null = Invoke-ReactorArm POST "$frontendId/start" '2026-03-02-preview'
    }
    Set-LocalValue REACTOR_HOSTED_ENDPOINT $endpoint
    Write-Host 'Frontend only was refreshed; execution ownership state was not redeployed. Sign in again.'
} elseif ($config['REACTOR_PREPARED'] -ne 'true') {
    $project = Invoke-ReactorArm GET $projectId '2025-06-01'
    Set-LocalValue REACTOR_PROJECT_OBJECT_ID $project.identity.principalId
    $registry = Invoke-ReactorArm GET $config.REACTOR_REGISTRY_ID '2023-07-01'
    if ($registry.properties.loginServer -cne 'acateam.azurecr.io') { throw 'Selected registry is not the approved acateam registry.' }
    Ensure-ReactorRole $projectId $config.LAB_USER_PRINCIPAL_ID 'eadc314b-1a2d-4efa-be10-5d325db5065e' 'User'
    Ensure-ReactorRole $config.REACTOR_REGISTRY_ID $project.identity.principalId '7f951dda-4ed3-4680-a7ca-43fe172d538d'
    Ensure-ReactorRole $accountId $project.identity.principalId '53ca6127-db72-4b80-b1b0-d745d6d5456d'
    $body = New-ReactorConnectionBody 'acateam.azurecr.io' '' $config.REACTOR_REGISTRY_ID $project.identity.principalId
    $connection = Invoke-ReactorArm PUT "$projectId/connections/reactor-acateam" '2025-06-01' $body
    if ($connection.properties.authType -cne 'ManagedIdentity') { throw 'Registry managed-identity connection was not established.' }

    $private = $ServiceManagementReference
    if ($null -eq $private) {
        $private = Read-Host 'Private serviceManagementReference (Enter if your tenant does not require it)' -AsSecureString
    }
    $inputJson = @{ service_management_reference = [Net.NetworkCredential]::new('', $private).Password } |
        ConvertTo-Json -Compress
    try {
        $apiText = $inputJson | & $python -B (Join-Path $PSScriptRoot 'prepare-reactor-api.py') `
            --subscription $config.AZURE_SUBSCRIPTION_ID --resource-group $config.AZURE_RESOURCE_GROUP
        if ($LASTEXITCODE -ne 0) { throw 'Dedicated API preparation failed; preserve the exact registration and inspect it.' }
        $api = ($apiText -join "`n") | ConvertFrom-Json
    } finally { $private = $null; $inputJson = $null }
    Set-LocalValue REACTOR_API_OBJECT_ID $api.application_object_id
    Set-LocalValue REACTOR_API_CLIENT_ID $api.application_client_id
    Set-LocalValue REACTOR_API_SERVICE_PRINCIPAL_ID $api.service_principal_id
    Set-LocalValue REACTOR_API_AUDIENCE $api.audience

    $seedDirectory = Join-Path (Join-Path (Join-Path $root '.build-contexts') 'reactor-local') $config.AZURE_ENV_NAME
    $descriptorPath = if ($config['REACTOR_SEED_DESCRIPTOR']) { $config.REACTOR_SEED_DESCRIPTOR } else {
        Join-Path $seedDirectory 'runtime-seed.json'
    }
    if (-not (Test-Path -LiteralPath $descriptorPath)) {
        if (Test-Path -LiteralPath (Join-Path $seedDirectory 'seed-id.json')) {
            throw 'An incomplete seed is retained. Resume the exact seed through the facilitator procedure, then supply REACTOR_SEED_DESCRIPTOR; no new seed was created.'
        }
        $seed = & (Join-Path $PSScriptRoot 'prepare-worker-baseline.ps1') -Mode RuntimeSeed `
            -SubscriptionId $config.AZURE_SUBSCRIPTION_ID -ResourceGroup $config.AZURE_RESOURCE_GROUP `
            -Region $config.AZURE_LOCATION -GroupName $config.SANDBOX_GROUP_NAME `
            -OutputDirectory $seedDirectory -AuthorizeProvisioning -PythonExecutable $python -AsJson |
            ConvertFrom-Json
        $descriptorPath = $seed.descriptor
    }
    $descriptor = Get-Content -LiteralPath $descriptorPath -Raw | ConvertFrom-Json
    if (-not $descriptor.verified -or $descriptor.subscription_id -ine $config.AZURE_SUBSCRIPTION_ID -or
        $descriptor.resource_group -cne $config.AZURE_RESOURCE_GROUP -or
        $descriptor.group_name -cne $config.SANDBOX_GROUP_NAME -or
        $descriptor.region -cne $config.AZURE_LOCATION -or
        $descriptor.files.'source-records.json' -cne '5c31dcd20478c1644b50eff7a7286b9c568094dd1e26427843afd23fc9dfe57c' -or
        $descriptor.files.'data-manifest.json' -cne '99810e57a77cd3bc8b107287037e54fb2521795a96ec71d431fd585c03289f91' -or
        $descriptor.files.'caldova-research.duckdb' -cne 'f12f3e239f7b439b5c4fde1b405bd4e2346fa49fba79b1c1b198f42874ef9559') {
        throw 'Snapshot descriptor does not match this verified allocation and frozen data.'
    }
    Set-LocalValue REACTOR_SEED_DESCRIPTOR $descriptorPath
    Set-LocalValue REACTOR_SNAPSHOT_ID $descriptor.snapshot_id
    Set-LocalValue REACTOR_SEED_ID $descriptor.seed_id
    $null = Invoke-LocalNative aca @('sandbox', 'stop', '--subscription', $config.AZURE_SUBSCRIPTION_ID,
        '--resource-group', $config.AZURE_RESOURCE_GROUP, '--region', $config.AZURE_LOCATION,
        '--group', $config.SANDBOX_GROUP_NAME, '--id', $descriptor.seed_id)

    $alice = $AlicePassword
    $bob = $BobPassword
    if ($null -eq $alice) { $alice = Read-Host 'Private Alice demo password (12-1024 characters)' -AsSecureString }
    if ($null -eq $bob) { $bob = Read-Host 'Private Bob demo password (different, 12-1024 characters)' -AsSecureString }
    try {
        $outputs = & (Join-Path $PSScriptRoot 'deploy-reactor.ps1') `
            -SubscriptionId $config.AZURE_SUBSCRIPTION_ID -ResourceGroupName $config.AZURE_RESOURCE_GROUP `
            -ExpressEnvironmentName $config.EXPRESS_ENVIRONMENT_NAME -FoundryAccountName $config.FOUNDRY_ACCOUNT_NAME `
            -FoundryProjectName $config.FOUNDRY_PROJECT_NAME -SandboxGroupName $config.SANDBOX_GROUP_NAME `
            -SnapshotId $descriptor.snapshot_id -ServiceImage $config.REACTOR_SERVICE_IMAGE `
            -ExecutionApiAudience $api.audience -AlicePassword $alice -BobPassword $bob
    } finally { $alice = $null; $bob = $null }
    Set-LocalValue REACTOR_FRONTEND_URL $outputs.frontendEndpoint.value
    Set-LocalValue REACTOR_EXECUTION_URL $outputs.executionEndpoint.value
    Set-LocalValue REACTOR_FRONTEND_OBJECT_ID $outputs.frontendObjectId.value
    Set-LocalValue REACTOR_EXECUTION_OBJECT_ID $outputs.executionObjectId.value

    $body = New-ReactorConnectionBody $config.REACTOR_EXECUTION_URL $config.REACTOR_API_AUDIENCE ''
    $null = Invoke-ReactorArm PUT "$projectId/connections/reactor-execution" '2025-06-01' $body
    $connection = Invoke-ReactorArm GET "$projectId/connections/reactor-execution" '2025-06-01'
    if ($connection.properties.authType -cne 'ProjectManagedIdentity' -or
        $connection.properties.target -cne $config.REACTOR_EXECUTION_URL -or
        $connection.properties.audience -cne $config.REACTOR_API_AUDIENCE) {
        throw 'Execution connection read-back differs. Inspect normal Foundry Connections; no key-auth fallback was used.'
    }
    $setup = Join-Path $PSScriptRoot 'setup-reactor-foundry.py'
    $toolbox = Invoke-LocalNative $python @('-B', $setup, 'toolbox', '--project-endpoint',
        $config.FOUNDRY_PROJECT_ENDPOINT, '--name', 'runtime-reactor', '--execution-endpoint',
        $config.REACTOR_EXECUTION_URL, '--connection-id', "$projectId/connections/reactor-execution") |
        ConvertFrom-Json
    Set-LocalValue REACTOR_TOOLBOX_VERSION $toolbox.version
    $hosted = Invoke-LocalNative $python @('-B', $setup, 'hosted', '--project-endpoint',
        $config.FOUNDRY_PROJECT_ENDPOINT, '--name', 'reactor-orchestrator', '--image',
        $config.REACTOR_HOSTED_IMAGE, '--model', $config.FOUNDRY_MODEL_DEPLOYMENT_NAME,
        '--toolbox-endpoint', "$($config.FOUNDRY_PROJECT_ENDPOINT)/toolboxes/runtime-reactor/mcp?api-version=v1",
        '--operation', 'reactor___reactor_execute') | ConvertFrom-Json
    $deadline = [DateTime]::UtcNow.AddMinutes(3)
    do {
        $runtime = Invoke-LocalNative az @('rest', '--method', 'get', '--resource', 'https://ai.azure.com',
            '--url', "$($config.FOUNDRY_PROJECT_ENDPOINT)/agents/reactor-orchestrator?api-version=v1",
            '--query', 'instance_identity.principal_id', '-o', 'tsv')
        if ($runtime) { break }
        if ([DateTime]::UtcNow -gt $deadline) { throw 'Native runtime identity is absent; preserve the registration.' }
        Start-Sleep -Seconds 10
    } while ($true)
    Ensure-ReactorRole $projectId $runtime '53ca6127-db72-4b80-b1b0-d745d6d5456d'
    Wait-LocalHosted 'reactor-orchestrator' $hosted.version
    Set-LocalValue REACTOR_STARTER_VERSION $hosted.version
}

$deadline = [DateTime]::UtcNow.AddMinutes(3)
do {
    $health = Invoke-WebRequest "$($config.REACTOR_EXECUTION_URL)/health" -SkipHttpErrorCheck -TimeoutSec 30
    $session = Invoke-WebRequest "$($config.REACTOR_FRONTEND_URL)/api/session" -SkipHttpErrorCheck -TimeoutSec 30
    if ($health.StatusCode -eq 200 -and $session.StatusCode -eq 200) { break }
    if ([DateTime]::UtcNow -gt $deadline) { throw 'Service HTTP readiness failed; inspect both app logs.' }
    Start-Sleep -Seconds 5
} while ($true)
$configured = ($session.Content | ConvertFrom-Json).hosted_configured
if ($Mode -eq 'Connect' -and -not $configured) { throw 'Saved endpoint has not reached the running frontend.' }
if ($Mode -eq 'Prepare') {
    Set-LocalValue REACTOR_PREPARED_PROJECT $projectId
    Set-LocalValue REACTOR_PREPARED 'true'
}
Write-Host "Services responsive; hosted_configured=$configured. This is preparation, not a live owner-workflow pass."
Write-Host "Frontend: $($config.REACTOR_FRONTEND_URL)"
Write-Host 'Load public learner values with -Mode Values, then follow the local walkthrough guide.'
