@echo off
setlocal EnableExtensions
REM Keep window open on double-click so errors are visible.
if /I not "%~1"=="_run" (
  cmd /k "%~f0" _run
  exit /b
)

cd /d "%~dp0"
title Local Subsidies Offline Setup
chcp 65001 >nul 2>&1

set "LOG=%CD%\SetupOffline.log"
echo ===== SetupOffline %DATE% %TIME% ===== > "%LOG%"
call :log "cwd=%CD%"

echo.
echo ========================================
echo  Offline setup (one-time)
echo ========================================
echo.

REM --- Python ---
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
  echo [ERROR] Python not found.
  echo   Install Python 3.12 x64 on this PC first, then run SetupOffline.bat again.
  echo   Guide: docs\offline_setup.md
  call :log "ERROR: Python not found"
  goto :fail
)

echo [1/4] Python: %PYEXE%
call :log "Python=%PYEXE%"
"%PYEXE%" -c "import sys; v=sys.version_info; raise SystemExit(0 if (v.major,v.minor)==(3,12) else 1)" 2>nul
if errorlevel 1 (
  echo [WARN] Not Python 3.12. Wheels are built for 3.12 x64. Continuing anyway...
  echo.
  call :log "WARN: not Python 3.12"
)

REM --- wheels ---
set "WHEELDIR=%CD%\vendor\wheels"
if not exist "%WHEELDIR%" (
  echo [ERROR] Folder missing: vendor\wheels
  echo   Unzip wheels-win-amd64-py312.zip so .whl files are under vendor\wheels\
  echo   Example:
  echo     LocalSubsidies_SupervisedLearning\
  echo       vendor\wheels\*.whl
  call :log "ERROR: vendor\wheels missing"
  goto :fail
)

dir /b "%WHEELDIR%\*.whl" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] No .whl files in vendor\wheels
  echo   Unzip wheels-win-amd64-py312.zip into vendor\wheels\
  call :log "ERROR: no whl files"
  goto :fail
)

REM --- venv ---
echo [2/4] Creating/checking .venv ...
call :log "venv step"
if not exist "%CD%\.venv\Scripts\python.exe" (
  "%PYEXE%" -m venv .venv
  if errorlevel 1 (
    echo [ERROR] venv creation failed.
    call :log "ERROR: venv failed"
    goto :fail
  )
)

set "VPIP=%CD%\.venv\Scripts\pip.exe"
set "VPY=%CD%\.venv\Scripts\python.exe"
if not exist "%VPIP%" (
  echo [ERROR] .venv\Scripts\pip.exe missing after venv create.
  call :log "ERROR: pip missing"
  goto :fail
)

echo [3/4] Installing packages from vendor\wheels (no internet)...
call :log "pip install start"
"%VPIP%" install --no-index --find-links="%WHEELDIR%" -r "%CD%\requirements.lock.txt"
if errorlevel 1 (
  echo [ERROR] pip install failed.
  echo   Check Python 3.12 x64 and that wheels match.
  call :log "ERROR: pip install failed"
  goto :fail
)

"%VPY%" -c "import fastapi, uvicorn, pandas, sklearn, catboost; print('OK: fastapi', fastapi.__version__)"
if errorlevel 1 (
  echo [ERROR] Import check failed.
  call :log "ERROR: import failed"
  goto :fail
)

REM --- local.yaml ---
echo [4/4] configs\local.yaml ...
if not exist "%CD%\configs\local.yaml" (
  copy /Y "%CD%\configs\local.yaml.example" "%CD%\configs\local.yaml" >nul
  echo   Copied local.yaml from example. Edit data_root path:
  echo     notepad configs\local.yaml
) else (
  echo   local.yaml already exists. Check data_root path.
)

if not exist "%CD%\web\out\index.html" (
  echo.
  echo [WARN] web\out\index.html not found.
  echo   Unzip web-out.zip into web\out\  ^(need web\out\index.html^)
  echo.
  call :log "WARN: web\out missing"
)

echo.
echo ========================================
echo  Setup complete
echo ========================================
echo.
echo  Next:
echo    1^) notepad configs\local.yaml  - set data_root
echo    2^) InitDataRoot.bat
echo    3^) Put CSV into raw / raw_inference
echo    4^) If needed: web-out.zip -^> web\out\
echo    5^) RunWebNext.bat  -^> http://127.0.0.1:8600
echo.
echo  Log: SetupOffline.log
echo  Guide: docs\offline_setup.md
echo.
call :log "OK complete"
goto :end

:fail
echo.
echo Setup failed. See messages above and SetupOffline.log
echo.
goto :end

:log
>> "%LOG%" echo %~1
exit /b 0

:end
echo.
echo Window stays open so you can read messages. Type exit to close.
echo.
endlocal
exit /b 0
