@echo off
REM Agent/개발용: 기존 웹 UI 종료 후 RunWeb.bat restart
cd /d "%~dp0"
start "Local Subsidies Web UI" cmd /k "%~dp0RunWeb.bat" restart
