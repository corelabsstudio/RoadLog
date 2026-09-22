$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$adminUrl = 'http://127.0.0.1:8501/admin/'
$healthUrl = 'http://127.0.0.1:8501/api/health'

Set-Location $projectRoot

if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Host 'ROADLOG 실행환경이 없습니다. Codex에게 실행환경 복구를 요청해 주세요.' -ForegroundColor Red
    Read-Host 'Enter를 누르면 닫힙니다'
    exit 1
}

try {
    $existing = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 2
    if ($existing.StatusCode -eq 200) {
        Start-Process $adminUrl
        exit 0
    }
} catch {
    # 서버가 꺼져 있으면 아래에서 새로 시작한다.
}

Write-Host 'ROADLOG 관리자 서버를 시작합니다.' -ForegroundColor Cyan
Write-Host '브라우저가 자동으로 열립니다. 서버를 끄려면 이 창에서 Ctrl+C를 누르세요.'

$browserCommand = "Start-Sleep -Seconds 3; Start-Process '$adminUrl'"
Start-Process powershell.exe -WindowStyle Hidden -ArgumentList '-NoProfile', '-Command', $browserCommand

& $pythonPath -m uvicorn server:app --host 127.0.0.1 --port 8501
