@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Local Subsidies — Offline Setup
cd /d "%~dp0"

echo.
echo ========================================
echo  오프라인 환경 설치 (1회)
echo ========================================
echo.

REM --- Python 확인 ---
set "PYEXE="
where py >nul 2>&1
if not errorlevel 1 (
  for /f "delims=" %%I in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%I"
)
if not defined PYEXE (
  where python >nul 2>&1
  if not errorlevel 1 (
    for /f "delims=" %%I in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%I"
  )
)

if not defined PYEXE (
  echo [ERROR] Python 을 찾을 수 없습니다.
  echo   오프라인 PC에 Python 3.12 ^(64-bit^) 를 먼저 설치하세요.
  echo   설치 후 이 창을 닫고 SetupOffline.bat 을 다시 실행하세요.
  echo   안내: docs\offline_setup.md
  pause
  exit /b 1
)

echo [1/4] Python: %PYEXE%
"%PYEXE%" -c "import sys; v=sys.version_info; raise SystemExit(0 if (v.major,v.minor)==(3,12) else 1)" 2>nul
if errorlevel 1 (
  echo [WARN] Python 3.12 가 아닙니다. wheel 묶음은 3.12용입니다.
  echo        가능하면 3.12 x64 로 다시 설치하세요. 계속 진행합니다...
  echo.
)

REM --- wheels 확인 ---
set "WHEELDIR=%CD%\vendor\wheels"
if not exist "%WHEELDIR%" (
  echo [ERROR] vendor\wheels 폴더가 없습니다.
  echo.
  echo   GitHub Releases 에서 wheels-win-amd64-py312.zip 을 받아
  echo   압축을 풀면 vendor\wheels\ 아래에 .whl 파일들이 있어야 합니다.
  echo.
  echo   예^)
  echo     LocalSubsidies_SupervisedLearning\
  echo       vendor\wheels\*.whl
  echo.
  echo   Release: https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases
  echo   안내: docs\offline_setup.md
  pause
  exit /b 1
)

dir /b "%WHEELDIR%\*.whl" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] vendor\wheels 에 .whl 파일이 없습니다.
  echo   wheels-win-amd64-py312.zip 을 이 폴더에 풀어 주세요.
  pause
  exit /b 1
)

REM --- venv ---
echo [2/4] 가상환경 .venv 생성/확인...
if not exist "%CD%\.venv\Scripts\python.exe" (
  "%PYEXE%" -m venv .venv
  if errorlevel 1 (
    echo [ERROR] venv 생성 실패.
    pause
    exit /b 1
  )
)

set "VPIP=%CD%\.venv\Scripts\pip.exe"
set "VPY=%CD%\.venv\Scripts\python.exe"

echo [3/4] vendor\wheels 에서 패키지 설치 (인터넷 불필요)...
"%VPIP%" install --no-index --find-links="%WHEELDIR%" -r "%CD%\requirements.lock.txt"
if errorlevel 1 (
  echo [ERROR] 패키지 설치 실패.
  echo   Python 버전^(3.12 x64^)과 wheel 묶음이 일치하는지 확인하세요.
  pause
  exit /b 1
)

"%VPY%" -c "import fastapi, uvicorn, pandas, sklearn, catboost; print('OK: fastapi', fastapi.__version__)"
if errorlevel 1 (
  echo [ERROR] import 검증 실패.
  pause
  exit /b 1
)

REM --- local.yaml ---
echo [4/4] configs\local.yaml ...
if not exist "%CD%\configs\local.yaml" (
  copy /Y "%CD%\configs\local.yaml.example" "%CD%\configs\local.yaml" >nul
  echo   local.yaml 을 예제에서 복사했습니다.
  echo   메모장으로 열어 data_root 경로를 본인 PC에 맞게 수정하세요.
  echo     notepad configs\local.yaml
) else (
  echo   이미 존재합니다. ^(경로만 확인하세요^)
)

if not exist "%CD%\web\out\index.html" (
  echo.
  echo [WARN] web\out\index.html 이 없습니다.
  echo   Release 의 web-out.zip 을 풀어 web\out\ 이 되게 하세요.
  echo   예^) web\out\index.html 이 보여야 합니다.
  echo.
)

echo.
echo ========================================
echo  설치 완료
echo ========================================
echo.
echo  다음 단계:
echo    1^) notepad configs\local.yaml  — data_root 수정
echo    2^) InitDataRoot.bat            — 데이터 폴더 골격 생성 ^(선택^)
echo    3^) raw / raw_inference 에 CSV 배치
echo    4^) ^(미완료 시^) web-out.zip → web\out\
echo    5^) RunWebNext.bat              — 웹 UI 실행 (http://127.0.0.1:8600^)
echo.
echo  상세: docs\offline_setup.md
echo.
pause
endlocal
