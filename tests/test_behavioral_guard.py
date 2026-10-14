"""
Unit and Institutional Test Suite for risk/behavioral_guard.py
Tests Progressive Escalation Ladder (30m, 60m, Day Lockout),
VIX Adaptive Scaling, Symbol Lockouts, EOD Awareness, and State Persistence.
"""

from datetime import datetime, timedelta, timezone, time as dt_time
import json
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import mjonai.risk.behavioral_guard as bg
from mjonai.risk.behavioral_guard import (
    BehavioralGuardStatus,
    record_trade_outcome,
    check_behavioral_guard,
    get_behavioral_guard_status,
    is_symbol_locked,
    reset_guard,
)


@pytest.fixture(autouse=True)
def isolate_behavioral_state(tmp_path):
    """Isolate local storage and reset in-memory state before each test."""
    test_storage = tmp_path / "storage"
    test_storage.mkdir(parents=True, exist_ok=True)
    state_file = test_storage / "behavioral_guard_state.json"

    with patch("mjonai.risk.behavioral_guard._STORAGE_DIR", test_storage), \
         patch("mjonai.risk.behavioral_guard._STATE_FILE", state_file):
        reset_guard()
        yield
        reset_guard()


# ── 0. STOPLOSS COOLDOWN (freqtrade CooldownPeriod, clean-room) ───────────────

def test_stoploss_exit_locks_symbol_on_first_occurrence():
    """A single STOP_LOSS_HIT locks the symbol for the cooldown window —
    the loss ladder alone needs 2 same-symbol losses before acting."""
    record_trade_outcome("LOSS", symbol="RELIANCE", exit_reason="STOP_LOSS_HIT")
    assert is_symbol_locked("RELIANCE") is True


def test_non_stoploss_exit_does_not_lock_symbol():
    """TARGET/limit exits are planned exits — no cooldown on first occurrence."""
    record_trade_outcome("WIN", symbol="INFY", exit_reason="TARGET_HIT")
    assert is_symbol_locked("INFY") is False
    record_trade_outcome("LOSS", symbol="TCS", exit_reason="TIME_BARRIER_EXPIRED")
    assert is_symbol_locked("TCS") is False


def test_stoploss_cooldown_survives_win_outcome():
    """A trailed stop can exit green — the lock keys off the exit reason,
    not the P&L sign."""
    record_trade_outcome("WIN", symbol="HDFCBANK", exit_reason="STOP_LOSS_HIT")
    assert is_symbol_locked("HDFCBANK") is True


# ── 1. CONTRACT TESTS ────────────────────────────────────────────────────────

def test_behavioral_guard_status_contract():
    """Verify BehavioralGuardStatus dataclass serializes cleanly to dict."""
    status = BehavioralGuardStatus(
        is_allowed=True,
        cooldown_active=False,
        is_day_locked=False,
        cooldown_remaining_seconds=0,
        consecutive_losses=0,
        locked_symbols=[],
        is_symbol_locked=False,
        daily_trade_count=3,
        max_daily_trades=8,
        reason="Behavioral guard clear",
    )
    d = status.to_dict()
    assert d["is_allowed"] is True
    assert d["daily_trade_count"] == 3
    assert d["max_daily_trades"] == 8


# ── 2. PROGRESSIVE ESCALATION LADDER TESTS ───────────────────────────────────

def test_consecutive_losses_progressive_escalation():
    """Verify 2 losses -> 30m pause, 3 losses -> 60m pause, 4 losses -> Day lockout."""
    mock_now = datetime(2026, 8, 18, 10, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))

    with patch("mjonai.risk.behavioral_guard.now_ist", return_value=mock_now), \
         patch("mjonai.db.repository.insert_risk_event"):

        # Trade 1: Loss 1 -> Still allowed
        record_trade_outcome("LOSS", symbol="RELIANCE")
        allowed, _ = check_behavioral_guard(today_trade_count=1)
        assert allowed is True

        # Trade 2: Loss 2 -> Stage 1 Cooldown (30 mins)
        record_trade_outcome("LOSS", symbol="INFY")
        allowed, reason = check_behavioral_guard(today_trade_count=2)
        assert allowed is False
        assert "Cooling off active" in reason

        # Advance time by 31 minutes -> Cooldown expires
        mock_later = mock_now + timedelta(minutes=31)
        with patch("mjonai.risk.behavioral_guard.now_ist", return_value=mock_later):
            allowed, _ = check_behavioral_guard(today_trade_count=2)
            assert allowed is True

            # Trade 3: Loss 3 -> Stage 2 Cooldown (60 mins)
            record_trade_outcome("LOSS", symbol="TCS")
            allowed, reason = check_behavioral_guard(today_trade_count=3)
            assert allowed is False
            assert "60-minute" in reason or "Cooling off active" in reason

            # Trade 4: Loss 4 -> Full Day Lockout
            record_trade_outcome("LOSS", symbol="HDFCBANK")
            status = get_behavioral_guard_status(today_trade_count=4)
            assert status.is_day_locked is True
            assert status.is_allowed is False


