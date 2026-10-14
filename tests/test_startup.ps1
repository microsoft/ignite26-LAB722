#requires -Version 7.2
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$savedEnvironment = @{}
foreach ($name in @('AZURE_SUBSCRIPTION_ID', 'LAB_USER_PRINCIPAL_ID', 'LAB_USER_PRINCIPAL_TYPE',
    'LAB_STARTUP_PURPOSE', 'LAB_DATA_MANIFEST', 'LAB_DATA_MANIFEST_SHA256', 'LAB_PYTHON_EXECUTABLE',
    'LAB_APPLICATION_NAME', 'LAB_APPLICATION_IMAGE_DIGEST', 'LAB_APPLICATION_PREVIEW_STATE', 'LAB_APPLICATION_IMAGE_SOURCE')) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name)
}
. (Join-Path (Join-Path $root 'scripts') 'start-lab.ps1') -ResourceGroupName 'stub-rg'
$nativeRunner = ${function:Invoke-LabNative}
$templateReader = ${function:Get-LabTemplate}
$script:passed = 0
$script:subscription = '40000000-0000-0000-0000-000000000001'
$script:groupId = "/subscriptions/$script:subscription/resourceGroups/stub-rg"
$script:preparationDirectories = [Collections.Generic.List[string]]::new()
$script:frozenText = '{"synthetic":"offline startup wiring test"}'
$script:frozenHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData(
    [Text.Encoding]::UTF8.GetBytes($script:frozenText))).ToLowerInvariant()

function Assert-Test([bool] $Condition, [string] $Message) {
    if (-not $Condition) { throw $Message }
}

function Get-TestArgument([string[]] $Arguments, [string] $Flag) {
    $index = [array]::IndexOf($Arguments, $Flag)
    Assert-Test ($index -ge 0 -and $index + 1 -lt $Arguments.Count) "Missing native flag $Flag"
    return $Arguments[$index + 1]
}

function Reset-Test([string] $Fault = '', [switch] $Existing) {
    $env:AZURE_SUBSCRIPTION_ID = $script:subscription
    Remove-Item Env:LAB_USER_PRINCIPAL_ID,Env:LAB_USER_PRINCIPAL_TYPE -ErrorAction SilentlyContinue
    foreach ($name in @('LAB_STARTUP_PURPOSE', 'LAB_DATA_MANIFEST', 'LAB_DATA_MANIFEST_SHA256', 'LAB_PYTHON_EXECUTABLE',
        'LAB_APPLICATION_NAME', 'LAB_APPLICATION_IMAGE_DIGEST', 'LAB_APPLICATION_PREVIEW_STATE', 'LAB_APPLICATION_IMAGE_SOURCE')) {
        Remove-Item "Env:$name" -ErrorAction SilentlyContinue
    }
    $script:calls = [Collections.Generic.List[object]]::new()
    $script:fault = $Fault
    $script:existing = $Existing.IsPresent
    $script:submittedName = $null
    $script:failureVerb = ''
}

function Get-LabTemplate {
    return @{ Path = (Join-Path $root 'stub-template.json'); Parameters = @{
        environmentName = @{ defaultValue = "[format('caldova-{0}', uniqueString(resourceGroup().id))]" }
    } }
}

function New-TestDeployment([string] $Name) {
    $values = @{
        AZURE_CONTAINER_REGISTRY_NAME = 'stubregistry'; FOUNDRY_ACCOUNT_NAME = 'stub-ai'
        FOUNDRY_PROJECT_NAME = 'caldova'; FOUNDRY_MODEL_DEPLOYMENT_NAME = 'gpt-4.1-mini'
        FOUNDRY_PROJECT_ENDPOINT = 'https://stub-ai.services.ai.azure.com/api/projects/caldova'
        EXPRESS_ENVIRONMENT_NAME = 'stub-express'; SANDBOX_GROUP_NAME = 'stub-sandboxes'
        SANDBOX_REGION = 'westus3'
    }
    if (-not $script:existing) {
        $values += @{
            AZURE_SUBSCRIPTION_ID = $script:subscription; AZURE_RESOURCE_GROUP = 'stub-rg'
            AZURE_LOCATION = 'westus3'; AZURE_ENV_NAME = 'caldova-stub'
        }
    }
    $outputs = @{}
    foreach ($outputName in $values.Keys) {
        $parts = $outputName.Split('_', 2)
        $normalized = $parts[0].Substring(0, $parts[0].Length - 1).ToLowerInvariant() + $parts[0][-1] + '_' + $parts[1]
        $outputs[$normalized] = @{ type = 'String'; value = $values[$outputName] }
    }
    $outputs['applicatioN_INSIGHTS_CONNECTION_STRING'] = @{ type = 'String'; value = 'untrusted secret connection string' }
    $environment = if ($script:existing) { 'retained-env' } else { 'caldova-stub' }
    $deployment = @{
        id = "$script:groupId/providers/Microsoft.Resources/deployments/$Name"; name = $Name
        properties = @{
            provisioningState = 'Succeeded'
            parameters = @{ location = @{ value = 'westus3' }; environmentName = @{ value = $environment } }
            outputs = $outputs
        }
    }
    switch ($script:fault) {
        'Failed' { $deployment.properties.provisioningState = 'Failed' }
        'Running' { $deployment.properties.provisioningState = 'Running' }
        'MissingOutput' { $outputs.Remove('SANDBOX_GROUP_NAME') }
        'WrongOutputScope' { $outputs['AZURE_RESOURCE_GROUP'] = @{ type = 'String'; value = 'other-rg' } }
        'WrongOutputRegion' { $outputs.SANDBOX_REGION.value = 'eastus2' }
        'WrongOutputEnvironment' { $deployment.properties.parameters.environmentName.value = 'other-env' }
        'WrongEndpoint' { $outputs.FOUNDRY_PROJECT_ENDPOINT.value += '?credential=untrusted' }
    }
    return $deployment
}

