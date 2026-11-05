#requires -Version 7.2
[CmdletBinding(SupportsShouldProcess)]
param(
    [string] $RepositoryPath = (Split-Path -Parent $PSScriptRoot),
    [string] $DesktopPath = [Environment]::GetFolderPath('DesktopDirectory')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'Lab desktop preparation requires the Windows learner VM.' }
$RepositoryPath = (Resolve-Path -LiteralPath $RepositoryPath -ErrorAction Stop).Path
if (-not (Test-Path -LiteralPath (Join-Path $RepositoryPath 'scripts\start-lab.ps1') -PathType Leaf)) {
    throw 'The desktop shortcuts require the prepared LAB722 checkout.'
}
if (-not (Test-Path -LiteralPath $DesktopPath -PathType Container)) {
    throw 'The learner desktop directory does not exist.'
}
$powershell = (Get-Command pwsh.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$terminal = (Get-Command wt.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$shortcuts = @(
    @{ Name = 'PowerShell 7'; Target = $powershell; Arguments = '-NoLogo' },
    @{ Name = 'Windows Terminal'; Target = $terminal
       Arguments = "-d `"$RepositoryPath`" `"$powershell`" -NoLogo" }
)
foreach ($item in $shortcuts) {
    $path = Join-Path $DesktopPath ($item.Name + '.lnk')
    if ($PSCmdlet.ShouldProcess($path, 'Create learner shell shortcut')) {
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($path)
        $shortcut.TargetPath = $item.Target
        $shortcut.Arguments = $item.Arguments
        $shortcut.WorkingDirectory = $RepositoryPath
        $shortcut.Description = 'Open the prepared Caldova lab checkout'
        $shortcut.Save()
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Desktop shortcut was not created: $path"
        }
        [pscustomobject] @{ Name = $item.Name; Path = $path; WorkingDirectory = $RepositoryPath }
    }
}
