"""
12-Dimensional Production Test Suite for db/snapshots.py
Tests Financial Float Sanitization, Peak Equity Monotonicity Protection,
Crash Recovery, Environment Isolation, and Local WAL Journaling.
"""

import json
import math
import os
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import mjonai.db.snapshots as snapshots
from mjonai.db.snapshots import (
    upsert_daily_snapshot,
    get_snapshot_history,
    get_latest_snapshot,
    upsert_market_state,
    update_mqi_score,
    get_latest_market_state,
    save_peak_equity,
    load_peak_equity,
    _sanitize_payload,
)


@pytest.fixture(autouse=True)
def clean_storage_and_cache(tmp_path):
    """Reset peak equity cache and isolate local test storage."""
    snapshots._CACHED_PEAK_EQUITY = None
    test_storage = tmp_path / "storage"
    test_storage.mkdir(parents=True, exist_ok=True)
    
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()
    mock_sb.table.return_value.upsert.return_value.execute.return_value.data = []
    
    with patch("mjonai.db.snapshots._STORAGE_DIR", test_storage), \
         patch("mjonai.db.snapshots._PEAK_EQUITY_FILE", test_storage / "peak_equity.json"), \
         patch("mjonai.db.snapshots._LOCAL_JOURNAL_FILE", test_storage / "snapshots_journal.jsonl"), \
         patch("mjonai.db.snapshots.sb", mock_sb):
        yield


# ── 1. FINANCIAL FLOAT SANITIZATION TESTS ────────────────────────────────────

def test_nan_and_inf_payload_sanitization():
    """Verify NaN, Inf, and -Inf are converted to None (SQL NULL) and normal numbers preserved."""
    raw_payload = {
        "capital_total": 250000.50,
        "daily_return_pct": float("nan"),
        "max_drawdown_pct": float("inf"),
        "negative_inf": float("-inf"),
        "nested_stats": {
            "valid_stat": 1.25,
            "corrupt_stat": float("nan"),
        },
        "list_stats": [10.0, float("nan"), 20.0],
    }

    sanitized = _sanitize_payload(raw_payload)
    assert sanitized["capital_total"] == 250000.50
    assert sanitized["daily_return_pct"] is None
    assert sanitized["max_drawdown_pct"] is None
    assert sanitized["negative_inf"] is None
    assert sanitized["nested_stats"]["valid_stat"] == 1.25
    assert sanitized["nested_stats"]["corrupt_stat"] is None
    assert sanitized["list_stats"] == [10.0, None, 20.0]


# ── 2. PEAK EQUITY MONOTONICITY & RISK KILL-LINE INTEGRITY ───────────────────

def test_peak_equity_monotonicity_protection():
    """
    CRITICAL RISK-CONTROL TEST:
    Verify peak equity can NEVER decrease due to stale data, restarts, or malformed writes.
    new_peak = max(current_peak, candidate_peak)
    """
    # 1. Set initial peak
    peak_1 = save_peak_equity(250000.0)
    assert peak_1 == 250000.0

    # 2. Attempt to save higher peak -> Updates successfully
    peak_2 = save_peak_equity(275000.0)
    assert peak_2 == 275000.0

    # 3. Attempt to save lower stale candidate (e.g. 240,000) -> Monotonicity clamps to 275,000!
    peak_3 = save_peak_equity(240000.0)
    assert peak_3 == 275000.0
    assert load_peak_equity(default=100000.0) == 275000.0


def test_peak_equity_crash_and_offline_recovery():
    """Verify peak equity restores from local durable storage when Supabase is unreachable."""
    # 1. Save peak equity
    save_peak_equity(320000.0)

    # 2. Reset in-memory cache to simulate sudden process reboot
    snapshots._CACHED_PEAK_EQUITY = None

    # 3. Mock Supabase completely failing (raising exception)
    mock_sb = MagicMock()
    mock_sb.table.side_effect = Exception("Supabase Connection Refused")
    with patch("mjonai.db.snapshots.sb", mock_sb):
        recovered_peak = load_peak_equity(default=100000.0)
        assert recovered_peak == 320000.0


# ── 3. ENVIRONMENT ISOLATION TESTS ───────────────────────────────────────────

