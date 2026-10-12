[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string] $EnvironmentName,

    [switch] $GrantCurrentUser
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)

azd env select $EnvironmentName | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Unable to select azd environment '$EnvironmentName'."
}
$values = azd env get-values --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to read the Foundry deployment outputs.'
}
$endpoint = $values.FOUNDRY_PROJECT_ENDPOINT.TrimEnd('/')
$endpointUri = [uri] $endpoint
if ($endpointUri.Scheme -ne 'https' -or
    $endpointUri.Host -notlike '*.services.ai.azure.com' -or
    $endpointUri.AbsolutePath -notlike '/api/projects/*') {
    throw 'The Foundry deployment output is not an HTTPS project endpoint.'
}
$projectId = '/subscriptions/{0}/resourceGroups/{1}/providers/Microsoft.CognitiveServices/accounts/{2}/projects/{3}' -f `
    $values.AZURE_SUBSCRIPTION_ID, $values.AZURE_RESOURCE_GROUP,
    $values.FOUNDRY_ACCOUNT_NAME, $values.FOUNDRY_PROJECT_NAME

if ($GrantCurrentUser) {
    $principalId = az ad signed-in-user show --query id --output tsv
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($principalId)) {
        throw 'Unable to locate the signed-in maintainer principal.'
    }
    $roleId = '53ca6127-db72-4b80-b1b0-d745d6d5456d'
    $assignments = az role assignment list --assignee $principalId `
        --scope $projectId --subscription $values.AZURE_SUBSCRIPTION_ID `
        --output json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to inspect project-scoped Foundry assignments.'
    }
    if (@($assignments | Where-Object {
        $_.scope -eq $projectId -and $_.roleDefinitionId -like "*/$roleId"
    }).Count -eq 0) {
        az role assignment create --assignee-object-id $principalId `
            --assignee-principal-type User --role $roleId --scope $projectId `
            --subscription $values.AZURE_SUBSCRIPTION_ID --output none
        if ($LASTEXITCODE -ne 0) {
            throw 'Unable to assign project-scoped Foundry User access.'
        }
    }
}

$token = az account get-access-token --subscription $values.AZURE_SUBSCRIPTION_ID `
    --resource https://ai.azure.com --query accessToken --output tsv
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($token)) {
    throw 'Unable to authenticate the Foundry data-plane checks.'
}
$headers = @{ Authorization = "Bearer $token" }
$timer = [System.Diagnostics.Stopwatch]::StartNew()
do {
    $agents = Invoke-WebRequest -Uri "$endpoint/agents?api-version=v1" `
        -Headers $headers -SkipHttpErrorCheck -TimeoutSec 30
    if ($agents.StatusCode -eq 200) {
        break
    }
    if ($agents.StatusCode -ne 403) {
        throw "Foundry agent access returned HTTP $($agents.StatusCode): $($agents.Content)"
    }
    Write-Warning 'Foundry agent access returned 403; waiting for project role propagation.'
    Start-Sleep -Seconds 10
} while ($timer.Elapsed.TotalMinutes -lt 5)
if ($agents.StatusCode -ne 200) {
    throw 'Foundry agent access remains forbidden. Verify the project-scoped data-plane role.'
}

$body = @{
    model = $values.FOUNDRY_MODEL_DEPLOYMENT_NAME
    input = 'Reply with exactly LAB722_FOUNDRY_READY'
    max_output_tokens = 64
    store = $false
} | ConvertTo-Json
$response = Invoke-WebRequest -Method Post -Uri "$endpoint/openai/v1/responses" `
    -Headers $headers -ContentType 'application/json' -Body $body `
    -SkipHttpErrorCheck -TimeoutSec 60
$token = $null
$headers = $null
if ($response.StatusCode -ne 200) {
    throw "Foundry inference returned HTTP $($response.StatusCode): $($response.Content)"
}
$result = $response.Content | ConvertFrom-Json
$text = (@($result.output | Where-Object { $_.type -eq 'message' } |
    ForEach-Object { $_.content } | Where-Object { $_.type -eq 'output_text' } |
    ForEach-Object { $_.text }) -join '')
if ($result.status -ne 'completed' -or $text.Trim() -ne 'LAB722_FOUNDRY_READY') {
    throw 'The Foundry response did not satisfy the bounded inference smoke contract.'
}
[pscustomobject] @{
    Environment = $EnvironmentName
    ProjectEndpoint = $endpoint
    Model = $values.FOUNDRY_MODEL_DEPLOYMENT_NAME
    AgentApiStatus = $agents.StatusCode
    InferenceStatus = $response.StatusCode
    ResponseId = $result.id
    Output = $text.Trim()
}
