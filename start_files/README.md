# eBook CoverInjektor - Start Scripts

This folder contains platform-specific start scripts to easily run the eBook CoverInjektor application on different operating systems.

## macOS & Linux

### Using the Shell Script

1. **Make the script executable** (first time only):
   ```bash
   chmod +x start.sh
   ```

2. **Run the script**:
   ```bash
   ./start.sh
   ```

The script will:
- Check for Python 3 installation
- Create a virtual environment (if needed)
- Install all dependencies from `requirements.txt`
- Launch the application

## Windows

### Option 1: Using the Batch File (Recommended)

1. **Double-click** `start.bat` in File Explorer, or
2. **Run from Command Prompt**:
   ```cmd
   start.bat
   ```

The script will:
- Check for Python installation
- Create a virtual environment (if needed)
- Install all dependencies from `requirements.txt`
- Launch the application

### Option 2: Using the PowerShell Script

1. **Open PowerShell** as Administrator
2. **Run the script**:
   ```powershell
   .\start.ps1
   ```

   If you get an execution policy error, run:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

## System Requirements

- **Python 3.9** or higher
- Supported Operating Systems:
  - macOS 10.9+
  - Linux (most distributions)
  - Windows 7 SP1 or later

## Troubleshooting

### Python not found
Make sure Python 3.9+ is installed and added to your system PATH.
- Download from: https://www.python.org/downloads/

### Permission Denied (macOS/Linux)
If you get a "Permission denied" error, make the script executable:
```bash
chmod +x start.sh
```

### Virtual Environment Errors
If the virtual environment is corrupted, delete the `.venv` folder and run the start script again to create a fresh environment.

## Manual Setup (Alternative)

If the scripts don't work, you can manually set up and run the application:

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

## Notes

- The scripts automatically create and manage a Python virtual environment (`.venv`)
- All dependencies are installed in the virtual environment, keeping your system Python clean
- The application will prompt you to close the terminal/window when finished
