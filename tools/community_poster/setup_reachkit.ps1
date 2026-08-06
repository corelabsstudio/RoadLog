#Requires -Version 5.1
<#
.SYNOPSIS
  리치킷 1.0 원클릭 설치 (로컬 venv + 의존성 + Chromium + 바로가기)
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  리치킷 (ReachKit) 1.0 설치" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "경로: $Root"
Write-Host ""

function Find-Python {
  $cands = @(
    (Get-Command py -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
    (Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "C:\Users\hysoo\Projects\RoadLog\.venv\Scripts\python.exe"
  ) | Where-Object { $_ -and (Test-Path $_) }
  foreach ($c in $cands) {
    try {
      $v = & $c -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
      if ($v -match '^(3\.(1[0-9]|[2-9][0-9]))') { return $c }
    } catch {}
  }
  return $null
}

$py = Find-Python
if (-not $py) {
  Write-Host "ERROR: Python 3.10+ 가 필요합니다. https://www.python.org/downloads/" -ForegroundColor Red
  exit 1
}
Write-Host "[1/5] Python: $py"

$venv = Join-Path $Root ".venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
  Write-Host "[2/5] venv 생성..."
  & $py -m venv $venv
} else {
  Write-Host "[2/5] venv 이미 있음"
}

$venvPy = Join-Path $venv "Scripts\python.exe"
$venvPip = Join-Path $venv "Scripts\pip.exe"

Write-Host "[3/5] 패키지 설치 (requirements.txt)..."
& $venvPip install --upgrade pip
& $venvPip install -r (Join-Path $Root "requirements.txt")

Write-Host "[4/5] Playwright Chromium..."
& $venvPy -m playwright install chromium

Write-Host "[5/5] 환경 점검..."
& $venvPy (Join-Path $Root "healthcheck.py")

# Desktop shortcut
$desk = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $desk "리치킷.lnk"
$bat = Join-Path $Root "ReachKit.bat"
try {
  $w = New-Object -ComObject WScript.Shell
  $s = $w.CreateShortcut($lnkPath)
  $s.TargetPath = $bat
  $s.WorkingDirectory = $Root
  $ico = Join-Path $Root "assets\icon.ico"
  if (Test-Path $ico) { $s.IconLocation = $ico }
  $s.Description = "리치킷 1.0 — 3단계 홍보 글 올리기"
  $s.Save()
  Write-Host "바탕화면 바로가기: $lnkPath"
} catch {
  Write-Host "바로가기 생성 실패 (무시 가능): $_"
}

New-Item -ItemType Directory -Force -Path (Join-Path $Root "data") | Out-Null
Write-Host ""
Write-Host "설치 완료. 실행: ReachKit.bat  또는 바탕화면「리치킷」" -ForegroundColor Green
Write-Host ""
