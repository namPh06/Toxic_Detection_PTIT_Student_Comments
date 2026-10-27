@echo off
cd /d "%~dp0"
echo PTIT Comment Lab - Crawl, gan nhan va phan loai toxic
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 goto fail
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail
".venv\Scripts\python.exe" app.py
pause
exit /b
:fail
echo Khong khoi dong duoc. Can Python, Chrome va Internet de cai phu thuoc lan dau.
pause
