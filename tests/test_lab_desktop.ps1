#requires -Version 7.2
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Split-Path -Parent $PSScriptRoot
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('lab722-desktop-' + [guid]::NewGuid().ToString('N'))
[void] [IO.Directory]::CreateDirectory($fixture)
$paths = @('PowerShell 7.lnk', 'Windows Terminal.lnk') | ForEach-Object { Join-Path $fixture $_ }
try {
    & (Join-Path $root 'scripts\initialize-lab-desktop.ps1') -DesktopPath $fixture -WhatIf | Out-Null
    if (@(Get-ChildItem -LiteralPath $fixture).Count) { throw 'WhatIf created a desktop shortcut.' }
    $created = @(& (Join-Path $root 'scripts\initialize-lab-desktop.ps1') -DesktopPath $fixture)
    if ($created.Count -ne 2) { throw 'Both shell shortcuts must be created.' }
    $shell = New-Object -ComObject WScript.Shell
    foreach ($path in $paths) {
        $shortcut = $shell.CreateShortcut($path)
        if ($shortcut.WorkingDirectory -cne $root -or -not (Test-Path -LiteralPath $shortcut.TargetPath)) {
            throw 'A shortcut lost its prepared checkout or installed shell target.'
        }
        if ($path.EndsWith('Windows Terminal.lnk') -and
            ($shortcut.Arguments -notmatch 'pwsh\.exe' -or -not $shortcut.Arguments.Contains($root))) {
            throw 'Windows Terminal must explicitly open PowerShell 7 in the checkout.'
        }
    }
    & (Join-Path $root 'scripts\initialize-lab-desktop.ps1') -DesktopPath $fixture | Out-Null
    if (@(Get-ChildItem -LiteralPath $fixture).Count -ne 2) { throw 'Repeated preparation created extra shortcuts.' }
    'PASS: desktop targets, PowerShell profile, working directory, repeat preparation and WhatIf.'
}
finally {
    foreach ($path in $paths) {
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
    }
    [IO.Directory]::Delete($fixture)
}
