@echo off
setlocal EnableExtensions
REM Incremental offline update — preserves configs\local.yaml, .venv, vendor\wheels.
if /I not "%~1"=="_run" (
  cmd /k "%~f0" _run %*
  exit /b
)

cd /d "%~dp0"
title Local Subsidies Offline Update

echo.
echo ========================================
echo  Offline update (changed files only)
echo ========================================
echo.
echo Preserved: configs\local.yaml, .venv, vendor\wheels, data_root (outside project)
echo Guide: docs\offline_update.md
echo.

if "%~2"=="" (
  echo Usage:
  echo   UpdateOffline.bat [update_folder_or_zip]
  echo.
  echo Examples:
  echo   UpdateOffline.bat D:\USB\update-v0.5.1
  echo   UpdateOffline.bat D:\USB\update-v0.5.1.zip
  echo.
  echo Prepare package on online PC:
  echo   powershell -ExecutionPolicy Bypass -File scripts\build_offline_update_package.ps1
  echo   ^(creates dist\update-vX.Y.Z.zip^)
  echo.
  goto :fail
)

set "SRC=%~2"
if not exist "%SRC%" (
  echo [ERROR] Not found: %SRC%
  goto :fail
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\apply_offline_update.ps1" -ProjectRoot "%CD%" -Source "%SRC%"
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" goto :fail

echo.
echo Done. If SetupOffline was NOT requested above, run:
echo   RunWebNext.bat restart
echo.
pause
exit /b 0

:fail
echo.
pause
exit /b 1
