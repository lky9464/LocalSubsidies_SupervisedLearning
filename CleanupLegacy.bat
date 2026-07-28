@echo off
setlocal EnableExtensions
REM Wipe legacy pipeline artifacts + ops DB. Keeps raw/ by default.
if /I not "%~1"=="_run" (
  cmd /k "%~f0" _run %*
  exit /b
)

cd /d "%~dp0"
title Local Subsidies Legacy Cleanup

set "PY=%CD%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo.
echo ========================================
echo  Legacy cleanup (artifacts + ops DB)
echo ========================================
echo.
echo Stop RunWebNext.bat first.
echo Keeps: raw\, raw_inference\, configs\local.yaml
echo Removes: interim, processed, algorithms, runs, ops, outputs\reports\*
echo.
echo Guide: docs\offline_setup.md / scripts\cleanup_legacy_artifacts.py
echo.

"%PY%" "%CD%\scripts\cleanup_legacy_artifacts.py" %2 %3 %4 %5
set "EC=%ERRORLEVEL%"
echo.
pause
exit /b %EC%
