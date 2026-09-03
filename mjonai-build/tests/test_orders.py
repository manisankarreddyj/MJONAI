"""
Unit and Institutional Test Suite for SOTA Order Execution Management System (EMS)
(execution/orders.py)
"""

import sys

import pytest
from unittest.mock import patch, MagicMock

from execution.orders import (
    get_freeze_qty,
    calculate_limit_price_with_buffer,
    slice_order_for_freeze_limits,
    execute_order,
    open_paper_trade,
    close_paper_trade,
    close_all_paper_trades,
    OrderExecutionResult,
)


def test_get_freeze_qty_and_order_slicing():
    """Verify NSE/BSE/MCX freeze quantity lookup and order slicing."""
    # NIFTY freeze = 1800, BANKNIFTY = 900
    assert get_freeze_qty("NIFTY") == 1800
    assert get_freeze_qty("BANKNIFTY") == 900
    assert get_freeze_qty("MIDCPNIFTY") == 4200
    assert get_freeze_qty("CRUDEOIL") == 10000

    # Slicing test
    slices = slice_order_for_freeze_limits("NIFTY", 4000)
    assert sum(slices) == 4000
    assert slices == [1800, 1800, 400]

    # Non-oversized order
    assert slice_order_for_freeze_limits("NIFTY", 500) == [500]
    assert slice_order_for_freeze_limits("NIFTY", 0) == []


def test_calculate_limit_price_with_buffer():
    """Verify Market-with-Protection dynamic limit price calculation."""
    # BUY with 0.5% buffer: 1000.0 -> 1005.0
    assert calculate_limit_price_with_buffer(1000.0, side="BUY", buffer_pct=0.005) == 1005.0

    # SELL with 0.5% buffer: 1000.0 -> 995.0
    assert calculate_limit_price_with_buffer(1000.0, side="SELL", buffer_pct=0.005) == 995.0


def test_execute_order_dual_key_sentry():
    """Verify dual-key security gate blocks live order dispatch without authorization."""
    signal = {
        "symbol": "TCS",
        "entry_price": 3500.0,
        "stop_loss": 3430.0,
        "signal_direction": "LONG",
        "quantity": 10,
    }

    with patch("execution.orders.SYSTEM_MODE", "LIVE"), \
         patch("execution.orders.LIVE_EXECUTION_AUTHORIZED", False):
        res = execute_order(signal)
        assert res.is_success is False
        assert "LIVE execution blocked" in res.message


def test_open_paper_trade_with_slippage_and_tranches():
    """Verify open_paper_trade computes slippage bps and splits 3 tranches."""
    signal = {
        "symbol": "RELIANCE",
        "entry_price": 2500.0,
        "decision_price": 2490.0,  # 10 Rs slippage = 40.16 bps
        "stop_loss": 2450.0,
        "target": 2600.0,
        "quantity": 10,
        "signal_direction": "LONG",
        "asset_class": "EQUITY",
        "strategy_id": "S01_MomentumRSI",
        "total_cost": 50.0,
    }

    mock_trade_id = "test-trade-001"
    mock_insert = MagicMock(return_value={"id": mock_trade_id})
    mock_tranches = MagicMock(return_value=[])

    with patch("execution.orders.SYSTEM_MODE", "PAPER"), \
         patch("execution.orders.get_open_trade_by_symbol", return_value=None), \
         patch("execution.orders.insert_trade", mock_insert), \
         patch("execution.orders.insert_trade_tranches", mock_tranches):

        res = open_paper_trade(signal)
        assert res.is_success is True
        assert res.trade_id == mock_trade_id
        assert res.symbol == "RELIANCE"
        assert res.slippage_bps > 0  # 40.16 bps

        # Verify 3 tranches inserted: 50% (5), 30% (3), 20% (2)
        assert mock_tranches.call_count == 1
        inserted_tranches = mock_tranches.call_args[0][1]
        assert len(inserted_tranches) == 3
        assert inserted_tranches[0]["quantity"] == 5
        assert inserted_tranches[1]["quantity"] == 3
        assert inserted_tranches[2]["quantity"] == 2


