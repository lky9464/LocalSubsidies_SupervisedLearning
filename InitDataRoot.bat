@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Local Subsidies — Init data_root
cd /d "%~dp0"

echo.
echo data_root 폴더 골격을 만듭니다. ^(raw 내용은 사용자가 직접 넣습니다^)
echo.

set "ROOTARG=%~1"
if defined ROOTARG (
  set "DATA_ROOT=%ROOTARG%"
  goto :have_root
)

set "LOCAL=%CD%\configs\local.yaml"
if not exist "%LOCAL%" (
  echo [ERROR] configs\local.yaml 이 없습니다.
  echo   먼저 SetupOffline.bat 을 실행하거나 example 을 복사하세요.
  pause
  exit /b 1
)

REM local.yaml 의 data_root: "..." 한 줄 파싱 (간단 YAML)
set "DATA_ROOT="
for /f "usebackq tokens=1,* delims=:" %%A in (`findstr /i /b /c:"data_root" "%LOCAL%"`) do (
  set "RAW=%%B"
)
if not defined RAW (
  echo [ERROR] local.yaml 에서 data_root 를 찾지 못했습니다.
  pause
  exit /b 1
)

REM trim spaces and quotes
for /f "tokens=* delims= " %%A in ("%RAW%") do set "RAW=%%A"
set "DATA_ROOT=%RAW:"=%"
set "DATA_ROOT=%DATA_ROOT:/=\%"

:have_root
if not defined DATA_ROOT (
  echo [ERROR] 경로가 비어 있습니다.
  echo   사용법: InitDataRoot.bat "D:\LocalSubsidies_ML_Data"
  pause
  exit /b 1
)

echo data_root = %DATA_ROOT%
echo.

for %%D in (
  "raw"
  "raw_inference"
  "interim"
  "processed"
  "ops"
  "algorithms\operations"
  "algorithms\catboost\scores\test"
  "algorithms\catboost\scores\inference"
  "algorithms\stacked_ensemble\scores\test"
  "algorithms\stacked_ensemble\scores\inference"
  "algorithms\easy_ensemble\scores\test"
  "algorithms\easy_ensemble\scores\inference"
  "algorithms\gradient_boosting\scores\test"
  "algorithms\gradient_boosting\scores\inference"
  "algorithms\random_forest\scores\test"
  "algorithms\random_forest\scores\inference"
) do (
  if not exist "%DATA_ROOT%\%%~D" (
    mkdir "%DATA_ROOT%\%%~D"
    echo   + %%~D
  ) else (
    echo   = %%~D ^(이미 있음^)
  )
)

echo.
echo 완료. 학습·평가 CSV 는 raw\ 에, 추론 CSV 는 raw_inference\ 에 넣으세요.
echo ^(스키마: TLS4902R_Layout.csv^)
echo.
pause
endlocal
