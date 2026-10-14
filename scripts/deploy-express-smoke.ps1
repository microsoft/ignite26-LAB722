[CmdletBinding(DefaultParameterSetName = 'Azd')]
param(
    [Parameter(Mandatory, ParameterSetName = 'Azd')]
    [string] $EnvironmentName,

    [Parameter(Mandatory, ParameterSetName = 'Scope')] [guid] $SubscriptionId,
    [Parameter(Mandatory, ParameterSetName = 'Scope')] [string] $ResourceGroupName,
    [Parameter(Mandatory, ParameterSetName = 'Scope')] [string] $ExpressEnvironmentName,

    [ValidatePattern('^[a-z][a-z0-9-]{0,30}[a-z0-9]$')]
    [string] $AppName = 'lab722-express-smoke',

    [string] $Image = 'docker.io/library/nginx:alpine',

    [ValidateRange(1, 5)] [int] $RetryCount = 3
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repositoryRoot

if ($PSCmdlet.ParameterSetName -eq 'Azd') {
    azd env select $EnvironmentName | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Unable to select the requested azd environment.' }
    $text = azd env get-values --output json
    if ($LASTEXITCODE -ne 0) { throw 'Unable to read the requested azd environment.' }
    $values = $text | ConvertFrom-Json
    $SubscriptionId = [guid] $values.AZURE_SUBSCRIPTION_ID
    $ResourceGroupName = $values.AZURE_RESOURCE_GROUP
    $ExpressEnvironmentName = $values.EXPRESS_ENVIRONMENT_NAME
}
$resourceGroup = $ResourceGroupName
$expressEnvironment = $ExpressEnvironmentName

if ([string]::IsNullOrWhiteSpace($resourceGroup) -or
    [string]::IsNullOrWhiteSpace($expressEnvironment)) {
    throw 'The azd environment is missing Express deployment outputs.'
}

. (Join-Path $PSScriptRoot 'lab-image-target.ps1')
$target = Get-LabExpressTarget -SubscriptionId $SubscriptionId `
    -ResourceGroupName $resourceGroup -ExpressEnvironmentName $expressEnvironment
$apps = Invoke-LabImageAz @('containerapp', 'list', '--resource-group', $resourceGroup,
    '--subscription', $SubscriptionId.ToString())
$existing = @($apps | Where-Object { $_.name -ceq $AppName })
if ($existing.Count -gt 1 -or ($existing.Count -eq 1 -and
    $existing[0].properties.environmentId -ine $target.Id)) {
    throw 'The existing application is not uniquely bound to the allocated Express environment.'
}
$appExists = $existing.Count -eq 1

if (-not $appExists) {
    $created = $false

    for ($attempt = 1; $attempt -le $RetryCount; $attempt++) {
        Write-Output "Express create attempt $attempt of $RetryCount"

        az containerapp create `
            --resource-group $resourceGroup `
            --subscription $SubscriptionId `
            --name $AppName `
            --environment $expressEnvironment `
            --image $Image `
            --target-port 80 `
            --ingress external `
            --min-replicas 0 `
            --max-replicas 1 `
            --only-show-errors

        if ($LASTEXITCODE -eq 0) {
            $created = $true
            break
        }

        if ($attempt -lt $RetryCount) {
            Start-Sleep -Seconds (30 * $attempt)
        }
    }

    if (-not $created) {
        throw "Express app creation failed after $RetryCount attempts."
    }
}

$fqdn = az containerapp show `
    --resource-group $resourceGroup `
    --subscription $SubscriptionId `
    --name $AppName `
    --query properties.configuration.ingress.fqdn `
    --output tsv

if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($fqdn)) {
    throw 'The Express application FQDN is empty.'
}

$url = "https://$fqdn"

for ($attempt = 1; $attempt -le 12; $attempt++) {
    try {
        $response = Invoke-WebRequest `
            -Uri $url `
            -UseBasicParsing `
            -TimeoutSec 20

        if ($response.StatusCode -eq 200) {
            [pscustomobject] @{
                AppName = $AppName
                Url = $url
                StatusCode = $response.StatusCode
            }
            return
        }
    }
    catch {
        if ($attempt -eq 12) {
            throw
        }
    }

    Start-Sleep -Seconds 10
}

throw "Express application '$AppName' did not return HTTP 200."
