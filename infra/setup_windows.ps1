# ==============================================================================
# MJONAI 1-CLICK WINDOWS ENVIRONMENT SETUP SCRIPT
# ==============================================================================

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "Setting up MJONAI Unified Environment for Windows 11..." -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

# 1. Check Python 3.12
$pythonPath = (Get-Command py).Source
if (-not $pythonPath) {
    Write-Host "ERROR: Python launcher 'py' not found. Please install Python 3.12+." -ForegroundColor Red
    exit 1
}

# 2. Create Virtual Environment
if (-not (Test-Path ".venv")) {
    Write-Host "Creating clean Python 3.12 virtual environment in .venv..." -ForegroundColor Yellow
    py -3.12 -m venv .venv
} else {
    Write-Host "Found existing .venv directory." -ForegroundColor Green
}

# 3. Upgrade pip and install requirements
Write-Host "Installing pinned dependencies from requirements.txt..." -ForegroundColor Yellow
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 4. Verify Installation
Write-Host "Verifying environment packages..." -ForegroundColor Yellow
.\.venv\Scripts\python.exe -c "import pandas, numpy, scipy, duckdb, pyarrow, yfinance, fastapi, uvicorn, SmartApi, pyotp; print('ALL CORE PACKAGES VERIFIED 100% OPERATIONAL!')"

Write-Host "=======================================================" -ForegroundColor Green
Write-Host "MJONAI Windows Setup Completed Successfully!" -ForegroundColor Green
Write-Host "To activate in PowerShell: .\.venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Green
