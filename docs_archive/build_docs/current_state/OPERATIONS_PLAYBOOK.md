# MJONAI Operations Playbook

**Extracted from:** MJONAI_HANDOVER_v2.0.md (Sections 1-4, 11, 14)
**Cross-checked against:** main.py, orchestration/startup.py, current code
**Last verified:** 27 May 2026
**Status:** OPERATIONAL — required for system to run

> **Purpose:** Everything you need to know to operate the system day-to-day. Server access, deployment, env vars, startup verification. Replaces stale references in Master/Handover v2.0.

---

## 1. LOCAL ENVIRONMENT
OS: Windows 11 + WSL2 Ubuntu 22.04 (mandatory)
Python: 3.11.15
Venv path: /mnt/d/mjonai_build/.venv (note: .venv with dot)
Project path: /mnt/d/mjonai_build
GitHub: https://github.com/manisankarreddyj/mjonai-build (private)
Branch: master

text


**Activate venv:**
```bash
source /mnt/d/mjonai_build/.venv/bin/activate
Run locally:

Bash

cd /mnt/d/mjonai_build
source .venv/bin/activate
python main.py
Git credential fix (run once if push fails):

Bash

git config --global credential.helper store
2. ORACLE CLOUD SERVER (production 24/7)
text

Instance:     VM.Standard.E2.1.Micro
OCPU:         1 | RAM: 1GB | Storage: 48.27GB
Public IP:    140.245.234.150
OS:           Ubuntu 22.04.5 LTS
Project path: /home/ubuntu/mjonai-build
Python venv:  /home/ubuntu/mjonai-build/venv
SSH command:

Bash

ssh -i ~/.ssh/ssh-key-2026-04-27.key ubuntu@140.245.234.150
SSH key backup: Bitwarden

systemd Service Commands
Action	Command
Start	sudo systemctl start mjonai
Stop	sudo systemctl stop mjonai
Restart	sudo systemctl restart mjonai
Status	sudo systemctl status mjonai
Recent logs	sudo journalctl -u mjonai -n 50 --no-pager
Live logs	sudo journalctl -u mjonai -f
Service Settings
PYTHONUNBUFFERED=1
Auto-start on boot: enabled
Auto-restart on crash: enabled
Oracle system clock: UTC | App: forces IST via os.environ['TZ'] = 'Asia/Kolkata'
Oracle Rules — NEVER
NEVER do-release-upgrade or Ubuntu 24.04 upgrade
NEVER keep SSH open unnecessarily
NEVER deploy during market hours (9:15 AM - 3:30 PM IST)
Oracle Rules — ALWAYS
ALWAYS deploy after 3:40 PM IST only
Kill Line reset: sudo systemctl restart mjonai
Full system restart (sudo reboot) — weekends only, sequence:
Verify no open trades (/trades on Telegram -> Active: 0)
sudo reboot
Wait 2-3 minutes
SSH back in
sudo systemctl status mjonai
sudo journalctl -u mjonai -n 30 --no-pager
Confirm clean startup sequence
3. DEPLOYMENT PROTOCOL
Full deploy sequence (every time, no exceptions):

Step 1 — Local: commit and push
Bash

cd /mnt/d/mjonai_build
git add <specific files>           # never `git add .`
git commit -m "[type] description"
git push origin master
Step 2 — Oracle: pull and restart
Bash

ssh -i ~/.ssh/ssh-key-2026-04-27.key ubuntu@140.245.234.150
cd ~/mjonai-build
source venv/bin/activate
git pull origin master
sudo systemctl restart mjonai
sleep 15
sudo journalctl -u mjonai -n 50 --no-pager
Commit Types
Tag	Use for
[feat]	New feature
[fix]	Bug fixed
[refactor]	Code restructured
[docs]	Documentation only
[hotfix]	Urgent fix
Deploy Rules
Always check logs after restart
Deploy after 3:40 PM IST only
Never deploy during market hours
Never batch different concerns in one commit
Two-Terminal Workflow
Terminal 1: Local WSL2 (mani@Mani) — write, commit, push
Terminal 2: Oracle SSH (ubuntu@mjonai-vcn) — pull, restart, logs
4. SERVICE CONNECTIONS
AngelOne (primary broker)
text

Account:    AABM259382
API:        SmartAPI (free)
Features:   WebSocket (499 stocks), Historical data, Options Chain, GTT
Session:    Auto-renews 8:25 AM daily via TOTP
Cost:       0
Shoonya (execution backup — NOT integrated)
text

Purpose:    Zero brokerage for real money trades (future)
Status:     Credentials in .env, NOT integrated
TOTP:       Manual login only (cannot automate)
Plan:       Integrate when real money mode activates
Telegram (primary execution layer)
text

Bot:        ArthAITrading_bot
Token:      TELEGRAM_BOT_TOKEN in .env
Chat ID:    TELEGRAM_CHAT_ID in .env
Commands:   /status /pnl /trades /stop /pause /resume /close /help
Supabase (primary database)
text

Region:     Mumbai (ap-south-1)
Tier:       Free (500MB limit)
Tables:     17 live (see SYSTEM_ALGORITHMS.md Section 1)
RLS:        Disabled on all 17 tables
Groq (Bull agent)
text

Model:      llama-3.3-70b-versatile
Fallback:   llama-3.1-8b-instant
Rate Limit: 2.1s minimum between calls (per FIX-M)
Key:        GROQ_API_KEY in .env
Gemini (Supervisor agent)
text

SDK:        google-genai==1.74.0
Model:      models/gemini-2.5-flash
Usage:      system_instruction via GenerateContentConfig
Optimization: Only called on APPROVE path (saves quota)
Key:        GEMINI_API_KEY in .env
5. .ENV FILE — REQUIRED KEY NAMES
These are the env variables orchestration/startup.py checks for at boot. Missing any of the first 8 = system refuses to start.

Required (system won't boot without these)
text

ANGELONE_API_KEY
ANGELONE_CLIENT_ID          (value: AABM259382)
ANGELONE_PASSWORD
ANGELONE_TOTP_SECRET
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
SUPABASE_URL
SUPABASE_KEY
Additional (used by features but boot tolerates missing)
text

SUPABASE_DB_URL
GROQ_API_KEY                # Bull agent
GEMINI_API_KEY              # Supervisor agent
Shoonya (stored for future, not used yet)
text

SHOONYA_USER_ID
SHOONYA_PASSWORD
SHOONYA_SECRET_CODE
SHOONYA_VENDOR_CODE
SHOONYA_API_KEY
SHOONYA_IMEI
Rules
Never commit .env to git (confirmed in .gitignore)
All values backed up in Bitwarden
logs/ in .gitignore
6. STARTUP CHECKLIST
Before Market (before 9:15 AM IST)
 SSH Oracle and check overnight logs:
Bash

sudo journalctl -u mjonai -n 100 --no-pager
 Confirm 8:25 AM reset fired — look for: Daily reset — consecutive losses cleared
 Confirm 8:30 AM morning routine fired — look for:
Market State Engine starting
Market state saved to Supabase
Signals allowed today: 9999 (RESEARCH mode) or N (LIVE mode)
 Check for any Telegram alerts overnight
 On Telegram: /status
 On Telegram: /trades — confirm 0 active
First Scan 9:30 AM
 Watchlist: 499 symbols [RESEARCH mode]
 All 7 strategy IDs appearing: S01 S02 S03 S04 S05 S06 S07
 No ImportError. No crashes.
 agent_logs being written to Supabase
 signal_intelligence_log entries appearing
 No Soft Stop blocking
 Gemini calls only on APPROVE signals
After Market (4:00 PM)
 Forward returns calculated (16:00 IST log entry)
 Daily research report sent to Telegram (16:30 IST)
 Check signal_direction values in DB (LONG/SHORT)
7. CONNECTIVITY & RECOVERY
Connectivity
Primary: WiFi
Backup: Mobile hotspot (pre-configured WSL2)
Heartbeat: ping 1.1.1.1 every 10 seconds (inside orchestration/health_monitor.py)
Disconnect -> pause signals -> Telegram alert
Reconnect -> hard sync AngelOne vs Supabase before resuming
Backup Strategy (3-2-1)
Supabase cloud (real-time, Mumbai)
Local WSL2 (periodic export)
GitHub (code) + Google Drive (weekly CSV export)
Phoenix Recovery (<15 min, any machine)
Clone GitHub repo
Install Python 3.11 + WSL2
pip install -r requirements.txt
Copy .env from Bitwarden
python main.py -> pulls state from Supabase
Operational — no data loss
Daily Startup Sequence (8:45 AM)
Open WSL2 terminal
Ping 1.1.1.1
AngelOne: verify token, auto re-login if expired
AngelOne vs yfinance Nifty price diff >0.5% -> NO-GO
Supabase vs AngelOne holdings diff >1% -> NO-GO
Capital/margin check
Calendar: events today/tomorrow?
Shoonya: manual check
All APIs responding?
GO -> Telegram: MJONAI LIVE — {Date}. Regime: {STATE}. MQI: {LEVEL}.
Fail -> NO-GO. No signals until resolved.

Kill Switch
Always on dashboard. One click -> cancel orders, close positions, disable signals, log, Telegram alert.

8. EXECUTION MODES
Mode	Description	Currently Active?
Paper	Automated, no broker calls	YES
Semi-manual live	Signal sent, MJ places order in AngelOne app	Future
Full auto	Direct broker API order placement	DISABLED until SEBI review
9. OPERATIONAL CONFIG VALUES
From core/runtime_config.py — change these to adjust runtime behavior:

Setting	Value	Purpose
WEBSOCKET_STALE_ALERT_INTERVAL_SECONDS	300	Max 1 alert every 5 min
SCHEDULER_LOOP_SLEEP_SECONDS	30	Main loop sleep
HEALTH_MONITOR_INTERVAL_MINUTES	1	Health log frequency
ANGELONE_MAX_RETRIES	3	Login retry attempts
ANGELONE_RETRY_DELAY_SECONDS	10	Backoff between retries
ENABLE_TELEGRAM_ALERTS	True	Master alert switch
Never store secrets here. Use .env only.
