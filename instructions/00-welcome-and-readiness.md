# 3. Sign in and check your environment

Open the **PowerShell 7** desktop shortcut in the VM. The **Windows Terminal** shortcut opens the same prepared shell and checkout.

## 3.1 Sign in and check the prepared resources

Run this block. Sign in with the Azure credentials from your lab's **Resources** tab, not your personal account. After sign-in, confirm the subscription once: enter its ID from Resources, or press **Enter** if the displayed selected ID matches. The resource check then continues without another confirmation prompt. **Use your Azure credentials from the Resources tab (at the top of the instructions) when asked for Username and temporary access password**.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\Users\LabUser\code\ignite26-LAB722'
    $env:AZURE_CORE_LOGIN_EXPERIENCE_V2 = 'off'
    az login --use-device-code --output none
    if ($LASTEXITCODE -ne 0) { throw 'Azure sign-in failed. Check your lab credentials.' }
    $selectedText = az account show --query id --output tsv
    if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect the signed-in subscription.' }
    $selectedId = [guid]::Empty
    $hasSelected = [guid]::TryParse(($selectedText -join "`n").Trim(), [ref] $selectedId) -and
        $selectedId -ne [guid]::Empty
    do {
        $prompt = if ($hasSelected) {
            "Subscription ID from Resources (Enter to use selected $selectedId)"
        } else { 'Subscription ID from Resources' }
        $answer = (Read-Host $prompt).Trim()
        if ($answer -eq '' -and $hasSelected) { $answer = $selectedId.ToString() }
        $subscriptionId = [guid]::Empty
        $validSubscription = [guid]::TryParse($answer, [ref] $subscriptionId) -and
            $subscriptionId -ne [guid]::Empty
        if (-not $validSubscription) {
            Write-Warning 'Enter a valid, nonempty subscription ID from Resources.'
        }
    } until ($validSubscription)
    $env:AZURE_SUBSCRIPTION_ID = $subscriptionId.ToString()
    az account set --subscription $env:AZURE_SUBSCRIPTION_ID
    if ($LASTEXITCODE -ne 0) { throw 'The allocated subscription could not be selected.' }
    az account show --subscription $env:AZURE_SUBSCRIPTION_ID `
        --query "{account:user.name, subscription:name}" --output table
    if ($LASTEXITCODE -ne 0) { throw 'The allocated account could not be checked.' }
    $resourceGroupName = 'LAB722'
    $region = 'westus3'
    $labOutputs = $null
    $readiness = $null
    $readiness = .\scripts\start-lab.ps1 -ResourceGroupName $resourceGroupName `
        -Region $region -Mode Readiness | ConvertFrom-Json
    if (-not $readiness.infrastructure_ready) { throw 'The prepared infrastructure is not ready.' }
    $labOutputs = $readiness.outputs
    $readiness | Select-Object infrastructure_ready
}
```

**Expected:** `infrastructure_ready` is `True`. This checks existing infrastructure; it does not deploy the application. You will create that application in the next exercise.

Your lab scope is resource group **LAB722**, region **West US 3**, in the subscription you selected. Use this same scope for the Express application.

If sign-in fails, resources are missing, or a request returns **403 Forbidden**, stop and contact your instructor. Do not redeploy the infrastructure or change role assignments.
