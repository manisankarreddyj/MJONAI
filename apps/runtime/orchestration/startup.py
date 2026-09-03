"""
Module: orchestration/startup.py
Purpose: SOTA Pre-Flight Health Verification & Initialization Sequence for MJONAI.
         Executes before scheduler initialization, verifying database latency,
         environment integrity, cross-platform process locks (Windows/Linux),
         risk state restoration, and daily instrument master token synchronization.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import logging
import os
import sys
import time
from typing import Dict, List, Any, Optional, Tuple, Union

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from mjonai.core.time_utils import now_ist
from mjonai.communication.telegram import send_message
from mjonai.core.constants import SYSTEM_MODE, TOTAL_CAPITAL
from mjonai.core.runtime_config import LOCK_FILE

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StartupHealthReport:
    """Immutable contract representing pre-flight verification outcomes."""
    is_ready: bool
    system_mode: str
    db_latency_ms: Optional[int]
    peak_equity_restored: float
    risk_stop_active: bool
    kill_line_active: bool
    checks_passed: List[str]
    warnings: List[str]
    errors: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _is_pid_running(pid: int) -> bool:
    """
    Check if a process ID is currently active in a cross-platform manner using Python standard library.
    Avoids hardcoded /proc/ paths which fail on Windows.
    """
    if pid <= 0:
        return False

    if os.name == "nt":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            exit_code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            ctypes.windll.kernel32.CloseHandle(handle)
            return exit_code.value == STILL_ACTIVE
        except Exception:
            return True  # Safe assumption on permission error
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def _acquire_process_lock() -> Tuple[bool, Optional[str]]:
    """Acquire single-instance execution lock safely across OS platforms."""
    lock_path = LOCK_FILE
    current_pid = os.getpid()

    if os.path.exists(lock_path):
        try:
            with open(lock_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                old_pid = int(content)
                if old_pid != current_pid and _is_pid_running(old_pid):
                    return False, f"MJONAI is already running with PID {old_pid}"
                logger.info(f"[Startup] Cleaned stale lock file from inactive PID {old_pid}")
        except Exception as e:
            logger.warning(f"[Startup] Stale lock read notice: {e}")

    try:
        with open(lock_path, "w", encoding="utf-8") as f:
            f.write(str(current_pid))
        return True, None
    except Exception as e:
        return False, f"Failed to write process lock file: {e}"


def startup_health_check() -> StartupHealthReport:
    """
    Execute comprehensive 7-tier pre-flight verification sequence.
    Returns structured StartupHealthReport.
    """
    logger.info("=" * 65)
    logger.info(f"  🚀 MJONAI PRE-FLIGHT VERIFICATION [{SYSTEM_MODE} MODE]")
    logger.info("=" * 65)

    checks_passed: List[str] = []
    warnings: List[str] = []
    errors: List[str] = []
    db_latency: Optional[int] = None
    peak_equity_restored: float = TOTAL_CAPITAL
    risk_stop_active: bool = False
    kill_line_active: bool = False

    # ── Check 1: Process Mutex Lock ──────────────────────────────────
    lock_ok, lock_err = _acquire_process_lock()
    if not lock_ok:
        errors.append(str(lock_err))
        logger.error(f"❌ Process Lock: {lock_err}")
        return StartupHealthReport(
            is_ready=False,
            system_mode=SYSTEM_MODE,
            db_latency_ms=None,
            peak_equity_restored=TOTAL_CAPITAL,
            risk_stop_active=False,
            kill_line_active=False,
            checks_passed=checks_passed,
            warnings=warnings,
            errors=errors,
        )
    checks_passed.append("Process Mutex Lock Acquired")
    logger.info(f"✅ Process Mutex Lock acquired (PID: {os.getpid()})")

    # ── Check 2: Environment Variables ───────────────────────────────
    required_keys = [
        "ANGELONE_API_KEY",
        "ANGELONE_CLIENT_ID",
        "ANGELONE_PASSWORD",
        "ANGELONE_TOTP_SECRET",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "SUPABASE_URL",
        "SUPABASE_KEY",
    ]
    missing_keys = [k for k in required_keys if not os.getenv(k)]

    if missing_keys:
        if SYSTEM_MODE == "LIVE":
            errors.append(f"Missing required live credentials: {', '.join(missing_keys)}")
            logger.error(f"❌ Missing live credentials: {missing_keys}")
        else:
            warnings.append(f"Running in RESEARCH mode with mock credentials for: {', '.join(missing_keys)}")
            logger.warning(f"⚠️ Research mode active: credentials optional for {missing_keys}")
    else:
        checks_passed.append("Environment Credentials Verified")
        logger.info("✅ Environment credentials verified")

    # ── Check 3: Database & Risk State Restoration ───────────────────
    try:
        from mjonai.db.repository import insert_system_log
        from mjonai.risk.emergency_triggers import restore_risk_state

        t_start = time.time()
        insert_system_log(
            "STARTUP",
            f"MJONAI pre-flight check initiated at {now_ist().strftime('%Y-%m-%d %H:%M:%S IST')}",
        )
        db_latency = int((time.time() - t_start) * 1000)

        restored = restore_risk_state()
        peak_equity_restored = float(restored.get("peak_equity") or TOTAL_CAPITAL)
        risk_stop_active = bool(restored.get("risk_stop_restored", False))
        kill_line_active = bool(restored.get("kill_line_restored", False))

        checks_passed.append(f"Database Connected ({db_latency}ms)")
        checks_passed.append(f"Risk State Restored (Peak Equity: ₹{peak_equity_restored:,.0f})")
        logger.info(f"✅ Database connected ({db_latency}ms) — Peak Equity Restored: ₹{peak_equity_restored:,.0f}")

        if risk_stop_active:
            warnings.append("⚠️ Daily Risk Stop state active from previous session")
        if kill_line_active:
            warnings.append("🚨 15% Lifetime Kill Line state active from previous session")

    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        if SYSTEM_MODE == "LIVE":
            errors.append(f"Database connection failed: {e}")
        else:
            warnings.append(f"Local WAL offline fallback active: {e}")

    # ── Check 4: Daily Instrument Master Token Sync (TD-014) ───────────
    try:
        from mjonai.data.angelone.token_map import sync_instrument_master
        sync_res = sync_instrument_master()
        if sync_res:
            checks_passed.append("Angel One Token Master Synchronized")
            logger.info("✅ Angel One Instrument Master synchronized")
    except Exception as e:
        logger.warning(f"⚠️ Token master sync notice (using local cache): {e}")
        warnings.append(f"Token master sync notice: {e}")

    # ── Check 5: Outbound Telegram Gateway ───────────────────────────
    try:
        import requests
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if token:
            r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
            if r.status_code == 200 and r.json().get("ok"):
                checks_passed.append("Telegram Bot Gateway Connected")
                logger.info("✅ Telegram Bot gateway connected")
            else:
                warnings.append("Telegram Bot credentials invalid")
        else:
            warnings.append("Telegram Bot token not configured")
    except Exception as e:
        warnings.append(f"Telegram connection probe error: {e}")

    # ── Check 6: Internet Connectivity Gateway ───────────────────────
    try:
        import requests
        requests.get("https://www.google.com", timeout=4)
        checks_passed.append("Internet Gateway Operational")
        logger.info("✅ Internet gateway operational")
    except Exception as e:
        if SYSTEM_MODE == "LIVE":
            errors.append("No active internet connection")
        else:
            warnings.append("No active internet connection (offline simulation mode)")

    # ── Check 7: NSE Holiday Calendar Mode ───────────────────────────
    try:
        from mjonai.core.time_utils import _USING_FALLBACK_CALENDAR
        if _USING_FALLBACK_CALENDAR:
            warnings.append("NSE calendar using fallback calendar (pandas-market-calendars not loaded)")
            logger.warning("⚠️ NSE holiday calendar using fallback mode")
        else:
            checks_passed.append("NSE Exchange Calendar Verified")
    except Exception:
        pass

    is_ready = len(errors) == 0
    report = StartupHealthReport(
        is_ready=is_ready,
        system_mode=SYSTEM_MODE,
        db_latency_ms=db_latency,
        peak_equity_restored=peak_equity_restored,
        risk_stop_active=risk_stop_active,
        kill_line_active=kill_line_active,
        checks_passed=checks_passed,
        warnings=warnings,
        errors=errors,
    )

    logger.info("-" * 65)
    logger.info(f"  PRE-FLIGHT STATUS: {'ALL CHECKS PASSED ✅' if is_ready else 'STARTUP ISSUES FOUND ❌'}")
    logger.info("=" * 65 + "\n")
    return report