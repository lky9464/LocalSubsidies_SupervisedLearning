@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

where node >nul 2>&1
if errorlevel 1 (
  if exist "%ProgramFiles%\nodejs\node.exe" (
    set "PATH=%ProgramFiles%\nodejs;%PATH%"
  ) else if exist "%LocalAppData%\Programs\node\node.exe" (
    set "PATH=%LocalAppData%\Programs\node;%PATH%"
  )
)
where node >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js not found. UI build needs Node ^(not required on offline PCs^).
  echo.
  echo   Option 1 - winget ^(admin PowerShell^):
  echo     winget install OpenJS.NodeJS.LTS
  echo.
  echo   Option 2 - manual install:
  echo     https://nodejs.org/  ^> LTS ^> Windows Installer ^(64-bit^)
  echo     Then open a NEW cmd window and run build_web.bat again.
  echo.
  echo   If Node is already installed: restart the terminal/Cursor, or check PATH.
  pause
  exit /b 1
)

cd web
if not exist package.json (
  echo [ERROR] web\package.json missing
  pause
  exit /b 1
)

echo Installing npm dependencies...
call npm install
if errorlevel 1 exit /b 1

echo Building static export to web\out ...
call npm run build
if errorlevel 1 exit /b 1

echo.
echo Build complete: web\out\
echo For offline deploy, include web\out in the Release zip.
pause
