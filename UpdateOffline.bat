@echo off
setlocal EnableExtensions
REM Offline update to latest (full sync). ASCII only - codepage safe.
REM Double-click OK: auto-finds update-to-vX.Y.Z.zip in this folder / project root.
if /I not "%~1"=="_run" (
  cmd /k "%~f0" _run %*
  exit /b
)

cd /d "%~dp0"
title Local Subsidies Offline Update

echo.
echo ========================================
echo  Offline update to latest
echo ========================================
echo.
echo Preserved: configs\local.yaml, .venv, vendor\wheels, data_root
echo Guide: docs\offline_update.md
echo.

set "SRC=%~2"
set "AUTO_WHEELS="

REM Optional arg: /autowheels (2nd or 3rd)
if /I "%~2"=="/autowheels" (
  set "SRC="
  set "AUTO_WHEELS=1"
)
if /I "%~3"=="/autowheels" set "AUTO_WHEELS=1"

if "%SRC%"=="" (
  echo No zip path given - searching for update-to-v*.zip / update-v*.zip ...
  echo.
)

if "%SRC%"=="" (
  if "%AUTO_WHEELS%"=="1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\apply_offline_update.ps1" -ProjectRoot "%CD%" -AutoWheels
  ) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\apply_offline_update.ps1" -ProjectRoot "%CD%"
  )
) else (
  if "%AUTO_WHEELS%"=="1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\apply_offline_update.ps1" -ProjectRoot "%CD%" -Source "%SRC%" -AutoWheels
  ) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\apply_offline_update.ps1" -ProjectRoot "%CD%" -Source "%SRC%"
  )
)
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" goto :fail

echo.
echo Done. Follow Next: lines above.
echo.
pause
exit /b 0

:fail
echo.
echo [ERROR] Update failed. See messages above.
echo Usage:
echo   UpdateOffline.bat
echo   UpdateOffline.bat D:\USB\update-to-v0.5.2.zip
echo   UpdateOffline.bat D:\USB\update-to-v0.5.2.zip /autowheels
echo.
pause
exit /b 1
