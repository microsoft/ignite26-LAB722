[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string] $EnvironmentName,

    [Parameter(Mandatory)]
    [ValidatePattern('^sha256:[0-9a-f]{64}$')]
    [string] $ImageDigest,

    [string] $AppName = 'caldova-research',

    [ValidateSet('starter', 'reference')]
    [string] $PreviewState = 'reference'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repositoryRoot

azd env select $EnvironmentName | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Unable to select azd environment '$EnvironmentName'."
}
$values = azd env get-values --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read azd environment '$EnvironmentName'."
}
$scope = @('--resource-group', $values.AZURE_RESOURCE_GROUP, '--subscription', $values.AZURE_SUBSCRIPTION_ID)
$registryName = $values.AZURE_CONTAINER_REGISTRY_NAME
if ([string]::IsNullOrWhiteSpace($registryName)) {
    throw 'The azd environment is missing its registry output.'
}

$apps = az containerapp list @scope --output json --only-show-errors | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to check the Express application inventory.'
}
if (@($apps | Where-Object { $_.name -eq $AppName }).Count -eq 0) {
    & (Join-Path $PSScriptRoot 'deploy-express-smoke.ps1') `
        -EnvironmentName $EnvironmentName -AppName $AppName | Out-Null
}

$registry = az acr show --name $registryName @scope --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw "Registry lookup failed for '$registryName'."
}
$tokenName = "$AppName-pull"
$scopeMaps = az acr scope-map list `
    --registry $registryName --subscription $values.AZURE_SUBSCRIPTION_ID `
    --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to check registry scope maps.'
}
if (@($scopeMaps | Where-Object { $_.name -eq $tokenName }).Count -eq 0) {
    az acr scope-map create `
        --registry $registryName --subscription $values.AZURE_SUBSCRIPTION_ID `
        --name $tokenName `
        --repository caldova/research-portal content/read metadata/read `
        --description 'LAB722 Express preview: read-only portal image access.' `
        --output none
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to create the repository-scoped pull permissions.'
    }
}

$scopeMap = az acr scope-map show `
    --registry $registryName --subscription $values.AZURE_SUBSCRIPTION_ID `
    --name $tokenName --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to inspect the repository-scoped pull permissions.'
}
$expectedActions = @(
    'repositories/caldova/research-portal/content/read',
    'repositories/caldova/research-portal/metadata/read'
)
if (@(Compare-Object $expectedActions @($scopeMap.actions)).Count -ne 0) {
    throw 'The existing pull scope map does not match the approved read-only repository scope.'
}

$tokens = az acr token list `
    --registry $registryName --subscription $values.AZURE_SUBSCRIPTION_ID `
    --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to check registry tokens.'
}
$existingToken = $tokens | Where-Object { $_.name -eq $tokenName }
if ($null -eq $existingToken) {
    az acr token create `
        --registry $registryName --subscription $values.AZURE_SUBSCRIPTION_ID `
        --name $tokenName --scope-map $tokenName --no-passwords --output none
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to create the scoped registry pull token.'
    }
}
elseif ($existingToken.scopeMapId -ne $scopeMap.id) {
    throw 'The existing registry token points to an unexpected scope map.'
}

$credential = az acr token credential generate `
    --registry $registryName --subscription $values.AZURE_SUBSCRIPTION_ID `
    --name $tokenName --password1 --expiration-in-days 7 `
    --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or @($credential.passwords).Count -ne 1) {
    throw 'Unable to generate the seven-day scoped registry credential.'
}

$applicationId = az containerapp show --name $AppName @scope --query id --output tsv
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($applicationId)) {
    throw 'Unable to locate the Express application resource.'
}
$managementToken = az account get-access-token `
    --subscription $values.AZURE_SUBSCRIPTION_ID `
    --resource https://management.azure.com/ --query accessToken --output tsv
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($managementToken)) {
    throw 'Unable to authenticate the application configuration update.'
}
$headers = @{ Authorization = "Bearer $managementToken" }
$resourceUri = "https://management.azure.com${applicationId}?api-version=2025-10-02-preview"
$application = Invoke-RestMethod -Method Get -Uri $resourceUri -Headers $headers
$existingSecrets = Invoke-RestMethod -Method Post -Headers $headers `
    -Uri "https://management.azure.com${applicationId}/listSecrets?api-version=2025-10-02-preview" `
    -ContentType 'application/json' -Body '{}'
$secretName = 'caldova-acr-pull'
$secrets = @($existingSecrets.value | Where-Object { $null -ne $_ -and $_.name -ne $secretName }) + @(@{
    name = $secretName
    value = $credential.passwords[0].value
})
$registries = @($application.properties.configuration.registries |
    Where-Object { $null -ne $_ -and $_.server -ne $registry.loginServer }) + @(@{
    server = $registry.loginServer
    username = $credential.username
    passwordSecretRef = $secretName
})
$image = '{0}/caldova/research-portal@{1}' -f $registry.loginServer, $ImageDigest
$containers = @($application.properties.template.containers)
if ($containers.Count -ne 1) {
    throw 'The Caldova Express preview requires exactly one application container.'
}
$containers[0].image = $image
$environmentVariables = @()
if ($null -ne $containers[0].PSObject.Properties['env']) {
    $environmentVariables = @($containers[0].env |
        Where-Object { $null -ne $_ -and $_.name -ne 'CALDOVA_PREVIEW_STATE' })
}
$environmentVariables += @{ name = 'CALDOVA_PREVIEW_STATE'; value = $PreviewState }
$containers[0] | Add-Member -MemberType NoteProperty -Name env -Value $environmentVariables -Force

# Express needs the pull credentials in the same request as the private image update.
$body = @{
    location = $application.location
    properties = @{
        environmentId = $application.properties.environmentId
        configuration = @{
            secrets = $secrets
            registries = $registries
            ingress = @{ external = $true; targetPort = 8080; transport = 'auto' }
        }
        template = @{ containers = $containers }
    }
} | ConvertTo-Json -Depth 20
$deploymentResponse = Invoke-WebRequest -Method Put -Uri $resourceUri -Headers $headers `
    -ContentType 'application/json' -Body $body
