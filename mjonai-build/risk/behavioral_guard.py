"""
Module: risk/behavioral_guard.py
Purpose: SOTA Behavioral Psychology Guard & Revenge-Trading Defense Engine.
         Prevents revenge trading via Progressive Escalation Cooldowns, Volatility (VIX)
         Adaptive Durations, Symbol-Level Lockouts, End-of-Day Terminal Awareness,
         and Crash-Resilient Local Disk State Persistence.

Architectural Principles:
  1. Progressive Escalation Ladder (Exponential Backoff):
     - 2 Consecutive Losses -> 30-Minute Pause (Regime digestion).
     - 3 Consecutive Losses -> 60-Minute Pause (Structural exhaustion).
     - 4 Consecutive Losses -> FULL DAY LOCKOUT (Capital preservation shutdown).
  2. Volatility (VIX) Adaptive Scaling:
     - Automatically stretches cooldown durations during high-panic regimes (VIX > 20).
  3. End-of-Day Terminal Awareness:
     - After 02:30 PM IST (less than 45 mins before market cutoff), consecutive losses
       trigger immediate Full Day Lockout to prevent dangerous late-session chop.
  4. Two-Tier Symbol vs System-Wide Hierarchy:
     - 2 losses on same symbol -> 45-minute symbol freeze.
     - 3 losses on same symbol -> Full Day symbol quarantine.
  5. Thread-Safe Concurrency via Re-entrant Lock (threading.RLock).
  6. Crash-Resilient State Persistence (storage/behavioral_guard_state.json)
     preventing state wipeouts during server or bot restarts.
  7. Automatic Immutable Audit Logging to db.repository.insert_risk_event.
  8. Typed Immutable Status Contract (BehavioralGuardStatus).
  9. 100% Backward-Compatible Public API.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone, time as dt_time
import json
import logging
from pathlib import Path
import threading
from typing import Tuple, Dict, Any, List, Optional

from core.time_utils import now_ist, today_ist, is_market_open
from core.constants import (
    CONSECUTIVE_LOSS_LIMIT,
    DAILY_LOSS_LIMIT_PCT,
    MAX_OPEN_POSITIONS,
)

logger = logging.getLogger(__name__)

# State lock
_GUARD_LOCK = threading.RLock()

# Local durable state persistence
_STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"
_STATE_FILE = _STORAGE_DIR / "behavioral_guard_state.json"

# Configuration
CONSECUTIVE_LOSS_THRESHOLD: int = 2   # Stage 1: 2 consecutive losses -> 30m pause
STAGE_2_LOSS_THRESHOLD: int = 3       # Stage 2: 3 consecutive losses -> 60m pause
STAGE_3_LOSS_THRESHOLD: int = 4       # Stage 3: 4 consecutive losses -> Full Day Lockout
SYMBOL_LOSS_THRESHOLD: int = 2
BASE_COOLDOWN_MINUTES: int = 30
SYMBOL_COOLDOWN_MINUTES: int = 45
MAX_DAILY_TRADES_LIVE: int = 8
MAX_DAILY_TRADES_RESEARCH: int = 30
EOD_CUTOFF_TIME = dt_time(14, 30)  # 02:30 PM IST: After this, losses trigger full day stop

# In-Memory State
_cooldown_active: bool = False
_cooldown_until: Optional[datetime] = None
_cooldown_reason: str = ""
_day_locked: bool = False
_day_lock_date = None
_consecutive_losses: int = 0
_symbol_losses: Dict[str, int] = {}
_locked_symbols: Dict[str, datetime] = {}
_day_locked_symbols: set = set()


# ── 1. TYPE-SAFE DATA CONTRACT ───────────────────────────────────────────────

@dataclass(frozen=True)
class BehavioralGuardStatus:
    """Immutable contract representing the real-time behavioral guard state."""
    is_allowed: bool
    cooldown_active: bool
    is_day_locked: bool
    cooldown_remaining_seconds: int
    consecutive_losses: int
    locked_symbols: List[str]
    is_symbol_locked: bool
    daily_trade_count: int
    max_daily_trades: int
    reason: str
    cooldown_until_ist: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── 2. DURABLE PERSISTENCE HELPERS ───────────────────────────────────────────

def _save_state() -> None:
    """Persist behavioral guard state to disk to survive bot restarts."""
    try:
        _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "cooldown_active": _cooldown_active,
            "day_locked": _day_locked,
            "day_lock_date": _day_lock_date,
            "cooldown_until": _cooldown_until.isoformat() if _cooldown_until else None,
            "cooldown_reason": _cooldown_reason,
            "consecutive_losses": _consecutive_losses,
            "symbol_losses": _symbol_losses,
            "locked_symbols": {k: v.isoformat() for k, v in _locked_symbols.items()},
            "day_locked_symbols": list(_day_locked_symbols),
            "updated_at": now_ist().isoformat(),
        }
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception as e:
        logger.error(f"[BehavioralGuard] Failed to save state to disk: {e}")


def _load_state() -> None:
    """Restore behavioral guard state from disk if valid for today."""
    global _cooldown_active, _cooldown_until, _cooldown_reason, _consecutive_losses
    global _symbol_losses, _locked_symbols, _day_locked, _day_lock_date, _day_locked_symbols

    if not _STATE_FILE.exists():
        return

    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        updated_at_str = data.get("updated_at")
        if updated_at_str:
            saved_date = updated_at_str[:10]
            today_str = str(today_ist())
            # Only restore state if recorded today
            if saved_date != today_str:
                logger.info("[BehavioralGuard] Saved state is from a previous trading day -> resetting for new session.")
                reset_guard()
                return

        _cooldown_active = bool(data.get("cooldown_active", False))
        _day_locked = bool(data.get("day_locked", False))
        _day_lock_date = data.get("day_lock_date")
        until_str = data.get("cooldown_until")
        _cooldown_until = datetime.fromisoformat(until_str) if until_str else None
        _cooldown_reason = str(data.get("cooldown_reason", ""))
        _consecutive_losses = int(data.get("consecutive_losses", 0))
        _symbol_losses = {str(k): int(v) for k, v in data.get("symbol_losses", {}).items()}

        raw_locked = data.get("locked_symbols", {})
        _locked_symbols = {
            str(k): datetime.fromisoformat(v)
            for k, v in raw_locked.items()
            if v
        }
        _day_locked_symbols = set(data.get("day_locked_symbols", []))
        logger.info(f"[BehavioralGuard] Restored state: {_consecutive_losses} losses, day_locked={_day_locked}, cooldown={_cooldown_active}")
    except Exception as e:
        logger.error(f"[BehavioralGuard] Failed to load state from disk: {e}")




# ── 3. VOLATILITY & PROGRESSIVE LADDER CALCULATOR ────────────────────────────

def _calculate_cooldown_duration(consecutive_losses: int, current_vix: Optional[float] = None) -> int:
    """
    Calculate progressive escalation duration adjusted for India VIX volatility.
    - 2 Losses -> 30 mins base
    - 3 Losses -> 60 mins base
    - Adjusted by (1 + max(0, (VIX - 15) / 15))
    """
    if consecutive_losses >= 3:
        base_mins = 60
    else:
        base_mins = BASE_COOLDOWN_MINUTES

    if current_vix and current_vix > 15.0:
        # Scale duration with VIX volatility (e.g. VIX 22 -> 1.46x duration)
        vix_mult = 1.0 + min(1.0, max(0.0, (current_vix - 15.0) / 15.0))
        return int(round(base_mins * vix_mult))

    return base_mins


# ── 4. CORE PUBLIC API ───────────────────────────────────────────────────────

def record_trade_outcome(
    outcome: str,
    symbol: str = "",
    system_mode: str = "RESEARCH",
    current_vix: Optional[float] = None,
) -> None:
    """
    Record a closed trade outcome (WIN / LOSS / BREAKEVEN).
    Applies Progressive Escalation Ladder (2 losses -> 30m, 3 losses -> 60m, 4 losses -> Day stop),
    VIX volatility scaling, and EOD terminal shutdown.
    """
    global _consecutive_losses, _cooldown_active, _cooldown_until, _cooldown_reason
    global _symbol_losses, _locked_symbols, _day_locked, _day_lock_date, _day_locked_symbols

    clean_out = str(outcome or "").strip().upper()
    clean_sym = str(symbol or "").strip().upper()
    now = now_ist()

    with _GUARD_LOCK:
        if clean_out == "LOSS":
            _consecutive_losses += 1

            # 1. Track Symbol-Level Progressive Quarantine
            if clean_sym:
                _symbol_losses[clean_sym] = _symbol_losses.get(clean_sym, 0) + 1
                sym_loss_count = _symbol_losses[clean_sym]

                if sym_loss_count >= 3:
                    _day_locked_symbols.add(clean_sym)
                    logger.critical(
                        f"[BehavioralGuard] Symbol Full-Day Quarantine: {clean_sym} hit {sym_loss_count} consecutive losses. "
                        f"Quarantined for the remainder of today's session."
                    )
                elif sym_loss_count >= SYMBOL_LOSS_THRESHOLD:
                    sym_mins = int(round(SYMBOL_COOLDOWN_MINUTES * (1.2 if (current_vix or 0) > 20 else 1.0)))
                    lock_until = now + timedelta(minutes=sym_mins)
                    _locked_symbols[clean_sym] = lock_until
                    logger.warning(
                        f"[BehavioralGuard] Symbol Lockout: {clean_sym} hit {sym_loss_count} losses. "
                        f"Quarantined for {sym_mins}m until {lock_until.strftime('%I:%M %p IST')}."
                    )

            logger.warning(
                f"[BehavioralGuard] Trade LOSS recorded for {clean_sym or 'PORTFOLIO'}. "
                f"Consecutive losses: {_consecutive_losses}/4"
            )

            # 2. End-of-Day Awareness Sentry (After 02:30 PM)
            is_late_session = now.time() >= EOD_CUTOFF_TIME
            if is_late_session and _consecutive_losses >= 2:
                _day_locked = True
                _day_lock_date = now.date().isoformat()
                _cooldown_active = True
                _cooldown_reason = (
                    f"Late Session Sentry: {_consecutive_losses} consecutive losses after 02:30 PM. "
                    f"Trading halted for remainder of today's session to prevent late-day whipsaws."
                )
                logger.critical(f"[BehavioralGuard] LATE-DAY LOCKOUT TRIGGERED: {_cooldown_reason}")

            # 3. Progressive Escalation Ladder (4+ Losses -> Full Day Lockout)
            elif _consecutive_losses >= 4:
                _day_locked = True
                _day_lock_date = now.date().isoformat()
                _cooldown_active = True
                _cooldown_reason = (
                    f"Capital Preservation Circuit Breaker: 4 consecutive losses. "
                    f"Trading halted for remainder of today's session."
                )
                logger.critical(f"[BehavioralGuard] FULL-DAY CIRCUIT BREAKER TRIGGERED: {_cooldown_reason}")

            # 4. System-Wide Cooldown Ladder (2 or 3 Losses)
            elif _consecutive_losses >= CONSECUTIVE_LOSS_THRESHOLD:
                cooldown_mins = _calculate_cooldown_duration(_consecutive_losses, current_vix)
                _cooldown_active = True
                _cooldown_until = now + timedelta(minutes=cooldown_mins)
                _cooldown_reason = (
                    f"Revenge Trading Circuit Breaker (Stage {_consecutive_losses - 1}): "
                    f"{_consecutive_losses} consecutive losses. "
                    f"{cooldown_mins}-minute cooling off active until {_cooldown_until.strftime('%I:%M %p IST')}."
                )
                logger.critical(f"[BehavioralGuard] COOLDOWN TRIGGERED: {_cooldown_reason}")

            # Log risk event to Supabase
            if _cooldown_active:
                try:
                    from db.repository import insert_risk_event
                    insert_risk_event(
                        event_type="REVENGE_TRADING_COOLDOWN",
                        message=_cooldown_reason,
                        level="WARNING" if not _day_locked else "EMERGENCY",
                        system_mode=system_mode,
                    )
                except Exception as e:
                    logger.warning(f"[BehavioralGuard] Could not persist risk event to DB: {e}")

        elif clean_out == "WIN":
            if _consecutive_losses > 0:
                logger.info(f"[BehavioralGuard] WIN recorded for {clean_sym} — resetting consecutive loss counter.")
            _consecutive_losses = 0
            if clean_sym and clean_sym in _symbol_losses:
                _symbol_losses[clean_sym] = 0

        _save_state()


def is_symbol_locked(symbol: str) -> bool:
    """Check if a specific symbol is quarantined in temporary or full-day cooldown."""
    if not symbol:
        return False
    clean_sym = symbol.strip().upper()
    now = now_ist()

    with _GUARD_LOCK:
        if clean_sym in _day_locked_symbols:
            return True

        if clean_sym in _locked_symbols:
            lock_until = _locked_symbols[clean_sym]
            if now >= lock_until:
                del _locked_symbols[clean_sym]
                _save_state()
                return False
            return True
        return False


def check_behavioral_guard(
    today_trade_count: int,
    symbol: Optional[str] = None,
    system_mode: str = "RESEARCH",
) -> Tuple[bool, str]:
    """
    Check if trading is permitted by the Behavioral Guard.
    Evaluates Full-Day lockouts, dynamic cooling-off, symbol lockouts, and daily volume limits.

    Returns:
        (is_allowed: bool, reason: str)
    """
    global _cooldown_active, _cooldown_until, _cooldown_reason, _day_locked, _day_lock_date
    now = now_ist()
    clean_sym = str(symbol or "").strip().upper()
    sys_mode = system_mode.upper()

    with _GUARD_LOCK:
        # 0. Day Rollover: day-scoped locks expire when the IST date
        # changes. The 24/7 process never restarts, so without this a
        # single bad day halted trading forever.
        _today_iso = now.date().isoformat()
        if _day_locked and _day_lock_date != _today_iso:
            logger.info("[BehavioralGuard] Day rollover - clearing day-scoped lockout.")
            _day_locked = False
            _day_lock_date = None
            _day_locked_symbols.clear()
            _save_state()

        # 1. Check Full-Day System Lockout
        if _day_locked:
            return False, f"Trading halted for today: {_cooldown_reason}"

        # 2. Check System-Wide Cooldown
        if _cooldown_active:
            if _cooldown_until and now >= _cooldown_until:
                logger.info("[BehavioralGuard] Cooling off period expired — resuming normal trading.")
                _cooldown_active = False
                _cooldown_until = None
                _cooldown_reason = ""
                _save_state()
            else:
                remaining_sec = int((_cooldown_until - now).total_seconds()) if _cooldown_until else 0
                remaining_mins = max(1, remaining_sec // 60)
                return False, f"Cooling off active ({remaining_mins}m remaining): {_cooldown_reason}"

        # 3. Check Specific Symbol Lockout
        if clean_sym and is_symbol_locked(clean_sym):
            if clean_sym in _day_locked_symbols:
                return False, f"Symbol {clean_sym} is quarantined for the rest of today due to 3 consecutive stop-outs."
            until_time = _locked_symbols.get(clean_sym)
            until_str = until_time.strftime('%I:%M %p IST') if until_time else ""
            return False, f"Symbol {clean_sym} is quarantined in cooling-off until {until_str}."

        # 4. Check Daily Volume Overtrading Limiter
        max_trades = MAX_DAILY_TRADES_RESEARCH if sys_mode == "RESEARCH" else MAX_DAILY_TRADES_LIVE
        if today_trade_count >= max_trades:
            return False, f"Daily trade limit ({today_trade_count}/{max_trades}) reached — overtrading protection."

        return True, "Behavioral guard clear"


def get_behavioral_guard_status(
    today_trade_count: int = 0,
    symbol: Optional[str] = None,
    system_mode: str = "RESEARCH",
) -> BehavioralGuardStatus:
    """
    Return comprehensive structured status of the Behavioral Guard for telemetry & UI dashboards.
    """
    now = now_ist()
    clean_sym = str(symbol or "").strip().upper()
    sys_mode = system_mode.upper()
    max_trades = MAX_DAILY_TRADES_RESEARCH if sys_mode == "RESEARCH" else MAX_DAILY_TRADES_LIVE

    with _GUARD_LOCK:
        is_allowed, reason = check_behavioral_guard(
            today_trade_count=today_trade_count,
            symbol=symbol,
            system_mode=system_mode,
        )

        remaining_sec = 0
        until_ist_str = None
        if _cooldown_active and _cooldown_until and now < _cooldown_until and not _day_locked:
            remaining_sec = max(0, int((_cooldown_until - now).total_seconds()))
            until_ist_str = _cooldown_until.strftime('%I:%M %p IST')
        elif _day_locked:
            until_ist_str = "EOD (Tomorrow 09:15 AM)"

        active_locked = list(_day_locked_symbols) + [
            sym for sym, until_dt in _locked_symbols.items()
            if now < until_dt and sym not in _day_locked_symbols
        ]

        return BehavioralGuardStatus(
            is_allowed=is_allowed,
            cooldown_active=_cooldown_active,
            is_day_locked=_day_locked,
            cooldown_remaining_seconds=remaining_sec,
            consecutive_losses=_consecutive_losses,
            locked_symbols=active_locked,
            is_symbol_locked=bool(clean_sym and is_symbol_locked(clean_sym)),
            daily_trade_count=today_trade_count,
            max_daily_trades=max_trades,
            reason=reason,
            cooldown_until_ist=until_ist_str,
        )


def reset_guard() -> None:
    """Manual reset of behavioral guard, all symbol lockouts, and full-day locks."""
    global _cooldown_active, _cooldown_until, _cooldown_reason, _consecutive_losses
    global _symbol_losses, _locked_symbols, _day_locked, _day_lock_date, _day_locked_symbols

    with _GUARD_LOCK:
        _cooldown_active = False
        _day_locked = False
        _cooldown_until = None
        _cooldown_reason = ""
        _consecutive_losses = 0
        _symbol_losses.clear()
        _locked_symbols.clear()
        _day_locked_symbols.clear()
        _save_state()
        logger.info("[BehavioralGuard] Guard reset manually and state cleared.")


# Initialize state from disk on module import (after all defs)
_load_state()