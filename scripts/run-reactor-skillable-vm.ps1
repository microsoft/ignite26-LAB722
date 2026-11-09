#requires -Version 7.3
[CmdletBinding()]
param(
    [Parameter(Mandatory)][guid]$SubscriptionId,
    [Parameter(Mandatory)][guid]$TenantId,
    [Parameter(Mandatory)][string]$ResourceGroupName
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$accountText = & az account show --output json 2>$null
$signedIn = $LASTEXITCODE -eq 0
if ($signedIn) {
    $account = $accountText -join "`n" | ConvertFrom-Json
    $signedIn = $account.tenantId -ieq $TenantId -and $account.user.type -ceq 'user'
}
if (-not $signedIn) {
    Write-Host 'Sign into the allocated lab Entra user, not a personal account or service principal.'
    & az login --use-device-code --tenant $TenantId --output none
    if ($LASTEXITCODE -ne 0) { throw 'Learner Entra sign-in failed; no deployment was attempted.' }
}
& az account set --subscription $SubscriptionId
if ($LASTEXITCODE -ne 0) { throw 'The signed-in learner cannot select the allocated subscription.' }
$account = & az account show --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $account.user.type -cne 'user' -or
    $account.id -ine $SubscriptionId -or $account.tenantId -ine $TenantId) {
    throw 'Setup requires the allocated learner user and subscription; no service-principal fallback is supported.'
}
$basePython = & py -3.13 -c 'import sys; print(sys.executable)'
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $basePython)) {
    throw 'The prepared VM must provide Python 3.13 through the py launcher.'
}
$venv = Join-Path $root '.venv'
$python = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    & $basePython -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Creating the isolated setup environment failed.' }
}
& $python -B -c 'from azure.ai.projects.models import HostedAgentDefinition,OpenApiToolboxTool; from mcp import ClientSession; from azure.identity.aio import AzureCliCredential'
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install -r (Join-Path $root 'src\orchestrator\requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Restoring the declared setup dependencies failed.' }
    & $python -B -c 'from azure.ai.projects.models import HostedAgentDefinition,OpenApiToolboxTool; from mcp import ClientSession; from azure.identity.aio import AzureCliCredential'
    if ($LASTEXITCODE -ne 0) { throw 'The restored SDK does not expose the required Toolbox/hosted types.' }
}
$credentialPath = Join-Path $root '.build-contexts\demo-credentials.clixml'
if (Test-Path -LiteralPath $credentialPath) {
    $credentials = Import-Clixml -LiteralPath $credentialPath
} else {
    $credentials = @{}
    foreach ($name in @('alice', 'bob')) {
        $password = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
        $credentials[$name] = [pscredential]::new($name, (ConvertTo-SecureString $password -AsPlainText -Force))
        $password = $null
    }
    $null = New-Item -ItemType Directory -Path (Split-Path -Parent $credentialPath) -Force
    $credentials | Export-Clixml -LiteralPath $credentialPath
}
$prepared = & (Join-Path $PSScriptRoot 'initialize-reactor-skillable.ps1') `
    -SubscriptionId $SubscriptionId -TenantId $TenantId -ResourceGroupName $ResourceGroupName `
    -AlicePassword $credentials.alice.Password -BobPassword $credentials.bob.Password -PythonExecutable $python
$desktop = [Environment]::GetFolderPath('DesktopDirectory')
@"
[InternetShortcut]
URL=$($prepared.FrontendUrl)
"@ | Set-Content -LiteralPath (Join-Path $desktop 'Reactor 2 research app.url') -Encoding ascii
$prepared | ConvertTo-Json -Depth 20 | Set-Content (Join-Path $root 'learner-values.json') -Encoding utf8NoBOM
Write-Host "REACTOR2_SKILLABLE_READY $($prepared.FrontendUrl)"
