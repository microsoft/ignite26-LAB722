#requires -Version 7.2
[CmdletBinding(SupportsShouldProcess, DefaultParameterSetName = 'Create')]
param(
    [Parameter(Mandatory)] [guid] $SubscriptionId,
    [Parameter(Mandatory)] [string] $ResourceGroupName,
    [Parameter(Mandatory, ParameterSetName = 'Create')] [string] $ExpressEnvironmentName,
    [Parameter(Mandatory, ParameterSetName = 'Pin')] [switch] $PinExisting,
    [Parameter(Mandatory, ParameterSetName = 'Pin')] [string] $RegistryName,
    [string] $Region,
    [switch] $AuthorizeDeployment
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Split-Path -Parent $PSScriptRoot
$catalog = Get-Content -LiteralPath (Join-Path $root 'data\lab-images.json') -Raw | ConvertFrom-Json
if ($SubscriptionId -eq [guid]::Empty -or $catalog.registry -cne 'acateam.azurecr.io' -or
    $catalog.repository -cne 'lab722/caldova-research' -or $catalog.application_name -cne 'caldova-research' -or
    $catalog.images.starter.digest -cnotmatch '^sha256:[0-9a-f]{64}$') {
    throw 'The explicit subscription or pinned public starter catalog is invalid.'
}
$appName = $catalog.application_name
$image = "$($catalog.registry)/$($catalog.repository)@$($catalog.images.starter.digest)"
$operation = if ($PinExisting) { "Pin the existing starter application to $image" }
    else { "Create the pinned starter $image in existing Express environment $ExpressEnvironmentName" }
if (-not $PSCmdlet.ShouldProcess(
    "$SubscriptionId/$ResourceGroupName/$appName",
    $operation
)) { return }
if (-not $AuthorizeDeployment) {
    throw 'Starter setup requires explicit AuthorizeDeployment after reviewing the image and target.'
}
. (Join-Path $PSScriptRoot 'lab-image-target.ps1')
$account = Invoke-LabImageAz @('account', 'show', '--subscription', $SubscriptionId.ToString(),
    '--query', '{id:id,state:state}')
if ($account.id -ine $SubscriptionId.ToString() -or $account.state -cne 'Enabled') {
    throw 'The authenticated account does not match the enabled allocated subscription.'
}
if ($PinExisting) {
    $apps = Invoke-LabImageAz @('containerapp', 'list', '--resource-group', $ResourceGroupName,
        '--subscription', $SubscriptionId.ToString())
    if ($apps -isnot [array]) {
        throw 'Application inventory is malformed; no starter was changed.'
    }
    if (@($apps | Where-Object { $_['name'] -ceq $appName }).Count -ne 1) {
        throw "No unique '$appName' exists in resource group '$ResourceGroupName' in subscription '$SubscriptionId'. The Express portal generates default app and resource-group names. Set App Name to '$appName' and select existing Resource Group '$ResourceGroupName', then rerun the starter step. Stop before planning or Sandbox preparation. No app was created or changed."
    }
    $groupId = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroupName"
    $appId = "$groupId/providers/Microsoft.App/containerApps/$appName"
    $app = Invoke-LabImageAz @('resource', 'show', '--ids', $appId,
        '--api-version', '2025-10-02-preview', '--subscription', $SubscriptionId.ToString(),
        '--query', '{id:id,type:type,environmentId:properties.environmentId,images:properties.template.containers[].image}')
    $prefix = "$groupId/providers/Microsoft.App/managedEnvironments/"
    $tagImage = '{0}/{1}:{2}' -f $catalog.registry, $catalog.repository, $catalog.images.starter.tag
    if ($app['id'] -ine $appId -or $app['type'] -ine 'Microsoft.App/containerApps' -or
        $app['environmentId'] -isnot [string] -or
        -not $app.environmentId.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or
        $app['images'] -isnot [array] -or $app.images.Count -ne 1 -or
        $app.images[0] -cnotin @($image, $tagImage)) {
        throw 'The existing same-scope application must use the supplied starter tag or digest. Nothing was updated.'
    }
    $ExpressEnvironmentName = $app.environmentId.Substring($prefix.Length)
    $target = Get-LabExpressTarget -SubscriptionId $SubscriptionId -ResourceGroupName $ResourceGroupName `
        -ExpressEnvironmentName $ExpressEnvironmentName -PortalApplicationName $appName
    if ($app.images[0] -ceq $image) {
        [pscustomobject] @{ AppName = $appName; Image = $image; ExpressEnvironmentId = $target.Id
            CreationPath = 'Existing starter already digest-pinned; no update submitted' }
        return
    }
    & (Join-Path $PSScriptRoot 'deploy-research-preview.ps1') `
        -SubscriptionId $SubscriptionId -ResourceGroupName $ResourceGroupName -RegistryName $RegistryName `
        -ExpressEnvironmentName $ExpressEnvironmentName -AppName $appName -PortalCreatedApplication `
        -ImageDigest $catalog.images.starter.digest -ImageSource ReferenceRegistry -ReferenceAnonymousPull `
        -PreviewState starter -AuthorizeDeployment
    return
}
$target = Get-LabExpressTarget -SubscriptionId $SubscriptionId -ResourceGroupName $ResourceGroupName `
    -ExpressEnvironmentName $ExpressEnvironmentName -RequireExpressMode
if ($PSBoundParameters.ContainsKey('Region') -and
    ([string]::IsNullOrWhiteSpace($Region) -or
     ($target.Location -replace '\s', '') -ine ($Region -replace '\s', ''))) {
    throw 'The existing Express environment is not in the explicitly requested application region.'
}
$scope = @('--resource-group', $ResourceGroupName, '--subscription', $SubscriptionId.ToString())
$apps = Invoke-LabImageAz (@('containerapp', 'list') + $scope)
if ($apps -isnot [array]) { throw 'Application inventory is malformed; no starter was created.' }
if (@($apps | Where-Object { $_.name -ieq $appName }).Count) {
    throw 'caldova-research already exists. Inspect it and its diagnostics; this fallback never updates or replaces it.'
}
[Console]::Error.WriteLine("Creating the approved starter once in $($target.Id). Keep diagnostics if it fails; do not retry blindly.")
$app = Invoke-LabImageAz (@('containerapp', 'create', '--name', $appName,
    '--environment', $target.Id, '--image', $image, '--target-port', '8080',
    '--ingress', 'external', '--cpu', '0.5', '--memory', '1Gi',
    '--min-replicas', '0', '--max-replicas', '1') + $scope)
$expectedId = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroupName/providers/Microsoft.App/containerApps/$appName"
if ($app.id -ine $expectedId -or $app.properties.environmentId -ine $target.Id -or
    $app.properties.provisioningState -cne 'Succeeded' -or
    $app.properties.template.containers[0].image -cne $image) {
    throw 'Starter creation did not return the exact scoped image/environment in Succeeded state. Keep the existing operation and inspect it before retrying.'
}
[pscustomobject] @{
    AppName = $appName
    Image = $image
    ExpressEnvironmentId = $target.Id
    CreationPath = 'Explicitly authorized CLI fallback'
}
