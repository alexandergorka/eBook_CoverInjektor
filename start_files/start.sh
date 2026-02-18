#!/bin/bash
#
# eBook CoverInjektor - Start Script for macOS/Linux
#
# This script sets up the virtual environment and runs the application on macOS and Linux.

set -e

# Get the absolute path to the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "  eBook CoverInjektor - Start Script"
echo "=========================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed."
    echo "Please install Python 3.9+ from https://www.python.org/"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✓ Python $PYTHON_VERSION found"
echo ""

# Navigate to project directory
cd "$PROJECT_DIR"

# Check if virtual environment exists, create if not
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

echo ""
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip > /dev/null 2>&1
echo "✓ pip upgraded"

# Install requirements
if [ -f "requirements.txt" ]; then
    echo ""
    echo "Installing dependencies..."
    pip install -r requirements.txt > /dev/null 2>&1
    echo "✓ Dependencies installed"
else
    echo "Warning: requirements.txt not found"
fi

echo ""
echo "=========================================="
echo "  Starting eBook CoverInjektor..."
echo "=========================================="
echo ""

# Run the main application
python main.py

# Deactivate virtual environment on exit
deactivate 2>/dev/null || true