def test_snapshot_history_environment_isolation():
    """Verify get_snapshot_history strictly filters queries by system_mode."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.gte.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"snapshot_date": "2026-08-15", "system_mode": "LIVE"}])

    with patch("mjonai.db.snapshots.sb", mock_sb):
        history = get_snapshot_history(days=30, system_mode="LIVE")
        mock_table.eq.assert_called_once_with("system_mode", "LIVE")
        assert len(history) == 1


# ── 4. DAILY SNAPSHOT UPSERT & LOCAL WAL JOURNALING ──────────────────────────

def test_upsert_daily_snapshot_success():
    """Verify the daily snapshot upsert flow: no existing row for
    (snapshot_date, system_mode) → INSERT with the sanitized payload
    (volatile P&L columns stripped); an existing row → UPDATE.
    S7 (canonical verification wave 2026-09-03): re-pinned to the current
    select→insert/update implementation (the old test pinned the retired
    single .upsert(on_conflict='snapshot_date') call, which was wrong for
    the (date, mode)-keyed table)."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    # select("id").eq(date).eq(mode).limit(1).execute() → no existing row
    mock_table.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = \
        MagicMock(data=[])
    inserted_row = {"snapshot_date": "2026-08-15", "capital_total": 200000.0}
    mock_table.insert.return_value.execute.return_value = MagicMock(data=[inserted_row])

    with patch("mjonai.db.snapshots.sb", mock_sb):
        result = upsert_daily_snapshot({
            "snapshot_date": "2026-08-15",
            "capital_total": 200000.0,
            "system_mode": "LIVE",
        })
        mock_table.insert.assert_called_once()
        cleaned = mock_table.insert.call_args[0][0]
        assert cleaned["snapshot_date"] == "2026-08-15"
        assert "cash_balance" not in cleaned
        assert "margin_used" not in cleaned
        assert result["snapshot_date"] == "2026-08-15"


def test_upsert_daily_snapshot_offline_buffering():
    """Verify that when database is offline, snapshot is durably buffered to local WAL file."""
    mock_sb = MagicMock()
    mock_sb.table.side_effect = Exception("Database Offline")

    with patch("mjonai.db.snapshots.sb", mock_sb):
        record = upsert_daily_snapshot({
            "snapshot_date": "2026-08-15",
            "capital_total": 200000.0,
            "system_mode": "LIVE",
        })
        assert record["snapshot_date"] == "2026-08-15"

        # Verify local journal was written
        assert snapshots._LOCAL_JOURNAL_FILE.exists()
        with open(snapshots._LOCAL_JOURNAL_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) >= 1
            entry = json.loads(lines[-1])
            assert entry["event_type"] == "DAILY_PORTFOLIO_SNAPSHOT"
            assert entry["payload"]["snapshot_date"] == "2026-08-15"


# ── 5. MARKET STATE & MQI SCORE INTEGRITY ────────────────────────────────────

def test_market_state_upsert_and_retrieval_order():
    """Verify market state upsert and retrieval orders by (date desc, created_at desc)."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"date": "2026-08-15", "market_state": "BULL"}])

    with patch("mjonai.db.snapshots.sb", mock_sb):
        # 1. Upsert
        res = upsert_market_state({"date": "2026-08-15", "market_state": "BULL"})
        assert res.get("market_state") == "BULL"
        assert mock_table.update.call_count >= 1

        # 2. Get latest
        latest = get_latest_market_state()
        assert latest is not None
        assert latest["market_state"] == "BULL"
        assert mock_table.order.call_count >= 2


def test_update_mqi_score_status():
    """Verify update_mqi_score returns True on success and False when no row updated."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.upsert.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.eq.return_value = mock_table
    
    # 1. Success case (row updated/upserted)
    mock_table.execute.return_value = MagicMock(data=[{"date": "2026-08-15", "mqi_score": 80.0}])
    with patch("mjonai.db.snapshots.sb", mock_sb):
        assert update_mqi_score("2026-08-15", 80.0, "HIGH", False) is True

    # 2. Not found case (0 rows updated)
    mock_table.execute.return_value = MagicMock(data=[])
    with patch("mjonai.db.snapshots.sb", mock_sb):
        assert update_mqi_score("2026-08-15", 80.0, "HIGH", False) is False


