@echo off
chcp 65001 >nul
cd /d "%~dp0"
title ReachKit
set PY=C:\Users\hysoo\Projects\RoadLog\.venv\Scripts\pythonw.exe
if not exist "%PY%" set PY=C:\Users\hysoo\Projects\RoadLog\.venv\Scripts\python.exe
if not exist "%PY%" set PY=pythonw
if not exist "%PY%" set PY=python
start "" "%PY%" "%~dp0app.py"
if errorlevel 1 (
  echo ReachKit failed to start.
  echo   "%PY%" -m pip install -r "%~dp0requirements.txt"
  echo   "%PY%" -m playwright install chromium
  pause
)
