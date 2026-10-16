"""
Unit and Institutional Test Suite for End-of-Day (EOD) Reconciliation & Snapshots
(execution/eod.py)
"""

import pytest
from unittest.mock import patch, MagicMock

from mjonai.execution.eod import (
    eod_summary,
    save_daily_snapshot,
)


def test_eod_summary_metrics_and_profit_factor():
    """Verify EOD performance metrics, profit factor, and strategy attribution."""
    mock_trades = [
        # Win trade 1 (S01)
        {"id": "t-1", "symbol": "INFY", "exit_price": 1550.0, "net_pnl": 1000.0, "strategy_id": "S01_MomentumRSI"},
        # Win trade 2 (S08)
        {"id": "t-2", "symbol": "RELIANCE", "exit_price": 2550.0, "net_pnl": 500.0, "strategy_id": "S08_IntradayScalp"},
        # Loss trade 1 (S01)
        {"id": "t-3", "symbol": "TCS", "exit_price": 3400.0, "net_pnl": -300.0, "strategy_id": "S01_MomentumRSI"},
        # Open trade (not closed yet)
        {"id": "t-4", "symbol": "SBIN", "exit_price": None, "entry_price": 600.0, "quantity": 10},
    ]

    with patch("mjonai.execution.eod.get_all_trades_today", return_value=mock_trades), \
         patch("mjonai.execution.eod.get_trades_closed_today", return_value=[t for t in mock_trades if t.get("exit_price") is not None]), \
         patch("mjonai.execution.eod.get_open_trades_with_pnl", return_value=[{"pnl": 200.0}]), \
         patch("mjonai.execution.eod.save_daily_snapshot"):

        res = eod_summary(send_telegram=False)
        assert res["total_trades"] == 4
        assert res["closed_trades"] == 3
        assert res["open_trades"] == 1
        assert res["winners"] == 2
        assert res["losers"] == 1
        assert res["win_rate_pct"] == 66.7
        # Profit Factor: Gross Wins (1500) / Gross Losses (300) = 5.0
        assert res["profit_factor"] == 5.0
        assert res["realised_pnl"] == 1200.0
        assert res["unrealised_pnl"] == 200.0
        assert res["total_pnl"] == 1400.0

        # Strategy Attribution
        strat_map = res["strategy_attribution"]
        assert strat_map["S01_MomentumRSI"]["pnl"] == 700.0  # 1000 - 300
        assert strat_map["S01_MomentumRSI"]["trades"] == 2
        assert strat_map["S08_IntradayScalp"]["pnl"] == 500.0


def test_eod_summary_zero_trades():
    """Verify clean zero-state handling when no trades occurred."""
    with patch("mjonai.execution.eod.get_all_trades_today", return_value=[]), \
         patch("mjonai.execution.eod.get_trades_closed_today", return_value=[]), \
         patch("mjonai.execution.eod.get_open_trades_with_pnl", return_value=[]), \
         patch("mjonai.execution.eod.save_daily_snapshot"):

        res = eod_summary(send_telegram=False)
        assert res["total_trades"] == 0
        assert res["closed_trades"] == 0
        assert res["realised_pnl"] == 0.0
        assert res["profit_factor"] == 0.0


def test_save_daily_snapshot_hwm_and_drawdown():
    """Verify High-Water Mark and drawdown percentage computation in daily snapshot."""
    mock_upsert = MagicMock(return_value=True)
    prev_snapshot = {
        "capital_total": 100000.0,
        "high_water_mark": 110000.0,
    }

    trades_today = [
        {"id": "t-1", "exit_price": 100.0, "net_pnl": -5000.0, "total_cost": 20.0},
    ]

    with patch("mjonai.execution.eod.get_latest_snapshot_before", return_value=prev_snapshot), \
         patch("mjonai.execution.eod.get_latest_market_state", return_value={"state": "BULL"}), \
         patch("mjonai.execution.eod.get_trades_closed_today",
               return_value=[{**trades_today[0], "status": "CLOSED"}]), \
         patch("mjonai.execution.eod.get_open_trades", return_value=[]), \
         patch("mjonai.execution.eod.upsert_daily_snapshot", mock_upsert):

        # Realised P&L = -5000 -> Capital drops to 95,000 from previous 100,000
        save_daily_snapshot(realised_pnl=-5000.0, unrealised_pnl=0.0, trades_today=trades_today)

        assert mock_upsert.call_count == 1
        snapshot = mock_upsert.call_args[0][0]
        assert snapshot["capital_total"] == 95000.0
        assert snapshot["high_water_mark"] == 110000.0  # Retains peak HWM
        # Drawdown: (110000 - 95000) / 110000 = 13.64%
        assert snapshot["drawdown_pct"] == 13.64
        assert snapshot["market_state"] == "BULL"


def test_save_daily_snapshot_counts_real_book_not_created_today():
    """Counters must read the live open book + exit-time closes — the created-
    today list misses swing positions opened days ago (the 2026-10-15/16
    all-zero snapshot vs a 29-position book)."""
    mock_upsert = MagicMock(return_value=True)
    open_book = [
        {"id": "o-1", "symbol": "SBIN", "entry_price": 600.0, "quantity": 10,
         "status": "OPEN"},
        {"id": "o-2", "symbol": "INFY", "entry_price": 1500.0, "quantity": 5,
         "status": "OPEN"},
    ]
    closed = [
        {"id": "c-1", "exit_price": 100.0, "net_pnl": 500.0, "total_cost": 10.0},
    ]

    with patch("mjonai.execution.eod.get_latest_snapshot_before",
               return_value={"capital_total": 100000.0, "high_water_mark": 100000.0}), \
         patch("mjonai.execution.eod.get_latest_market_state", return_value=None), \
         patch("mjonai.execution.eod.get_trades_closed_today", return_value=closed), \
         patch("mjonai.execution.eod.get_open_trades", return_value=open_book), \
         patch("mjonai.execution.eod.upsert_daily_snapshot", mock_upsert):

        # Created-today list is EMPTY — counters must still see the book.
        save_daily_snapshot(realised_pnl=500.0, unrealised_pnl=0.0, trades_today=[])

        snapshot = mock_upsert.call_args[0][0]
        assert snapshot["open_positions"] == 2
        assert snapshot["closed_trades_today"] == 1
        assert snapshot["win_trades_today"] == 1
        assert snapshot["loss_trades_today"] == 0
        assert snapshot["capital_deployed"] == 600.0 * 10 + 1500.0 * 5
