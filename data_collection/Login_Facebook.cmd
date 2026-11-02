@echo off
cd /d "%~dp0\.."
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" data_collection\login.py
) else (
  python data_collection\login.py
)
if errorlevel 1 pause
