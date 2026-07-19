@echo off
setlocal EnableExtensions
REM Keep window open on double-click so errors are visible.
if /I not "%~1"=="_run" (
  if "%~1"=="" (
    cmd /k "%~f0" _run
  ) else (
    cmd /k "%~f0" _run %*
  )
  exit /b
)

cd /d "%~dp0"
title Local Subsidies Init data_root

echo.
echo ========================================
echo  Init data_root folders
echo ========================================
echo.

set "VPY=%CD%\.venv\Scripts\python.exe"
set "PYEXE="
if exist "%VPY%" (
  set "PYEXE=%VPY%"
) else (
  where py >nul 2>&1
  if not errorlevel 1 (
    for /f "delims=" %%I in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%I"
  )
)
if not defined PYEXE (
  where python >nul 2>&1
  if not errorlevel 1 (
    for /f "delims=" %%I in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%I"
  )
)

if not defined PYEXE (
  echo [ERROR] Python not found. Run SetupOffline.bat first.
  goto :fail
)

REM Optional path after _run: InitDataRoot.bat "D:\LocalSubsidies_ML_Data"
set "ROOTARG="
if not "%~2"=="" set "ROOTARG=%~2"

echo Using: %PYEXE%
echo.
if defined ROOTARG (
  "%PYEXE%" "%CD%\scripts\init_data_root.py" "%ROOTARG%"
) else (
  "%PYEXE%" "%CD%\scripts\init_data_root.py"
)
if errorlevel 1 goto :fail

echo.
echo Window stays open so you can read messages. Type exit to close.
echo.
endlocal
exit /b 0

:fail
echo.
echo InitDataRoot failed. Check configs\local.yaml data_root path.
echo   notepad configs\local.yaml
echo.
echo Window stays open so you can read messages. Type exit to close.
echo.
endlocal
exit /b 1
