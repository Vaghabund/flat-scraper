@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment not found at .venv\Scripts\python.exe
    echo Run setup first, then try again.
    pause
    exit /b 1
)

echo Starting Flat Scraper Bot...
".venv\Scripts\python.exe" main.py

echo.
echo Bot process exited.
pause