function Invoke-LabNative {
    param([string] $Executable, [string[]] $Arguments, [int] $TimeoutMilliseconds)
    if ($Executable -eq 'python-application-stub') {
        $script:calls.Add(@{ arguments = $Arguments; timeout = $TimeoutMilliseconds })
        Assert-Test ($Arguments[0].EndsWith('check_application.py') -and
            (Get-TestArgument $Arguments '--url') -ceq 'https://stub-app.example.azurecontainerapps.io' -and
            (Get-TestArgument $Arguments '--manifest') -ceq $env:LAB_DATA_MANIFEST -and
            (Get-TestArgument $Arguments '--manifest-sha256') -ceq $script:frozenHash -and
            (Get-TestArgument $Arguments '--purpose') -ceq $env:LAB_STARTUP_PURPOSE -and
            (Get-TestArgument $Arguments '--preview-state') -ceq $env:LAB_APPLICATION_PREVIEW_STATE) 'Application checks lost their scoped URL or harness data/state pins.'
        Assert-Test ($TimeoutMilliseconds -gt 0 -and $TimeoutMilliseconds -le 90000 -and
            [double](Get-TestArgument $Arguments '--timeout-seconds') -lt $TimeoutMilliseconds / 1000) 'Application verification escaped its startup deadline.'
        if ($script:fault -eq 'ApplicationCheckFailure') { return @{ exit_code = 1; stdout = 'untrusted secret diagnostic' } }
        if ($script:fault -eq 'ApplicationCheckMalformed') { return @{ exit_code = 0; stdout = 'not JSON' } }
        if ($script:fault -eq 'ApplicationCheckTimeout') { throw 'Application verification timed out.' }
        $json = @{
            schema_version = '1.0'
            status = 'pinned-development-application-ready'; url = 'https://stub-app.example.azurecontainerapps.io'
            preview_state = $env:LAB_APPLICATION_PREVIEW_STATE
            identity = @{
                data_manifest_sha256 = $script:frozenHash; acceptance_purpose = $env:LAB_STARTUP_PURPOSE
                dataset_kind = $(if ($env:LAB_STARTUP_PURPOSE -ceq 'public-lab-development') { 'reviewed-public' } else { 'synthetic-development' })
                database_sha256 = ('a' * 64); logical_sha256 = ('b' * 64)
                source_records_sha256 = ('c' * 64); pipeline_source_sha256 = ('d' * 64); source_use_sha256 = ('e' * 64)
            }
            live_manifest_verified = $true; local_frozen_artifacts_verified = $true
            live_original_sources_verified = ($env:LAB_STARTUP_PURPOSE -ceq 'public-lab-development')
            sample_state_verified = $true; release_approved = $false; attendee_ready = $false
            full_functional_acceptance_rerun = $false
        }
        switch ($script:fault) {
            'ApplicationCheckWrongPin' { $json.identity.data_manifest_sha256 = 'f' * 64 }
            'ApplicationCheckWidensScope' { $json.attendee_ready = $true }
            'ApplicationCheckNoSources' { $json.live_original_sources_verified = $false }
            'ApplicationCheckMissingIdentity' { $json.identity.Remove('source_use_sha256') }
            'ApplicationCheckClaimsAcceptance' { $json.full_functional_acceptance_rerun = $true }
        }
        return @{ exit_code = 0; stdout = ($json | ConvertTo-Json -Depth 5 -Compress) }
    }
    if ($Executable -eq 'python-public-stub') {
        $script:calls.Add(@{ arguments = $Arguments; timeout = $TimeoutMilliseconds })
        Assert-Test ((Get-TestArgument $Arguments '--purpose') -ceq 'public-lab-development' -and
            (Get-TestArgument $Arguments '--manifest-sha256') -ceq $script:frozenHash) 'Public identity verification lost purpose or pin.'
        if ($script:fault -eq 'PreparationIdentityFailure') { return @{ exit_code = 1; stdout = '' } }
        return @{ exit_code = 0; stdout = (@{
            database_sha256 = ('a' * 64); logical_sha256 = ('b' * 64)
            source_records_sha256 = ('d' * 64); pipeline_source_sha256 = ('e' * 64); source_use_sha256 = ('f' * 64)
        } | ConvertTo-Json -Compress) }
    }
    if ($Executable -eq 'pwsh') {
        $script:calls.Add(@{ arguments = $Arguments; timeout = $TimeoutMilliseconds })
        Assert-Test (($Arguments -contains '-NonInteractive') -and ($Arguments -contains '-AuthorizeProvisioning') -and
            ($Arguments -contains '-AsJson')) 'Startup preparation was interactive or lacked explicit authorization/JSON.'
        Assert-Test ((Get-TestArgument $Arguments '-Mode') -ceq 'Provision' -and
            (Get-TestArgument $Arguments '-SubscriptionId') -ceq $script:subscription -and
            (Get-TestArgument $Arguments '-ResourceGroup') -ceq 'stub-rg' -and
            (Get-TestArgument $Arguments '-Region') -ceq 'westus3' -and
            (Get-TestArgument $Arguments '-GroupName') -ceq 'stub-sandboxes') 'Preparation scope was not derived from verified infrastructure.'
        Assert-Test ((Get-TestArgument $Arguments '-FrozenManifest') -ceq $env:LAB_DATA_MANIFEST -and
            (Get-TestArgument $Arguments '-FrozenManifestSha256') -ceq $script:frozenHash) 'Pinned data was not wired into preparation.'
        Assert-Test ((Get-TestArgument $Arguments '-Purpose') -ceq $env:LAB_STARTUP_PURPOSE) 'Harness purpose was not passed to preparation.'
        Assert-Test ($TimeoutMilliseconds -gt 0 -and $TimeoutMilliseconds -le 900000) 'Preparation escaped the overall startup timeout.'
        if ($script:fault -eq 'PreparationFailure') { return @{ exit_code = 7; stdout = 'untrusted secret diagnostic' } }
        if ($script:fault -eq 'PreparationMalformed') { return @{ exit_code = 0; stdout = 'not JSON' } }
        if ($script:fault -eq 'PreparationTimeout') { throw 'Startup native command timed out.' }
        $outputDirectory = Get-TestArgument $Arguments '-OutputDirectory'
        $script:preparationDirectories.Add((Split-Path -Parent $outputDirectory))
        [void] [IO.Directory]::CreateDirectory($outputDirectory)
        $receipt = @{
            descriptor = Join-Path $outputDirectory 'baseline-descriptor.json'
            bindings = Join-Path $outputDirectory 'bindings.json'
            manifest = Join-Path $outputDirectory 'data-manifest.json'
            primary_id = '60000000-0000-0000-0000-000000000001'
            snapshot_id = '60000000-0000-0000-0000-000000000002'
        }
        $descriptor = @{
            mode = 'Provision'; dataset_kind = 'synthetic-development'
            scope = @{ subscription = $script:subscription; resource_group = 'stub-rg'; region = 'westus3'; group = 'stub-sandboxes' }
            frozen_identity = @{ data_manifest_sha256 = $script:frozenHash }
            primary_id = $receipt.primary_id; snapshot_id = $receipt.snapshot_id
        }
        if ($env:LAB_STARTUP_PURPOSE -ceq 'public-lab-development') {
            $descriptor.dataset_kind = 'reviewed-public'
            $descriptor.acceptance_purpose = 'public-lab-development'
            $descriptor.frozen_identity.database_sha256 = 'a' * 64
            $descriptor.frozen_identity.logical_sha256 = 'b' * 64
            $descriptor.frozen_identity.source_records_sha256 = 'd' * 64
            $descriptor.frozen_identity.pipeline_source_sha256 = 'e' * 64
            $descriptor.frozen_identity.source_use_sha256 = 'f' * 64
            if ($script:fault -eq 'PreparationPublicOriginalMismatch') { $descriptor.frozen_identity.source_records_sha256 = 'c' * 64 }
            if ($script:fault -eq 'PreparationPublicDecisionMismatch') { $descriptor.frozen_identity.source_use_sha256 = 'c' * 64 }
            if ($script:fault -eq 'PreparationPublicPurposeMismatch') { $descriptor.acceptance_purpose = 'synthetic-development' }
        }
        if ($script:fault -eq 'PreparationWrongScope') { $descriptor.scope.resource_group = 'other-rg' }
        [IO.File]::WriteAllText($receipt.descriptor, ($descriptor | ConvertTo-Json -Depth 6), [Text.UTF8Encoding]::new($false))
        [IO.File]::WriteAllText($receipt.bindings, '[]', [Text.UTF8Encoding]::new($false))
        [IO.File]::WriteAllText($receipt.manifest, $script:frozenText, [Text.UTF8Encoding]::new($false))
        if ($script:fault -eq 'PreparationWrongArtifact') {
            [IO.File]::WriteAllText($receipt.manifest, 'different artifact', [Text.UTF8Encoding]::new($false))
        }
        return @{ exit_code = 0; stdout = ($receipt | ConvertTo-Json -Compress) }
    }
    Assert-Test ($Executable -ceq 'az') 'Unexpected executable; tests must never run a live CLI.'
    $script:calls.Add(@{ arguments = $Arguments; timeout = $TimeoutMilliseconds })
    Assert-Test ((Get-TestArgument $Arguments '--subscription') -ceq $script:subscription) 'Subscription drift.'
    $format = if (($Arguments[0..2] -join ' ') -ceq 'deployment group create') { 'none' } else { 'json' }
    Assert-Test ((Get-TestArgument $Arguments '--output') -ceq $format -and $Arguments -contains '--only-show-errors') 'Unsafe output settings.'
    Assert-Test ($TimeoutMilliseconds -gt 0 -and $TimeoutMilliseconds -le 60000) 'Unbounded native timeout.'
    Assert-Test (-not @($Arguments | Where-Object {
        $_ -in @('ad', 'azd', 'login', 'set', 'delete', 'get-access-token', 'role', '--debug', '--verbose',
            '--token', '--credential', '--password', '--username', '--image')
    }).Count) 'Graph, credentials, account changes or extra mutations appeared in argv.'
    if ($Arguments -contains '--ids') {
        Assert-Test ($Arguments -notcontains '--resource-group') 'Resource-ID arguments were mixed with --ids.'
        Assert-Test ((Get-TestArgument $Arguments '--ids').StartsWith($script:groupId + '/providers/')) 'Resource ID left the requested scope.'
    }
    elseif ($Arguments[0] -ne 'account') {
        Assert-Test ((Get-TestArgument $Arguments '--resource-group') -ceq 'stub-rg') 'Resource-group drift.'
    }
    $verb = $Arguments[0..([Math]::Min(2, $Arguments.Count - 1))] -join ' '
    if ($script:failureVerb -eq '' -or $script:failureVerb -eq $verb) {
        if ($script:fault -eq 'CliFailure') { return @{ exit_code = 7; stdout = 'untrusted secret diagnostic' } }
        if ($script:fault -eq 'Malformed') { return @{ exit_code = 0; stdout = 'not JSON: untrusted secret diagnostic' } }
        if ($script:fault -eq 'NativeTimeout') { throw 'Startup native command timed out.' }
    }
    if ($Arguments[0] -eq 'account') {
        $json = @{ id = $script:subscription; state = 'Enabled' }
        if ($script:fault -eq 'ContextMismatch') { $json.id = '50000000-0000-0000-0000-000000000001' }
    }
    elseif ($Arguments[0] -eq 'group') {
        Assert-Test ($Arguments[1] -ceq 'show') 'Resource group mutation attempted.'
        $json = @{ id = $script:groupId; name = 'stub-rg'; location = 'westus3'; tags = @{} }
        if ($script:fault -eq 'WrongGroup') { $json.id += '-other' }
        if ($script:fault -eq 'InvalidGroupLocation') { $json.location = $null }
        if ($script:fault -eq 'DifferentGroupRegion') { $json.location = 'eastus' }
        if ($script:fault -eq 'AllocationMarker') { $json.tags.lab = 'LAB722' }
        if ($script:fault -eq 'ConflictingGroupName') { $json.tags['azd-env-name'] = 'other-env' }
    }
    elseif ($verb -eq 'resource list --query') {
        $json = @()
        if ($script:existing) {
            $json = @(1..2 | ForEach-Object {
                @{ id = "$script:groupId/providers/Microsoft.App/sandboxGroups/stub-$_"; location = 'westus3'
                    name = "stub-$_"; type = 'Microsoft.App/sandboxGroups'; tags = @{ lab = 'LAB722'; 'azd-env-name' = 'retained-env' } }
            })
        }
        if ($script:fault -eq 'ConflictingNames') { $json[1].tags['azd-env-name'] = 'other-env' }
        if ($script:fault -eq 'WrongWorkloadRegion') { $json[0].location = 'eastus2' }
        if ($script:fault -eq 'NonLabResources') {
            $json = @(@{ id = "$script:groupId/providers/Microsoft.App/sandboxGroups/other"; tags = @{} })
        }
    }
    elseif ($verb -eq 'deployment group list') {
        $json = @()
        if ($script:existing -or $script:fault -eq 'DeploymentHistory') {
            $json = @(@{
                id = "$script:groupId/providers/Microsoft.Resources/deployments/azd-root"; name = 'azd-root'
                state = 'Succeeded'; timestamp = '2026-01-01T00:00:00Z'
            })
            if ($script:existing) {
                $json += @(
                    @{ id = "$script:groupId/providers/Microsoft.Resources/deployments/PolicyDeployment"; name = 'PolicyDeployment'
                        state = 'Failed'; timestamp = '2026-01-03T00:00:00Z' },
                    @{ id = "$script:groupId/providers/Microsoft.Resources/deployments/foundry"; name = 'foundry'
                        state = 'Succeeded'; timestamp = '2026-01-02T00:00:00Z' }
                )
            }
        }
    }
    elseif ($verb -eq 'resource show --ids') {
        $id = Get-TestArgument $Arguments '--ids'
        if ($id.EndsWith('/Microsoft.App/containerApps/stub-app')) {
            Assert-Test ((Get-TestArgument $Arguments '--api-version') -ceq '2025-10-02-preview') 'Application readiness used the wrong tested API.'
            $query = Get-TestArgument $Arguments '--query'
            Assert-Test (-not $query.Contains('secret') -and -not $query.Contains('registries') -and
                -not $query.Contains('containers[].env')) 'Application metadata lookup requested credentials.'
            $json = @{
                id = $id; type = 'Microsoft.App/containerApps'; name = 'stub-app'; location = 'westus3'
                state = 'Succeeded'; running = 'Running'
                environmentId = "$script:groupId/providers/Microsoft.App/managedEnvironments/stub-express"
                containers = @(@{ name = 'stub-app'; image = "stubregistry.azurecr.io/caldova/research-portal@$env:LAB_APPLICATION_IMAGE_DIGEST" })
                ingress = @{ fqdn = 'stub-app.example.azurecontainerapps.io'; external = $true; targetPort = 8080 }
            }
            if ($env:LAB_APPLICATION_IMAGE_SOURCE -ceq 'SimonRegistry') {
                $json.containers[0].image = "simon.azurecr.io/lab722-stub-app@$env:LAB_APPLICATION_IMAGE_DIGEST"
            }
            if ($script:fault -eq 'DnlRegistry') {
                $json.containers[0].image = "stubregistry-hash.azurecr.io/caldova/research-portal@$env:LAB_APPLICATION_IMAGE_DIGEST"
            }
            switch ($script:fault) {
                'ApplicationMissing' { return @{ exit_code = 3; stdout = 'untrusted secret diagnostic' } }
                'ApplicationWrongScope' { $json.id += '-other' }
                'ApplicationWrongEnvironment' { $json.environmentId += '-other' }
                'ApplicationWrongImage' { $json.containers[0].image = 'otherregistry.azurecr.io/caldova/research-portal:mutable' }
                'ApplicationStopped' { $json.running = 'Stopped' }
                'ApplicationFailed' { $json.state = 'Failed' }
                'ApplicationPrivate' { $json.ingress.external = $false }
                'ApplicationWrongHost' { $json.ingress.fqdn = 'untrusted.example.invalid' }
                'ApplicationExtraContainer' { $json.containers += $json.containers[0] }
            }
            return @{ exit_code = 0; stdout = ($json | ConvertTo-Json -Depth 5 -Compress) }
        }
        $expected = @{
            'Microsoft.ContainerRegistry/registries/stubregistry' = @('Microsoft.ContainerRegistry/registries', 'stubregistry', '2023-07-01')
            'Microsoft.CognitiveServices/accounts/stub-ai' = @('Microsoft.CognitiveServices/accounts', 'stub-ai', '2025-06-01')
            'Microsoft.CognitiveServices/accounts/stub-ai/projects/caldova' = @('Microsoft.CognitiveServices/accounts/projects', 'stub-ai/caldova', '2025-06-01')
            'Microsoft.CognitiveServices/accounts/stub-ai/deployments/gpt-4.1-mini' = @('Microsoft.CognitiveServices/accounts/deployments', 'gpt-4.1-mini', '2025-06-01')
            'Microsoft.App/managedEnvironments/stub-express' = @('Microsoft.App/managedEnvironments', 'stub-express', '2026-03-02-preview')
            'Microsoft.App/sandboxGroups/stub-sandboxes' = @('Microsoft.App/sandboxGroups', 'stub-sandboxes', '2026-02-01-preview')
        }
        $path = $id.Substring(($script:groupId + '/providers/').Length)
        Assert-Test ($expected.ContainsKey($path)) 'Current resource lookup did not correspond to a deployment output.'
        Assert-Test ((Get-TestArgument $Arguments '--api-version') -ceq $expected[$path][2]) 'Resource lookup used an unreviewed API version.'
        if ((Get-TestArgument $Arguments '--query') -ceq '{id:id,loginServer:properties.loginServer}') {
            Assert-Test ($path -ceq 'Microsoft.ContainerRegistry/registries/stubregistry') 'Login-server lookup escaped the allocated registry.'
            $server = if ($script:fault -eq 'DnlRegistry') { 'stubregistry-hash.azurecr.io' } else { 'stubregistry.azurecr.io' }
            return @{ exit_code = 0; stdout = (@{id=$id;loginServer=$server} | ConvertTo-Json -Compress) }
        }
        Assert-Test ((Get-TestArgument $Arguments '--query') -ceq '{id:id,type:type,name:name,state:properties.provisioningState,location:location}') 'Resource lookup requested unnecessary metadata or secrets.'
        $json = @{ id = $id; type = $expected[$path][0]; name = $expected[$path][1]; state = 'Succeeded'; location = 'westus3' }
        if ($path -like '*/managedEnvironments/*') { $json.location = 'West US 3' }
        if ($path -like '*/deployments/*') {
            $json.location = $null
            if ($script:fault -eq 'MissingCurrentResource') { return @{ exit_code = 3; stdout = 'untrusted secret diagnostic' } }
            if ($script:fault -eq 'MissingCurrentState') { $json.Remove('state') }
        }
        if ($path -like '*/sandboxGroups/*') {
            if ($script:fault -eq 'FailedCurrentResource') { $json.state = 'Failed' }
            if ($script:fault -eq 'WrongCurrentId') { $json.id += '-different' }
            if ($script:fault -eq 'WrongCurrentRegion') { $json.location = 'eastus2' }
        }
    }
    elseif ($verb -eq 'deployment group validate') {
        Assert-Test ($Arguments -notcontains '--mode' -and $Arguments -notcontains '--no-wait') 'Validate mutated deployment settings.'
        $json = @{ error = $null; state = 'Succeeded' }
        if ($script:fault -eq 'ValidationFailure') { $json.state = 'Failed' }
    }
    elseif ($verb -eq 'deployment group create') {
        Assert-Test (-not $script:existing) 'Provision attempted to update retained infrastructure.'
        Assert-Test ((Get-TestArgument $Arguments '--mode') -ceq 'Incremental' -and $Arguments -contains '--no-wait') 'Provision is not bounded/incremental.'
        $script:submittedName = Get-TestArgument $Arguments '--name'
        return @{ exit_code = 0; stdout = '' }
    }
    elseif ($verb -eq 'deployment group show') {
        $json = New-TestDeployment (Get-TestArgument $Arguments '--name')
        if ($json.name -in @('PolicyDeployment', 'foundry')) {
            $json.properties.parameters = @{}
            $json.properties.outputs = @{}
            if ($json.name -eq 'PolicyDeployment') { $json.properties.provisioningState = 'Failed' }
        }
        $query = Get-TestArgument $Arguments '--query'
        Assert-Test (-not $query.Contains('APPLICATION_INSIGHTS') -and -not $query.Contains('labUserPrincipal')) 'Readiness requested credentials or identity metadata.'
    }
    else { throw "Unexpected offline operation: $verb" }
    return @{ exit_code = 0; stdout = (ConvertTo-Json -InputObject $json -Depth 12 -Compress) }
}

