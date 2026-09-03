"""
Module: risk/special_modes.py
Purpose: SOTA Special Macro Events & Market Regime Circuit Breaker Engine.
         - Crisis Mode: Market flash crash (Nifty drop >= -2.5%) or extreme VIX (>= 28.0).
         - Union Budget Day Mode: Speech blackout window on Feb 1 (10:30 AM - 01:30 PM).
         - RBI Monetary Policy Mode: Rate announcement blackout (10:00 AM - 11:30 AM).
         - Dynamic Expiry Day Gamma Mode: Holiday-aware weekly F&O expiry theta scaling.
         - Volatility Position Sizer: Automatically halves sizes during turbulence (VIX 22-28).
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, date, time as dt_time, timezone
import logging
import math
import threading
from typing import Dict, Any, Tuple, Optional, List, Sequence, Union

from mjonai.core.time_utils import now_ist, today_ist, is_expiry_day
from mjonai.core.constants import (
    SYSTEM_MODE,
    get_volatility_scaled_daily_stop,
)

logger = logging.getLogger(__name__)

# State lock
_MODE_LOCK = threading.RLock()

# State
_manual_crisis_override: bool = False
_manual_crisis_reason: str = ""

# Standard Scheduled RBI Monetary Policy Months & Dates (Bi-monthly)
# Can be supplemented by external calendar feeds
RBI_MPC_DATES = {
    (2, 6), (2, 7), (2, 8),      # February policy window
    (4, 3), (4, 4), (4, 5),      # April policy window
    (6, 5), (6, 6), (6, 7),      # June policy window
    (8, 6), (8, 7), (8, 8),      # August policy window
    (10, 7), (10, 8), (10, 9),   # October policy window
    (12, 4), (12, 5), (12, 6),   # December policy window
}


# ── 1. TYPE-SAFE DATA CONTRACT ───────────────────────────────────────────────

@dataclass(frozen=True)
class SpecialModesResult:
    """Immutable contract representing the real-time status of Special Market Modes."""
    is_allowed: bool
    crisis_active: bool
    budget_active: bool
    rbi_active: bool
    is_expiry_day: bool
    size_multiplier: float
    adjusted_signal: Dict[str, Any]
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── 2. DEFENSIVE FLOAT SANITIZER ─────────────────────────────────────────────

def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert any value to float, converting NaN/Inf to default."""
    try:
        if val is None or isinstance(val, (list, dict, tuple)):
            return default
        f = float(val)
        return default if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return default


# ── 3. INDIVIDUAL SPECIAL REGIME CHECKS ───────────────────────────────────────

def is_crisis_mode(vix: float = 16.0, intraday_index_drop_pct: float = 0.0) -> Tuple[bool, str]:
    """
    Check if extreme crisis / black swan conditions exist.
    Trips if manual override is active, India VIX >= 28.0, or Nifty drops >= -2.5% intraday.
    """
    global _manual_crisis_override, _manual_crisis_reason
    vix_val = _safe_float(vix, default=16.0)
    drop_pct = _safe_float(intraday_index_drop_pct, default=0.0)

    with _MODE_LOCK:
        if _manual_crisis_override:
            return True, f"Manual Crisis Override: {_manual_crisis_reason}"

        if vix_val >= 28.0:
            return True, f"Extreme Volatility Crisis: India VIX ({vix_val:.1f}) exceeds 28.0 ceiling"

        if drop_pct <= -2.5:
            return True, f"Flash Crash Circuit: Index down {drop_pct:.2f}% intraday"

        return False, "Normal market conditions"


def is_budget_day_blackout(eval_time: Optional[datetime] = None) -> Tuple[bool, str]:
    """
    Check if today is Union Budget Day (Feb 1) and within the speech blackout window (10:30 AM - 01:30 PM).
    """
    now = eval_time or now_ist()
    today = now.date()

    # Union Budget Day in India is February 1st
    if today.month == 2 and today.day == 1:
        speech_start = dt_time(10, 30)
        speech_end = dt_time(13, 30)
        if speech_start <= now.time() <= speech_end:
            return True, "Union Budget speech active (10:30 AM - 01:30 PM) — extreme whipsaw risk"

    return False, "No budget blackout"


def is_rbi_policy_blackout(eval_time: Optional[datetime] = None, calendar_events: Optional[Sequence[dict]] = None) -> Tuple[bool, str]:
    """
    Check if today is an RBI MPC Policy announcement day and within the rate decision window (10:00 AM - 11:30 AM).
    """
    now = eval_time or now_ist()
    today = now.date()

    # 1. Check external calendar events if provided
    if calendar_events:
        for ev in calendar_events:
            ev_name = str(ev.get("name", "")).upper()
            if "RBI" in ev_name or "MPC" in ev_name:
                hours_away = _safe_float(ev.get("hours_away", 999))
                if 0 <= hours_away <= 2.0:
                    return True, f"RBI Policy announcement imminent ({ev.get('name')}) — interest rate volatility blackout"

    # 2. Check scheduled calendar dates
    if (today.month, today.day) in RBI_MPC_DATES:
        policy_start = dt_time(10, 0)
        policy_end = dt_time(11, 30)
        if policy_start <= now.time() <= policy_end:
            return True, "RBI MPC Policy Announcement active (10:00 AM - 11:30 AM) — rate sensitivity blackout"

    return False, "No RBI policy blackout"


