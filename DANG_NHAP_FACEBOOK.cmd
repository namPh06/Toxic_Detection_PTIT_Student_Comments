@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" dang_nhap.py
) else (
  python dang_nhap.py
)
if errorlevel 1 pause
