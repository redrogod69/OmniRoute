@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" powershell -ExecutionPolicy Bypass -File setup.ps1
powershell -ExecutionPolicy Bypass -File start.ps1
pause