def calculate_volatility_size_multiplier(vix: float = 16.0) -> float:
    """
    Calculate position sizing scaler based on India VIX volatility regime:
      - VIX < 16.0:  1.00x (Normal calm)
      - VIX 16-22:   0.80x (Moderate volatility)
      - VIX 22-28:   0.50x (Elevated turbulence -> halve position sizes)
      - VIX >= 28.0: 0.00x (Crisis Mode -> hard block)
    """
    v = _safe_float(vix, default=16.0)
    if v < 16.0:
        return 1.0
    elif v < 22.0:
        return 0.80
    elif v < 28.0:
        return 0.50
    else:
        return 0.0


# ── 4. MASTER SPECIAL MODES EVALUATION ───────────────────────────────────────

def check_special_modes(
    signal: Dict[str, Any],
    vix: float = 16.0,
    intraday_index_drop_pct: float = 0.0,
    eval_time: Optional[datetime] = None,
    calendar_events: Optional[Sequence[dict]] = None,
) -> Tuple[bool, Dict[str, Any], str]:
    """
    Apply all special mode checks in priority order:
    100% Backward-compatible tuple return: (is_allowed, adjusted_signal, reason).
    """
    res = evaluate_special_modes(
        signal=signal,
        vix=vix,
        intraday_index_drop_pct=intraday_index_drop_pct,
        eval_time=eval_time,
        calendar_events=calendar_events,
    )
    return res.is_allowed, res.adjusted_signal, res.reason


def evaluate_special_modes(
    signal: Dict[str, Any],
    vix: float = 16.0,
    intraday_index_drop_pct: float = 0.0,
    eval_time: Optional[datetime] = None,
    calendar_events: Optional[Sequence[dict]] = None,
) -> SpecialModesResult:
    """
    SOTA Structured Special Modes Evaluator returning typed SpecialModesResult.
    """
    adjusted = signal.copy()
    now = eval_time or now_ist()
    vix_val = _safe_float(vix, default=16.0)
    drop_pct = _safe_float(intraday_index_drop_pct, default=0.0)

    # 1. Crisis Mode Check (Hard Block)
    is_crisis, crisis_reason = is_crisis_mode(vix_val, drop_pct)
    if is_crisis:
        logger.critical(f"[SpecialModes] CRISIS MODE ACTIVE — {crisis_reason}")
        adjusted["crisis_blocked"] = True
        return SpecialModesResult(
            is_allowed=False,
            crisis_active=True,
            budget_active=False,
            rbi_active=False,
            is_expiry_day=False,
            size_multiplier=0.0,
            adjusted_signal=adjusted,
            reason=crisis_reason,
        )

    # 2. Union Budget Day Blackout Check
    is_budget, budget_reason = is_budget_day_blackout(eval_time=now)
    if is_budget:
        logger.warning(f"[SpecialModes] BUDGET DAY BLACKOUT — {budget_reason}")
        adjusted["budget_blocked"] = True
        return SpecialModesResult(
            is_allowed=False,
            crisis_active=False,
            budget_active=True,
            rbi_active=False,
            is_expiry_day=False,
            size_multiplier=0.0,
            adjusted_signal=adjusted,
            reason=budget_reason,
        )

    # 3. RBI Monetary Policy Blackout Check
    is_rbi, rbi_reason = is_rbi_policy_blackout(eval_time=now, calendar_events=calendar_events)
    if is_rbi:
        logger.warning(f"[SpecialModes] RBI POLICY BLACKOUT — {rbi_reason}")
        adjusted["rbi_blocked"] = True
        return SpecialModesResult(
            is_allowed=False,
            crisis_active=False,
            budget_active=False,
            rbi_active=True,
            is_expiry_day=False,
            size_multiplier=0.0,
            adjusted_signal=adjusted,
            reason=rbi_reason,
        )

    # 4. Dynamic Holiday-Aware Weekly Expiry Scaling
    symbol = str(signal.get("symbol", "")).strip().upper()
    is_expiry = False

    # Check via core.time_utils dynamic options expiry detector
    try:
        is_expiry = is_expiry_day(dt=now.date())
    except Exception:
        # Fallback to standard days if resolution not available
        is_thursday = (now.weekday() == 3)
        is_wednesday = (now.weekday() == 2)
        if is_thursday and ("NIFTY" in symbol and "BANK" not in symbol):
            is_expiry = True
        elif is_wednesday and "BANKNIFTY" in symbol:
            is_expiry = True

    if is_expiry:
        adjusted["expiry_day"] = True
        adjusted["reasons"] = adjusted.get("reasons", []) + ["Options Expiry Session — accelerated theta decay"]

    # 5. Volatility Sizing Multiplier
    size_mult = calculate_volatility_size_multiplier(vix_val)
    adjusted["size_multiplier"] = size_mult

    return SpecialModesResult(
        is_allowed=True,
        crisis_active=False,
        budget_active=False,
        rbi_active=False,
        is_expiry_day=is_expiry,
        size_multiplier=size_mult,
        adjusted_signal=adjusted,
        reason="Special modes clear",
    )


# ── 5. MANUAL OVERRIDE CONTROLLER ────────────────────────────────────────────

def set_crisis_override(active: bool, reason: str = "") -> None:
    """Manually activate/deactivate crisis mode override with thread safety."""
    global _manual_crisis_override, _manual_crisis_reason
    with _MODE_LOCK:
        _manual_crisis_override = bool(active)
        _manual_crisis_reason = str(reason or "").strip()
        logger.warning(f"[SpecialModes] Crisis override set to {active}: {_manual_crisis_reason}")
