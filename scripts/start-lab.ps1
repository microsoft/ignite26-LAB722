#requires -Version 7.2
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $ResourceGroupName,
    [string] $Region = 'westus3',
    [ValidateSet('Validate', 'Provision', 'Readiness', 'Prepare', 'PreparePrimary')] [string] $Mode = 'Validate',
    [ValidateRange(1, 3600)] [int] $TimeoutSeconds = 900
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:LabStartupRoot = Split-Path -Parent $PSScriptRoot
$script:LabOutputNames = @(
    'AZURE_CONTAINER_REGISTRY_NAME', 'FOUNDRY_ACCOUNT_NAME', 'FOUNDRY_PROJECT_NAME',
    'FOUNDRY_PROJECT_ENDPOINT', 'FOUNDRY_MODEL_DEPLOYMENT_NAME', 'EXPRESS_ENVIRONMENT_NAME',
    'SANDBOX_GROUP_NAME', 'SANDBOX_REGION',
    'AZURE_SUBSCRIPTION_ID', 'AZURE_RESOURCE_GROUP', 'AZURE_LOCATION', 'AZURE_ENV_NAME'
)

function Invoke-LabNative {
    param([string] $Executable, [string[]] $Arguments, [int] $TimeoutMilliseconds)
    $executablePath = (Get-Command $Executable -CommandType Application -ErrorAction Stop |
        Select-Object -First 1).Source
    if ([IO.Path]::GetFileName($executablePath) -ieq 'az.cmd') {
        # Azure CLI's Windows launcher uses a bundled interpreter; avoid shell argument quoting.
        $executablePath = Join-Path (Split-Path -Parent (Split-Path -Parent $executablePath)) 'python.exe'
        if (-not (Test-Path -LiteralPath $executablePath -PathType Leaf)) {
            throw 'The Azure CLI launcher is missing its bundled Python interpreter.'
        }
        $Arguments = @('-I', '-X', 'utf8', '-m', 'azure.cli') + $Arguments
    }
    $scratch = Join-Path (Join-Path $script:LabStartupRoot '.validation-workspaces') (
        'startup-native-' + [guid]::NewGuid().ToString('N'))
    [void] [IO.Directory]::CreateDirectory($scratch)
    $process = [Diagnostics.Process]::new()
    try {
        $process.StartInfo.FileName = $executablePath
        $process.StartInfo.WorkingDirectory = $script:LabStartupRoot
        $process.StartInfo.UseShellExecute = $false
        $process.StartInfo.RedirectStandardOutput = $true
        $process.StartInfo.RedirectStandardError = $true
        $process.StartInfo.StandardOutputEncoding = [Text.Encoding]::UTF8
        $process.StartInfo.StandardErrorEncoding = [Text.Encoding]::UTF8
        foreach ($name in @('TEMP', 'TMP', 'TMPDIR')) { $process.StartInfo.Environment[$name] = $scratch }
        $process.StartInfo.Environment['AZURE_CORE_COLLECT_TELEMETRY'] = '0'
        foreach ($argument in $Arguments) { $process.StartInfo.ArgumentList.Add($argument) }
        [void] $process.Start()
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        $timer = [Diagnostics.Stopwatch]::StartNew()
        while (-not $process.WaitForExit([Math]::Min(30000, [Math]::Max(
            1, $TimeoutMilliseconds - [int] $timer.ElapsedMilliseconds)))) {
            if ($timer.ElapsedMilliseconds -ge $TimeoutMilliseconds) {
                $process.Kill($true)
                [void] $process.WaitForExit(5000)
                throw 'Startup native command timed out. A submitted Azure deployment is not cancelled; inspect it before retrying.'
            }
            if ($Arguments -contains '-AuthorizeProvisioning') {
                $preparationLabel = if ($Arguments -contains '-PrimaryOnly') {
                    'Preparing only the primary Sandbox'
                } else { 'Preparing the primary, snapshot and three worker clones' }
                [Console]::Error.WriteLine("${preparationLabel}: still running ($([int] $timer.Elapsed.TotalSeconds)s).")
            }
        }
        $out = $stdout.GetAwaiter().GetResult()
        $err = $stderr.GetAwaiter().GetResult()
        if ([Text.Encoding]::UTF8.GetByteCount($out + $err) -gt 1048576) {
            throw 'Startup native command exceeded the retained-output limit.'
        }
        return @{ exit_code = $process.ExitCode; stdout = $out }
    }
    finally {
        $process.Dispose()
        Remove-Item -LiteralPath $scratch -Recurse -Force
    }
}

function Get-LabRemainingMilliseconds {
    param([hashtable] $Context)
    $remaining = [Math]::Floor($Context.TimeoutSeconds * 1000 - $Context.Timer.Elapsed.TotalMilliseconds)
    if ($remaining -le 0) {
        throw 'Startup timed out. No deployment cancellation, deletion or automatic retry was performed.'
    }
    return [int] $remaining
}

function Invoke-LabAz {
    param([hashtable] $Context, [string[]] $Arguments, [switch] $GroupScoped, [switch] $NoOutput)
    $format = if ($NoOutput) { 'none' } else { 'json' }
    $scope = @('--subscription', $Context.Subscription, '--output', $format, '--only-show-errors')
    if ($GroupScoped) { $scope += @('--resource-group', $Context.ResourceGroup) }
    $result = Invoke-LabNative 'az' ($Arguments + $scope) (
        [Math]::Min(60000, (Get-LabRemainingMilliseconds $Context)))
    if ($result.exit_code -ne 0) {
        throw "Azure CLI $($Arguments[0..([Math]::Min(2, $Arguments.Count - 1))] -join ' ') failed (exit $($result.exit_code)). Native diagnostics withheld; inspect the scoped operation before retrying."
    }
    [void] (Get-LabRemainingMilliseconds $Context)
    if ($NoOutput) { return }
    try {
        $document = ConvertFrom-Json -InputObject $result.stdout -AsHashtable -NoEnumerate -ErrorAction Stop
    }
    catch { throw 'Azure CLI returned malformed JSON; startup cannot establish readiness.' }
    [void] (Get-LabRemainingMilliseconds $Context)
    return ,$document
}

