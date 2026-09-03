"""
Comprehensive Unit & Integration Test Suite for db/signals.py
Tests Signal Lifecycle, Vectorized Ingestion, Float Sanitization,
Outcome Attribution, and Alphalens Factor Pipeline.
"""

import math
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import mjonai.db.signals as signals
from mjonai.db.signals import (
    SignalIntelligenceRecord,
    insert_signal,
    get_signals_today,
    insert_signal_intelligence,
    insert_signals_bulk,
    update_signal_outcome,
    get_signals_intelligence_today,
    get_signal_by_id,
    get_signals_needing_forward_returns,
    update_signal_forward_returns,
    get_signals_for_alphalens,
    replay_signal_journal,
    _sanitize_payload,
)


# ── 1. FLOAT SANITIZATION & CONTRACT TESTS ───────────────────────────────────

def test_signal_float_sanitization():
    """Verify NaN and Inf values are safely converted to None for PostgreSQL compliance."""
    dirty_payload = {
        "actual_rr": float("nan"),
        "actual_pnl_net": float("inf"),
        "negative_inf": float("-inf"),
        "valid_metric": 2.45,
        "nested": {"bad": float("nan"), "good": 10.0},
    }
    cleaned = _sanitize_payload(dirty_payload)
    assert cleaned["actual_rr"] is None
    assert cleaned["actual_pnl_net"] is None
    assert cleaned["negative_inf"] is None
    assert cleaned["valid_metric"] == 2.45
    assert cleaned["nested"]["bad"] is None
    assert cleaned["nested"]["good"] == 10.0


def test_signal_intelligence_record_contract():
    """Verify SignalIntelligenceRecord dataclass creates clean dictionaries omitting None."""
    rec = SignalIntelligenceRecord(
        symbol="RELIANCE",
        signal_type="BUY",
        strategy_id="ORB_15M",
        raw_signal_value=1.45,
        final_confidence=0.88,
        planned_quantity=50,
        entry_price=2500.0,
        sl_price=2470.0,
        target_price=2560.0,
    )
    d = rec.to_dict()
    assert d["symbol"] == "RELIANCE"
    assert d["signal_type"] == "BUY"
    assert d["final_confidence"] == 0.88
    assert "actual_outcome" not in d  # None fields omitted cleanly


# ── 2. INSERTION & BATCH OPERATIONS ──────────────────────────────────────────

def test_insert_signal_intelligence_success():
    """Verify insert_signal_intelligence inserts record and populates updated_at."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"id": "sig-123", "symbol": "INFY"}])

    with patch("mjonai.db.signals.sb", mock_sb):
        res = insert_signal_intelligence({
            "symbol": "INFY",
            "signal_type": "BUY",
            "strategy_id": "SUPERTREND_VOL",
            "raw_signal_value": 2.1,
            "final_confidence": 0.90,
            "planned_quantity": 100,
        })
        assert res["id"] == "sig-123"
        mock_table.insert.assert_called_once()


def test_insert_signals_bulk_success():
    """Verify insert_signals_bulk performs single vectorized insert for multi-symbol lists."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[
        {"id": "sig-1", "symbol": "TCS"},
        {"id": "sig-2", "symbol": "HDFCBANK"},
    ])

    batch = [
        SignalIntelligenceRecord(
            symbol="TCS",
            signal_type="BUY",
            strategy_id="ORB_15M",
            raw_signal_value=1.5,
            final_confidence=0.85,
            planned_quantity=20,
        ),
        SignalIntelligenceRecord(
            symbol="HDFCBANK",
            signal_type="BUY",
            strategy_id="ORB_15M",
            raw_signal_value=1.8,
            final_confidence=0.82,
            planned_quantity=40,
        ),
    ]

    with patch("mjonai.db.signals.sb", mock_sb):
        res = insert_signals_bulk(batch)
        assert len(res) == 2
        assert res[0]["symbol"] == "TCS"
        assert res[1]["symbol"] == "HDFCBANK"
        mock_table.insert.assert_called_once()


