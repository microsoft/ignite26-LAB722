[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string] $EnvironmentName,

    [string] $AppName = 'lab722-express-smoke',

    [string] $Image = 'docker.io/library/nginx:alpine',

    [int] $RetryCount = 3
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repositoryRoot

azd env select $EnvironmentName | Out-Null
$values = azd env get-values --output json | ConvertFrom-Json
$resourceGroup = $values.AZURE_RESOURCE_GROUP
$expressEnvironment = $values.EXPRESS_ENVIRONMENT_NAME

if ([string]::IsNullOrWhiteSpace($resourceGroup) -or
    [string]::IsNullOrWhiteSpace($expressEnvironment)) {
    throw 'The azd environment is missing Express deployment outputs.'
}

az containerapp show `
    --resource-group $resourceGroup `
    --name $AppName `
    --output none 2>$null

$appExists = $LASTEXITCODE -eq 0

if (-not $appExists) {
    $created = $false

    for ($attempt = 1; $attempt -le $RetryCount; $attempt++) {
        Write-Output "Express create attempt $attempt of $RetryCount"

        az containerapp create `
            --resource-group $resourceGroup `
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
    --name $AppName `
    --query properties.configuration.ingress.fqdn `
    --output tsv

if ([string]::IsNullOrWhiteSpace($fqdn)) {
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
