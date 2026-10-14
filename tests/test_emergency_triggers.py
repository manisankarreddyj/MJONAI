"""
Unit and Institutional Test Suite for risk/emergency_triggers.py
Tests Multi-Tier Emergency Circuit Breakers (Soft Stop, Risk Stop, Kill Line, Flash Crash).
"""

from datetime import datetime, timedelta, timezone
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from mjonai.core.constants import TOTAL_CAPITAL
import mjonai.risk.emergency_triggers as et
from mjonai.risk.emergency_triggers import (
    EmergencyRiskStatus,
    restore_risk_state,
    reset_daily_state,
    set_manual_pause,
    clear_manual_pause,
    is_trading_allowed,
    get_emergency_risk_status,
    update_consecutive_losses,
    check_daily_loss,
)


@pytest.fixture(autouse=True)
def reset_emergency_state():
    """Reset emergency triggers state before each test."""
    with et._RISK_LOCK:
        et._state["risk_stop_active"] = False
        et._state["soft_stop_active"] = False
        et._state["soft_stop_until"] = None
        et._state["flash_crash_pause_active"] = False
        et._state["flash_crash_until"] = None
        et._state["kill_line_active"] = False
        et._state["peak_equity"] = TOTAL_CAPITAL
        et._state["consecutive_losses"] = 0
        et._state["manual_pause_active"] = False
        et._state["manual_pause_reason"] = None
        et._equity_history.clear()
    yield
    with patch.object(et, "_safe_send_telegram", lambda *a, **k: None):
        reset_daily_state()


# ── 1. CONTRACT TESTS ────────────────────────────────────────────────────────

def test_emergency_risk_status_contract():
    """Verify EmergencyRiskStatus dataclass serializes cleanly to dict."""
    status = EmergencyRiskStatus(
        trading_allowed=True,
        kill_line_active=False,
        risk_stop_active=False,
        soft_stop_active=False,
        manual_pause_active=False,
        flash_crash_pause_active=False,
        current_drawdown_pct=0.0,
        daily_loss_pct=0.0,
        peak_equity=TOTAL_CAPITAL,
        current_equity=TOTAL_CAPITAL,
        realized_pnl_today=0.0,
        unrealized_pnl=0.0,
        total_pnl_today=0.0,
        reasons=[],
    )
    d = status.to_dict()
    assert d["trading_allowed"] is True
    assert d["peak_equity"] == TOTAL_CAPITAL


# ── 2. MANUAL PAUSE TESTS ───────────────────────────────────────────────────

def test_manual_pause_and_resume():
    """Verify manual pause freezes trading and resume lifts it."""
    assert is_trading_allowed() is True

    set_manual_pause("Testing manual halt")
    assert is_trading_allowed() is False
    status = get_emergency_risk_status()
    assert status.manual_pause_active is True
    assert any("Testing manual halt" in r for r in status.reasons)

    clear_manual_pause()
    assert is_trading_allowed() is True


# ── 3. SOFT STOP (3 CONSECUTIVE LOSSES) TESTS ────────────────────────────────

def test_soft_stop_consecutive_losses():
    """Verify 3 consecutive losses fires 60-min Soft Stop in LIVE mode."""
    with patch("mjonai.communication.telegram.send_message"), \
         patch("mjonai.db.repository.insert_risk_event"):

        update_consecutive_losses("LOSS", symbol="RELIANCE", system_mode="LIVE")
        update_consecutive_losses("LOSS", symbol="INFY", system_mode="LIVE")
        assert et._state["soft_stop_active"] is False

        update_consecutive_losses("LOSS", symbol="TCS", system_mode="LIVE")
        assert et._state["soft_stop_active"] is True
        assert is_trading_allowed(system_mode="LIVE") is False


# ── 4. FLASH CRASH VELOCITY SENTRY TESTS ─────────────────────────────────────

