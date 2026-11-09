# Run in the cloud at Tearing Down, before the resource group is deleted.
$ErrorActionPreference = 'Stop'
$subscriptionId = '@lab.CloudSubscription.Id'
$tenantId = '@lab.CloudSubscription.TenantId'
$rg = '@lab.CloudResourceGroup(ResourceGroup1).Name'
$context = Get-AzContext
if (-not $context -or $context.Subscription.Id -ine $subscriptionId -or $context.Tenant.Id -ine $tenantId) {
    throw 'Authenticated cloud LCA context does not match this allocation.'
}
$token = Get-AzAccessToken -ResourceUrl 'https://graph.microsoft.com/'
$value = if ($token.Token -is [securestring]) {
    [System.Net.NetworkCredential]::new('', $token.Token).Password
} else { $token.Token }
$headers = @{ Authorization = 'Bearer ' + $value }
function Invoke-ReactorCleanupGraph {
    param([ValidateSet('GET', 'DELETE')][string]$Method,
          [ValidateSet('applications', 'servicePrincipals')][string]$Collection,
          [guid]$ObjectId)
    try {
        return Invoke-RestMethod -Method $Method -Headers $headers `
            -Uri "https://graph.microsoft.com/v1.0/$Collection/$ObjectId"
    } catch {
        $response = $_.Exception.PSObject.Properties['Response']
        if ($null -eq $response -or $null -eq $response.Value -or
            [int]$response.Value.StatusCode -ne 404) { throw }
        [Console]::WriteLine("Allocation API cleanup target already absent: $Collection/$ObjectId")
        return $null
    }
}
try {
    $apiName = "LAB722-Reactor2-$subscriptionId-$rg"
    $escapedName = [uri]::EscapeDataString($apiName.Replace("'", "''"))
    $applications = @((Invoke-RestMethod -Headers $headers `
        -Uri "https://graph.microsoft.com/v1.0/applications?`$filter=displayName eq '$escapedName'").value)
    if ($applications.Count -eq 0) { return }
    if ($applications.Count -ne 1) { throw 'Allocation API name is ambiguous; no deletion.' }
    $objectId = $applications[0].id
    if ($objectId -notmatch '^[0-9a-fA-F-]{36}$') { throw 'Invalid allocation API object ID; no deletion.' }
    $app = Invoke-ReactorCleanupGraph GET applications $objectId
    if ($null -eq $app) { return }
    $audience = 'api://' + $app.appId
    if ($app.id -cne $objectId -or $app.displayName -cne $apiName -or
        $app.notes -cne "Skillable allocation /subscriptions/$subscriptionId/resourceGroups/$rg" -or
        $app.signInAudience -cne 'AzureADMyOrg' -or $app.api.requestedAccessTokenVersion -ne 1 -or
        $audience -notmatch '^api://[a-fA-F0-9-]{36}$' -or
        @($app.identifierUris).Count -gt 1 -or
        (@($app.identifierUris).Count -eq 1 -and $app.identifierUris[0] -cne $audience)) {
        throw 'API ownership read-back does not match this allocation; no deletion.'
    }
    $principals = @( (Invoke-RestMethod -Headers $headers `
        -Uri "https://graph.microsoft.com/v1.0/servicePrincipals?`$filter=appId eq '$($app.appId)'").value )
    if ($principals.Count -gt 1) { throw 'Allocation API service principal is ambiguous; no deletion.' }
    foreach ($principal in $principals) {
        if ($principal.appId -cne $app.appId -or $principal.id -notmatch '^[0-9a-fA-F-]{36}$') {
            throw 'Allocation API service-principal ownership differs; no deletion.'
        }
        Invoke-ReactorCleanupGraph Delete servicePrincipals $principal.id | Out-Null
    }
    Invoke-ReactorCleanupGraph Delete applications $objectId | Out-Null
} finally { $value = $null; $headers = $null; $token = $null }
