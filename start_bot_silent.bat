@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment not found at .venv\Scripts\python.exe
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '.\.venv\Scripts\python.exe' -ArgumentList 'main.py' -WorkingDirectory '.' -WindowStyle Hidden"

echo Bot started in background.
echo Use Task Manager or Stop-Process to stop it.