function Get-LabTemplate {
    $path = Join-Path (Join-Path (Join-Path $script:LabStartupRoot 'infra') 'skillable') 'azuredeploy.json'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw 'Compiled infra/skillable/azuredeploy.json is missing. Compile it separately before startup.'
    }
    try { $template = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop }
    catch { throw 'Compiled infra/skillable/azuredeploy.json is malformed.' }
    if ($template -isnot [Collections.IDictionary] -or
        $template['$schema'] -notmatch '/deploymentTemplate\.json#$' -or
        $template['parameters'] -isnot [Collections.IDictionary] -or
        -not $template.parameters.Contains('location') -or -not $template.parameters.Contains('environmentName')) {
        throw 'Startup requires the compiled resource-group-scoped LAB722 template.'
    }
    return @{ Path = $path; Parameters = $template.parameters }
}

function Assert-LabEnvironmentName {
    param($Name)
    if ($Name -isnot [string] -or $Name -cnotmatch '^[A-Za-z0-9][A-Za-z0-9._-]{1,31}$') {
        throw 'LAB722 scope has a missing or invalid azd-env-name; maintainer review is required.'
    }
}

function Get-LabNormalizedLocation {
    param($Location)
    if ($Location -isnot [string]) { return $null }
    $normalized = [regex]::Replace($Location, '\s', '').ToLowerInvariant()
    if ($normalized -cnotmatch '^[a-z0-9]{1,30}$') { return $null }
    return $normalized
}