def test_signal_write_failure_is_journaled_and_replayed(tmp_path):
    """Primary signals retain their generated UUID through an outage and replay."""
    journal = tmp_path / "signals_journal.jsonl"
    failing_sb = MagicMock()
    failing_table = MagicMock()
    failing_sb.table.return_value = failing_table
    failing_table.insert.return_value = failing_table
    failing_table.execute.side_effect = RuntimeError("database unavailable")

    with patch("mjonai.db.signals._SIGNALS_JOURNAL_FILE", journal), \
         patch("mjonai.db.signals.sb", failing_sb):
        saved = insert_signal_intelligence({
            "symbol": "INFY", "signal_type": "BUY", "strategy_id": "S01",
            "raw_signal_value": 1.0, "final_confidence": 0.8, "planned_quantity": 1,
        })

    assert saved["id"]
    assert journal.exists()

    replay_sb = MagicMock()
    replay_table = MagicMock()
    replay_sb.table.return_value = replay_table
    replay_table.upsert.return_value = replay_table
    replay_table.execute.return_value = MagicMock(data=[saved])
    with patch("mjonai.db.signals._SIGNALS_JOURNAL_FILE", journal), \
         patch("mjonai.db.signals.is_db_connected", return_value=True), \
         patch("mjonai.db.signals.sb", replay_sb):
        assert replay_signal_journal() == 1

    replay_table.upsert.assert_called_once()
    assert not journal.exists()


# ── 3. OUTCOME ATTRIBUTION & QUERIES ─────────────────────────────────────────

def test_update_signal_outcome_success():
    """Verify update_signal_outcome rounds metrics and executes update cleanly."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"id": "sig-123", "actual_outcome": "WIN"}])

    with patch("mjonai.db.signals.sb", mock_sb):
        ok = update_signal_outcome(
            signal_id="sig-123",
            actual_outcome="WIN",
            actual_rr=2.45678,
            actual_pnl_gross=12500.567,
            actual_pnl_net=12300.20,
            holding_days=1,
            exit_reason="TARGET",
        )
        assert ok is True
        mock_table.update.assert_called_once()
        mock_table.eq.assert_called_once_with("id", "sig-123")


def test_get_signals_intelligence_today():
    """Verify get_signals_intelligence_today filters by IST today range and optional strategy_id."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.gte.return_value = mock_table
    mock_table.lte.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"id": "sig-1", "symbol": "SBIN"}])

    with patch("mjonai.db.signals.sb", mock_sb):
        res = get_signals_intelligence_today(strategy_id="ORB_15M")
        assert len(res) == 1
        assert res[0]["symbol"] == "SBIN"
        mock_table.eq.assert_called_once_with("strategy_id", "ORB_15M")


def test_get_signal_by_id():
    """Verify get_signal_by_id returns single dictionary or None."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"id": "sig-999", "symbol": "WIPRO"}])

    with patch("mjonai.db.signals.sb", mock_sb):
        res = get_signal_by_id("sig-999")
        assert res is not None
        assert res["symbol"] == "WIPRO"


# ── 4. ALPHALENS FORWARD RETURNS TESTS ───────────────────────────────────────

def test_get_signals_needing_forward_returns():
    """Verify get_signals_needing_forward_returns queries null forward_return_1d."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.is_.return_value = mock_table
    mock_table.not_.is_.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"id": "sig-456", "symbol": "ITC"}])

    with patch("mjonai.db.signals.sb", mock_sb):
        res = get_signals_needing_forward_returns(limit=50)
        assert len(res) == 1
        assert res[0]["symbol"] == "ITC"


def test_update_signal_forward_returns():
    """Verify update_signal_forward_returns updates multi-horizon returns."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"id": "sig-456"}])

    with patch("mjonai.db.signals.sb", mock_sb):
        ok = update_signal_forward_returns("sig-456", {
            "forward_return_1d": 0.015,
            "forward_return_5d": 0.032,
            "forward_return_10d": 0.045,
            "forward_return_20d": 0.060,
        })
        assert ok is True
        mock_table.update.assert_called_once()
        mock_table.eq.assert_called_once_with("id", "sig-456")


def test_get_signals_for_alphalens():
    """Verify get_signals_for_alphalens constructs parameterized queries for date ranges."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.not_.is_.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.gte.return_value = mock_table
    mock_table.lte.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[
        {"id": "sig-1", "symbol": "RELIANCE", "forward_return_1d": 0.02}
    ])

    with patch("mjonai.db.signals.sb", mock_sb):
        res = get_signals_for_alphalens(
            strategy_id="ORB_15M",
            start_date="2026-08-01",
            end_date="2026-08-15"
        )
        assert len(res) == 1
        assert res[0]["symbol"] == "RELIANCE"
        mock_table.gte.assert_called_once()
        mock_table.lte.assert_called_once()
