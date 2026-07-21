# Desktop shortcut for ReachKit
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Bat = Join-Path $Root "ReachKit.bat"
$Ico = Join-Path $Root "assets\icon.ico"
$Desktop = [Environment]::GetFolderPath("Desktop")

if (-not (Test-Path -LiteralPath $Bat)) {
    Write-Error "Missing ReachKit.bat in $Root"
    exit 1
}

$Wsh = New-Object -ComObject WScript.Shell
$Lnk = Join-Path $Desktop "ReachKit.lnk"
$Sc = $Wsh.CreateShortcut($Lnk)
$Sc.TargetPath = $Bat
$Sc.WorkingDirectory = $Root
$Sc.Description = "ReachKit — analyze, write, promote"
if (Test-Path -LiteralPath $Ico) {
    $Sc.IconLocation = ($Ico + ",0")
}
$Sc.Save()
Write-Host "Created: $Lnk"
Write-Host "Icon: $Ico"