$credential = $null
$body = $null
$secrets = $null
$existingSecrets = $null

$operationHeader = $deploymentResponse.Headers.Keys |
    Where-Object { $_ -ieq 'Azure-AsyncOperation' } | Select-Object -First 1
$locationHeader = $deploymentResponse.Headers.Keys |
    Where-Object { $_ -ieq 'Location' } | Select-Object -First 1
if ($null -ne $operationHeader -or $null -ne $locationHeader) {
    $headerName = if ($null -ne $operationHeader) { $operationHeader } else { $locationHeader }
    $operationUri = [string] @($deploymentResponse.Headers[$headerName])[0]
    $parsedOperationUri = [uri] $operationUri
    if ($parsedOperationUri.Scheme -ne 'https' -or $parsedOperationUri.Host -ne 'management.azure.com') {
        throw 'The deployment returned an unexpected management operation endpoint.'
    }
    $operationReady = $false
    $operationTimer = [System.Diagnostics.Stopwatch]::StartNew()
    while ($operationTimer.Elapsed.TotalMinutes -lt 5) {
        $operationResponse = Invoke-WebRequest -Uri $operationUri -Headers $headers -TimeoutSec 30
        if ($null -ne $operationHeader) {
            $operation = $operationResponse.Content | ConvertFrom-Json
            if ($operation.status -eq 'Succeeded') {
                $operationReady = $true
                break
            }
            if ($operation.status -in @('Failed', 'Canceled')) {
                $detail = $operationResponse.Content
                if ($null -ne $operation.PSObject.Properties['error']) {
                    $detail = $operation.error | ConvertTo-Json -Depth 10 -Compress
                }
                throw "The private-image deployment operation $($operation.status): $detail"
            }
            if ($operation.status -notin @('Accepted', 'InProgress', 'Running')) {
                throw "The deployment returned an unexpected operation status '$($operation.status)'."
            }
        }
        elseif ($operationResponse.StatusCode -in @(200, 204)) {
            $operationReady = $true
            break
        }
        elseif ($operationResponse.StatusCode -ne 202) {
            throw "The deployment operation returned HTTP $($operationResponse.StatusCode)."
        }
        Start-Sleep -Seconds 5
    }
    if (-not $operationReady) {
        throw 'The private-image deployment operation did not complete within five minutes.'
    }
}

$configurationReady = $false
for ($attempt = 1; $attempt -le 60; $attempt++) {
    $application = Invoke-RestMethod -Method Get -Uri $resourceUri -Headers $headers
    if ($application.properties.provisioningState -eq 'Succeeded') {
        $configurationReady = $true
        break
    }
    if ($application.properties.provisioningState -eq 'Failed') {
        throw "The private-image deployment failed: $($application.properties.deploymentErrors)"
    }
    Start-Sleep -Seconds 5
}
$managementToken = $null
$headers = $null
if (-not $configurationReady) {
    throw 'The private-image deployment did not become ready within five minutes.'
}

$deployed = az containerapp show --name $AppName @scope `
    --query '{fqdn:properties.configuration.ingress.fqdn,image:properties.template.containers[0].image}' `
    --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $deployed.image -ne $image) {
    throw 'The deployed image does not match the approved digest.'
}
$url = "https://$($deployed.fqdn)"
for ($attempt = 1; $attempt -le 20; $attempt++) {
    try {
        $response = Invoke-WebRequest -Uri "$url/health" -SkipHttpErrorCheck -TimeoutSec 20
    }
    catch [System.OperationCanceledException] {
        Write-Warning "Application readiness attempt $attempt of 20 timed out."
        Start-Sleep -Seconds 5
        continue
    }
    catch [System.Net.Http.HttpRequestException] {
        Write-Warning "Application readiness attempt $attempt of 20 had a transport error: $($_.Exception.Message)"
        Start-Sleep -Seconds 5
        continue
    }
    if ($response.StatusCode -eq 200) {
        $health = $response.Content | ConvertFrom-Json
        if ($health.status -eq 'healthy' -and $health.preview_state -eq $PreviewState) {
            [pscustomobject] @{
                AppName = $AppName
                Url = $url
                Image = $image
                PreviewState = $PreviewState
                DatasetVersion = $health.dataset_version
                DatasetKind = $health.dataset_kind
            }
            return
        }
    }
    if ($response.StatusCode -eq 200) {
        Write-Warning "Application readiness attempt $attempt of 20 reports preview '$($health.preview_state)', expected '$PreviewState'."
    }
    else {
        Write-Warning "Application readiness attempt $attempt of 20 returned HTTP $($response.StatusCode)."
    }
    Start-Sleep -Seconds 5
}
throw "Application '$AppName' did not become healthy in state '$PreviewState'. Deploy a newly built digest with the matching preview state; an environment-only Express update may leave the existing process unchanged."
