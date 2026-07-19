@echo off
setlocal EnableExtensions
title Local Subsidies Web UI Next (127.0.0.1:8600)
cd /d "%~dp0"

set "PY=%CD%\.venv\Scripts\python.exe"
set "LAUNCH=%CD%\scripts\_next_web_launcher.py"

if not exist "%PY%" (
  echo [ERROR] .venv missing. Run SetupOffline.bat or: pip install -r requirements.txt
  pause
  exit /b 1
)

"%PY%" -c "import fastapi, uvicorn" 2>nul
if errorlevel 1 (
  echo [ERROR] fastapi/uvicorn not installed:
  echo   .venv\Scripts\activate
  echo   pip install -r requirements.txt
  pause
  exit /b 1
)

if /I "%~1"=="restart" goto DO_RESTART
if /I "%~1"=="/restart" goto DO_RESTART

echo.
echo Starting FastAPI + Next static UI ...
echo.
echo   Browser: http://127.0.0.1:8600
echo   Do not open web\out\index.html via file://  ^(menu/API will not work^)
echo.
echo Closing this window stops the server.
echo.
"%PY%" "%LAUNCH%"
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" echo [ERROR] exit=%EC%
pause
exit /b %EC%

:DO_RESTART
echo Restarting ...
"%PY%" "%LAUNCH%" --restart
set "EC=%ERRORLEVEL%"
pause
exit /b %EC%
