# eBook CoverInjektor - Start Script for Windows (PowerShell)
# This PowerShell script sets up the virtual environment and runs the application on Windows.

# Set error action preference
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  eBook CoverInjektor - Start Script" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ $pythonVersion found" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.9+ from https://www.python.org/" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""

# Get the project directory (parent of this script's directory)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir
Set-Location $projectDir

# Check if virtual environment exists, create if not
$venvDir = ".venv"
if (-not (Test-Path $venvDir)) {
    Write-Host "Creating virtual environment..."
    python -m venv $venvDir
    Write-Host "✓ Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "✓ Virtual environment already exists" -ForegroundColor Green
}

Write-Host ""
Write-Host "Activating virtual environment..."
& "$venvDir\Scripts\Activate.ps1"

# Upgrade pip
Write-Host "Upgrading pip..."
python -m pip install --upgrade pip | Out-Null
Write-Host "✓ pip upgraded" -ForegroundColor Green

# Install requirements
if (Test-Path "requirements.txt") {
    Write-Host ""
    Write-Host "Installing dependencies..."
    pip install -r requirements.txt | Out-Null
    Write-Host "✓ Dependencies installed" -ForegroundColor Green
} else {
    Write-Host "Warning: requirements.txt not found" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   Starting eBook CoverInjektor..." -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Run the main application
python main.py

Write-Host ""
Write-Host "Application closed." -ForegroundColor Cyan
Read-Host "Press Enter to exit"