function Get-LabScope {
    param([hashtable] $Context)
    $account = Invoke-LabAz $Context @('account', 'show', '--query', '{id:id,state:state}')
    if ($account -isnot [Collections.IDictionary] -or $account.id -ine $Context.Subscription -or
        $account.state -cne 'Enabled') {
        throw 'Azure account context does not match the enabled harness subscription.'
    }
    $group = Invoke-LabAz $Context @('group', 'show', '--query',
        '{id:id,name:name,location:location,tags:tags}') -GroupScoped
    if ($group -isnot [Collections.IDictionary] -or $group['id'] -ine $Context.GroupId -or
        $group['name'] -ine $Context.ResourceGroup) {
        throw 'Existing resource group does not match the requested subscription and name.'
    }
    $metadataLocation = Get-LabNormalizedLocation $group['location']
    if ($null -eq $metadataLocation) {
        throw 'Existing resource group is missing a valid metadata location.'
    }
    $inventory = Invoke-LabAz $Context @('resource', 'list', '--query',
        '[].{id:id,type:type,name:name,location:location,tags:tags}') -GroupScoped
    if ($inventory -isnot [array]) {
        throw 'Azure CLI returned malformed scoped resource inventory.'
    }
    $names = [Collections.Generic.List[string]]::new()
    $groupTags = if ($group['tags'] -is [Collections.IDictionary]) { $group.tags } else { @{} }
    $labResources = [Collections.Generic.List[object]]::new()
    foreach ($resource in $inventory) {
        if ($resource -isnot [Collections.IDictionary] -or
            -not ([string] $resource['id']).StartsWith($Context.GroupId + '/providers/', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Resource inventory metadata does not match the requested scope.'
        }
        $tags = $resource['tags']
        if ($tags -isnot [Collections.IDictionary] -or $tags['lab'] -ine 'LAB722') { continue }
        if ((Get-LabNormalizedLocation $resource['location']) -cne $Context.Region) {
            throw 'Tagged LAB722 resource metadata does not match the requested region.'
        }
        Assert-LabEnvironmentName $tags['azd-env-name']
        $names.Add($tags['azd-env-name'])
        $labResources.Add($resource)
    }
    if (($groupTags['lab'] -ieq 'LAB722' -or $labResources.Count -gt 0) -and
        $null -ne $groupTags['azd-env-name']) {
        Assert-LabEnvironmentName $groupTags['azd-env-name']
        $names.Add($groupTags['azd-env-name'])
    }
    $unique = @($names | Sort-Object -Unique -CaseSensitive)
    if ($unique.Count -gt 1) { throw 'Conflicting LAB722 azd-env-name tags; startup will not choose or rename an environment.' }
    $deployments = Invoke-LabAz $Context @('deployment', 'group', 'list', '--query',
        '[].{id:id,name:name,state:properties.provisioningState,timestamp:properties.timestamp}') -GroupScoped
    if ($deployments -isnot [array]) { throw 'Azure CLI returned malformed deployment inventory.' }
    foreach ($deployment in $deployments) {
        if ($deployment -isnot [Collections.IDictionary] -or
            $deployment.name -notmatch '^[A-Za-z0-9][A-Za-z0-9._()-]{0,63}$' -or
            $deployment.id -ine "$($Context.GroupId)/providers/Microsoft.Resources/deployments/$($deployment.name)") {
            throw 'Deployment metadata does not match the explicitly supplied resource group.'
        }
    }
    return @{
        EnvironmentName = $(if ($unique.Count) { $unique[0] } else { $null })
        ResourceCount = $inventory.Count; LabResourceCount = $labResources.Count
        AllocationMarker = ($groupTags['lab'] -ieq 'LAB722' -or -not [string]::IsNullOrEmpty($groupTags['azd-env-name']))
        Deployments = $deployments; GroupMetadataLocation = $metadataLocation
    }
}

function Get-LabDeployment {
    param([hashtable] $Context, [string] $Name)
    # CLI SDKs normalize output-key casing. Parse that dictionary, then emit only allowlisted values.
    $query = '{id:id,name:name,properties:{provisioningState:properties.provisioningState,parameters:{location:properties.parameters.location,environmentName:properties.parameters.environmentName},outputs:properties.outputs}}'
    $deployment = Invoke-LabAz $Context @('deployment', 'group', 'show', '--name', $Name, '--query', $query) -GroupScoped
    if ($deployment -isnot [Collections.IDictionary] -or
        $deployment.id -ine "$($Context.GroupId)/providers/Microsoft.Resources/deployments/$Name" -or
        $deployment.name -cne $Name -or $deployment.properties -isnot [Collections.IDictionary]) {
        throw 'Deployment response does not match the requested resource-group scope.'
    }
    if ($deployment.properties['outputs'] -is [Collections.IDictionary]) {
        $rawOutputs = $deployment.properties.outputs
        $safeOutputs = @{}
        foreach ($name in $script:LabOutputNames) {
            $matches = @($rawOutputs.Keys | Where-Object { $_ -ieq $name })
            if ($matches.Count -gt 1) { throw "Deployment contains ambiguous output keys for '$name'." }
            if ($matches.Count -eq 1) { $safeOutputs[$name] = $rawOutputs[$matches[0]] }
        }
        $deployment.properties['outputs'] = $safeOutputs
    }
    return $deployment
}

function Wait-LabDeployment {
    param([hashtable] $Context, [string] $Name, [hashtable] $InitialDeployment)
    $deployment = $InitialDeployment
    while ($true) {
        if ($null -eq $deployment) { $deployment = Get-LabDeployment $Context $Name }
        $state = $deployment.properties['provisioningState']
        if ($state -ceq 'Succeeded') { return $deployment }
        if ($state -cnotin @('Accepted', 'Running', 'Creating', 'Updating')) {
            throw "Deployment '$Name' is not successful (state '$state'). Inspect it; no retry or cleanup was performed."
        }
        Start-Sleep -Milliseconds ([Math]::Min(5000, (Get-LabRemainingMilliseconds $Context)))
        $deployment = $null
    }
}

function Get-LabAuthoritativeOutputs {
    param([hashtable] $Context, [hashtable] $Scope, [hashtable] $Deployment)
    $properties = $Deployment.properties
    if ($properties['outputs'] -isnot [Collections.IDictionary] -or
        $properties['parameters'] -isnot [Collections.IDictionary]) {
        throw 'Successful deployment is missing authoritative outputs or parameter metadata.'
    }
    $values = [ordered] @{}
    foreach ($name in $script:LabOutputNames) {
        $entry = $properties.outputs[$name]
        if ($null -eq $entry -and $name -in $script:LabOutputNames[8..11]) { continue }
        if ($entry -isnot [Collections.IDictionary] -or $entry['type'] -ine 'String' -or
            $entry['value'] -isnot [string] -or [string]::IsNullOrWhiteSpace($entry.value)) {
            throw "Successful deployment has a missing or malformed required output '$name'."
        }
        $values[$name] = $entry.value
    }
    $environment = $values['AZURE_ENV_NAME']
    $parameterEnvironment = $properties.parameters['environmentName']
    if ($null -eq $environment -and $parameterEnvironment -is [Collections.IDictionary]) {
        $environment = $parameterEnvironment['value']
    }
    Assert-LabEnvironmentName $environment
    if (($null -ne $Scope.EnvironmentName -and $environment -cne $Scope.EnvironmentName) -or
        ($parameterEnvironment -is [Collections.IDictionary] -and $parameterEnvironment['value'] -cne $environment)) {
        throw 'Deployment outputs disagree with the retained LAB722 environment name.'
    }
    foreach ($pair in @(
        @('AZURE_SUBSCRIPTION_ID', $Context.Subscription), @('AZURE_RESOURCE_GROUP', $Context.ResourceGroup),
        @('AZURE_LOCATION', $Context.Region), @('AZURE_ENV_NAME', $environment)
    )) {
        $actual = $values[$pair[0]]
        if ($pair[0] -eq 'AZURE_LOCATION') { $actual = Get-LabNormalizedLocation $actual }
        if ($values.Contains($pair[0]) -and $actual -ine $pair[1]) {
            throw "Deployment output '$($pair[0])' does not match the requested context."
        }
        # Older azd roots lack these context outputs; their checked ARM ID/parameters establish scope.
        $values[$pair[0]] = $pair[1]
    }
    $parameterLocation = $properties.parameters['location']
    if ((Get-LabNormalizedLocation $values['SANDBOX_REGION']) -cne $Context.Region -or
        ($parameterLocation -is [Collections.IDictionary] -and
            (Get-LabNormalizedLocation $parameterLocation['value']) -cne $Context.Region)) {
        throw 'Deployment location does not match the requested region.'
    }
    foreach ($name in $script:LabOutputNames[0..6] | Where-Object { $_ -ne 'FOUNDRY_PROJECT_ENDPOINT' }) {
        if ($values[$name] -cnotmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$') {
            throw "Deployment output '$name' is not a resource name."
        }
    }
    $expectedEndpoint = "https://$($values['FOUNDRY_ACCOUNT_NAME']).services.ai.azure.com/api/projects/$($values['FOUNDRY_PROJECT_NAME'])"
    if ($values['FOUNDRY_PROJECT_ENDPOINT'].TrimEnd('/') -cne $expectedEndpoint) {
        throw 'Foundry project endpoint does not match the authoritative account and project names.'
    }
    return $values
}

function Assert-LabCurrentResources {
    param([hashtable] $Context, [Collections.IDictionary] $Outputs)
    $account = $Outputs['FOUNDRY_ACCOUNT_NAME']
    $resources = @(
        @{ Type = 'Microsoft.ContainerRegistry/registries'; Name = $Outputs['AZURE_CONTAINER_REGISTRY_NAME']
            Path = "Microsoft.ContainerRegistry/registries/$($Outputs['AZURE_CONTAINER_REGISTRY_NAME'])"; Version = '2023-07-01'; CheckLocation = $true },
        @{ Type = 'Microsoft.CognitiveServices/accounts'; Name = $account
            Path = "Microsoft.CognitiveServices/accounts/$account"; Version = '2025-06-01'; CheckLocation = $true },
        @{ Type = 'Microsoft.CognitiveServices/accounts/projects'; Name = $Outputs['FOUNDRY_PROJECT_NAME']
            Path = "Microsoft.CognitiveServices/accounts/$account/projects/$($Outputs['FOUNDRY_PROJECT_NAME'])"
            ParentName = $account; Version = '2025-06-01'; CheckLocation = $true },
        @{ Type = 'Microsoft.CognitiveServices/accounts/deployments'; Name = $Outputs['FOUNDRY_MODEL_DEPLOYMENT_NAME']
            Path = "Microsoft.CognitiveServices/accounts/$account/deployments/$($Outputs['FOUNDRY_MODEL_DEPLOYMENT_NAME'])"
            ParentName = $account; Version = '2025-06-01'; CheckLocation = $false },
        @{ Type = 'Microsoft.App/managedEnvironments'; Name = $Outputs['EXPRESS_ENVIRONMENT_NAME']
            Path = "Microsoft.App/managedEnvironments/$($Outputs['EXPRESS_ENVIRONMENT_NAME'])"; Version = '2026-03-02-preview'; CheckLocation = $true },
        @{ Type = 'Microsoft.App/sandboxGroups'; Name = $Outputs['SANDBOX_GROUP_NAME']
            Path = "Microsoft.App/sandboxGroups/$($Outputs['SANDBOX_GROUP_NAME'])"; Version = '2026-02-01-preview'; CheckLocation = $true }
    )
    foreach ($expected in $resources) {
        $id = "$($Context.GroupId)/providers/$($expected.Path)"
        # --ids already contains the checked subscription/group; do not mix other resource-ID arguments.
        $current = Invoke-LabAz $Context @('resource', 'show', '--ids', $id, '--api-version', $expected.Version,
            '--query', '{id:id,type:type,name:name,state:properties.provisioningState,location:location}')
        $validNames = @($expected.Name)
        if ($expected.ContainsKey('ParentName')) { $validNames += "$($expected.ParentName)/$($expected.Name)" }
        if ($current -isnot [Collections.IDictionary] -or $current['id'] -ine $id -or
            $current['type'] -ine $expected.Type -or $current['name'] -notin $validNames) {
            throw "Current resource '$id' returned a mismatched scoped ID, type or name."
        }
        if ($expected.CheckLocation -and (Get-LabNormalizedLocation $current['location']) -cne $Context.Region) {
            throw "Current resource '$id' does not match the requested workload region."
        }
        if ($current['state'] -isnot [string] -or [string]::IsNullOrWhiteSpace($current['state'])) {
            throw "Current resource '$id' omits properties.provisioningState at API '$($expected.Version)'; control-plane readiness is uncertain."
        }
        if ($current['state'] -cne 'Succeeded') {
            throw "Current resource '$id' is not healthy (provisioningState '$($current['state'])'). Historical deployment success is not readiness."
        }
    }
}

function Get-LabPreparationConfiguration {
    param([string] $Operation = 'Prepare')
    if ($env:LAB_STARTUP_PURPOSE -cnotin @('synthetic-development', 'public-lab-development')) {
        throw "$Operation requires harness LAB_STARTUP_PURPOSE=synthetic-development or public-lab-development; neither authorizes attendee release."
    }
    if ([string]::IsNullOrWhiteSpace($env:LAB_DATA_MANIFEST) -or
        $env:LAB_DATA_MANIFEST_SHA256 -cnotmatch '^[0-9a-f]{64}$') {
        throw "$Operation requires harness LAB_DATA_MANIFEST and its lowercase LAB_DATA_MANIFEST_SHA256 trust anchor."
    }
    if ($env:LAB_DATA_MANIFEST -match '^[A-Za-z][A-Za-z0-9+.-]*://') {
        $uri = $null
        if (-not [uri]::TryCreate($env:LAB_DATA_MANIFEST, [UriKind]::Absolute, [ref] $uri) -or
            $uri.Scheme -cne 'https' -or $uri.UserInfo -or $uri.Query -or $uri.Fragment) {
            throw 'Prepare requires a credential-free HTTPS manifest URL without query or fragment; no signed tokens enter native arguments.'
        }
    }
    return @{
        Purpose = $env:LAB_STARTUP_PURPOSE
        Manifest = $env:LAB_DATA_MANIFEST; ManifestSha256 = $env:LAB_DATA_MANIFEST_SHA256
        Python = $(if ([string]::IsNullOrWhiteSpace($env:LAB_PYTHON_EXECUTABLE)) { 'python' } else { $env:LAB_PYTHON_EXECUTABLE })
    }
}

function Get-LabApplicationConfiguration {
    $settings = @('LAB_APPLICATION_NAME', 'LAB_APPLICATION_IMAGE_DIGEST', 'LAB_APPLICATION_PREVIEW_STATE',
        'LAB_APPLICATION_IMAGE_SOURCE', 'LAB_APPLICATION_ENVIRONMENT_SOURCE')
    if (-not @($settings | Where-Object { $null -ne [Environment]::GetEnvironmentVariable($_) }).Count) {
        return $null
    }
    $source = if ($null -eq $env:LAB_APPLICATION_IMAGE_SOURCE) { 'LabRegistry' } else { $env:LAB_APPLICATION_IMAGE_SOURCE }
    $environmentSource = if ($null -eq $env:LAB_APPLICATION_ENVIRONMENT_SOURCE) {
        'Allocated'
    } else { $env:LAB_APPLICATION_ENVIRONMENT_SOURCE }
    if ($source -cnotin @('LabRegistry', 'ReferenceRegistry', 'SimonRegistry') -or
        $environmentSource -cnotin @('Allocated', 'Portal') -or
        $env:LAB_APPLICATION_NAME -cnotmatch '^[a-z][a-z0-9-]{0,30}[a-z0-9]$' -or
        $env:LAB_APPLICATION_IMAGE_DIGEST -cnotmatch '^sha256:[0-9a-f]{64}$' -or
        $env:LAB_APPLICATION_PREVIEW_STATE -cnotin @('starter', 'reference')) {
        throw 'Application readiness requires the complete harness LAB_APPLICATION_NAME, lowercase LAB_APPLICATION_IMAGE_DIGEST and LAB_APPLICATION_PREVIEW_STATE=starter or reference.'
    }
    $data = Get-LabPreparationConfiguration -Operation 'Application readiness'
    if ($data.Manifest -match '^[A-Za-z][A-Za-z0-9+.-]*://') {
        throw 'Application readiness requires a locally staged pinned manifest and its frozen files, not a remote manifest URL.'
    }
    return $data + @{
        Name = $env:LAB_APPLICATION_NAME; Digest = $env:LAB_APPLICATION_IMAGE_DIGEST
        PreviewState = $env:LAB_APPLICATION_PREVIEW_STATE; ImageSource = $source
        EnvironmentSource = $environmentSource
    }
}

function Get-LabApplicationReadiness {
    param([hashtable] $Context, [Collections.IDictionary] $Outputs, [hashtable] $Configuration)
    $id = "$($Context.GroupId)/providers/Microsoft.App/containerApps/$($Configuration.Name)"
    $query = '{id:id,type:type,name:name,location:location,state:properties.provisioningState,running:properties.runningStatus,environmentId:properties.environmentId,ingress:{fqdn:properties.configuration.ingress.fqdn,external:properties.configuration.ingress.external,targetPort:properties.configuration.ingress.targetPort},containers:properties.template.containers[].{name:name,image:image}}'
    $app = Invoke-LabAz $Context @('resource', 'show', '--ids', $id, '--api-version', '2025-10-02-preview',
        '--query', $query)
    $environmentId = "$($Context.GroupId)/providers/Microsoft.App/managedEnvironments/$($Outputs['EXPRESS_ENVIRONMENT_NAME'])"
    $applicationRegion = $Context.Region
    if ($Configuration['EnvironmentSource'] -ceq 'Portal') {
        $prefix = "$($Context.GroupId)/providers/Microsoft.App/managedEnvironments/"
        if ($app -isnot [Collections.IDictionary] -or $app['environmentId'] -isnot [string] -or
            -not $app.environmentId.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or
            $app.environmentId.Substring($prefix.Length) -cnotmatch '^[A-Za-z0-9][A-Za-z0-9-]{0,59}$') {
            throw 'The portal application must use an Express environment in the allocated subscription and resource group.'
        }
        $environmentId = $app.environmentId
        $environment = Invoke-LabAz $Context @('resource', 'show', '--ids', $environmentId,
            '--api-version', '2026-03-02-preview',
            '--query', '{id:id,type:type,name:name,location:location,state:properties.provisioningState,mode:properties.environmentMode}')
        if ($environment -isnot [Collections.IDictionary] -or $environment['id'] -ine $environmentId -or
            $environment['type'] -ine 'Microsoft.App/managedEnvironments' -or
            $environment['state'] -cne 'Succeeded' -or $environment['mode'] -cne 'Express' -or
            $null -eq (Get-LabNormalizedLocation $environment['location'])) {
            throw 'The portal application environment is not a healthy same-scope Express environment with a valid region.'
        }
        $applicationRegion = Get-LabNormalizedLocation $environment['location']
    }
    if ($Configuration['ImageSource'] -ceq 'ReferenceRegistry') {
        $image = "acateam.azurecr.io/lab722/caldova-research@$($Configuration.Digest)"
    }
    elseif ($Configuration['ImageSource'] -ceq 'SimonRegistry') {
        $image = "simon.azurecr.io/lab722-$($Configuration.Name)@$($Configuration.Digest)"
    }
    else {
        $registryName = $Outputs['AZURE_CONTAINER_REGISTRY_NAME']
        $registryId = "$($Context.GroupId)/providers/Microsoft.ContainerRegistry/registries/$registryName"
        $registry = Invoke-LabAz $Context @('resource', 'show', '--ids', $registryId, '--api-version', '2023-07-01',
            '--query', '{id:id,loginServer:properties.loginServer}')
        if ($registry -isnot [Collections.IDictionary] -or $registry['id'] -ine $registryId -or
            $registry['loginServer'] -cnotmatch "^$([regex]::Escape($registryName))(?:-[a-z0-9]+)?\.azurecr\.io$") {
            throw 'Application readiness could not verify the allocated registry login server.'
        }
        $image = "$($registry.loginServer)/caldova/research-portal@$($Configuration.Digest)"
    }
    if ($app -isnot [Collections.IDictionary] -or $app['id'] -ine $id -or
        $app['type'] -ine 'Microsoft.App/containerApps' -or $app['name'] -cne $Configuration.Name -or
        (Get-LabNormalizedLocation $app['location']) -cne $applicationRegion -or
        $app['environmentId'] -ine $environmentId) {
        throw 'Application metadata does not match the requested scoped resource and Express environment.'
    }
    if ($app['state'] -cne 'Succeeded' -or $app['running'] -cne 'Running') {
        throw 'The pinned application is not provisioned and running; no application readiness is implied.'
    }
    if ($app['containers'] -isnot [array] -or $app.containers.Count -ne 1 -or
        $app.containers[0] -isnot [Collections.IDictionary] -or $app.containers[0]['image'] -cne $image) {
        throw 'The application does not run the harness-pinned immutable image from the scoped registry.'
    }
    $ingress = $app['ingress']
    if ($ingress -isnot [Collections.IDictionary] -or $ingress['external'] -isnot [bool] -or
        -not $ingress.external -or $ingress['targetPort'] -ne 8080 -or
        $ingress['fqdn'] -isnot [string] -or
        $ingress.fqdn -cnotmatch '^[a-z0-9][a-z0-9.-]*\.azurecontainerapps\.io$') {
        throw 'The pinned application lacks the expected public HTTPS endpoint on port 8080.'
    }
    $url = "https://$($ingress.fqdn)"
    $remaining = [Math]::Min(90000, (Get-LabRemainingMilliseconds $Context))
    $seconds = ([Math]::Max(0.001, ($remaining - 100) / 1000)).ToString([Globalization.CultureInfo]::InvariantCulture)
    $verification = Invoke-LabNative $Configuration.Python @(
        (Join-Path $script:LabStartupRoot 'src\workers\check_application.py'),
        '--manifest', $Configuration.Manifest, '--manifest-sha256', $Configuration.ManifestSha256,
        '--purpose', $Configuration.Purpose, '--url', $url,
        '--preview-state', $Configuration.PreviewState, '--timeout-seconds', $seconds
    ) $remaining
    if ($verification.exit_code -ne 0) {
        throw "Pinned application/data verification failed (exit $($verification.exit_code)); no readiness, deployment, retry or source substitution was performed."
    }
    try { $receipt = ConvertFrom-Json -InputObject $verification.stdout -AsHashtable -ErrorAction Stop }
    catch { throw 'Application verification returned malformed JSON; no application readiness is established.' }
    if ($receipt -isnot [Collections.IDictionary] -or $receipt['identity'] -isnot [Collections.IDictionary] -or
        $receipt['schema_version'] -cne '1.0' -or
        $receipt['status'] -cne 'pinned-development-application-ready' -or $receipt['url'] -cne $url -or
        $receipt['preview_state'] -cne $Configuration.PreviewState -or
        $receipt.identity['data_manifest_sha256'] -cne $Configuration.ManifestSha256 -or
        $receipt.identity['acceptance_purpose'] -cne $Configuration.Purpose -or
        $receipt.identity['dataset_kind'] -cne $(if ($Configuration.Purpose -ceq 'public-lab-development') { 'reviewed-public' } else { 'synthetic-development' }) -or
        $receipt['live_manifest_verified'] -isnot [bool] -or -not $receipt.live_manifest_verified -or
        $receipt['local_frozen_artifacts_verified'] -isnot [bool] -or -not $receipt.local_frozen_artifacts_verified -or
        $receipt['sample_state_verified'] -isnot [bool] -or -not $receipt.sample_state_verified -or
        ($Configuration.Purpose -ceq 'public-lab-development' -and
            ($receipt['live_original_sources_verified'] -isnot [bool] -or -not $receipt.live_original_sources_verified)) -or
        $receipt['release_approved'] -isnot [bool] -or $receipt.release_approved -or
        $receipt['full_functional_acceptance_rerun'] -isnot [bool] -or $receipt.full_functional_acceptance_rerun -or
        $receipt['attendee_ready'] -isnot [bool] -or $receipt.attendee_ready) {
        throw 'Application verification changed its requested pins, checks or development-only readiness scope.'
    }
    $identityFields = @('database_sha256', 'logical_sha256')
    if ($Configuration.Purpose -ceq 'public-lab-development') {
        $identityFields += @('source_records_sha256', 'pipeline_source_sha256', 'source_use_sha256')
    }
    foreach ($field in $identityFields) {
        if ($receipt.identity[$field] -cnotmatch '^[0-9a-f]{64}$') {
            throw 'Application verification omitted a required frozen identity checksum.'
        }
    }
    [void] (Get-LabRemainingMilliseconds $Context)
    return $receipt + @{
        resource_id = $id; image = $image
        express_environment_name = $environmentId.Split('/')[-1]
        region = $applicationRegion
    }
}

function Invoke-LabBaselinePreparation {
    param([hashtable] $Context, [Collections.IDictionary] $Outputs, [hashtable] $Configuration)
    $directory = Join-Path (Join-Path $script:LabStartupRoot '.build-contexts') (
        'startup-' + [guid]::NewGuid().ToString('N'))
    $outputDirectory = Join-Path $directory 'baseline'
    $sourceDirectory = Join-Path $directory 'source'
    $helper = Join-Path (Join-Path $script:LabStartupRoot 'scripts') 'prepare-worker-baseline.ps1'
    $remaining = Get-LabRemainingMilliseconds $Context
    $arguments = @(
        '-NoProfile', '-NonInteractive', '-File', $helper, '-Mode', 'Provision',
        '-SubscriptionId', $Context.Subscription, '-ResourceGroup', $Context.ResourceGroup,
        '-Region', $Context.Region, '-GroupName', $Outputs['SANDBOX_GROUP_NAME'],
        '-OutputDirectory', $outputDirectory, '-SourceContextDirectory', $sourceDirectory,
        '-FrozenManifest', $Configuration.Manifest, '-FrozenManifestSha256', $Configuration.ManifestSha256,
        '-Purpose', $Configuration.Purpose,
        '-PythonExecutable', $Configuration.Python, '-AuthorizeProvisioning', '-AsJson'
    )
    $primaryOnly = [bool] $Configuration['PrimaryOnly']
    if ($primaryOnly) { $arguments += '-PrimaryOnly' }
    $result = Invoke-LabNative 'pwsh' $arguments $remaining
    if ($result.exit_code -ne 0) {
        throw "Worker preparation failed (exit $($result.exit_code)). No attendee readiness or automatic retry is implied. Inspect the scoped operations and '$directory' before retrying."
    }
    try {
        $receipt = ConvertFrom-Json -InputObject $result.stdout -AsHashtable -ErrorAction Stop
    }
    catch { throw 'Worker preparation returned malformed JSON; no baseline readiness can be established.' }
    $artifacts = if ($primaryOnly) {
        @(@('descriptor', 'primary-descriptor.json'), @('manifest', 'data-manifest.json'))
    } else {
        @(@('descriptor', 'baseline-descriptor.json'), @('bindings', 'bindings.json'), @('manifest', 'data-manifest.json'))
    }
    foreach ($pair in $artifacts) {
        $expected = Join-Path $outputDirectory $pair[1]
        if ($receipt -isnot [Collections.IDictionary] -or $receipt[$pair[0]] -ine $expected -or
            -not (Test-Path -LiteralPath $expected -PathType Leaf)) {
            throw 'Worker preparation did not publish the expected project-local controller artifacts.'
        }
    }
    $descriptor = Get-Content -LiteralPath $receipt.descriptor -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    if ($descriptor -isnot [Collections.IDictionary] -or $descriptor['scope'] -isnot [Collections.IDictionary] -or
        $descriptor['frozen_identity'] -isnot [Collections.IDictionary] -or $descriptor['mode'] -cne 'Provision' -or
        $descriptor.scope['subscription'] -ine $Context.Subscription -or
        $descriptor.scope['resource_group'] -ine $Context.ResourceGroup -or
        $descriptor.scope['region'] -cne $Context.Region -or
        $descriptor.scope['group'] -cne $Outputs['SANDBOX_GROUP_NAME'] -or
        $descriptor['dataset_kind'] -cne $(if ($Configuration.Purpose -eq 'public-lab-development') { 'reviewed-public' } else { 'synthetic-development' }) -or
        ($Configuration.Purpose -eq 'public-lab-development' -and $descriptor['acceptance_purpose'] -cne $Configuration.Purpose) -or
        $descriptor.frozen_identity['data_manifest_sha256'] -cne $Configuration.ManifestSha256 -or
        (Get-FileHash -LiteralPath $receipt.manifest -Algorithm SHA256).Hash.ToLowerInvariant() -cne $Configuration.ManifestSha256 -or
        $receipt['primary_id'] -cne $descriptor['primary_id'] -or
        ($primaryOnly -and ($receipt['phase'] -cne 'primary-prepared' -or
            $descriptor['phase'] -cne 'primary-prepared' -or
            $receipt['disk_id'] -cne $descriptor['disk_id'] -or
            $receipt['descriptor_sha256'] -cne (
                Get-FileHash -LiteralPath $receipt.descriptor -Algorithm SHA256
            ).Hash.ToLowerInvariant())) -or
        (-not $primaryOnly -and $receipt['snapshot_id'] -cne $descriptor['snapshot_id'])) {
        throw 'Worker preparation artifacts do not match the requested scope and pinned frozen dataset.'
    }
    if ($Configuration.Purpose -eq 'public-lab-development') {
        $identityResult = Invoke-LabNative $Configuration.Python @(
            (Join-Path $script:LabStartupRoot 'src\workers\frozen_contract.py'),
            '--manifest', $receipt.manifest, '--manifest-sha256', $Configuration.ManifestSha256,
            '--purpose', $Configuration.Purpose
        ) (Get-LabRemainingMilliseconds $Context)
        if ($identityResult.exit_code -ne 0) { throw 'Public preparation manifest identity verification failed.' }
        try { $identity = $identityResult.stdout | ConvertFrom-Json -AsHashtable -ErrorAction Stop }
        catch { throw 'Public preparation identity returned malformed JSON.' }
        foreach ($field in @('database_sha256', 'logical_sha256', 'source_records_sha256',
            'pipeline_source_sha256', 'source_use_sha256')) {
            if ($identity -isnot [Collections.IDictionary] -or
                $identity[$field] -cnotmatch '^[0-9a-f]{64}$' -or
                $descriptor.frozen_identity[$field] -cne $identity[$field]) {
                throw 'Public preparation original-source, database, logical or decision identity changed.'
            }
        }
        $manifest = Get-Content -LiteralPath $receipt.manifest -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
        $public = $manifest['public_extract']
        $approval = if ($public -is [Collections.IDictionary]) { $public['source_use'] } else { $null }
        if ($manifest['dataset_kind'] -cne 'reviewed-public' -or
            $approval -isnot [Collections.IDictionary] -or
            $approval['scope'] -cne 'project-owner-selected-public-lab-use' -or
            $manifest['review']['approved_by'] -cne $approval['approved_by'] -or
            $manifest['review']['approved_at'] -cne $approval['approved_at'] -or
            $manifest['source_records']['sha256'] -cne $descriptor.frozen_identity['source_records_sha256'] -or
            $manifest['pipeline_source']['sha256'] -cne $descriptor.frozen_identity['pipeline_source_sha256'] -or
            $descriptor.frozen_identity['source_use_sha256'] -cnotmatch '^[0-9a-f]{64}$' -or
            @('expert_audit_performed', 'publication_authorized', 'live_replacement_authorized', 'attendee_release_approved' |
                Where-Object { $approval[$_] -isnot [bool] -or $approval[$_] }).Count) {
            throw 'Public preparation did not preserve the original-source pins and restricted source-use decision.'
        }
    }
    [void] (Get-LabRemainingMilliseconds $Context)
    return $receipt
}

function Invoke-LabStartup {
    param(
        [string] $ResourceGroupName, [string] $Region = 'westus3',
        [ValidateSet('Validate', 'Provision', 'Readiness', 'Prepare', 'PreparePrimary')] [string] $Mode = 'Validate',
        [ValidateRange(1, 3600)] [int] $TimeoutSeconds = 900
    )
    $subscription = [guid]::Empty
    if (-not [guid]::TryParseExact($env:AZURE_SUBSCRIPTION_ID, 'D', [ref] $subscription) -or $subscription -eq [guid]::Empty) {
        throw 'Harness AZURE_SUBSCRIPTION_ID must be an explicit nonempty GUID; no CLI default is used.'
    }
    if ($ResourceGroupName -notmatch '^[A-Za-z0-9][A-Za-z0-9._()-]{0,89}$' -or $ResourceGroupName.EndsWith('.') -or
        $Region -cnotmatch '^[a-z0-9]{1,30}$') {
        throw 'ResourceGroupName and Region must be valid explicit Azure scope values.'
    }
    $parameters = @("location=$Region")
    $principalId = $env:LAB_USER_PRINCIPAL_ID
    $principalType = $env:LAB_USER_PRINCIPAL_TYPE
    if ($null -ne $principalId -or $null -ne $principalType) {
        $principal = [guid]::Empty
        if (-not [guid]::TryParseExact($principalId, 'D', [ref] $principal) -or $principal -eq [guid]::Empty -or
            $principalType -cnotin @('User', 'Group', 'ServicePrincipal')) {
            throw 'Optional harness identity requires both a nonempty LAB_USER_PRINCIPAL_ID GUID and explicit LAB_USER_PRINCIPAL_TYPE.'
        }
        $parameters += @("labUserPrincipalId=$principal", "labUserPrincipalType=$principalType")
    }
    $preparation = if ($Mode -in @('Prepare', 'PreparePrimary')) {
        (Get-LabPreparationConfiguration -Operation $Mode) + @{ PrimaryOnly = ($Mode -eq 'PreparePrimary') }
    } else { $null }
    $applicationConfiguration = if ($Mode -eq 'Readiness') { Get-LabApplicationConfiguration } else { $null }
    $context = @{
        Subscription = $subscription.ToString(); ResourceGroup = $ResourceGroupName; Region = $Region
        GroupId = "/subscriptions/$subscription/resourceGroups/$ResourceGroupName"
        Timer = [Diagnostics.Stopwatch]::StartNew(); TimeoutSeconds = $TimeoutSeconds
    }
    $template = Get-LabTemplate
    $scope = Get-LabScope $context
    $pending = @(
        'Pinned application readiness was not requested; application provisioning is not performed by this entry point.',
        'Reviewed data and worker starter/baseline preparation have not been verified in this startup run.',
        'Exact attendee authorization and harness trigger/output adapter are unverified.',
        'Effective Foundry data-plane access, inference and event capacity are not verified by these control-plane checks.'
    )
    if ($Mode -eq 'Provision' -and
        ($scope.ResourceCount -ne 0 -or $scope.AllocationMarker -or $scope.Deployments.Count -ne 0)) {
        throw 'Provision refuses a nonempty or previously allocated scope. Retained LAB722 resources and capacity will not be updated; use Validate or Readiness.'
    }
    if ($Mode -notin @('Readiness', 'Prepare', 'PreparePrimary')) {
        if ($null -ne $scope.EnvironmentName) {
            $parameters += "environmentName=$($scope.EnvironmentName)"
        }
        elseif ($template.Parameters['environmentName'] -isnot [Collections.IDictionary] -or
            [string]::IsNullOrWhiteSpace($template.Parameters['environmentName']['defaultValue'])) {
            throw 'Compiled environmentName default is missing. Regenerate ARM separately; startup will not guess an environment name.'
        }
    }
    $deploymentName = $null
    $baseline = $null
    $application = $null
    $outputs = [ordered] @{
        AZURE_SUBSCRIPTION_ID = $context.Subscription; AZURE_RESOURCE_GROUP = $ResourceGroupName
        AZURE_LOCATION = $Region; AZURE_ENV_NAME = $scope.EnvironmentName
    }
    if ($Mode -eq 'Validate') {
        $validation = Invoke-LabAz $context (@('deployment', 'group', 'validate',
            '--template-file', $template.Path, '--parameters') + $parameters +
            @('--query', '{error:error,state:properties.provisioningState}')) -GroupScoped
        if ($validation -isnot [Collections.IDictionary] -or $null -ne $validation['error'] -or
            $validation['state'] -cne 'Succeeded') {
            throw 'ARM validation did not return a successful validation result.'
        }
        $pending = @('Infrastructure readiness was not checked in Validate mode.') + $pending
    }
    else {
        $deployment = $null
        if ($Mode -eq 'Provision') {
            $deploymentName = 'lab722-start-' + [guid]::NewGuid().ToString('N')
            [void] (Invoke-LabAz $context (@('deployment', 'group', 'create', '--name', $deploymentName,
                '--template-file', $template.Path, '--mode', 'Incremental', '--no-wait', '--parameters') +
                $parameters) -GroupScoped -NoOutput)
        }
        else {
            if ($scope.LabResourceCount -eq 0 -or $scope.Deployments.Count -eq 0) {
                throw 'No tagged LAB722 infrastructure and authoritative root deployment were found in this scope.'
            }
            foreach ($candidate in $scope.Deployments) {
                $timestamp = [DateTimeOffset]::MinValue
                if (-not [DateTimeOffset]::TryParse($candidate['timestamp'], [ref] $timestamp)) {
                    throw 'Root deployment inventory has a missing or malformed timestamp.'
                }
                $candidate['SortTimestamp'] = $timestamp
            }
            # Deployment list omits outputs. Inspect roots narrowly and skip unrelated policy/modules.
            foreach ($candidate in $scope.Deployments | Sort-Object { $_.SortTimestamp } -Descending) {
                $inspected = Get-LabDeployment $context $candidate.name
                $properties = $inspected.properties
                $environmentParameter = if ($properties['parameters'] -is [Collections.IDictionary]) {
                    $properties.parameters['environmentName']
                } else { $null }
                $hasLabOutputs = $properties['outputs'] -is [Collections.IDictionary] -and
                    $null -ne $properties.outputs['FOUNDRY_PROJECT_ENDPOINT']
                if ($hasLabOutputs -or $candidate.name.StartsWith('lab722-start-', [StringComparison]::Ordinal) -or
                    ($null -ne $scope.EnvironmentName -and $environmentParameter -is [Collections.IDictionary] -and
                        $environmentParameter['value'] -ceq $scope.EnvironmentName)) {
                    $deploymentName = $candidate.name
                    $deployment = $inspected
                    break
                }
            }
            if ($null -eq $deploymentName) {
                throw 'No authoritative LAB722 root deployment outputs or parameters were found in this scope.'
            }
        }
        $deployment = Wait-LabDeployment $context $deploymentName $deployment
        $outputs = Get-LabAuthoritativeOutputs $context $scope $deployment
        Assert-LabCurrentResources $context $outputs
        if ($null -ne $applicationConfiguration) {
            $application = Get-LabApplicationReadiness $context $outputs $applicationConfiguration
            $outputs['EXPRESS_ENVIRONMENT_NAME'] = $application.express_environment_name
            $outputs['CALDOVA_APPLICATION_NAME'] = $applicationConfiguration.Name
            $outputs['CALDOVA_APPLICATION_REGION'] = $application.region
            $outputs['CALDOVA_APPLICATION_URL'] = $application.url
            $outputs['CALDOVA_APPLICATION_IMAGE'] = $application.image
            $pending = @(
                'Frozen development files and live manifest/source identities match; attendee data-release and worker-baseline gates remain separate.',
                $pending[2], $pending[3]
            )
        }
        if ($Mode -in @('Prepare', 'PreparePrimary')) {
            $primaryOnly = $Mode -eq 'PreparePrimary'
            [Console]::Error.WriteLine($(if ($primaryOnly) {
                'Preparing and verifying only the primary Sandbox. You will create its snapshot and worker clones in the portal.'
            } else {
                'Preparing and verifying the primary Sandbox, snapshot and three assigned clones. This can take several minutes.'
            }))
            $baseline = Invoke-LabBaselinePreparation $context $outputs $preparation
            $outputs['CALDOVA_DATA_MANIFEST_PATH'] = $baseline.manifest
            $outputs['CALDOVA_VALIDATION_SANDBOX_ID'] = $baseline.primary_id
            if ($primaryOnly) {
                [Console]::Error.WriteLine('Primary verified. No snapshot, clones or worker bindings were created; complete the portal exercise next.')
                $outputs['CALDOVA_PRIMARY_DESCRIPTOR_PATH'] = $baseline.descriptor
                $outputs['CALDOVA_PRIMARY_DESCRIPTOR_SHA256'] = $baseline.descriptor_sha256
                $pending[1] = 'Only the primary and frozen starter data are verified. Capture its snapshot and create the three worker clones in the portal, then register them.'
            }
            else {
                [Console]::Error.WriteLine('Sandbox preparation complete: primary, snapshot, three distinct clones and frozen data verified.')
                $outputs['CALDOVA_BASELINE_DESCRIPTOR_PATH'] = $baseline.descriptor
                $outputs['CALDOVA_WORKER_BINDINGS_PATH'] = $baseline.bindings
                $outputs['CALDOVA_BASELINE_SNAPSHOT_ID'] = $baseline.snapshot_id
            }
            if (-not $primaryOnly) { $pending[1] = if ($preparation.Purpose -eq 'public-lab-development') {
                'Exact public lab-use artifact and missing worker starters are prepared; this is not expert audit, publication, image approval or attendee release.'
            } else {
                'Frozen synthetic data and worker starters are prepared; reviewed public data and attendee release are not approved.'
            } }
        }
    }
    [void] (Get-LabRemainingMilliseconds $context)
    return [ordered] @{
        schema_version = '1.0'; mode = $Mode; deployment_name = $deploymentName
        resource_group_metadata_location = $scope.GroupMetadataLocation
        validation_succeeded = ($Mode -eq 'Validate'); infrastructure_ready = ($Mode -ne 'Validate')
        primary_ready = ($null -ne $baseline)
        baseline_ready = ($null -ne $baseline -and $Mode -ne 'PreparePrimary')
        frozen_data_verified = ($null -ne $baseline -or $null -ne $application)
        synthetic_development_only = (($null -ne $preparation -and $preparation.Purpose -eq 'synthetic-development') -or
            ($null -ne $application -and $applicationConfiguration.Purpose -eq 'synthetic-development'))
        public_lab_development_only = (($null -ne $preparation -and $preparation.Purpose -eq 'public-lab-development') -or
            ($null -ne $application -and $applicationConfiguration.Purpose -eq 'public-lab-development'))
        application_ready = ($null -ne $application)
        application_manifest_verified = ($null -ne $application)
        data_ready = $false; attendee_ready = $false
        readiness_basis = $(if ($Mode -eq 'Validate') { 'ARM validation only' } elseif ($Mode -eq 'PreparePrimary') {
            'Infrastructure plus primary starter, UID, permissions, policy and pinned frozen-data verification. Snapshot, clones, bindings, application and attendee gates remain incomplete.'
        } elseif ($Mode -eq 'Prepare') {
            'Infrastructure plus primary/three-clone starter, UID, permissions, policy, lineage and pinned frozen-data verification. Explicit development purpose only; application and attendee gates remain blocked.'
        } elseif ($null -ne $application) {
            'Scoped infrastructure, pinned application image, HTTP health, manifest/original-source identity and one preview-state sample verified. No full acceptance rerun, attendee access, worker baseline, inference or release approval.'
        } else {
            'Scoped deployment and six current resource identities/provisioning states verified: control plane only. No inference, access, quota, application, baseline or source-review checks.'
        })
        outputs = $outputs; baseline = $baseline; application = $application; pending_reasons = $pending
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    Invoke-LabStartup @PSBoundParameters | ConvertTo-Json -Depth 6 -Compress
}
