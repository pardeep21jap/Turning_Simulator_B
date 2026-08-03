@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    py -m venv .venv
    if errorlevel 1 goto :error
)

echo Installing required package...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo Starting CNC Lathe Simulator...
".venv\Scripts\python.exe" main.py
exit /b 0

:error
echo.
echo Setup failed. Confirm that Python 3.11 or newer is installed.
pause
exit /b 1
