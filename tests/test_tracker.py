"""
Unit and Institutional Test Suite for SOTA Active Position Tracker
(execution/tracker.py)
"""

from datetime import datetime, timedelta
import pytest
from unittest.mock import patch, MagicMock

from mjonai.execution.tracker import (
    calculate_trailing_sl,
    update_position_extremes,
    _calculate_holding_days,
    evaluate_tranche_exits,
    check_paper_trades,
    get_open_trades_with_pnl,
)


def test_calculate_trailing_sl_long_and_short():
    """Verify ATR trailing stop ratchets upwards for LONG and downwards for SHORT."""
    # Long: Entry 100, Current Price 120, ATR 2.0 -> Trailing SL = max(100, 120 - 5.0) = 115.0
    long_sl = calculate_trailing_sl(
        entry=100.0,
        current_price=120.0,
        symbol="RELIANCE",
        signal_direction="LONG",
        current_sl=100.0,
        atr=2.0,
    )
    assert long_sl == 115.0

    # Long stop never ratchets down if price dips
    long_sl_dip = calculate_trailing_sl(
        entry=100.0,
        current_price=110.0,
        symbol="RELIANCE",
        signal_direction="LONG",
        current_sl=115.0,
        atr=2.0,
    )
    assert long_sl_dip == 115.0

    # Short: Entry 100, Current Price 80, ATR 2.0 -> Trailing SL = min(100, 80 + 5.0) = 85.0
    short_sl = calculate_trailing_sl(
        entry=100.0,
        current_price=80.0,
        symbol="TCS",
        signal_direction="SHORT",
        current_sl=100.0,
        atr=2.0,
    )
    assert short_sl == 85.0


def test_trailing_sl_uses_entry_risk_not_flat_when_no_atr():
    """F31 regression: without a stored ATR, the trail buffer derives from the entry-time
    stop distance (volatility-scaled) rather than a flat 2%-of-entry."""
    # Entry 1000, entry stop 900 -> entry_risk 100 (10%); price 1200 -> trail 1200-100 = 1100
    sl_vol = calculate_trailing_sl(
        entry=1000.0, current_price=1200.0, symbol="RELIANCE",
        signal_direction="LONG", current_sl=900.0, entry_risk=100.0,
    )
    assert sl_vol == 1100.0

    # Flat 2%-of-entry fallback only when neither atr nor entry_risk supplied
    sl_flat = calculate_trailing_sl(
        entry=1000.0, current_price=1200.0, symbol="RELIANCE",
        signal_direction="LONG", current_sl=900.0,
    )
    assert sl_flat == 1180.0  # 1200 - (1000*0.02)=20

    # ATR (2.5*ATR) takes precedence over entry_risk when both present
    sl_atr = calculate_trailing_sl(
        entry=1000.0, current_price=1200.0, symbol="RELIANCE",
        signal_direction="LONG", current_sl=900.0, atr=2.0, entry_risk=100.0,
    )
    assert sl_atr == 1195.0  # 1200 - (2.0*2.5)=5


def test_calculate_holding_days():
    """Verify business holding days calculation from ISO timestamp."""
    assert _calculate_holding_days(None) == 0

    from mjonai.core.time_utils import now_ist
    ten_days_ago = (now_ist() - timedelta(days=14)).isoformat()
    assert _calculate_holding_days(ten_days_ago) >= 8


def test_evaluate_tranche_exits_breakeven_ratchet():
    """Verify Tranche 1 hit closes tranche and ratchets SL to entry price (Breakeven)."""
    trade = {
        "id": "trade-001",
        "symbol": "INFY",
        "entry_price": 1500.0,
        "signal_direction": "LONG",
        "target_1": 1550.0,
    }

    open_tranches = [
        {"id": "tr-1", "tranche_number": 1, "quantity": 5, "target_price": 1550.0},
        {"id": "tr-2", "tranche_number": 2, "quantity": 3, "target_price": 1600.0},
    ]

    mock_close_tranche = MagicMock(return_value=True)
    mock_update_sl = MagicMock(return_value=True)

    with patch("mjonai.execution.tracker.get_open_tranches_by_trade", return_value=open_tranches), \
         patch("mjonai.execution.tracker.close_tranche", mock_close_tranche), \
         patch("mjonai.execution.tracker.update_trade_sl", mock_update_sl):

        # Price reaches Target 1 (1550.0)
        has_hit, remaining_tranches = evaluate_tranche_exits(trade, current_price=1552.0, send_alerts=False)
        assert has_hit is True
        assert len(remaining_tranches) == 1
        assert mock_close_tranche.call_count == 1
        assert mock_update_sl.call_count == 1

        # Verify SL was ratcheted to Breakeven (1500.0)
        sl_call_args = mock_update_sl.call_args
        assert sl_call_args[1]["sl_stage"] == "BREAKEVEN"
        assert sl_call_args[1]["current_sl"] == 1500.0

        # Fill realism: the tranche limit fills AT the target (1550.0), not
        # at the overshooting touch price (1552.0) — parity with the
        # research backtest's trade_through limit semantics.
        assert mock_close_tranche.call_args[1]["exit_price"] == 1550.0


