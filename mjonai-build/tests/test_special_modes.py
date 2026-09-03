"""
Unit and Institutional Test Suite for risk/special_modes.py
Tests Crisis Mode, Union Budget Speech Blackout, RBI Monetary Policy Mode,
Dynamic Expiry Day Detection, and Volatility Sizing Multipliers.
"""

from datetime import datetime, date, time as dt_time, timezone
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from risk.special_modes import (
    SpecialModesResult,
    is_crisis_mode,
    is_budget_day_blackout,
    is_rbi_policy_blackout,
    calculate_volatility_size_multiplier,
    check_special_modes,
    evaluate_special_modes,
    set_crisis_override,
)


@pytest.fixture(autouse=True)
def reset_modes():
    """Reset manual crisis overrides before each test."""
    set_crisis_override(False, "")
    yield
    set_crisis_override(False, "")


# ── 1. CONTRACT TESTS ────────────────────────────────────────────────────────

def test_special_modes_result_contract():
    """Verify SpecialModesResult dataclass serializes cleanly to dict."""
    res = SpecialModesResult(
        is_allowed=True,
        crisis_active=False,
        budget_active=False,
        rbi_active=False,
        is_expiry_day=False,
        size_multiplier=1.0,
        adjusted_signal={"symbol": "RELIANCE"},
        reason="Special modes clear",
    )
    d = res.to_dict()
    assert d["is_allowed"] is True
    assert d["size_multiplier"] == 1.0


# ── 2. CRISIS MODE TESTS ─────────────────────────────────────────────────────

def test_crisis_mode_triggers():
    """Verify Crisis Mode trips on extreme VIX (>=28), index crash (<=-2.5%), or manual override."""
    # Normal -> False
    assert is_crisis_mode(vix=15.0, intraday_index_drop_pct=-0.5)[0] is False

    # Extreme VIX (29.5 >= 28.0) -> True
    crisis_vix, reason_vix = is_crisis_mode(vix=29.5)
    assert crisis_vix is True
    assert "India VIX" in reason_vix

    # Flash Crash (-3.0% <= -2.5%) -> True
    crisis_crash, reason_crash = is_crisis_mode(vix=18.0, intraday_index_drop_pct=-3.0)
    assert crisis_crash is True
    assert "Flash Crash" in reason_crash

    # Manual Override -> True
    set_crisis_override(True, "War outbreak emergency")
    crisis_man, reason_man = is_crisis_mode(vix=15.0)
    assert crisis_man is True
    assert "War outbreak emergency" in reason_man


# ── 3. BUDGET DAY BLACKOUT TESTS ─────────────────────────────────────────────

def test_budget_day_speech_blackout():
    """Verify Feb 1st 10:30-13:30 triggers Budget blackout."""
    # Feb 1st at 11:30 AM -> Blackout active
    feb1_speech = datetime(2026, 2, 1, 11, 30, tzinfo=timezone.utc)
    is_budget, reason = is_budget_day_blackout(eval_time=feb1_speech)
    assert is_budget is True
    assert "Union Budget" in reason

    # Feb 1st at 02:00 PM (14:00) -> After speech -> Clear
    feb1_after = datetime(2026, 2, 1, 14, 0, tzinfo=timezone.utc)
    assert is_budget_day_blackout(eval_time=feb1_after)[0] is False

    # Normal day (Aug 18) at 11:30 AM -> Clear
    aug_normal = datetime(2026, 8, 18, 11, 30, tzinfo=timezone.utc)
    assert is_budget_day_blackout(eval_time=aug_normal)[0] is False


# ── 4. RBI MONETARY POLICY BLACKOUT TESTS ────────────────────────────────────

def test_rbi_policy_blackout():
    """Verify RBI MPC rate decision window triggers blackout."""
    # October 8th at 10:30 AM (Scheduled RBI date) -> Blackout active
    rbi_time = datetime(2026, 10, 8, 10, 30, tzinfo=timezone.utc)
    is_rbi, reason = is_rbi_policy_blackout(eval_time=rbi_time)
    assert is_rbi is True
    assert "RBI MPC" in reason

    # With external calendar event
    events = [{"name": "RBI Rate Hike Decision", "hours_away": 1.0}]
    assert is_rbi_policy_blackout(calendar_events=events)[0] is True


# ── 5. VOLATILITY SIZING MULTIPLIER TESTS ────────────────────────────────────

def test_volatility_sizing_multiplier():
    """Verify sizing multiplier halves positions during high turbulence (VIX 22-28)."""
    assert calculate_volatility_size_multiplier(14.0) == 1.0
    assert calculate_volatility_size_multiplier(19.0) == 0.80
    assert calculate_volatility_size_multiplier(24.0) == 0.50
    assert calculate_volatility_size_multiplier(29.0) == 0.0


# ── 6. MASTER ORCHESTRATION & EXPIRY DETECTION TESTS ─────────────────────────

def test_check_special_modes_orchestrator():
    """Verify check_special_modes evaluates all rules in sequence."""
    signal = {"symbol": "NIFTY", "entry_price": 24500.0}

    # Normal conditions with VIX 24 -> Allowed, but sized to 50%
    allowed, adj, reason = check_special_modes(signal=signal, vix=24.0)
    assert allowed is True
    assert adj["size_multiplier"] == 0.50

    # Crisis VIX 30 -> Blocked
    allowed_crisis, _, _ = check_special_modes(signal=signal, vix=30.0)
    assert allowed_crisis is False