def test_flash_crash_velocity_sentry():
    """Verify rapid 1.5% drop within 5 minutes triggers flash-crash pause."""
    t0 = datetime(2026, 8, 18, 10, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    t1 = datetime(2026, 8, 18, 10, 3, tzinfo=timezone(timedelta(hours=5, minutes=30)))  # 3 mins later

    with patch("mjonai.risk.emergency_triggers.now_ist", return_value=t0), \
         patch("mjonai.db.repository.get_trades_closed_today", return_value=[]), \
         patch("mjonai.execution.paper.get_open_trades_with_pnl", return_value=[]), \
         patch("mjonai.db.repository.get_current_drawdown_pct", return_value=0.0), \
         patch("mjonai.db.repository.load_peak_equity", return_value=TOTAL_CAPITAL), \
         patch("mjonai.db.repository.save_peak_equity", return_value=TOTAL_CAPITAL):

        # Minute 0: Equity = 200,000
        check_daily_loss(system_mode="LIVE")

    with patch("mjonai.risk.emergency_triggers.now_ist", return_value=t1), \
         patch("mjonai.db.repository.get_trades_closed_today", return_value=[]), \
         patch("mjonai.execution.paper.get_open_trades_with_pnl", return_value=[{"pnl": -4000.0}]), \
         patch("mjonai.db.repository.get_current_drawdown_pct", return_value=2.0), \
         patch("mjonai.db.repository.load_peak_equity", return_value=TOTAL_CAPITAL), \
         patch("mjonai.db.repository.save_peak_equity", return_value=TOTAL_CAPITAL), \
         patch("mjonai.communication.telegram.send_message"), \
         patch("mjonai.db.repository.insert_risk_event"):

        # Minute 3: Equity drops from 200k -> 196k (2.0% drop in 3 mins > 1.5% limit)
        check_daily_loss(system_mode="LIVE")
        assert et._state["flash_crash_pause_active"] is True
        assert is_trading_allowed(system_mode="LIVE") is False


# ── 5. DAILY RISK STOP (3% LOSS) TESTS ───────────────────────────────────────

def test_daily_risk_stop():
    """Verify 3% daily loss limit (>= 6,000 on 200k) fires Risk Stop and blocks signals."""
    with patch("mjonai.db.repository.get_trades_closed_today", return_value=[{"net_pnl": -7000.0}]), \
         patch("mjonai.execution.paper.get_open_trades_with_pnl", return_value=[]), \
         patch("mjonai.communication.telegram.send_message"), \
         patch("mjonai.db.repository.insert_risk_event"), \
         patch("mjonai.db.repository.get_current_drawdown_pct", return_value=3.5), \
         patch("mjonai.db.repository.load_peak_equity", return_value=TOTAL_CAPITAL), \
         patch("mjonai.db.repository.save_peak_equity", return_value=TOTAL_CAPITAL):

        check_daily_loss(system_mode="LIVE")
        assert et._state["risk_stop_active"] is True
        assert is_trading_allowed(system_mode="LIVE") is False


# ── 6. THE 15% KILL LINE TESTS ───────────────────────────────────────────────

def test_lifetime_kill_line_nuclear_shutdown():
    """Verify 15% drawdown triggers Kill Line and auto-closes positions."""
    with patch("mjonai.db.repository.get_trades_closed_today", return_value=[{"net_pnl": -35000.0}]), \
         patch("mjonai.execution.paper.get_open_trades_with_pnl", return_value=[]), \
         patch("mjonai.db.repository.load_peak_equity", return_value=TOTAL_CAPITAL), \
         patch("mjonai.db.repository.save_peak_equity", return_value=TOTAL_CAPITAL), \
         patch("mjonai.execution.paper.close_all_paper_trades",
               return_value={"closed": 0, "left_open": [], "total": 0}) as mock_close, \
         patch("mjonai.communication.telegram.send_message"), \
         patch("mjonai.db.repository.insert_risk_event"):

        check_daily_loss(system_mode="LIVE")
        assert et._state["kill_line_active"] is True
        assert is_trading_allowed(system_mode="LIVE") is False
        # Pinned to the REAL signature: close_all_paper_trades(exit_reason=...)
        # The old assertion pinned the buggy reason= keyword (TypeError 100%).
        mock_close.assert_called_once_with(exit_reason="KILL_LINE")


def test_kill_line_message_names_left_open_positions():
    """P1: the kill-line alert must name stale-feed leftovers instead of
    claiming 'all closed' while positions stay open."""
    import mjonai.risk.emergency_triggers as et_mod
    et_mod._state["kill_line_active"] = False
    try:
        with patch("mjonai.execution.paper.close_all_paper_trades",
                   return_value={"closed": 2, "left_open": ["INFY"], "total": 3}), \
             patch("mjonai.communication.telegram.send_message") as mock_send, \
             patch("mjonai.risk.emergency_triggers._log_risk_event"):
            et_mod._fire_kill_line(16.0, -16000.0, system_mode="PAPER")
        body = mock_send.call_args[0][0]
        assert "STILL OPEN" in body and "INFY" in body
        assert "All paper positions closed" not in body
    finally:
        et_mod._state["kill_line_active"] = False


def test_kill_line_arms_in_paper_mode():
    """P0.6 (2026-09-20 ruling): the Kill Line must arm in ANY non-RESEARCH
    mode (LIVE + PAPER), so the emergency stack is exercised in simulation.
    The old `sys_mode == "LIVE"` guard left PAPER un-protected."""
    with patch("mjonai.db.repository.get_trades_closed_today", return_value=[{"net_pnl": -35000.0}]), \
         patch("mjonai.execution.paper.get_open_trades_with_pnl", return_value=[]), \
         patch("mjonai.db.repository.load_peak_equity", return_value=TOTAL_CAPITAL), \
         patch("mjonai.db.repository.save_peak_equity", return_value=TOTAL_CAPITAL), \
         patch("mjonai.execution.paper.close_all_paper_trades") as mock_close, \
         patch("mjonai.communication.telegram.send_message"), \
         patch("mjonai.db.repository.insert_risk_event"):

        check_daily_loss(system_mode="PAPER")
        assert et._state["kill_line_active"] is True
        assert is_trading_allowed(system_mode="PAPER") is False
        mock_close.assert_called_once_with(exit_reason="KILL_LINE")


def test_kill_line_does_not_arm_in_research_mode():
    """P0.6: RESEARCH must never arm the Kill Line — research equity is
    exploratory and must not lock the operator out of trading."""
    with patch("mjonai.db.repository.get_trades_closed_today", return_value=[{"net_pnl": -35000.0}]), \
         patch("mjonai.execution.paper.get_open_trades_with_pnl", return_value=[]), \
         patch("mjonai.db.repository.load_peak_equity", return_value=TOTAL_CAPITAL), \
         patch("mjonai.db.repository.save_peak_equity", return_value=TOTAL_CAPITAL), \
         patch("mjonai.execution.paper.close_all_paper_trades") as mock_close, \
         patch("mjonai.communication.telegram.send_message"), \
         patch("mjonai.db.repository.insert_risk_event"):

        check_daily_loss(system_mode="RESEARCH")
        assert et._state["kill_line_active"] is False
        assert get_emergency_risk_status(system_mode="RESEARCH").kill_line_active is False
        mock_close.assert_not_called()


def test_lifetime_ruin_circuit_fires_even_when_session_is_flat():
    """P0.6: the NEW lifetime-ruin circuit (equity <= (100 - KILL_LINE_PCT)% of
    the persisted lifetime peak watermark) fires even when today's session shows
    ZERO drawdown — multi-day ruin below a high watermark must still lock."""
    et._state["peak_session_date"] = str(et.today_ist())  # session already anchored today
    et._state["peak_equity"] = TOTAL_CAPITAL              # session peak = flat
    era_peak = TOTAL_CAPITAL * 1.25                       # persisted watermark 25% above

    with patch("mjonai.db.repository.get_trades_closed_today", return_value=[]), \
         patch("mjonai.execution.paper.get_open_trades_with_pnl", return_value=[]), \
         patch("mjonai.db.repository.load_peak_equity", return_value=era_peak), \
         patch("mjonai.db.repository.save_peak_equity", return_value=TOTAL_CAPITAL), \
         patch("mjonai.execution.paper.close_all_paper_trades") as mock_close, \
         patch("mjonai.communication.telegram.send_message"), \
         patch("mjonai.db.repository.insert_risk_event"):

        check_daily_loss(system_mode="PAPER")
        assert et._state["kill_line_active"] is True
        mock_close.assert_called_once_with(exit_reason="KILL_LINE")


def test_kill_line_autoclose_runs_real_close_without_typeerror():
    """CRITICAL (2026-09-03 audit): the Kill Line caller passed reason="KILL_LINE"
    to close_all_paper_trades(exit_reason=...), raising TypeError every fire;
    the surrounding except swallowed it and positions were never auto-closed.
    This test runs the REAL close_all_paper_trades end-to-end (only DB,
    telegram and the risk-event insert are mocked) to pin both the keyword
    contract and the mode-scoped open-trades query."""
    with patch.object(et, "SYSTEM_MODE", "PAPER"), \
         patch("mjonai.execution.orders.SYSTEM_MODE", "PAPER"), \
         patch("mjonai.execution.orders.get_open_trades", return_value=[]) as mock_get, \
         patch("mjonai.execution.orders.close_paper_trade") as mock_close_one, \
         patch.object(et, "_safe_send_telegram"), \
         patch("mjonai.db.repository.insert_risk_event"):

        et._fire_kill_line(drawdown_pct=17.5, total_pnl=-15_000.0, system_mode="PAPER")

    assert et._state["kill_line_active"] is True
    # The real auto-close path executed (no TypeError was swallowed) and
    # queried ONLY the current mode's open positions.
    mock_get.assert_called_once_with(system_mode="PAPER")
    mock_close_one.assert_not_called()


# ── Regression tests: 2026-08-23 risk-control fixes (Session 2, A3) ────────


def test_soft_stop_fires_in_live_mode_after_three_losses():
    """S2-A3-01: the Soft Stop must actually ACTIVATE in LIVE mode.
    The old mode-default bug kept it in log-only RESEARCH branch forever."""
    et._state["consecutive_losses"] = 0
    et._state["soft_stop_active"] = False

    with patch.object(et, "SYSTEM_MODE", "LIVE"), \
         patch.object(et, "_safe_send_telegram"), \
         patch("mjonai.risk.behavioral_guard.record_trade_outcome"):
        for _ in range(3):
            et.update_consecutive_losses("LOSS", symbol="TEST", system_mode="LIVE")

    try:
        assert et._state["consecutive_losses"] >= 3
        assert et._state["soft_stop_active"] is True
        assert et._state["soft_stop_until"] is not None
    finally:
        et._state["soft_stop_active"] = False
        et._state["soft_stop_until"] = None
        et._state["consecutive_losses"] = 0


def test_session_baseline_uses_snapshot_not_stale_constant():
    """S2-A3-02 (part): baseline equity must come from yesterday's
    snapshot chain, not the static TOTAL_CAPITAL constant."""
    fake_snapshot = {"capital_total": 137000.0}

    with patch("mjonai.db.repository.get_latest_snapshot_before", return_value=fake_snapshot):
        baseline = et._session_baseline_equity("LIVE")

    assert baseline == 137000.0


def test_kill_line_drawdown_uses_session_peak_not_lifetime_watermark():
    """S2-A3-02: session peak re-anchors to the daily baseline each new
    day, so a lifetime high-watermark cannot fabricate phantom drawdown."""
    et._state["peak_session_date"] = "2000-01-01"   # stale day marker
    et._state["peak_equity"] = 1_000_000.0          # old lifetime watermark

    today_iso = str(et.today_ist())
    baseline = 100_000.0

    # Simulate the anchoring block from check_daily_loss:
    if et._state.get("peak_session_date") != today_iso:
        et._state["peak_session_date"] = today_iso
        et._state["peak_equity"] = max(baseline, 99_500.0)

    assert et._state["peak_equity"] == 100_000.0    # NOT the 1M watermark

    drawdown_pct = ((et._state["peak_equity"] - 99_500.0) / et._state["peak_equity"]) * 100.0
    assert abs(drawdown_pct - 0.5) < 0.01           # real damage only


def test_day_lockout_expires_on_calendar_rollover():
    """S2-A3-03: day-scoped lockouts clear when the IST date changes."""
    from mjonai.risk import behavioral_guard as bg

    bg._day_locked = True
    bg._day_lock_date = "2000-01-01"                # clearly yesterday-or-older
    bg._cooldown_reason = "test"
    bg._cooldown_active = False                     # isolate the rollover behavior
    bg._cooldown_until = None

    try:
        allowed, reason = bg.check_behavioral_guard(
            today_trade_count=0, symbol=None, system_mode="LIVE"
        )
        assert allowed is True                      # rollover cleared the lock
        assert bg._day_locked is False
        assert bg._day_lock_date is None
    finally:
        bg._day_locked = False
        bg._day_lock_date = None


def test_behavioral_guard_failure_blocks_trading_fail_closed():
    """F14: if the psychology guard cannot be evaluated, LIVE/PAPER must block trading
    (fail-closed), not let it through. RESEARCH is exempt (exploratory)."""
    with patch("mjonai.risk.behavioral_guard.check_behavioral_guard", side_effect=RuntimeError("guard db down")):
        status_paper = get_emergency_risk_status(system_mode="PAPER")
        assert status_paper.trading_allowed is False
        assert any("Behavioral guard" in r for r in status_paper.reasons)

        status_research = get_emergency_risk_status(system_mode="RESEARCH")
        assert not any("Behavioral guard" in r for r in status_research.reasons)