def test_check_paper_trades_final_target_fills_at_level():
    """A final-target hit books AT the target level, never at a better
    overshooting LTP (resting-limit fill realism)."""
    trade = {
        "id": "trade-tgt-01",
        "symbol": "SBIN",
        "entry_price": 600.0,
        "current_sl": 580.0,
        "target": 620.0,
        "signal_direction": "LONG",
        "timeframe": "SWING",
        "strategy_id": "S01_MomentumRSI",
    }

    mock_close = MagicMock(return_value={"trade_id": "trade-tgt-01", "exit_reason": "TARGET_HIT"})

    with patch("mjonai.execution.tracker.get_open_trades", return_value=[trade]), \
         patch("mjonai.execution.tracker.get_open_tranches_by_trade", return_value=[]), \
         patch("mjonai.execution.tracker.update_position_extremes"), \
         patch("mjonai.execution.orders.close_paper_trade", mock_close), \
         patch("mjonai.data.angelone.websocket.is_token_fresh", return_value=True):

        # LTP overshoots the target (625 >= 620); fill must be at 620.
        closed = check_paper_trades(live_prices={"SBIN": 625.0}, symbol_map={"SBIN": "SBIN"}, send_alerts=False)
        assert len(closed) == 1
        assert closed[0]["exit_reason"] == "TARGET_HIT"
        assert mock_close.call_args[1]["exit_price"] == 620.0


def test_check_paper_trades_sl_hit():
    """Verify Stop Loss breach triggers trade closure."""
    trade = {
        "id": "trade-sl-01",
        "symbol": "SBIN",
        "entry_price": 600.0,
        "current_sl": 590.0,
        "signal_direction": "LONG",
        "timeframe": "SWING",
        "strategy_id": "S01_MomentumRSI",
    }

    mock_close = MagicMock(return_value={"trade_id": "trade-sl-01", "exit_reason": "STOP_LOSS_HIT"})

    with patch("mjonai.execution.tracker.get_open_trades", return_value=[trade]), \
         patch("mjonai.execution.tracker.update_position_extremes"), \
         patch("mjonai.execution.orders.close_paper_trade", mock_close), \
         patch("mjonai.data.angelone.websocket.is_token_fresh", return_value=True):

        # LTP breaches Stop Loss (588.0 <= 590.0)
        closed = check_paper_trades(live_prices={"SBIN": 588.0}, symbol_map={"SBIN": "SBIN"}, send_alerts=False)
        assert len(closed) == 1
        assert closed[0]["exit_reason"] == "STOP_LOSS_HIT"


def test_check_paper_trades_intraday_eod_squareoff():
    """Verify Intraday MIS trades auto-exit at 03:15 PM IST."""
    trade = {
        "id": "trade-mis-01",
        "symbol": "TATAMOTORS",
        "entry_price": 800.0,
        "current_sl": 780.0,
        "signal_direction": "LONG",
        "timeframe": "INTRADAY",
        "strategy_id": "S08_IntradayScalp",
    }

    mock_close = MagicMock(return_value={"trade_id": "trade-mis-01", "exit_reason": "INTRADAY_EOD_SQUAREOFF"})
    mock_time = datetime(2026, 8, 18, 15, 20, 0)  # 03:20 PM IST

    with patch("mjonai.execution.tracker.get_open_trades", return_value=[trade]), \
         patch("mjonai.execution.tracker.now_ist", return_value=mock_time), \
         patch("mjonai.execution.tracker.update_position_extremes"), \
         patch("mjonai.execution.orders.close_paper_trade", mock_close), \
         patch("mjonai.data.angelone.websocket.is_token_fresh", return_value=True):

        closed = check_paper_trades(live_prices={"TATAMOTORS": 805.0}, symbol_map={"TATAMOTORS": "TATAMOTORS"}, send_alerts=False)
        assert len(closed) == 1
        assert closed[0]["exit_reason"] == "INTRADAY_EOD_SQUAREOFF"


def test_get_open_trades_with_pnl():
    """Verify real-time unrealized P&L and ROI % calculation."""
    trade = {
        "id": "trade-pnl-01",
        "symbol": "BAJFINANCE",
        "entry_price": 7000.0,
        "quantity": 10,
        "quantity_remaining": 10,
        "signal_direction": "LONG",
    }

    with patch("mjonai.execution.tracker.get_open_trades", return_value=[trade]), \
         patch("mjonai.data.angelone.websocket.is_token_fresh", return_value=True):
        # LTP = 7100 -> P&L = +₹1,000 (+1.43%)
        res = get_open_trades_with_pnl(live_prices={"BAJFINANCE": 7100.0}, symbol_map={"BAJFINANCE": "BAJFINANCE"})
        assert len(res) == 1
        assert res[0]["current_price"] == 7100.0
        assert res[0]["pnl"] == 1000.0
        assert res[0]["roi_pct"] == 1.43


def test_check_paper_trades_ignores_stale_raw_price():
    """Freshness gate: a raw live_prices entry whose tick is stale must be
    ignored fail-closed — the position must NOT be closed on a stale price."""
    trade = {
        "id": "trade-stale-01",
        "symbol": "TESTSYM",
        "entry_price": 600.0,
        "current_sl": 590.0,
        "signal_direction": "LONG",
        "timeframe": "SWING",
        "strategy_id": "S01_MomentumRSI",
    }
    mock_close = MagicMock(return_value={"trade_id": "trade-stale-01", "exit_reason": "STOP_LOSS_HIT"})

    with patch("mjonai.execution.tracker.get_open_trades", return_value=[trade]), \
         patch("mjonai.execution.tracker.update_position_extremes"), \
         patch("mjonai.execution.orders.close_paper_trade", mock_close), \
         patch("mjonai.data.angelone.websocket.is_token_fresh", return_value=False):

        # 588.0 would breach the 590.0 stop, but the tick is stale -> ignored.
        closed = check_paper_trades(live_prices={"TESTSYM": 588.0}, symbol_map={"TESTSYM": "TESTSYM"}, send_alerts=False)
        assert closed == []
        mock_close.assert_not_called()
