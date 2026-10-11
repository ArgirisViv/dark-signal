@echo off
REM Starts backend and frontend in separate terminal windows
REM This script uses relative paths and works from any location (including flash drives)

set "SCRIPT_DIR=%~dp0"

REM Check if virtual environment exists
if not exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found!
    echo Please run setup first (see SETUP.md)
    pause
    exit /b 1
)

REM Check if node_modules exists
if not exist "%SCRIPT_DIR%frontend\node_modules" (
    echo ERROR: node_modules not found!
    echo Please run setup first (see SETUP.md)
    pause
    exit /b 1
)

echo Starting backend and frontend servers...
start "Backend" cmd /k "cd /d ""%SCRIPT_DIR%backend"" && ""%SCRIPT_DIR%.venv\Scripts\python.exe"" -m uvicorn app.main:app --reload --port 8000"
timeout /t 2 /nobreak >nul
start "Frontend" cmd /k "cd /d ""%SCRIPT_DIR%frontend"" && npm run dev"
echo.
echo Both servers are starting in separate windows.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
pause
