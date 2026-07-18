@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Local Subsidies Web UI (127.0.0.1)
cd /d "%~dp0"

set "PY=%CD%\.venv\Scripts\python.exe"
set "APP=%CD%\app\main.py"
set "PICK=%CD%\scripts\_pick_web_port.py"
set "PORTFILE=%TEMP%\lsl_web_port.txt"

if not exist "%PY%" (
  echo [ERROR] .venv 가 없습니다.
  echo   python -m venv .venv
  echo   .venv\Scripts\activate
  echo   pip install -r requirements.txt
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

REM 포트 선택 결과를 파일로 받아 for /f 경로 깨짐을 피함
del "%PORTFILE%" 2>nul
"%PY%" "%PICK%" >"%PORTFILE%" 2>nul
if errorlevel 1 (
  echo [ERROR] 사용 가능한 포트^(8501~8510^)를 찾지 못했습니다.
  echo   다른 Streamlit/웹 서버를 종료하거나 PC를 재시작 후 다시 시도하세요.
  type "%PORTFILE%" 2>nul
  pause
  exit /b 1
)

set "PORT="
set /p PORT=<"%PORTFILE%"
del "%PORTFILE%" 2>nul
if not defined PORT (
  echo [ERROR] 포트 번호를 읽지 못했습니다.
  pause
  exit /b 1
)

echo %PORT%| findstr /r "^[0-9][0-9]*$" >nul
if errorlevel 1 (
  echo [ERROR] 잘못된 포트 값: [%PORT%]
  pause
  exit /b 1
)

REM 이미 건강한 서버면 브라우저만 열고 종료
set "LSL_PORT=%PORT%"
"%PY%" -c "import os,sys,urllib.request;p=os.environ['LSL_PORT'];r=urllib.request.urlopen('http://127.0.0.1:'+p+'/_stcore/health',timeout=2);sys.exit(0 if r.read().strip().lower().startswith(b'ok') else 1)" 2>nul
if not errorlevel 1 (
  echo.
  echo 이미 실행 중입니다: http://127.0.0.1:%PORT%
  echo 브라우저를 엽니다.
  start "" "http://127.0.0.1:%PORT%"
  pause
  exit /b 0
)

echo.
echo Starting Streamlit on http://127.0.0.1:%PORT%
echo 이 창을 닫으면 서버가 종료됩니다.
echo 브라우저가 자동으로 열리지 않으면 위 주소를 직접 입력하세요.
echo.

start "" "http://127.0.0.1:%PORT%"

"%PY%" -m streamlit run "%APP%" --server.address=127.0.0.1 --server.port=%PORT% --browser.gatherUsageStats=false --server.headless=true

echo.
echo Streamlit 이 종료되었습니다.
pause
endlocal