def test_win_resets_loss_counter():
    """Verify a winning trade resets consecutive losses back to 0."""
    record_trade_outcome("LOSS", symbol="RELIANCE")
    assert bg._consecutive_losses == 1

    record_trade_outcome("WIN", symbol="RELIANCE")
    assert bg._consecutive_losses == 0


# ── 3. SYMBOL-LEVEL PROGRESSIVE LOCKOUT TESTS ────────────────────────────────

def test_symbol_specific_lockout():
    """Verify 2 losses on RELIANCE locks RELIANCE but leaves other symbols open."""
    mock_now = datetime(2026, 8, 18, 10, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))

    with patch("mjonai.risk.behavioral_guard.now_ist", return_value=mock_now), \
         patch("mjonai.db.repository.insert_risk_event"):

        # 2 losses on RELIANCE
        record_trade_outcome("LOSS", symbol="RELIANCE")
        record_trade_outcome("LOSS", symbol="RELIANCE")

        # RELIANCE is locked
        assert is_symbol_locked("RELIANCE") is True

        # System cooldown expires after 31 mins
        mock_later = mock_now + timedelta(minutes=31)
        with patch("mjonai.risk.behavioral_guard.now_ist", return_value=mock_later):
            # INFY is allowed (not locked)
            infy_allowed, _ = check_behavioral_guard(today_trade_count=2, symbol="INFY")
            assert infy_allowed is True

            # RELIANCE is still quarantined (45-min symbol cooldown)
            rel_allowed, reason = check_behavioral_guard(today_trade_count=2, symbol="RELIANCE")
            assert rel_allowed is False
            assert "RELIANCE" in reason


# ── 4. END-OF-DAY AWARENESS SENTRY ───────────────────────────────────────────

def test_end_of_day_awareness():
    """Verify consecutive losses after 02:30 PM trigger full-day stop."""
    # 02:35 PM IST
    mock_late = datetime(2026, 8, 18, 14, 35, tzinfo=timezone(timedelta(hours=5, minutes=30)))

    with patch("mjonai.risk.behavioral_guard.now_ist", return_value=mock_late), \
         patch("mjonai.db.repository.insert_risk_event"):

        record_trade_outcome("LOSS", symbol="RELIANCE")
        record_trade_outcome("LOSS", symbol="INFY")

        status = get_behavioral_guard_status(today_trade_count=2)
        assert status.is_day_locked is True
        assert status.is_allowed is False
        assert "Late Session" in status.reason or "halted" in status.reason


# ── 5. STATE PERSISTENCE & RESTORE ───────────────────────────────────────────

def test_state_persistence_across_restarts(tmp_path):
    """Verify behavioral guard state persists to disk and reloads cleanly."""
    test_storage = tmp_path / "storage"
    test_storage.mkdir(parents=True, exist_ok=True)
    state_file = test_storage / "behavioral_guard_state.json"

    with patch("mjonai.risk.behavioral_guard._STORAGE_DIR", test_storage), \
         patch("mjonai.risk.behavioral_guard._STATE_FILE", state_file), \
         patch("mjonai.db.repository.insert_risk_event"):

        record_trade_outcome("LOSS", symbol="RELIANCE")
        record_trade_outcome("LOSS", symbol="INFY")
        assert bg._consecutive_losses == 2
        assert bg._cooldown_active is True
        assert state_file.exists()

        # Simulate fresh process import reloading from disk
        bg._consecutive_losses = 0
        bg._cooldown_active = False
        bg._load_state()

        assert bg._consecutive_losses == 2
        assert bg._cooldown_active is True
