# Oracle Cloud Infrastructure (OCI) Live Deployment Guide ☁️🐧

This guide walks you through deploying **MJONAI** onto an **Always Free Oracle Cloud Linux VM (Ubuntu 22.04/24.04 LTS in Mumbai `ap-mumbai-1`)** for 24/7 autonomous live algorithmic trading.

---

## 1. Oracle Cloud VM Provisioning

1. Sign in to your [Oracle Cloud Console](https://cloud.oracle.com/).
2. Select Region: **India South (Mumbai)** (`ap-mumbai-1`) or **India West (Hyderabad)** (`ap-hyderabad-1`).
3. Navigate to **Compute ➔ Instances ➔ Create Instance**.
4. **Instance Settings**:
   - **Image**: Ubuntu 22.04 LTS or 24.04 LTS (Canonical)
   - **Shape**: `VM.Standard.A1.Flex` (Ampere ARM, 4 OCPU, 24 GB RAM — *Always Free Eligible*) or `VM.Standard.E2.1.Micro` (AMD x86, 1 OCPU, 1 GB RAM).
   - **SSH Keys**: Download and save your private SSH key (`oracle_vm_key.pem`).
5. Click **Create**.

---

## 2. Ingress & Firewall Configuration (Security Rules)

In the OCI Console:
1. Go to **Virtual Cloud Networks (VCN)** ➔ Click your VCN ➔ Click **Security Lists**.
2. Add Ingress Rules:
   - **Port 22 (SSH)**: CIDR `0.0.0.0/0`
   - **Port 80 / 443 (HTTP/HTTPS Dashboard)**: CIDR `0.0.0.0/0`
   - **Port 8000 (FastAPI Backend)**: CIDR `0.0.0.0/0`

---

## 3. Connecting to the VM & Code Transfer

From your Windows local machine (PowerShell):
```powershell
# 1. SSH into Oracle VM
ssh -i oracle_vm_key.pem ubuntu@<YOUR_ORACLE_PUBLIC_IP>

# 2. Inside the VM, create the project directory
sudo mkdir -p /opt/MJONAI
sudo chown -R ubuntu:ubuntu /opt/MJONAI
```

From Windows PowerShell, upload the project files:
```powershell
scp -i oracle_vm_key.pem -r d:\MJONAI\* ubuntu@<YOUR_ORACLE_PUBLIC_IP>:/opt/MJONAI/
```

---

## 4. 1-Click Automated Setup on Oracle VM

Inside the Oracle VM:
```bash
cd /opt/MJONAI
chmod +x scripts/setup_oracle_vm.sh
./scripts/setup_oracle_vm.sh
```

This automated script will:
- Install Python 3.11, build-essentials, and system tools.
- Create the Linux `.venv` environment and install all dependencies.
- Verify that `pandas`, `numpy`, `scipy`, `duckdb`, `yfinance`, `SmartApi`, and `fastapi` are 100% operational.
- Register `mjonai.service` with Linux `systemd`.

---

## 5. Starting & Managing Live Trading

### Start the Live Trading Daemon:
```bash
sudo systemctl start mjonai
```

### View Live Execution Logs in Real Time:
```bash
sudo journalctl -u mjonai -f
```

### Check Service Health & Status:
```bash
sudo systemctl status mjonai
```

### Stop / Restart Service:
```bash
sudo systemctl stop mjonai
sudo systemctl restart mjonai
```

---

## 6. Daily Trading Automation Timeline

| Time (IST) | Subsystem | Automated Action |
| :--- | :--- | :--- |
| **08:45 AM** | `gift_nifty.py` | Calculates SGX/Gift Nifty opening gap and classifies market regime. |
| **09:00 AM** | `token_manager.py` | Syncs NSE & AngelOne token masters and options strikes. |
| **09:15 AM** | `main.py` | Activates live WebSocket tick feeds and starts 8 quantitative strategies. |
| **09:15 AM - 03:15 PM** | `agents/debate_room.py` | Real-time multi-agent debate & order execution with dynamic ATR stops. |
| **03:15 PM** | `special_modes.py` | Closes all intraday MIS positions. |
| **03:30 PM** | `main.py` | Market closes; pauses live feeds. |
| **04:00 PM** | `reporting/` | Compiles EOD PnL, tax audit ledger, and sends Telegram summary report. |
