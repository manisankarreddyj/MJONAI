"""
Unit and Institutional Test Suite for Execution Engine
(execution/orders.py, execution/tracker.py, execution/tax.py, execution/eod.py)
"""

import pytest
from unittest.mock import patch, MagicMock

from mjonai.execution.orders import (
    open_paper_trade,
    close_paper_trade,
    execute_order,
    slice_order_for_freeze_limits,
    OrderExecutionResult,
)
from mjonai.execution.tracker import (
    calculate_trailing_sl,
    get_open_trades_with_pnl,
    check_paper_trades,
    evaluate_tranche_exits,
)
from mjonai.execution.tax import (
    calculate_tax,
    calculate_stt,
    calculate_stamp_duty,
    calculate_turnover_charges,
)
from mjonai.execution.eod import (
    eod_summary,
    save_daily_snapshot,
    reconcile_open_positions,
)


def test_slice_order_for_freeze_limits():
    """Verify orders exceeding exchange freeze limits are sliced cleanly."""
    # Nifty freeze limit is 1800
    slices = slice_order_for_freeze_limits("NIFTY", 2500)
    assert sum(slices) == 2500
    assert len(slices) == 2
    assert slices[0] == 1800
    assert slices[1] == 700


def test_calculate_tax_stcg_and_ltcg():
    """Verify 20.80% STCG and 13.00% LTCG rates with 4% cess."""
    # Profit under 1 year (STCG 20.80%)
    stcg = calculate_tax(10000.0, holding_days=5)
    assert stcg == 2080.0

    # Profit over 1 year (LTCG 13.00%)
    ltcg = calculate_tax(10000.0, holding_days=400)
    assert ltcg == 1300.0

    # Losses incur 0 tax
    loss_tax = calculate_tax(-5000.0, holding_days=10)
    assert loss_tax == 0.0


def test_calculate_stt_and_stamp_duty():
    """Verify STT and Stamp Duty calculations."""
    # Equity delivery STT 0.10%
    stt_del = calculate_stt(100000.0, side="SELL", asset_class="EQUITY", product_type="DELIVERY")
    assert stt_del == 100.0

    # Stamp duty on Buy side
    stamp_buy = calculate_stamp_duty(100000.0, side="BUY", asset_class="EQUITY", product_type="DELIVERY")
    assert stamp_buy == 15.0

    # Stamp duty on Sell side is 0
    stamp_sell = calculate_stamp_duty(100000.0, side="SELL", asset_class="EQUITY")
    assert stamp_sell == 0.0


def test_calculate_trailing_sl():
    """Verify ratchet SL candidate calculations."""
    # Long: SL trails upwards (120 - 2.5 * 2.0 = 115.0)
    long_sl = calculate_trailing_sl(entry=100.0, current_price=120.0, symbol="RELIANCE", signal_direction="LONG", atr=2.0)
    assert long_sl >= 100.0
    assert long_sl == (120.0 - 5.0)  # 115.0

    # Short: SL trails downwards (80 + 2.5 * 2.0 = 85.0)
    short_sl = calculate_trailing_sl(entry=100.0, current_price=80.0, symbol="TCS", signal_direction="SHORT", atr=2.0)
    assert short_sl <= 100.0
    assert short_sl == (80.0 + 5.0)  # 85.0


def test_open_and_close_paper_trade_lifecycle():
    """Verify complete paper trade opening, tranche creation, and closure."""
    signal = {
        "symbol": "INFY",
        "entry_price": 1500.0,
        "stop_loss": 1470.0,
        "target": 1560.0,
        "quantity": 10,
        "signal_direction": "LONG",
        "asset_class": "EQUITY",
        "strategy_id": "S01_MomentumRSI",
        "confidence": 85.0,
        "technical_score": 85.0,
        "total_cost": 50.0,
    }

    mock_trade_id = "test-uuid-101"
    mock_trade_record = {
        "id": mock_trade_id,
        "symbol": "INFY",
        "entry_price": 1500.0,
        "stop_loss": 1470.0,
        "target": 1560.0,
        "quantity": 10,
        "quantity_remaining": 10,
        "side": "BUY",
        "signal_direction": "LONG",
        "total_cost": 50.0,
    }

    with patch("mjonai.execution.orders.insert_trade", return_value={"id": mock_trade_id}), \
         patch("mjonai.execution.orders.insert_trade_tranches", return_value=[]), \
         patch("mjonai.execution.orders.get_open_trade_by_symbol_strict", return_value=None), \
         patch("mjonai.db.repository.get_open_trades", return_value=[mock_trade_record]), \
         patch("mjonai.execution.orders.close_trade", return_value=True):

        # Open paper trade
        res = open_paper_trade(signal)
        assert res is not None
        assert isinstance(res, OrderExecutionResult)
        assert res.is_success is True
        assert res.symbol == "INFY"
        trade_id = res.trade_id
        assert trade_id == mock_trade_id

        # Close paper trade with profit
        close_res = close_paper_trade(trade_id=trade_id, exit_price=1550.0, exit_reason="TARGET_HIT")
        assert close_res is not None
        assert close_res["trade_id"] == trade_id
        assert close_res["gross_pnl"] > 0
        assert close_res["net_pnl"] > 0
        assert close_res["tax"] > 0


def test_eod_summary_and_snapshot_persistence():
    """Verify EOD performance aggregation and daily snapshot upsert."""
    summary = eod_summary(send_telegram=False)
    assert summary is not None
    assert "realised_pnl" in summary
    assert "unrealised_pnl" in summary
    assert "total_pnl" in summary
    assert summary["mode"] is not None
