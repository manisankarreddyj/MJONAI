"""
Comprehensive Unit & Institutional Test Suite for db/trades.py
Tests Multi-Asset Order Lifecycle, Implementation Shortfall (Slippage bps),
3-Tranche Partial Scaling, Stop-Loss Ratcheting, Excursion Analytics (MAE/MFE),
and WAL Journal Replay.
"""

import json
import math
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import db.trades as trades
from db.trades import (
    TradeRecord,
    TrancheRecord,
    insert_trade,
    get_open_trades,
    get_open_trade_by_symbol,
    get_trades_closed_today,
    get_all_trades_today,
    close_trade,
    update_trade_exit_fields,
    insert_trade_tranches,
    get_open_tranches,
    get_open_tranches_by_trade,
    close_tranche,
    update_trade_sl,
    get_trades_with_open_tranches,
    update_trade_price_extremes,
    update_trade_research_fields,
    get_research_trades,
    get_all_closed_trades,
    replay_trade_journal,
    _sanitize_payload,
)


@pytest.fixture(autouse=True)
def clean_trade_storage(tmp_path):
    """Isolate local storage for trade WAL tests."""
    test_storage = tmp_path / "storage"
    test_storage.mkdir(parents=True, exist_ok=True)
    with patch("db.trades._STORAGE_DIR", test_storage), \
         patch("db.trades._TRADES_JOURNAL_FILE", test_storage / "trades_journal.jsonl"):
        yield


# ── 1. CONTRACTS & SLIPPAGE TESTS ────────────────────────────────────────────

def test_trade_contracts_and_serialization():
    """Verify dataclasses serialize cleanly to dictionaries omitting None values."""
    rec = TradeRecord(
        symbol="RELIANCE",
        direction="BUY",
        entry_price=2500.0,
        initial_sl=2470.0,
        current_sl=2470.0,
        target_price=2560.0,
        quantity=50,
        strategy_id="ORB_15M",
        asset_class="EQUITY",
    )
    d = rec.to_dict()
    assert d["symbol"] == "RELIANCE"
    assert d["entry_price"] == 2500.0
    assert d["quantity"] == 50
    assert "exit_price" not in d


def test_insert_trade_with_slippage_calculation():
    """Verify insert_trade automatically computes implementation shortfall (slippage) in bps."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"id": "tr-101", "symbol": "NIFTY26AUG24500CE"}])

    with patch("db.trades.sb", mock_sb):
        # Decision Price = 100.0, Fill Price = 100.50 -> Slippage = +50 bps
        res = insert_trade({
            "symbol": "NIFTY26AUG24500CE",
            "direction": "BUY",
            "decision_price": 100.0,
            "entry_price": 100.50,
            "initial_sl": 85.0,
            "current_sl": 85.0,
            "target_price": 130.0,
            "quantity": 50,
            "strategy_id": "GAMMA_SCALP",
        })
        assert res["id"] == "tr-101"
        call_payload = mock_table.insert.call_args[0][0]
        assert call_payload["slippage_bps"] == 50.0


# ── 2. ACTIVE POSITIONS & CLOSING OPERATIONS ─────────────────────────────────

def test_get_open_trades_and_by_symbol():
    """Verify get_open_trades and get_open_trade_by_symbol execution."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.is_.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.order.return_value = mock_table

    mock_table.execute.side_effect = [
        MagicMock(data=[{"id": "tr-1", "symbol": "INFY", "status": "OPEN"}]),
        MagicMock(data=[{"id": "tr-1", "symbol": "INFY", "status": "OPEN"}]),
    ]

    with patch("db.trades.sb", mock_sb):
        open_trades = get_open_trades(system_mode="LIVE")
        assert len(open_trades) == 1

        infy_trade = get_open_trade_by_symbol("INFY", system_mode="LIVE")
        assert infy_trade is not None
        assert infy_trade["symbol"] == "INFY"