function Assert-Fails([scriptblock] $Action, [string] $MessagePattern) {
    try { [void] (& $Action) }
    catch {
        Assert-Test ($_.Exception.Message -match $MessagePattern) "Unexpected error: $($_.Exception.Message)"
        Assert-Test (-not $_.Exception.Message.Contains('untrusted secret')) 'Native diagnostic leaked.'
        return
    }
    throw "Expected failure matching $MessagePattern"
}

try {
    foreach ($value in @($null, '', 'not-a-guid', '00000000-0000-0000-0000-000000000000')) {
        Reset-Test
        $env:AZURE_SUBSCRIPTION_ID = $value
        Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg } 'AZURE_SUBSCRIPTION_ID'
        Assert-Test ($script:calls.Count -eq 0) 'Invalid harness subscription caused native calls.'
    }
    Reset-Test
    $env:LAB_USER_PRINCIPAL_ID = '60000000-0000-0000-0000-000000000001'
    Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg } 'Optional harness identity'
    Assert-Test ($script:calls.Count -eq 0) 'Partial harness identity caused native calls.'
    $script:passed++

    Reset-Test -Existing
    Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg -Mode Prepare } 'LAB_STARTUP_PURPOSE'
    Assert-Test ($script:calls.Count -eq 0) 'Missing explicit development purpose reached Azure.'
    $env:LAB_STARTUP_PURPOSE = 'synthetic-development'
    Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg -Mode Prepare } 'LAB_DATA_MANIFEST'
    Assert-Test ($script:calls.Count -eq 0) 'An unpinned startup artifact reached Azure.'
    $env:LAB_DATA_MANIFEST_SHA256 = $script:frozenHash
    foreach ($url in @('http://example.invalid/data-manifest.json',
        'https://user:token@example.invalid/data-manifest.json',
        'https://example.invalid/data-manifest.json?sig=sensitive',
        'https://example.invalid/data-manifest.json#ignored')) {
        $env:LAB_DATA_MANIFEST = $url
        Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg -Mode Prepare } 'credential-free HTTPS'
        Assert-Test ($script:calls.Count -eq 0) 'Credentials or an insecure artifact URL entered native execution.'
    }
    Reset-Test -Existing
    $env:LAB_STARTUP_PURPOSE = 'synthetic-development'
    $env:LAB_DATA_MANIFEST = 'stub-frozen-manifest.json'
    $env:LAB_DATA_MANIFEST_SHA256 = $script:frozenHash
    $report = Invoke-LabStartup -ResourceGroupName stub-rg -Mode Prepare
    Assert-Test ($report.baseline_ready -and $report.frozen_data_verified -and $report.synthetic_development_only -and
        -not $report.application_ready -and -not $report.data_ready -and -not $report.attendee_ready) 'Synthetic preparation incorrectly authorized a full attendee release.'
    Assert-Test ($report.outputs.CALDOVA_VALIDATION_SANDBOX_ID -ceq $report.baseline.primary_id -and
        (Test-Path -LiteralPath $report.outputs.CALDOVA_WORKER_BINDINGS_PATH)) 'Startup did not emit usable controller bindings.'
    foreach ($fault in @('PreparationFailure', 'PreparationMalformed', 'PreparationTimeout', 'PreparationWrongScope', 'PreparationWrongArtifact')) {
        Reset-Test $fault -Existing
        $env:LAB_STARTUP_PURPOSE = 'synthetic-development'
        $env:LAB_DATA_MANIFEST = 'stub-frozen-manifest.json'
        $env:LAB_DATA_MANIFEST_SHA256 = $script:frozenHash
        Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg -Mode Prepare } 'preparation failed|malformed JSON|timed out|artifacts do not match'
    }
    $script:passed++

    $originalFrozenText = $script:frozenText
    $originalFrozenHash = $script:frozenHash
    $script:frozenText = @{
        dataset_kind = 'reviewed-public'
        review = @{ approved_by = 'Fictional test owner'; approved_at = '2026-10-10T05:17:00Z' }
        source_records = @{ sha256 = ('d' * 64) }; pipeline_source = @{ sha256 = ('e' * 64) }
        public_extract = @{ source_use = @{
            approved_by = 'Fictional test owner'; approved_at = '2026-10-10T05:17:00Z'
            scope = 'project-owner-selected-public-lab-use'
            expert_audit_performed = $false; publication_authorized = $false
            live_replacement_authorized = $false; attendee_release_approved = $false
        } }
    } | ConvertTo-Json -Depth 8 -Compress
    $script:frozenHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData(
        [Text.Encoding]::UTF8.GetBytes($script:frozenText))).ToLowerInvariant()
    foreach ($fault in @('', 'PreparationPublicOriginalMismatch', 'PreparationPublicDecisionMismatch',
        'PreparationPublicPurposeMismatch', 'PreparationIdentityFailure')) {
        Reset-Test $fault -Existing
        $env:LAB_STARTUP_PURPOSE = 'public-lab-development'
        $env:LAB_DATA_MANIFEST = 'stub-frozen-manifest.json'
        $env:LAB_DATA_MANIFEST_SHA256 = $script:frozenHash
        $env:LAB_PYTHON_EXECUTABLE = 'python-public-stub'
        if ($fault) {
            Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg -Mode Prepare } 'identity|artifacts do not match'
        }
        else {
            $report = Invoke-LabStartup -ResourceGroupName stub-rg -Mode Prepare
            Assert-Test ($report.baseline_ready -and $report.frozen_data_verified -and
                $report.public_lab_development_only -and -not $report.synthetic_development_only -and
                -not $report.application_ready -and -not $report.data_ready -and -not $report.attendee_ready) 'Public development improperly authorized an attendee or image release.'
            Assert-Test ($report.pending_reasons[1].Contains('not expert audit')) 'Public source-use decision was overstated.'
        }
    }
    $script:frozenText = $originalFrozenText
    $script:frozenHash = $originalFrozenHash
    $script:passed++

    foreach ($fault in @('ContextMismatch', 'WrongGroup', 'InvalidGroupLocation', 'CliFailure', 'Malformed', 'NativeTimeout')) {
        Reset-Test $fault
        Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg } 'context|resource group|failed|malformed|timed out'
        Assert-Test (-not @($script:calls | Where-Object { ($_.arguments[0..2] -join ' ') -eq 'deployment group validate' }).Count) 'Invalid context reached validation.'
    }
    $script:passed++

    Reset-Test -Existing
    $report = Invoke-LabStartup -ResourceGroupName stub-rg
    $validationCall = $script:calls[$script:calls.Count - 1].arguments
    Assert-Test ($validationCall -contains 'environmentName=retained-env' -and $validationCall -contains 'location=westus3') 'Retained names/location were not preserved.'
    Assert-Test ($report.validation_succeeded -and -not $report.infrastructure_ready -and -not $report.attendee_ready) 'Validation implied readiness.'
    foreach ($fault in @('ConflictingNames', 'ConflictingGroupName')) {
        Reset-Test $fault -Existing
        Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg } 'Conflicting'
    }
    foreach ($fault in @('', 'NonLabResources', 'DeploymentHistory', 'AllocationMarker')) {
        Reset-Test $fault -Existing:($fault -eq '')
        Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg -Mode Provision } 'Provision refuses'
        Assert-Test (-not @($script:calls | Where-Object { ($_.arguments[0..2] -join ' ') -eq 'deployment group create' }).Count) 'Retained scope was mutated.'
    }
    $script:passed++

    Reset-Test
    $report = Invoke-LabStartup -ResourceGroupName stub-rg
    $call = $script:calls[$script:calls.Count - 1].arguments
    $index = [array]::IndexOf($call, '--parameters')
    Assert-Test ($call[$index + 1] -ceq 'location=westus3' -and $call[$index + 2] -ceq '--query') 'Fresh validation supplied additional deployment configuration.'
    Reset-Test
    $env:LAB_USER_PRINCIPAL_ID = '60000000-0000-0000-0000-000000000001'
    $env:LAB_USER_PRINCIPAL_TYPE = 'ServicePrincipal'
    $report = Invoke-LabStartup -ResourceGroupName stub-rg
    $call = $script:calls[$script:calls.Count - 1].arguments
    Assert-Test ($call -contains "labUserPrincipalId=$env:LAB_USER_PRINCIPAL_ID" -and $call -contains 'labUserPrincipalType=ServicePrincipal') 'Explicit harness identity was not wired.'
    Reset-Test 'ValidationFailure'
    Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg } 'validation did not'
    $script:passed++

    Reset-Test
    $report = Invoke-LabStartup -ResourceGroupName stub-rg -Mode Provision
    $create = @($script:calls | Where-Object { ($_.arguments[0..2] -join ' ') -eq 'deployment group create' })[0].arguments
    Assert-Test (-not @($create | Where-Object { $_ -match '^environmentName=|^modelCapacity=|^sandboxMaxCount=' }).Count) 'Fresh provisioning overrode template defaults/capacity.'
    Assert-Test ($report.infrastructure_ready -and -not $report.application_ready -and -not $report.data_ready -and
        -not $report.attendee_ready -and $report.pending_reasons.Count -eq 4) 'Infrastructure success implied attendee readiness.'
    Assert-Test ($report.outputs.AZURE_ENV_NAME -ceq 'caldova-stub') 'Generated environment name was guessed instead of obtained from deployment outputs.'
    Assert-Test (-not ($report | ConvertTo-Json -Depth 6 -Compress).Contains('untrusted secret')) 'Unrelated connection-string output leaked into the report.'
    Reset-Test -Existing
    $report = Invoke-LabStartup -ResourceGroupName stub-rg -Mode Readiness
    Assert-Test ($report.deployment_name -ceq 'azd-root' -and $report.outputs.AZURE_ENV_NAME -ceq 'retained-env' -and
        $report.outputs.AZURE_SUBSCRIPTION_ID -ceq $script:subscription) 'Existing azd root outputs/context were not reused.'
    $currentCalls = @($script:calls | Where-Object { ($_.arguments[0..2] -join ' ') -eq 'resource show --ids' })
    Assert-Test ($currentCalls.Count -eq 6) 'Readiness did not check all six current resources.'
    Assert-Test (@($currentCalls | Where-Object {
        (Get-TestArgument $_.arguments '--ids') -ceq "$script:groupId/providers/Microsoft.CognitiveServices/accounts/stub-ai/deployments/gpt-4.1-mini"
    }).Count -eq 1) 'Model child omitted from inventory was not explicitly checked.'
    Reset-Test 'DifferentGroupRegion' -Existing
    $report = Invoke-LabStartup -ResourceGroupName stub-rg -Mode Readiness
    Assert-Test ($report.infrastructure_ready -and $report.resource_group_metadata_location -ceq 'eastus' -and
        $report.outputs.AZURE_LOCATION -ceq 'westus3') 'Valid RG metadata/workload region separation was rejected.'
    Reset-Test 'WrongWorkloadRegion' -Existing
    Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg -Mode Readiness } 'requested region'
    $script:passed++

    foreach ($fault in @('Failed', 'MissingOutput', 'WrongOutputScope', 'WrongOutputRegion', 'WrongOutputEnvironment', 'WrongEndpoint')) {
        Reset-Test $fault -Existing
        Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg -Mode Readiness } 'not successful|output|region|environment|endpoint'
    }
    foreach ($case in @(
        @('CliFailure', 'Provision', 'deployment group create'),
        @('Malformed', 'Validate', 'deployment group validate'),
        @('Malformed', 'Readiness', 'deployment group show')
    )) {
        Reset-Test $case[0] -Existing:($case[1] -eq 'Readiness')
        $script:failureVerb = $case[2]
        Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg -Mode $case[1] } 'failed|malformed'
    }
    Reset-Test 'Running'
    $timer = [Diagnostics.Stopwatch]::StartNew()
    Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg -Mode Provision -TimeoutSeconds 1 } 'timed out'
    Assert-Test ($timer.Elapsed.TotalSeconds -lt 4) 'Deployment polling exceeded its operation bound.'
    $script:passed++

    foreach ($fault in @('MissingCurrentResource', 'FailedCurrentResource', 'MissingCurrentState', 'WrongCurrentId', 'WrongCurrentRegion')) {
        Reset-Test $fault -Existing
        Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg -Mode Readiness } 'failed|not healthy|readiness is uncertain|mismatched scoped ID|workload region'
    }
    $script:passed++

    Reset-Test -Existing
    $env:LAB_APPLICATION_NAME = 'stub-app'
    Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg -Mode Readiness } 'complete harness'
    Assert-Test ($script:calls.Count -eq 0) 'Partial application pins reached Azure.'
    $env:LAB_APPLICATION_IMAGE_DIGEST = 'sha256:' + ('a' * 64)
    $env:LAB_APPLICATION_PREVIEW_STATE = 'starter'
    Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg -Mode Readiness } 'LAB_STARTUP_PURPOSE'
    Assert-Test ($script:calls.Count -eq 0) 'Unpinned application data reached Azure.'
    $env:LAB_STARTUP_PURPOSE = 'synthetic-development'
    $env:LAB_DATA_MANIFEST = 'https://example.invalid/data-manifest.json'
    $env:LAB_DATA_MANIFEST_SHA256 = $script:frozenHash
    Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg -Mode Readiness } 'locally staged'
    Assert-Test ($script:calls.Count -eq 0) 'Unstaged application data reached Azure.'
    $env:LAB_DATA_MANIFEST = 'stub-frozen-manifest.json'
    foreach ($case in @(
        @('LAB_APPLICATION_NAME', ''),
        @('LAB_APPLICATION_NAME', '../unsafe'),
        @('LAB_APPLICATION_IMAGE_DIGEST', ('sha256:' + ('A' * 64))),
        @('LAB_APPLICATION_PREVIEW_STATE', 'completed'),
        @('LAB_APPLICATION_IMAGE_SOURCE', 'arbitrary-registry'),
        @('LAB_STARTUP_PURPOSE', 'attendee-release'),
        @('LAB_DATA_MANIFEST_SHA256', 'not-a-checksum')
    )) {
        $original = [Environment]::GetEnvironmentVariable($case[0])
        [Environment]::SetEnvironmentVariable($case[0], $case[1])
        Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg -Mode Readiness } 'complete harness|LAB_STARTUP_PURPOSE|trust anchor'
        Assert-Test ($script:calls.Count -eq 0) 'Malformed application pins reached Azure.'
        [Environment]::SetEnvironmentVariable($case[0], $original)
    }
    $script:passed++

    foreach ($purpose in @('synthetic-development', 'public-lab-development')) {
        foreach ($state in @('starter', 'reference')) {
            Reset-Test -Existing
            $env:LAB_APPLICATION_NAME = 'stub-app'
            $env:LAB_APPLICATION_IMAGE_DIGEST = 'sha256:' + ('a' * 64)
            $env:LAB_APPLICATION_PREVIEW_STATE = $state
            $env:LAB_STARTUP_PURPOSE = $purpose
            $env:LAB_DATA_MANIFEST = 'stub-frozen-manifest.json'
            $env:LAB_DATA_MANIFEST_SHA256 = $script:frozenHash
            $env:LAB_PYTHON_EXECUTABLE = 'python-application-stub'
            $report = Invoke-LabStartup -ResourceGroupName stub-rg -Mode Readiness
            Assert-Test ($report.infrastructure_ready -and $report.application_ready -and $report.frozen_data_verified -and
                $report.application_manifest_verified -and -not $report.data_ready -and
                -not $report.attendee_ready -and -not $report.baseline_ready) 'Pinned development application incorrectly authorized attendee data/baseline/release.'
            Assert-Test ($report.public_lab_development_only -eq ($purpose -ceq 'public-lab-development') -and
                $report.synthetic_development_only -eq ($purpose -ceq 'synthetic-development')) 'Application readiness omitted its explicit development purpose.'
            Assert-Test ($report.outputs.CALDOVA_APPLICATION_URL -ceq 'https://stub-app.example.azurecontainerapps.io' -and
                $report.outputs.CALDOVA_APPLICATION_IMAGE.EndsWith($env:LAB_APPLICATION_IMAGE_DIGEST)) 'Verified application outputs were not published.'
        }
    }
    $script:passed++

    foreach ($case in @('SimonRegistry', 'DnlRegistry')) {
        Reset-Test -Fault $(if ($case -eq 'DnlRegistry') { 'DnlRegistry' } else { '' }) -Existing
        $env:LAB_APPLICATION_NAME = 'stub-app'
        $env:LAB_APPLICATION_IMAGE_DIGEST = 'sha256:' + ('a' * 64)
        $env:LAB_APPLICATION_PREVIEW_STATE = 'reference'
        if ($case -eq 'SimonRegistry') { $env:LAB_APPLICATION_IMAGE_SOURCE = $case }
        $env:LAB_STARTUP_PURPOSE = 'public-lab-development'
        $env:LAB_DATA_MANIFEST = 'stub-frozen-manifest.json'
        $env:LAB_DATA_MANIFEST_SHA256 = $script:frozenHash
        $env:LAB_PYTHON_EXECUTABLE = 'python-application-stub'
        $report = Invoke-LabStartup -ResourceGroupName stub-rg -Mode Readiness
        Assert-Test ($report.application_ready -and -not $report.attendee_ready) 'Explicit image source did not retain development-only readiness.'
        $expected = if ($case -eq 'SimonRegistry') { 'simon.azurecr.io/lab722-stub-app@' } else { 'stubregistry-hash.azurecr.io/caldova/research-portal@' }
        Assert-Test ($report.outputs.CALDOVA_APPLICATION_IMAGE.StartsWith($expected)) 'Readiness checked the wrong immutable image source.'
    }
    $script:passed++

    foreach ($fault in @('ApplicationMissing', 'ApplicationWrongScope', 'ApplicationWrongEnvironment',
        'ApplicationWrongImage', 'ApplicationStopped', 'ApplicationFailed', 'ApplicationPrivate',
        'ApplicationWrongHost', 'ApplicationExtraContainer', 'ApplicationCheckFailure',
        'ApplicationCheckMalformed', 'ApplicationCheckWrongPin', 'ApplicationCheckWidensScope',
        'ApplicationCheckNoSources', 'ApplicationCheckTimeout', 'ApplicationCheckMissingIdentity',
        'ApplicationCheckClaimsAcceptance')) {
        Reset-Test $fault -Existing
        $env:LAB_APPLICATION_NAME = 'stub-app'
        $env:LAB_APPLICATION_IMAGE_DIGEST = 'sha256:' + ('a' * 64)
        $env:LAB_APPLICATION_PREVIEW_STATE = 'starter'
        $env:LAB_STARTUP_PURPOSE = 'public-lab-development'
        $env:LAB_DATA_MANIFEST = 'stub-frozen-manifest.json'
        $env:LAB_DATA_MANIFEST_SHA256 = $script:frozenHash
        $env:LAB_PYTHON_EXECUTABLE = 'python-application-stub'
        Assert-Fails { Invoke-LabStartup -ResourceGroupName stub-rg -Mode Readiness } 'failed|scoped resource|immutable image|not provisioned|HTTPS endpoint|malformed JSON|requested pins|timed out|identity checksum'
        if ($fault -notlike 'ApplicationCheck*') {
            Assert-Test (-not @($script:calls | Where-Object { $_.arguments[0].EndsWith('check_application.py') }).Count) 'Mismatched application scope/image reached HTTP checks.'
        }
    }
    $script:passed++

    $resolved = & {
        function Get-Command {
            [CmdletBinding()]
            param([string] $Name, [string] $CommandType)
            Assert-Test ($Name -ceq 'startup-launcher-stub') 'Unexpected launcher-resolution test command.'
            $pwsh = Microsoft.PowerShell.Core\Get-Command pwsh -CommandType Application | Select-Object -First 1
            return @(@{ Source = $pwsh.Source }, @{ Source = $pwsh.Source })
        }
        & $nativeRunner 'startup-launcher-stub' @('-NoProfile', '-NonInteractive', '-Command', 'Write-Output "launcher-ready"') 10000
    }
    Assert-Test ($resolved.exit_code -eq 0 -and $resolved.stdout.Trim() -ceq 'launcher-ready') 'Multiple native launchers were combined instead of selecting one.'
    # Exercise the actual native timeout without executing Azure CLI or contacting any service.
    Assert-Fails { & $nativeRunner 'pwsh' @('-NoProfile', '-NonInteractive', '-Command', 'Start-Sleep -Seconds 5') 100 } 'timed out'
    $script:passed++
    Write-Output "PASS: $script:passed focused startup regression groups (offline; no Azure calls)."
}
finally {
    foreach ($directory in $script:preparationDirectories) {
        Remove-Item -LiteralPath $directory -Recurse -Force
    }
    foreach ($name in $savedEnvironment.Keys) {
        if ($null -eq $savedEnvironment[$name]) {
            Remove-Item "Env:$name" -ErrorAction SilentlyContinue
        } else {
            [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name])
        }
    }
    Set-Item Function:Invoke-LabNative $nativeRunner
    Set-Item Function:Get-LabTemplate $templateReader
}
