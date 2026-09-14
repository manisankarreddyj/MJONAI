#!/usr/bin/env bash
# ==============================================================================
# MJONAI 1-CLICK ORACLE CLOUD LINUX VM (UBUNTU 22.04/24.04) SETUP SCRIPT
# ==============================================================================

set -e

echo "======================================================="
echo "Setting up MJONAI Live Production Environment on Oracle Linux..."
echo "======================================================="

# 1. Update OS packages & install build essentials
sudo apt update && sudo apt upgrade -y
sudo apt install -y software-properties-common curl git build-essential ufw

# 2. Install Python 3.11 & venv
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# 3. Create clean Linux virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating Python 3.11 virtual environment..."
    python3.11 -m venv .venv
fi

# 4. Install & Upgrade Python Dependencies
echo "Installing MJONAI requirements..."
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

# 5. Verify Installation
.venv/bin/python -c "import pandas, numpy, scipy, duckdb, pyarrow, yfinance, fastapi, uvicorn, SmartApi, pyotp; print('ALL ORACLE LINUX PACKAGES VERIFIED 100% OPERATIONAL!')"

# 6. Configure Systemd Daemon Service
echo "Configuring MJONAI systemd background service..."
sudo cp infra/mjonai.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mjonai.service

echo "======================================================="
echo "MJONAI Oracle Cloud Linux Setup Complete!"
echo "To start the background trading service: sudo systemctl start mjonai"
echo "To view live logs: sudo journalctl -u mjonai -f"
echo "======================================================="