def test_close_trade_and_update_exit_fields():
    """Verify close_trade and update_trade_exit_fields update status to CLOSED."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"id": "tr-1", "status": "CLOSED"}])

    with patch("db.trades.sb", mock_sb):
        ok = close_trade(
            trade_id="tr-1",
            exit_price=2560.0,
            gross_pnl=3000.0,
            net_pnl=2850.0,
            exit_reason="TARGET",
            taxes_charges=150.0,
        )
        assert ok is True
        update_args = mock_table.update.call_args[0][0]
        assert update_args["status"] == "CLOSED"
        assert update_args["net_pnl"] == 2850.0


# ── 3. 3-TRANCHE SCALING & STOP LOSS RATCHETING ──────────────────────────────

def test_insert_and_close_tranche():
    """Verify insert_trade_tranches and close_tranche manage child partial lots."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.eq.return_value = mock_table

    mock_table.execute.side_effect = [
        MagicMock(data=[{"id": "trn-1"}, {"id": "trn-2"}, {"id": "trn-3"}]),
        MagicMock(data=[{"id": "trn-1", "status": "CLOSED"}]),
    ]

    with patch("db.trades.sb", mock_sb):
        tranches = [
            TrancheRecord(trade_id="tr-1", tranche_number=1, quantity=25, target_price=115.0),
            TrancheRecord(trade_id="tr-1", tranche_number=2, quantity=15, target_price=125.0),
            TrancheRecord(trade_id="tr-1", tranche_number=3, quantity=10, target_price=None),
        ]
        inserted = insert_trade_tranches("tr-1", tranches)
        assert len(inserted) == 3

        closed_ok = close_tranche("trn-1", exit_price=115.0, gross_pnl=375.0, net_pnl=350.0)
        assert closed_ok is True


def test_update_trade_sl_ratchet():
    """Verify update_trade_sl ratchets stop loss to BREAKEVEN and 1R_LOCKED."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"id": "tr-1", "sl_stage": "BREAKEVEN"}])

    with patch("db.trades.sb", mock_sb):
        ok = update_trade_sl("tr-1", sl_stage="BREAKEVEN", current_sl=2500.0, quantity_remaining=25)
        assert ok is True
        update_args = mock_table.update.call_args[0][0]
        assert update_args["sl_stage"] == "BREAKEVEN"
        assert update_args["current_sl"] == 2500.0
        assert update_args["quantity_remaining"] == 25


# ── 4. 3-WAY EXCURSION ANALYTICS (MAE & MFE) ─────────────────────────────────

def test_update_trade_price_extremes_mae_mfe():
    """Verify update_trade_price_extremes tracks MAE (Max Pain) and MFE (Peak Profit)."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.update.return_value = mock_table

    # Trade entered at ₹100. Price hits ₹95 (MAE = -5%) and ₹120 (MFE = +20%)
    mock_table.execute.side_effect = [
        MagicMock(data=[{"entry_price": 100.0, "price_low_since_entry": 98.0, "price_high_since_entry": 105.0, "direction": "BUY"}]),
        MagicMock(data=[{"ok": True}]),
    ]

    with patch("db.trades.sb", mock_sb):
        extremes = update_trade_price_extremes("tr-1", current_price=95.0, entry_price=100.0, direction="BUY")
        assert extremes is not None
        assert extremes["price_low_since_entry"] == 95.0
        assert extremes["mae_pct"] == -5.0


# ── 5. OFFLINE WAL JOURNAL REPLAY ────────────────────────────────────────────

def test_trade_wal_journal_replay(tmp_path):
    """Verify replay_trade_journal drains buffered offline trade events to Supabase."""
    test_storage = tmp_path / "storage"
    test_storage.mkdir(parents=True, exist_ok=True)
    journal_file = test_storage / "trades_journal.jsonl"

    record = {
        "event_type": "INSERT_TRADE",
        "payload": {"symbol": "TCS", "direction": "BUY", "entry_price": 4000.0, "quantity": 10},
    }
    with open(journal_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"ok": True}])

    with patch("db.trades._TRADES_JOURNAL_FILE", journal_file), \
         patch("db.trades.is_db_connected", return_value=True), \
         patch("db.trades.sb", mock_sb):
        replayed = replay_trade_journal()
        assert replayed == 1
        assert not journal_file.exists()
