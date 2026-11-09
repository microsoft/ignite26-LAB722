# Render the source placeholders, then install as a First Displayable VM LCA.
$ErrorActionPreference = 'Stop'
$root = 'C:\Lab\Reactor2'
$sourceBytes = [Convert]::FromBase64String('__REACTOR2_SOURCE_BASE64__')
$hash = [Security.Cryptography.SHA256]::Create()
$actual = ([BitConverter]::ToString($hash.ComputeHash($sourceBytes))).Replace('-', '').ToLowerInvariant()
if ($actual -cne '__REACTOR2_SOURCE_SHA256__') { throw 'Reactor 2 source payload digest differs.' }
$hash.Dispose()
$null = New-Item -ItemType Directory -Path $root -Force
$archivePath = Join-Path $root 'reactor2-source.zip'
[IO.File]::WriteAllBytes($archivePath, $sourceBytes)
Expand-Archive -LiteralPath $archivePath -DestinationPath $root -Force
$subscriptionId = '@lab.CloudSubscription.Id'
$tenantId = '@lab.CloudSubscription.TenantId'
$rg = '@lab.CloudResourceGroup(ResourceGroup1).Name'
$shell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('CommonDesktopDirectory')
$shortcut = $shell.CreateShortcut((Join-Path $desktop 'Reactor 2 - sign in and prepare.lnk'))
$shortcut.TargetPath = (Get-Command pwsh -ErrorAction Stop).Source
$shortcut.Arguments = "-NoProfile -NoExit -File `"$root\scripts\run-reactor-skillable-vm.ps1`" -SubscriptionId $subscriptionId -TenantId $tenantId -ResourceGroupName `"$rg`""
$shortcut.WorkingDirectory = $root
$shortcut.Description = 'Sign into the allocated lab Entra account, then prepare the native baseline and hosted research app.'
$shortcut.Save()
Write-Output 'Reactor 2 setup files installed. Open the desktop sign-in and prepare shortcut; the application is not ready yet.'
