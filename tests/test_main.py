"""
Unit and Institutional Test Suite for Master Runtime Coordinator
(apps/runtime/main.py — ADR-0008 layout)
"""

import pytest
from unittest.mock import patch, MagicMock

from apps.runtime import main


@pytest.mark.network
def test_connect_angelone_research_mode():
    """Verify broker connection succeeds safely in RESEARCH mode.
    Requires live Angel One credentials (SmartApi login) — skipped in
    deterministic CI which runs the non-network subset."""
    with patch("apps.runtime.main.SYSTEM_MODE", "RESEARCH"):
        assert main.connect_angelone() is True


def test_morning_routine_execution():
    """Verify 08:30 AM morning routine calculates regime, MQI, macro, and dispatches briefings."""
    with patch("apps.runtime.main.is_trading_day", return_value=True), \
         patch("apps.runtime.main.get_market_state", return_value=("BULL", 80, 14.5, False)), \
         patch("apps.runtime.main.calculate_mqi", return_value=("HIGH", 2, False, 85)), \
         patch("apps.runtime.main.fetch_macro_sentiment", return_value={"sp500_change_pct": 0.5, "crude_change_pct": -0.2, "dxy_change_pct": 0.1, "signal_limit_adjustment": 0, "flags": []}), \
         patch("apps.runtime.main.broadcast_market_state") as mock_b_market, \
         patch("apps.runtime.main.broadcast_pre_market") as mock_b_pre, \
         patch("apps.runtime.main.send_mqi_alert"):

        main.morning_routine()
        mock_b_market.assert_called_once_with("BULL", 80, 14.5)
        mock_b_pre.assert_called_once()


def test_monitor_trades_cycle_on_closed_trades():
    """Verify 1-min trade monitor updates trailing SL and dispatches closed trade alerts."""
    mock_trade = {"id": 101, "symbol": "RELIANCE", "pnl": 3500.0, "exit_reason": "TARGET_HIT"}

    with patch("apps.runtime.main.is_market_open", return_value=True), \
         patch("apps.runtime.main.is_websocket_healthy", return_value=True), \
         patch("apps.runtime.main.handle_websocket_health"), \
         patch("mjonai.execution.paper.check_paper_trades", return_value=[mock_trade]), \
         patch("mjonai.risk.emergency_triggers.update_consecutive_losses") as mock_upd, \
         patch("apps.runtime.main.broadcast_trade_closed") as mock_b_closed, \
         patch("apps.runtime.main.check_daily_loss"), \
         patch("apps.runtime.main.collect_health_log"):

        main.monitor_trades()
        # 2026-08-23 fix: the real SYSTEM_MODE is now passed explicitly so
        # the Soft Stop can activate in LIVE mode (was silently RESEARCH).
        mock_upd.assert_called_once_with("WIN", symbol="RELIANCE", system_mode=main.SYSTEM_MODE)
        mock_b_closed.assert_called_once_with(mock_trade)


def test_scan_and_execute_pipeline():
    """Verify 15-min scanner executes candidate signals via the unified
    dispatcher (G1: execution.orders.execute_order, which makes the LIVE
    ledger-first broker path reachable) and broadcasts ONLY on success."""
    from mjonai.execution.orders import OrderExecutionResult

    mock_signal = {
        "symbol": "TCS",
        "strategy_id": "S01_MomentumRSI",
        "entry_price": 4150.0,
        "stop_loss": 4050.0,
        "target": 4350.0,
        "quantity": 10,
    }

    mock_state = {"market_state": "BULL", "vix": 14.0, "mqi_level": "HIGH", "no_trade_day": False, "high_vol_override": False}

    # Successful dispatch -> broadcast exactly once.
    # NOTE: patch target is execution.orders.execute_order because main.py
    # imports it function-locally inside scan_and_execute.
    with patch("apps.runtime.main.is_trading_day", return_value=True), \
         patch("apps.runtime.main.now_ist") as mock_now, \
         patch("apps.runtime.main.is_trading_allowed", return_value=True), \
         patch("mjonai.db.repository.get_latest_market_state", return_value=mock_state), \
         patch("mjonai.db.repository.get_signals_intelligence_today", return_value=[]), \
         patch("mjonai.strategy.signal_scanner.scan_signals", return_value=[mock_signal]), \
         patch("mjonai.execution.orders.execute_order") as mock_exec, \
         patch("apps.runtime.main.broadcast_signal") as mock_b_signal:

        mock_time = MagicMock()
        mock_time.hour = 10
        mock_time.minute = 15
        mock_time.strftime.return_value = "10:15 IST"
        mock_now.return_value = mock_time

        mock_exec.return_value = OrderExecutionResult(is_success=True, symbol="TCS")

        main.scan_and_execute()
        mock_exec.assert_called_once_with(mock_signal)
        mock_b_signal.assert_called_once_with(mock_signal)

    # Refused dispatch (dedup block, invalid stop, broker failure) -> NO broadcast.
    with patch("apps.runtime.main.is_trading_day", return_value=True), \
         patch("apps.runtime.main.now_ist") as mock_now, \
         patch("apps.runtime.main.is_trading_allowed", return_value=True), \
         patch("mjonai.db.repository.get_latest_market_state", return_value=mock_state), \
         patch("mjonai.db.repository.get_signals_intelligence_today", return_value=[]), \
         patch("mjonai.strategy.signal_scanner.scan_signals", return_value=[mock_signal]), \
         patch("mjonai.execution.orders.execute_order") as mock_exec, \
         patch("apps.runtime.main.broadcast_signal") as mock_b_signal:

        mock_time = MagicMock()
        mock_time.hour = 10
        mock_time.minute = 15
        mock_time.strftime.return_value = "10:15 IST"
        mock_now.return_value = mock_time

        mock_exec.return_value = OrderExecutionResult(
            is_success=False, symbol="TCS", message="Blocked duplicate trade"
        )

        main.scan_and_execute()
        mock_b_signal.assert_not_called()


def test_eod_routine_broadcast():
    """Verify EOD routine summarizes performance and broadcasts scorecard."""
    mock_summary = {"total_trades": 5, "pnl_today": 12500.0, "win_rate": 80.0}

    with patch("apps.runtime.main.is_trading_day", return_value=True), \
         patch("mjonai.execution.paper.eod_summary", return_value=mock_summary), \
         patch("apps.runtime.main.broadcast_eod") as mock_b_eod:

        main.eod_routine()
        mock_b_eod.assert_called_once_with(mock_summary)
