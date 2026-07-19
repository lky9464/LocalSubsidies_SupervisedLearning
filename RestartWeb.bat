@echo off
REM FastAPI+Next UI(8600) 재시작 — Cursor stop hook / 수동 재시작용
cd /d "%~dp0"

set "PY=%CD%\.venv\Scripts\python.exe"
set "LAUNCH=%CD%\scripts\_next_web_launcher.py"
set "GUARD=%CD%\scripts\_restart_web_guard.ps1"

powershell -NoProfile -ExecutionPolicy Bypass -File "%GUARD%"
if errorlevel 2 (
  echo [RestartWeb] skipped - already restarting or just restarted.
  exit /b 0
)

if exist "%PY%" if exist "%LAUNCH%" (
  "%PY%" "%LAUNCH%" stop >nul 2>&1
)

timeout /t 1 /nobreak >nul

start "Local Subsidies Web UI Next" cmd /k ""%~dp0RunWebNext.bat" restart"
exit /b 0
