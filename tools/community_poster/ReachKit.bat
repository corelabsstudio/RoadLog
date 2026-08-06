@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 리치킷

REM 1) 제품 로컬 venv (setup_reachkit.ps1 설치 후)
set "PY=%~dp0.venv\Scripts\pythonw.exe"
if exist "%PY%" goto :run
set "PY=%~dp0.venv\Scripts\python.exe"
if exist "%PY%" goto :run

REM 2) RoadLog monorepo venv (개발 경로)
set "PY=%~dp0..\..\.venv\Scripts\pythonw.exe"
if exist "%PY%" goto :run
set "PY=%~dp0..\..\.venv\Scripts\python.exe"
if exist "%PY%" goto :run

REM 3) 시스템 Python
where pythonw >nul 2>&1 && set "PY=pythonw" && goto :run
where python >nul 2>&1 && set "PY=python" && goto :run

echo.
echo [리치킷] Python을 찾을 수 없습니다.
echo 설치:  PowerShell에서
echo   powershell -ExecutionPolicy Bypass -File "%~dp0setup_reachkit.ps1"
echo.
pause
exit /b 1

:run
start "" "%PY%" "%~dp0app.py"
if errorlevel 1 (
  echo.
  echo [리치킷] 실행 실패. 설치를 다시 시도하세요:
  echo   powershell -ExecutionPolicy Bypass -File "%~dp0setup_reachkit.ps1"
  echo.
  pause
)