def test_replay_local_journal_success(tmp_path):
    """Verify replay_local_journal reads WAL file, flushes records to Supabase, and clears file."""
    test_storage = tmp_path / "storage"
    test_storage.mkdir(parents=True, exist_ok=True)
    journal_file = test_storage / "snapshots_journal.jsonl"

    # Write 2 buffered offline records
    records = [
        {"event_type": "DAILY_PORTFOLIO_SNAPSHOT", "payload": {"snapshot_date": "2026-08-15", "total_equity": 250000.0}},
        {"event_type": "MARKET_STATE_HISTORY", "payload": {"date": "2026-08-15", "market_state": "BULL"}},
    ]
    with open(journal_file, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.upsert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"ok": True}])

    with patch("mjonai.db.snapshots._LOCAL_JOURNAL_FILE", journal_file), \
         patch("mjonai.db.snapshots.is_db_connected", return_value=True), \
         patch("mjonai.db.snapshots.sb", mock_sb):
        replayed = snapshots.replay_local_journal()
        assert replayed == 2
        assert not journal_file.exists()


# ── 6. DRAWDOWN & INTRADAY RISK CHECKPOINT TESTS ─────────────────────────────

def test_realtime_drawdown_pct_calculation():
    """Verify get_current_drawdown_pct computes exact percentage and auto-updates new peaks."""
    snapshots.reset_peak_equity_cache()
    # Baseline peak = 200,000. Current equity = 180,000 -> 10% Drawdown
    save_peak_equity(200000.0)
    dd_1 = snapshots.get_current_drawdown_pct(180000.0)
    assert dd_1 == 10.0

    # Current equity = 170,000 -> 15% Drawdown (Kill line trigger)
    dd_2 = snapshots.get_current_drawdown_pct(170000.0)
    assert dd_2 == 15.0

    # Current equity surpasses peak to 220,000 -> Drawdown = 0.0, Peak becomes 220,000
    dd_3 = snapshots.get_current_drawdown_pct(220000.0)
    assert dd_3 == 0.0
    assert snapshots.load_peak_equity(default=100000.0) == 220000.0


def test_upsert_intraday_snapshot_record():
    """Verify upsert_intraday_snapshot accepts IntradaySnapshotRecord dataclass cleanly."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"checkpoint_time": "2026-08-15T11:30:00", "current_equity": 210000.0}])

    record = snapshots.IntradaySnapshotRecord(
        checkpoint_time="2026-08-15T11:30:00",
        current_equity=210000.0,
        cash_available=50000.0,
        margin_utilized=160000.0,
        unrealized_pnl=2500.0,
        realized_pnl=1200.0,
        open_positions_count=2,
        drawdown_pct=2.5,
        system_mode="LIVE"
    )

    with patch("mjonai.db.snapshots.sb", mock_sb):
        res = snapshots.upsert_intraday_snapshot(record)
        assert res["current_equity"] == 210000.0
        mock_table.insert.assert_called_once()


def test_typed_snapshot_dataclass_serializations():
    """Verify PortfolioSnapshot and MarketStateSnapshotRecord serialize to dict cleanly."""
    port_snap = snapshots.PortfolioSnapshot(
        snapshot_date="2026-08-15",
        capital_total=250000.0,
        cash_balance=100000.0,
        daily_pnl=3500.0
    )
    port_dict = port_snap.to_dict()
    assert port_dict["snapshot_date"] == "2026-08-15"
    assert port_dict["daily_pnl"] == 3500.0

    market_snap = snapshots.MarketStateSnapshotRecord(
        date="2026-08-15",
        nifty_price=24500.0,
        nifty_ema200=23800.0,
        vix=13.5,
        atr=180.0,
        market_state="BULL",
        trend_regime="BULL_TREND",
        volatility_regime="NORMAL",
        breadth_pct=0.75
    )
    market_dict = market_snap.to_dict()
    assert market_dict["date"] == "2026-08-15"
    assert market_dict["market_state"] == "BULL"
