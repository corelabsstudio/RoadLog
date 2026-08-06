#Requires -Version 5.1
# 리치킷 1.0 포터블 zip (venv/캐시 제외)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$stamp = Get-Date -Format "yyyyMMdd"
$outDir = Join-Path ([Environment]::GetFolderPath("Desktop")) "ReachKit_1.0_portable_$stamp"
$zip = "$outDir.zip"

if (Test-Path $outDir) { Remove-Item $outDir -Recurse -Force }
New-Item -ItemType Directory -Path $outDir | Out-Null

$excludeDirs = @(".venv", "__pycache__", ".git", "data")
Get-ChildItem $Root -Force | Where-Object {
  $_.Name -notin $excludeDirs -and $_.Name -notmatch '^\.'
} | ForEach-Object {
  Copy-Item $_.FullName -Destination (Join-Path $outDir $_.Name) -Recurse -Force
}

# empty data dir + keep structure
New-Item -ItemType Directory -Path (Join-Path $outDir "data") -Force | Out-Null
Set-Content -Path (Join-Path $outDir "data\.gitkeep") -Value ""

# drop pyc recursively
Get-ChildItem $outDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $outDir "*") -DestinationPath $zip -Force
Remove-Item $outDir -Recurse -Force

Write-Host "포터블 패키지: $zip" -ForegroundColor Green
Write-Host "인수 PC: 압축 해제 후 setup_reachkit.ps1"
