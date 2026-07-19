@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Local Subsidies Web UI (127.0.0.1)
cd /d "%~dp0"

set "PY=%CD%\.venv\Scripts\python.exe"
set "LAUNCH=%CD%\scripts\_web_launcher.py"

if not exist "%PY%" (
  echo [ERROR] .venv 가 없습니다.
  echo   python -m venv .venv
  echo   .venv\Scripts\activate
  echo   pip install -r requirements.txt
  pause
  exit /b 1
)

if not exist "%LAUNCH%" (
  echo [ERROR] scripts\_web_launcher.py 가 없습니다.
  pause
  exit /b 1
)

"%PY%" -c "import streamlit" 2>nul
if errorlevel 1 (
  echo [ERROR] streamlit 미설치. 아래를 실행하세요:
  echo   .venv\Scripts\activate
  echo   pip install -r requirements.txt
  pause
  exit /b 1
)

REM for /f 따옴표 깨짐 방지: launcher 가 브라우저 오픈까지 담당
if /I "%~1"=="restart" goto DO_RESTART
if /I "%~1"=="/restart" goto DO_RESTART
if /I "%~1"=="-restart" goto DO_RESTART

echo.
echo Starting Streamlit ...
echo 이 창을 닫으면 서버가 종료됩니다.
echo.
"%PY%" "%LAUNCH%" run
set "EC=%ERRORLEVEL%"
echo.
if not "%EC%"=="0" (
  echo [ERROR] Streamlit 을 시작하지 못했습니다. ^(exit=%EC%^)
)
pause
exit /b %EC%

:DO_RESTART
echo.
echo 기존 Streamlit 을 종료하고 재시작합니다...
echo 이 창을 닫으면 서버가 종료됩니다.
echo.
"%PY%" "%LAUNCH%" run --restart
set "EC=%ERRORLEVEL%"
echo.
if not "%EC%"=="0" (
  echo [ERROR] Streamlit 을 시작하지 못했습니다. ^(exit=%EC%^)
)
pause
exit /b %EC%