def test_duplicate_trade_sentry_blocks_reentry():
    """Verify duplicate position guard blocks opening second trade on same symbol."""
    signal = {
        "symbol": "INFY",
        "entry_price": 1500.0,
        "stop_loss": 1470.0,
        "quantity": 5,
    }

    existing_trade = {"id": "existing-001", "symbol": "INFY", "status": "OPEN"}

    with patch("execution.orders.get_open_trade_by_symbol_strict", return_value=existing_trade):
        res = open_paper_trade(signal, allow_duplicate=False)
        assert res.is_success is False
        assert "Blocked duplicate trade" in res.message


def test_close_paper_trade_with_ml_feedback():
    """Verify trade close computes net P&L and triggers ML feedback loop."""
    mock_trade_id = "close-test-101"
    mock_trade = {
        "id": mock_trade_id,
        "symbol": "HDFCBANK",
        "entry_price": 1600.0,
        "quantity": 10,
        "quantity_remaining": 10,
        "side": "BUY",
        "total_cost": 40.0,
        "signal_id": "sig-uuid-888",
        "setup_hash": "S01_BULL_OPENING",
        "system_mode": "PAPER",
    }

    mock_close_db = MagicMock(return_value=True)
    mock_update_sig = MagicMock(return_value=True)
    mock_update_agents = MagicMock(return_value=True)
    mock_update_pattern = MagicMock(return_value=True)

    with patch("db.repository.get_open_trades", return_value=[mock_trade]), \
         patch("execution.orders.close_trade", mock_close_db), \
         patch("execution.orders.update_signal_outcome", mock_update_sig), \
         patch("execution.orders.update_agent_log_outcome", mock_update_agents), \
         patch("execution.orders.update_pattern_outcome", mock_update_pattern), \
         patch("execution.orders.get_closed_tranche_pnl", return_value={}):

        close_res = close_paper_trade(trade_id=mock_trade_id, exit_price=1650.0, exit_reason="TARGET_HIT")
        assert close_res is not None
        assert close_res["trade_id"] == mock_trade_id
        assert close_res["gross_pnl"] == 500.0  # (1650 - 1600) * 10
        assert close_res["net_pnl"] > 0
        assert close_res["tax"] > 0

        # Verify ML signal outcome updated
        assert mock_update_sig.call_count == 1
        call_kwargs = mock_update_sig.call_args[1]
        assert call_kwargs["signal_id"] == "sig-uuid-888"
        assert call_kwargs["actual_outcome"] == "WIN"
        mock_update_agents.assert_called_once_with(
            signal_id="sig-uuid-888", actual_outcome="WIN",
        )
        mock_update_pattern.assert_called_once_with(
            setup_hash="S01_BULL_OPENING", outcome="WIN", system_mode="PAPER",
        )


def test_close_all_paper_trades():
    """Verify emergency close_all_paper_trades loops through all active trades."""
    open_trades = [
        {"id": "t-1", "symbol": "INFY", "entry_price": 1500.0},
        {"id": "t-2", "symbol": "TCS", "entry_price": 3500.0},
    ]

    with patch("execution.orders.get_open_trades", return_value=open_trades), \
         patch("execution.orders.close_paper_trade", return_value={"trade_id": "t-1"}):
        count = close_all_paper_trades(exit_reason="EMERGENCY_HALT")
        assert count == 2


# ── Regression tests: 2026-08-23 money-path fixes (Session 2, A4) ──────────


def test_short_signal_gets_direction_aware_default_stop():
    """S2-A4-05: SHORT without explicit stop must stop ABOVE entry,
    not inherit the LONG-shaped entry*0.98 (instant false stop-out)."""
    signal = {
        "symbol": "INFY",
        "entry_price": 1500.0,
        "signal_direction": "SHORT",
        "stop_loss": None,
    }

    with patch("execution.orders.SYSTEM_MODE", "PAPER"), \
         patch("execution.orders.get_open_trade_by_symbol_strict", return_value=None), \
         patch("execution.orders.insert_trade", return_value={"id": "t-short"}) as mock_ins:
        result = open_paper_trade(signal)

    assert result.is_success
    recorded = mock_ins.call_args[0][0]
    assert float(recorded["stop_loss"]) > 1500.0  # above entry for a short


