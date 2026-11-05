#requires -Version 7.2
Set-StrictMode -Version Latest

function Invoke-LabImageAz {
    param([string[]] $Arguments)
    $text = & az @Arguments --only-show-errors --output json
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI $($Arguments[0..([Math]::Min(2, $Arguments.Count - 1))] -join ' ') failed; no default scope or retry was selected."
    }
    try { $value = ConvertFrom-Json -InputObject ($text -join "`n") -AsHashtable -NoEnumerate -ErrorAction Stop }
    catch { throw 'Azure CLI returned malformed JSON; the image target cannot be verified.' }
    return ,$value
}

function Get-LabImageTarget {
    param([guid] $SubscriptionId, [string] $ResourceGroupName, [string] $RegistryName)
    if ($SubscriptionId -eq [guid]::Empty -or
        $ResourceGroupName -notmatch '^[A-Za-z0-9][A-Za-z0-9._()-]{0,89}$' -or
        $ResourceGroupName.EndsWith('.') -or $RegistryName -cnotmatch '^[a-z0-9]{5,50}$') {
        throw 'An image target requires an explicit subscription, resource group and registry.'
    }
    $account = Invoke-LabImageAz @('account', 'show', '--subscription', $SubscriptionId.ToString(),
        '--query', '{id:id,state:state}')
    if ($account['id'] -ine $SubscriptionId.ToString() -or $account['state'] -cne 'Enabled') {
        throw 'The authenticated Azure account does not match the enabled target subscription.'
    }
    $id = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroupName/providers/Microsoft.ContainerRegistry/registries/$RegistryName"
    $registry = Invoke-LabImageAz @('resource', 'show', '--ids', $id, '--api-version', '2023-07-01',
        '--subscription', $SubscriptionId.ToString())
    if ($registry['id'] -ine $id -or $registry['type'] -ine 'Microsoft.ContainerRegistry/registries' -or
        $registry['name'] -cne $RegistryName -or $registry['properties']['provisioningState'] -cne 'Succeeded' -or
        $registry['tags']['lab'] -cne 'LAB722' -or
        $registry['properties']['loginServer'] -cnotmatch "^$([regex]::Escape($RegistryName))(?:-[a-z0-9]+)?\.azurecr\.io$") {
        throw 'The registry ID, LAB722 tag, state or login server does not match the allocated image target.'
    }
    return @{
        SubscriptionId = $SubscriptionId.ToString(); ResourceGroupName = $ResourceGroupName
        RegistryName = $RegistryName; RegistryId = $id; LoginServer = $registry.properties.loginServer
    }
}

function Get-LabExpressTarget {
    param([guid] $SubscriptionId, [string] $ResourceGroupName, [string] $ExpressEnvironmentName,
        [string] $PortalApplicationName, [switch] $RequireExpressMode)
    if ($SubscriptionId -eq [guid]::Empty -or
        $ResourceGroupName -notmatch '^[A-Za-z0-9][A-Za-z0-9._()-]{0,89}$' -or
        $ResourceGroupName.EndsWith('.') -or
        $ExpressEnvironmentName -notmatch '^[A-Za-z0-9][A-Za-z0-9-]{0,59}$') {
        throw 'Express deployment requires its explicit subscription, resource group and environment name.'
    }
    $id = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroupName/providers/Microsoft.App/managedEnvironments/$ExpressEnvironmentName"
    $environment = Invoke-LabImageAz @('resource', 'show', '--ids', $id, '--api-version', '2026-03-02-preview',
        '--subscription', $SubscriptionId.ToString())
    if ($environment['id'] -ine $id -or $environment['type'] -ine 'Microsoft.App/managedEnvironments' -or
        $environment['name'] -cne $ExpressEnvironmentName -or
        $environment['properties']['provisioningState'] -cne 'Succeeded') {
        throw 'The Express environment ID, LAB722 tag or state does not match the allocated target.'
    }
    if ($RequireExpressMode -and $environment['properties']['environmentMode'] -cne 'Express') {
        throw 'Starter creation requires the existing Express-mode environment; no replacement was created.'
    }
    if ($PortalApplicationName) {
        if ($PortalApplicationName -cnotmatch '^[a-z][a-z0-9-]{0,30}[a-z0-9]$' -or
            $environment['properties']['environmentMode'] -cne 'Express') {
            throw 'Portal deployment requires an explicit application and an Express-mode environment.'
        }
        $appId = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroupName/providers/Microsoft.App/containerApps/$PortalApplicationName"
        $app = Invoke-LabImageAz @('resource', 'show', '--ids', $appId, '--api-version', '2025-10-02-preview',
            '--subscription', $SubscriptionId.ToString(),
            '--query', '{id:id,type:type,location:location,environmentId:properties.environmentId}')
        if ($app['id'] -ine $appId -or $app['type'] -ine 'Microsoft.App/containerApps' -or
            $app['environmentId'] -ine $id -or $app['location'] -ine $environment['location']) {
            throw 'The existing portal application is not bound to the selected same-scope Express environment.'
        }
    }
    elseif ($environment['tags'] -isnot [Collections.IDictionary] -or $environment.tags['lab'] -cne 'LAB722') {
        throw 'The Express environment LAB722 tag does not match the allocated target.'
    }
    return @{ Id = $id; Location = $environment.location }
}
