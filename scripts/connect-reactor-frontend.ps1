#requires -Version 7.3
[CmdletBinding()]
param(
    [Parameter(Mandatory)][guid]$SubscriptionId,
    [Parameter(Mandatory)][string]$ResourceGroupName,
    [Parameter(Mandatory)][string]$FrontendName,
    [Parameter(Mandatory)][string]$ProjectEndpoint,
    [Parameter(Mandatory)][string]$AgentName,
    [Parameter(Mandatory)][uri]$HostedResponsesEndpoint
)
$ErrorActionPreference = 'Stop'
$expected = "$($ProjectEndpoint.TrimEnd('/'))/agents/$AgentName/endpoint/protocols/openai/responses"
if ($HostedResponsesEndpoint.Scheme -cne 'https' -or
    $HostedResponsesEndpoint.GetLeftPart([UriPartial]::Path) -cne $expected) {
    throw 'Copy the Responses endpoint for this exact allocated project and hosted agent.'
}
$builder = [UriBuilder]::new($HostedResponsesEndpoint)
if ($builder.Query -notmatch '(^\?|&)api-version=') {
    $query = $builder.Query.TrimStart('?')
    $builder.Query = $(if ($query) { "$query&api-version=v1" } else { 'api-version=v1' })
}
$id = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroupName/providers/Microsoft.App/containerApps/$FrontendName"
$auth = & az account get-access-token --subscription $SubscriptionId --resource 'https://management.azure.com/' -o json |
    ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Azure authentication failed.' }
function Invoke-FrontendArm {
    param([string]$Method, [string]$ResourceId, $Body)
    $request = @{ Uri = "https://management.azure.com${ResourceId}?api-version=2026-03-02-preview";
        Method = $Method; Headers = @{ Authorization = 'Bearer ' + $auth.accessToken } }
    if ($Method -ne 'GET') { $request.ContentType = 'application/json' }
    if ($null -ne $Body) { $request.Body = $Body | ConvertTo-Json -Depth 100 -Compress }
    Invoke-RestMethod @request
}
try {
    $app = Invoke-FrontendArm GET $id
    $container = $app.properties.template.containers[0]
    $container.env = @($container.env | Where-Object { $_.name -cne 'HOSTED_RESPONSES_ENDPOINT' }) +
        @([pscustomobject]@{ name = 'HOSTED_RESPONSES_ENDPOINT'; value = $builder.Uri.AbsoluteUri })
    $null = Invoke-FrontendArm PATCH $id @{ properties = @{ template = $app.properties.template } }
    $deadline = [DateTime]::UtcNow.AddMinutes(3)
    do {
        Start-Sleep -Seconds 5
        $state = (Invoke-FrontendArm GET $id).properties.provisioningState
        if ($state -in @('Failed', 'Canceled')) { throw 'Frontend configuration failed; inspect the retained operation.' }
        if ([DateTime]::UtcNow -gt $deadline) { throw 'Frontend configuration timed out; inspect before retrying.' }
    } until ($state -ceq 'Succeeded')
    try {
        $null = Invoke-FrontendArm POST "$id/stop"
        $deadline = [DateTime]::UtcNow.AddMinutes(3)
        do {
            Start-Sleep -Seconds 5
            $state = (Invoke-FrontendArm GET $id).properties.runningStatus
            if ([DateTime]::UtcNow -gt $deadline) { throw 'Frontend Stop timed out.' }
        } until ($state -ceq 'Stopped')
    } finally { $null = Invoke-FrontendArm POST "$id/start" }
    $url = 'https://' + $app.properties.configuration.ingress.fqdn
    $deadline = [DateTime]::UtcNow.AddMinutes(3)
    do {
        Start-Sleep -Seconds 5
        $state = (Invoke-FrontendArm GET $id).properties.runningStatus
        if ([DateTime]::UtcNow -gt $deadline) { throw 'Frontend Start timed out.' }
    } until ($state -ceq 'Running')
    $session = Invoke-RestMethod -Uri "$url/api/session"
    if (-not $session.hosted_configured) { throw 'Running frontend still reports hosted_configured=false.' }
    [pscustomobject]@{ FrontendUrl = $url; HostedEndpoint = $builder.Uri.AbsoluteUri; HostedConfigured = $true }
} finally { $auth = $null }
