@echo off
chcp 65001 >nul
cd /d "%~dp0"
"%~dp0PlantNexusCncDemo.exe" stop
if errorlevel 1 pause
