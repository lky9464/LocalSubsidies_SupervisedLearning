@echo off
REM 프로젝트 루트의 RunWeb.bat 로 위임
cd /d "%~dp0.."
call "%~dp0..\RunWeb.bat"
