# Run as a blocking Post-Build "Execute Script in Cloud Platform" LCA with a 30-minute timeout.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$subscriptionId = '@lab.CloudSubscription.Id'
$tenantId = '@lab.CloudSubscription.TenantId'
$resourceGroupName = '@lab.CloudResourceGroup(ResourceGroup1).Name'
$learnerUsername = '@lab.CloudPortalCredential(User1).Username'
if ($subscriptionId -notmatch '^[0-9a-fA-F-]{36}$' -or
    $tenantId -notmatch '^[0-9a-fA-F-]{36}$' -or
    [string]::IsNullOrWhiteSpace($resourceGroupName) -or
    $resourceGroupName.Contains('@lab.') -or $learnerUsername.Contains('@lab.')) {
    throw 'Skillable did not resolve the allocated scope and learner.'
}
$context = Get-AzContext
if (-not $context -or $context.Subscription.Id -ine $subscriptionId -or $context.Tenant.Id -ine $tenantId) {
    throw 'LCA cloud context does not match this allocation.'
}
function Get-ReactorSucceededFoundation {
    param([object[]]$Deployments)
    $Deployments | Where-Object {
        if ($_.ProvisioningState -ne 'Succeeded' -or -not $_.Outputs) { return $false }
        $markerKeys = @($_.Outputs.Keys | Where-Object { $_ -ieq 'REACTOR2_HARNESS_VERSION' })
        if ($markerKeys.Count -gt 1) { throw 'Foundation marker output is ambiguous.' }
        $markerKeys.Count -eq 1 -and $_.Outputs[$markerKeys[0]].Value -eq '1'
    }
}
$allDeployments = @(Get-AzResourceGroupDeployment -ResourceGroupName $resourceGroupName)
$deployments = @(Get-ReactorSucceededFoundation $allDeployments)
$resourceGroupId = "/subscriptions/$subscriptionId/resourceGroups/$resourceGroupName"
if ($deployments.Count -eq 0) {
    $foundationHash = '9372070027890358331'
    $failed = @($allDeployments | Where-Object {
        $_.ProvisioningState -eq 'Failed' -and $_.TemplateHash -ceq $foundationHash
    })
    if ($failed.Count -ne 1 -or $failed[0].Mode -ne 'Incremental') {
        throw 'Expected exactly one successful Reactor 2 foundation deployment.'
    }
    $foundation = $failed[0]
    $recoveryName = $foundation.DeploymentName + '-recovery'
    $readyModules = @($allDeployments | Where-Object {
        $_.DeploymentName -in @('reactor2-core', 'reactor2-express', 'reactor2-sandboxes') -and
        $_.ProvisioningState -eq 'Succeeded'
    })
    if ($readyModules.Count -ne 3 -or $recoveryName.Length -gt 64 -or
        @($allDeployments | Where-Object { $_.DeploymentName -ieq $recoveryName }).Count -ne 0) {
        throw 'Foundation recovery requires three successful peer modules and no previous recovery attempt.'
    }
    $operationResponse = Invoke-AzRestMethod -Method GET -Path (
        "$resourceGroupId/providers/Microsoft.Resources/deployments/reactor2-foundry/operations?api-version=2022-09-01")
    if ($operationResponse.StatusCode -ne 200) { throw 'Cannot read the failed Foundry operations.' }
    $operationPage = $operationResponse.Content | ConvertFrom-Json
    if ($operationPage.PSObject.Properties['nextLink'] -and $operationPage.nextLink) {
        throw 'Foundry operation history is paginated; automatic recovery is not safe.'
    }
    $failedOperations = @($operationPage.value | Where-Object { $_.properties.provisioningState -eq 'Failed' })
    if ($failedOperations.Count -ne 1) { throw 'Foundry failure is not a single account operation.' }
    $operation = $failedOperations[0].properties
    $accountName = $operation.targetResource.resourceName
    $accountId = "$resourceGroupId/providers/Microsoft.CognitiveServices/accounts/$accountName"
    $failure = $operation.statusMessage.error
    $expectedMessage = "Cannot modify resource with id '$accountId' because the resource entity provisioning state is not terminal. Please wait for the provisioning state to become terminal and then retry the request."
    if ($operation.targetResource.resourceType -ine 'Microsoft.CognitiveServices/accounts' -or
        $accountName -cnotmatch '^lab722-[a-z0-9]{13}-ai$' -or
        $operation.targetResource.id -ine $accountId -or
        $failure.code -cne 'RequestConflict' -or $failure.message -isnot [string] -or
        $failure.message.Trim() -ine $expectedMessage) {
        throw 'Foundry failure is not the allocation account provisioning-state conflict; no retry was performed.'
    }
    Write-Output "Foundry account provisioning conflicted in $($foundation.DeploymentName); checking readiness before one recovery."
    for ($read = 0; $read -lt 60; $read++) {
        $accountResponse = Invoke-AzRestMethod -Method GET -Path "${accountId}?api-version=2025-06-01"
        if ($accountResponse.StatusCode -ne 200) { throw 'Cannot verify the conflicting Foundry account.' }
        $account = $accountResponse.Content | ConvertFrom-Json
        if ($account.id -ine $accountId -or $account.kind -cne 'AIServices' -or
            $account.tags.lab -cne 'LAB722' -or $account.tags.purpose -cne 'reactor2-skillable') {
            throw 'Conflicting Foundry account does not belong to this foundation.'
        }
        $state = $account.properties.provisioningState
        if ($state -ceq 'Succeeded') { break }
        if ($state -cnotin @('Accepted', 'Creating', 'Updating') -or $read -eq 59) {
            throw "Foundry account did not become ready for recovery; observed provisioning state '$state'."
        }
        Start-Sleep -Seconds 15
    }
    $templatePath = Join-Path ([IO.Path]::GetTempPath()) ("reactor2-foundation-" + [guid]::NewGuid() + '.json')
    try {
        $null = Save-AzResourceGroupDeploymentTemplate -ResourceGroupName $resourceGroupName `
            -DeploymentName $foundation.DeploymentName -Path $templatePath -Force
        $template = Get-Content -LiteralPath $templatePath -Raw | ConvertFrom-Json
        if ($template.metadata._generator.templateHash -cne $foundationHash) {
            throw 'Exported foundation differs from the pinned template; no retry was performed.'
        }
        $parameters = @{}
        foreach ($entry in $foundation.Parameters.GetEnumerator()) {
            if ($entry.Key -cnotin @('location', 'modelCapacity')) {
                throw 'Foundation contains an unexpected parameter; no retry was performed.'
            }
            $parameters[$entry.Key] = $entry.Value.Value
        }
        Write-Output "Foundry account is ready. Recovering the original template and parameters as '$recoveryName' in Incremental mode."
        $recovered = New-AzResourceGroupDeployment -ResourceGroupName $resourceGroupName `
            -Name $recoveryName -Mode Incremental -TemplateFile $templatePath -TemplateParameterObject $parameters
        if ($recovered.ProvisioningState -ne 'Succeeded') { throw 'Foundation recovery deployment did not succeed.' }
        $deployments = @(Get-ReactorSucceededFoundation @($recovered))
    } finally {
        if (Test-Path -LiteralPath $templatePath) { Remove-Item -LiteralPath $templatePath -Force }
    }
}
if ($deployments.Count -ne 1) { throw 'Expected exactly one successful Reactor 2 foundation deployment.' }
$outputs = @{}
foreach ($entry in $deployments[0].Outputs.GetEnumerator()) {
    if ($outputs.ContainsKey($entry.Key)) { throw 'Foundation output names are ambiguous.' }
    $outputs[$entry.Key] = $entry.Value
}
if ($outputs['AZURE_SUBSCRIPTION_ID'].Value -ine $subscriptionId -or
    $outputs['AZURE_TENANT_ID'].Value -ine $tenantId -or
    $outputs['AZURE_RESOURCE_GROUP'].Value -cne $resourceGroupName) {
    throw 'Foundation output scope differs from the allocated lab.'
}
$learner = @(Get-AzADUser -UserPrincipalName $learnerUsername)
if ($learner.Count -ne 1 -or -not $learner[0].Id) { throw 'Allocated learner is not unique.' }
$prefix = "$resourceGroupId/providers/"
$accountId = $prefix + 'Microsoft.CognitiveServices/accounts/' + $outputs['FOUNDRY_ACCOUNT_NAME'].Value
$projectId = $accountId + '/projects/' + $outputs['FOUNDRY_PROJECT_NAME'].Value
$groupId = $prefix + 'Microsoft.App/sandboxGroups/' + $outputs['SANDBOX_GROUP_NAME'].Value
$registryId = $prefix + 'Microsoft.ContainerRegistry/registries/' + $outputs['AZURE_CONTAINER_REGISTRY_NAME'].Value
$aiRole = '53ca6127-db72-4b80-b1b0-d745d6d5456d'
$sandboxRole = 'c24cf47c-5077-412d-a19c-45202126392c'
$pullRole = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
$frontendId = $outputs['REACTOR2_FRONTEND_OBJECT_ID'].Value
$executionId = $outputs['REACTOR2_EXECUTION_OBJECT_ID'].Value
$projectObjectId = $outputs['REACTOR2_PROJECT_OBJECT_ID'].Value
$targets = @(
    @{ Principal = $learner[0].Id; Scope = $projectId; Role = $aiRole }
    @{ Principal = $learner[0].Id; Scope = $groupId; Role = $sandboxRole }
    @{ Principal = $frontendId; Scope = $projectId; Role = $aiRole }
    @{ Principal = $executionId; Scope = $groupId; Role = $sandboxRole }
    @{ Principal = $executionId; Scope = $accountId; Role = $aiRole }
    @{ Principal = $projectObjectId; Scope = $projectId; Role = $aiRole }
    @{ Principal = $projectObjectId; Scope = $accountId; Role = $aiRole }
    @{ Principal = $projectObjectId; Scope = $registryId; Role = $pullRole }
)
foreach ($target in $targets) {
    if ($target.Principal -notmatch '^[0-9a-fA-F-]{36}$' -or
        -not $target.Scope.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'A role principal or scope is outside the foundation contract.'
    }
    $existing = @(Get-AzRoleAssignment -ObjectId $target.Principal -Scope $target.Scope |
        Where-Object { $_.Scope -ieq $target.Scope -and $_.RoleDefinitionId -ieq $target.Role })
    if ($existing.Count -eq 0) {
        $created = New-AzRoleAssignment -ObjectId $target.Principal `
            -RoleDefinitionId $target.Role -Scope $target.Scope
        if (-not $created -or $created.ObjectId -ine $target.Principal -or
            $created.Scope -ine $target.Scope -or $created.RoleDefinitionId -ine $target.Role) {
            throw 'Role creation did not confirm the requested principal, role and scope.'
        }
    }
}
$token = Get-AzAccessToken -ResourceUrl 'https://graph.microsoft.com/'
$graphToken = if ($token.Token -is [securestring]) {
    [System.Net.NetworkCredential]::new('', $token.Token).Password
} else { $token.Token }
$graphHeaders = @{ Authorization = 'Bearer ' + $graphToken }
$graphOperation = @{ Method = ''; Path = '' }
function Invoke-ReactorGraph {
    param([string]$Method, [string]$Path, $Body, [ValidateRange(0, 6)][int]$NotFoundRetries = 0)
    if ($NotFoundRetries -gt 0 -and $Method -notin @('GET', 'PATCH')) {
        throw 'Automatic Graph not-found retries are limited to reads and idempotent updates.'
    }
    $graphOperation.Method = $Method
    $graphOperation.Path = $Path
    $request = @{ Uri = "https://graph.microsoft.com/v1.0/$Path"; Method = $Method; Headers = $graphHeaders }
    if ($null -ne $Body) {
        $request.ContentType = 'application/json'
        $request.Body = $Body | ConvertTo-Json -Depth 10 -Compress
    }
    $attempt = 0
    while ($true) {
        try { return Invoke-RestMethod @request }
        catch {
            $response = $_.Exception.PSObject.Properties['Response']
            if ($attempt -ge $NotFoundRetries -or $null -eq $response -or
                $null -eq $response.Value -or [int]$response.Value.StatusCode -ne 404) { throw }
            $attempt++
            Start-Sleep -Seconds 5
        }
    }
}
$apiName = "LAB722-Reactor2-$subscriptionId-$resourceGroupName"
$escapedName = [uri]::EscapeDataString($apiName.Replace("'", "''"))
try {
    $applications = @( (Invoke-ReactorGraph GET "applications?`$filter=displayName eq '$escapedName'").value )
    if ($applications.Count -gt 1) { throw 'Execution API name is ambiguous; no application was created.' }
    if ($applications.Count -eq 0) {
        $application = Invoke-ReactorGraph POST 'applications' @{
            displayName = $apiName; signInAudience = 'AzureADMyOrg'
            api = @{ requestedAccessTokenVersion = 1 }
            notes = "Skillable allocation /subscriptions/$subscriptionId/resourceGroups/$resourceGroupName"
        }
    } else { $application = $applications[0] }
    if ($application.notes -cne "Skillable allocation /subscriptions/$subscriptionId/resourceGroups/$resourceGroupName" -or
        $application.signInAudience -cne 'AzureADMyOrg' -or $application.api.requestedAccessTokenVersion -ne 1) {
        throw 'Existing API application differs from this allocation contract.'
    }
    $audience = 'api://' + $application.appId
    $identifierPatched = $false
    if (@($application.identifierUris).Count -eq 0) {
        $null = Invoke-ReactorGraph PATCH "applications/$($application.id)" `
            @{ identifierUris = @($audience) } -NotFoundRetries 6
        $identifierPatched = $true
    } elseif (@($application.identifierUris).Count -ne 1 -or $application.identifierUris[0] -cne $audience) {
        throw 'Existing API identifier differs; no replacement was performed.'
    }
    $principals = @((Invoke-ReactorGraph GET "servicePrincipals?`$filter=appId eq '$($application.appId)'").value)
    if ($principals.Count -gt 1) { throw 'API service principal is ambiguous.' }
    if ($principals.Count -eq 0) {
        for ($attempt = 0; $attempt -le 3; $attempt++) {
            try {
                $principal = Invoke-ReactorGraph POST 'servicePrincipals' @{ appId = $application.appId }
                break
            } catch {
                $response = $_.Exception.PSObject.Properties['Response']
                if ($null -eq $response -or $null -eq $response.Value) { throw }
                $status = [int]$response.Value.StatusCode
                $missingApplication = $status -eq 404
                if ($status -eq 400 -and $_.ErrorDetails -and $_.ErrorDetails.Message) {
                    $graphFailure = $_
                    try { $graphError = $_.ErrorDetails.Message | ConvertFrom-Json }
                    catch { throw $graphFailure }
                    $errorObject = $graphError.PSObject.Properties['error']
                    if ($errorObject -and $errorObject.Value) {
                        $errorDetails = $errorObject.Value.PSObject.Properties['details']
                        $errorCode = $errorObject.Value.PSObject.Properties['code']
                        if ($errorCode -and $errorCode.Value -ceq 'Request_BadRequest' -and $errorDetails) {
                            $missingApplication = @($errorDetails.Value | Where-Object {
                                $code = $_.PSObject.Properties['code']
                                $target = $_.PSObject.Properties['target']
                                $message = $_.PSObject.Properties['message']
                                $code -and $code.Value -ceq 'NoBackingApplicationObject' -and
                                $target -and $target.Value -ceq 'appId' -and $message -and
                                $message.Value -is [string] -and
                                $message.Value.IndexOf($application.appId, [StringComparison]::OrdinalIgnoreCase) -ge 0
                            }).Count -eq 1
                        }
                    }
                }
                if (-not $missingApplication -or $attempt -ge 3) { throw }
                Start-Sleep -Seconds 15
            }
        }
    } else { $principal = $principals[0] }
    for ($readAttempt = 0; $readAttempt -le 6; $readAttempt++) {
        $readback = Invoke-ReactorGraph GET "applications/$($application.id)" -NotFoundRetries 6
        $principalReadback = Invoke-ReactorGraph GET "servicePrincipals/$($principal.id)" -NotFoundRetries 6
        foreach ($check in @(
            @{ Field = 'application.id'; Expected = $application.id; Actual = $readback.id }
            @{ Field = 'application.appId'; Expected = $application.appId; Actual = $readback.appId }
            @{ Field = 'application.notes'; Expected = $application.notes; Actual = $readback.notes }
            @{ Field = 'application.signInAudience'; Expected = 'AzureADMyOrg'; Actual = $readback.signInAudience }
            @{ Field = 'application.api.requestedAccessTokenVersion'; Expected = 1; Actual = $readback.api.requestedAccessTokenVersion }
            @{ Field = 'servicePrincipal.id'; Expected = $principal.id; Actual = $principalReadback.id }
            @{ Field = 'servicePrincipal.appId'; Expected = $application.appId; Actual = $principalReadback.appId }
        )) {
            if ($check.Actual -cne $check.Expected) {
                throw "Execution API $($check.Field) differs: expected $(ConvertTo-Json -InputObject $check.Expected -Compress); observed $(ConvertTo-Json -InputObject $check.Actual -Compress)."
            }
        }
        if ($principalReadback.appRoleAssignmentRequired -isnot [bool] -or $principalReadback.appRoleAssignmentRequired) {
            throw "Execution API service-principal assignment policy differs: expected appRoleAssignmentRequired=false; observed $(ConvertTo-Json -InputObject $principalReadback.appRoleAssignmentRequired -Compress)."
        }
        $uris = @($readback.identifierUris)
        if ($uris.Count -eq 1 -and $uris[0] -ceq $audience) { break }
        if (-not $identifierPatched -or $uris.Count -ne 0 -or $readAttempt -ge 6) {
            throw "Execution API identifierUris differs: expected '$audience'; observed $(ConvertTo-Json -InputObject $uris -Compress)."
        }
        Write-Output 'Waiting for the successfully written allocation API identifier URI to become readable.'
        Start-Sleep -Seconds 5
    }
    Write-Output 'Reactor 2 allocation API and eight scoped role assignments are prepared.'
} catch {
    $detail = if ($_.ErrorDetails -and -not [string]::IsNullOrWhiteSpace($_.ErrorDetails.Message)) {
        $_.ErrorDetails.Message
    } else { $_.Exception.Message }
    throw "Execution API provisioning failed at $($graphOperation.Method) $($graphOperation.Path): $detail"
} finally { $graphToken = $null; $graphHeaders = $null; $token = $null }