def test_wrong_side_explicit_stop_is_rejected():
    """A LONG whose explicit stop sits ABOVE entry is invalid data."""
    signal = {
        "symbol": "TCS",
        "entry_price": 3500.0,
        "signal_direction": "LONG",
        "stop_loss": 3600.0,   # wrong side
    }

    with patch("execution.orders.SYSTEM_MODE", "PAPER"):
        result = open_paper_trade(signal)

    assert not result.is_success
    assert "Invalid stop" in result.message


def test_dedup_check_failure_blocks_new_position():
    """S2-A4-02: when the duplicate check cannot be evaluated (DB down),
    the trade must be REFUSED - never treated as 'no duplicate'."""

    def _raise(*args, **kwargs):
        raise RuntimeError("supabase unreachable")

    signal = {"symbol": "RELIANCE", "entry_price": 2500.0, "signal_direction": "LONG"}

    with patch("execution.orders.SYSTEM_MODE", "PAPER"), \
         patch("execution.orders.get_open_trade_by_symbol_strict", side_effect=_raise), \
         patch("execution.orders.insert_trade") as should_not_insert:
        result = open_paper_trade(signal)

    assert not result.is_success
    assert "fail-closed" in result.message or "unavailable" in result.message
    should_not_insert.assert_not_called()


def test_live_broker_module_missing_aborts_never_simulates():
    """N1 regression: LIVE dispatch with a missing/broken broker module must
    fail CLOSED - cancel the reserved ledger row and report failure. The old
    fallback returned is_success=True with fabricated SIMULATED_LIVE_* order
    ids (fill theater on the real-money path)."""

    signal = {
        "symbol": "TCS",
        "entry_price": 3500.0,
        "stop_loss": 3430.0,
        "signal_direction": "LONG",
        "quantity": 10,
        "timeframe": "SWING",
    }
    mock_trade_id = "ledger-reservation-001"

    # Placing None in sys.modules makes import_module raise ImportError.
    with patch("execution.orders.SYSTEM_MODE", "LIVE"), \
         patch("execution.orders.LIVE_EXECUTION_AUTHORIZED", True), \
         patch.dict(sys.modules, {"data.angelone.smart_api": None}), \
         patch("execution.orders.get_open_trade_by_symbol_strict", return_value=None), \
         patch("execution.orders.insert_trade", MagicMock(return_value={"id": mock_trade_id})), \
         patch("execution.orders.insert_trade_tranches", MagicMock()), \
         patch("execution.orders.cancel_trade") as mock_cancel:

        res = execute_order(signal)

        assert res.is_success is False
        assert res.mode == "LIVE"
        assert res.broker_order_id is None
        assert "unavailable" in res.message.lower()
        mock_cancel.assert_called_once_with(trade_id=mock_trade_id, reason="BROKER_UNAVAILABLE")


def test_close_reports_failure_when_db_close_does_not_apply():
    """S2-A4-04: if the CAS close updates zero rows (already closed /
    write failed), close_paper_trade returns None instead of claiming
    settlement - so callers cannot double-count."""

    open_trades = [{
        "id": "t-dup", "symbol": "SBIN", "entry_price": 500.0,
        "quantity": 10, "side": "BUY", "total_cost": 20.0,
        "signal_id": None,
    }]

    with patch("execution.orders.get_open_trades", return_value=open_trades), \
         patch("execution.orders.close_trade", return_value=False), \
         patch("execution.orders.update_signal_outcome"), \
         patch("execution.orders.update_agent_log_outcome"), \
         patch("execution.orders.get_closed_tranche_pnl", return_value={}):
        res = close_paper_trade(trade_id="t-dup", exit_price=510.0,
                                exit_reason="TARGET", holding_days=1)

    assert res is None
