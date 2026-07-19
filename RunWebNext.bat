@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Local Subsidies Web UI Next (127.0.0.1:8600)
cd /d "%~dp0"

set "PY=%CD%\.venv\Scripts\python.exe"
set "LAUNCH=%CD%\scripts\_next_web_launcher.py"

if not exist "%PY%" (
  echo [ERROR] .venv 가 없습니다. SetupOffline.bat 또는 pip install -r requirements.txt
  pause
  exit /b 1
)

"%PY%" -c "import fastapi, uvicorn" 2>nul
if errorlevel 1 (
  echo [ERROR] fastapi/uvicorn 미설치:
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
echo   브라우저: http://127.0.0.1:8600
echo   web\out\index.html 을 직접 열지 마세요 ^(file:// — 메뉴/API 동작 안 함^)
echo.
echo 이 창을 닫으면 서버가 종료됩니다.
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
