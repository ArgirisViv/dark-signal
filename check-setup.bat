@echo off
REM Checks if all dependencies are installed correctly
echo ========================================
echo   Dark Signal - Setup Checker
echo ========================================
echo.

set SCRIPT_DIR=%~dp0
set ERRORS=0

REM Check Python
echo [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo    [X] Python not found! Please install Python 3.8+
    set /a ERRORS+=1
) else (
    python --version
    echo    [OK] Python is installed
)
echo.

REM Check Node.js
echo [2/5] Checking Node.js...
where npm >nul 2>&1
if errorlevel 1 (
    echo    [X] Node.js/npm not found! Please install Node.js
    set /a ERRORS+=1
) else (
    node --version
    npm --version
    echo    [OK] Node.js is installed
)
echo.

REM Check Virtual Environment
echo [3/5] Checking Backend Virtual Environment...
if not exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    echo    [X] Virtual environment not found!
    echo    [ ] Run: python -m venv .venv
    echo    [ ] Then: .venv\Scripts\activate
    echo    [ ] Then: pip install -r backend\requirements.txt
    set /a ERRORS+=1
) else (
    echo    [OK] Virtual environment exists
)
echo.

REM Check Backend Dependencies
echo [4/5] Checking Backend Dependencies...
if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    "%SCRIPT_DIR%.venv\Scripts\python.exe" -c "import fastapi" >nul 2>&1
    if errorlevel 1 (
        echo    [X] Backend packages not installed!
        echo    [ ] Run: .venv\Scripts\activate
        echo    [ ] Then: pip install -r backend\requirements.txt
        set /a ERRORS+=1
    ) else (
        echo    [OK] Backend dependencies installed
    )
) else (
    echo    [SKIP] Skipping (no virtual environment)
)
echo.

REM Check Frontend Dependencies
echo [5/5] Checking Frontend Dependencies...
if not exist "%SCRIPT_DIR%frontend\node_modules" (
    echo    [X] Frontend dependencies not installed!
    echo    [ ] Run: cd frontend
    echo    [ ] Then: npm install
    set /a ERRORS+=1
) else (
    echo    [OK] Frontend dependencies installed
)
echo.

echo ========================================
if %ERRORS% EQU 0 (
    echo   All checks passed! Ready to run.
    echo   Use start-all.bat to launch the app.
) else (
    echo   Found %ERRORS% issue(s). Please fix them first.
    echo   See SETUP.md for detailed instructions.
)
echo ========================================
echo.
pause
