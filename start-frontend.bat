@echo off
REM Starts Vite frontend
REM This script uses relative paths and works from any location (including flash drives)

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%frontend"

REM Check if node_modules exists
if not exist "%SCRIPT_DIR%frontend\node_modules" (
    echo ERROR: node_modules not found!
    echo Please run setup first:
    echo   npm install
    pause
    exit /b 1
)

REM Check if npm is available
where npm >nul 2>&1
if errorlevel 1 (
    echo ERROR: npm not found! Please install Node.js first.
    pause
    exit /b 1
)

echo Starting frontend server...
npm run dev
