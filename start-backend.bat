@echo off
REM Starts FastAPI backend in a new terminal window
REM This script uses relative paths and works from any location (including flash drives)

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%backend"

REM Check if virtual environment exists
if not exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found!
    echo Please run setup first:
    echo   1. python -m venv .venv
    echo   2. .venv\Scripts\activate
    echo   3. pip install -r backend\requirements.txt
    pause
    exit /b 1
)

echo Starting backend server...
"%SCRIPT_DIR%.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000
