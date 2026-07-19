@echo off
chcp 65001 >nul
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
  echo [ERROR] Node.js 가 없습니다. UI 빌드는 Node가 필요합니다 ^(오프라인 PC에는 불필요^).
  echo.
  echo   방법 1 - winget ^(관리자 PowerShell^):
  echo     winget install OpenJS.NodeJS.LTS
  echo.
  echo   방법 2 - 수동 설치:
  echo     https://nodejs.org/  ^> LTS ^> Windows Installer ^(64-bit^)
  echo     설치 후 **새** cmd 창을 열고 build_web.bat 을 다시 실행하세요.
  echo.
  echo   이미 설치했는데도 이 메시지면: 터미널/Cursor를 재시작하거나 PATH에 node가 있는지 확인하세요.
  pause
  exit /b 1
)

cd web
if not exist package.json (
  echo [ERROR] web\package.json 없음
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
echo 오프라인 배포 시 web\out 폴더를 Release zip에 포함하세요.
pause
