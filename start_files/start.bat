@echo off
REM eBook CoverInjektor - Start Script for Windows
REM This batch script sets up the virtual environment and runs the application on Windows.

setlocal enabledelayedexpansion

echo.
echo ==========================================
echo   eBook CoverInjektor - Start Script
echo ==========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.9+ from https://www.python.org/
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo. %PYTHON_VERSION% found
echo.

REM Get the project directory (parent of this script's directory)
cd /d "%~dp0.."
set PROJECT_DIR=%cd%

REM Check if virtual environment exists, create if not
set VENV_DIR=.venv
if not exist "%VENV_DIR%" (
    echo Creating virtual environment...
    python -m venv "%VENV_DIR%"
    echo. Virtual environment created
) else (
    echo. Virtual environment already exists
)

echo.
echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1
echo. pip upgraded

REM Install requirements
if exist "requirements.txt" (
    echo.
    echo Installing dependencies...
    pip install -r requirements.txt >nul 2>&1
    if errorlevel 1 (
        echo Warning: Failed to install some dependencies
    ) else (
        echo. Dependencies installed
    )
) else (
    echo Warning: requirements.txt not found
)

echo.
echo ==========================================
echo   Starting eBook CoverInjektor...
echo ==========================================
echo.

REM Run the main application
python main.py

REM Deactivate virtual environment
call deactivate 2>nul

pause
