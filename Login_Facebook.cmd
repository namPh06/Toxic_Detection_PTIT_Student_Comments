@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m backend.login
) else (
  python -m backend.login
)
if errorlevel 1 pause
