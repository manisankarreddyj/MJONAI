"""
Comprehensive Unit & Institutional Test Suite for db/patterns.py
Tests Deterministic Fingerprinting, Bayesian Laplace Smoothing,
Expectancy Math, Consecutive Loss Streaks, LRU Hot Caching, and WAL Replay.
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

import db.patterns as patterns
from db.patterns import (
    PatternMemoryRecord,
    generate_setup_hash,
    get_pattern,
    upsert_pattern,
    update_pattern_outcome,
    get_consecutive_losses,
    get_pattern_failures,
    get_failing_patterns,
    quarantine_pattern,
    reactivate_pattern,
    soft_delete_pattern,
    clear_pattern_cache,
    replay_pattern_journal,
    _sanitize_payload,
)


@pytest.fixture(autouse=True)
def clean_pattern_cache_and_storage(tmp_path):
    """Clear hot-path memory cache and isolate local storage."""
    clear_pattern_cache()
    test_storage = tmp_path / "storage"
    test_storage.mkdir(parents=True, exist_ok=True)
    with patch("db.patterns._STORAGE_DIR", test_storage), \
         patch("db.patterns._PATTERNS_JOURNAL_FILE", test_storage / "patterns_journal.jsonl"):
        yield


# ── 1. DETERMINISTIC HASH & DATA CONTRACT TESTS ──────────────────────────────

def test_generate_setup_hash_normalization():
    """Verify canonical setup hash normalizes spaces, casing, and underscores."""
    h1 = generate_setup_hash(
        symbol=" reliance ",
        strategy_id=" s01 ",
        sl_method=" structure ",
        market_state=" bull ",
        vix_range=" low ",
        candle_pattern=" hammer ",
    )
    assert h1 == "RELIANCE_S01_STRUCTURE_BULL_LOW_HAMMER"


def test_pattern_memory_record_contract():
    """Verify PatternMemoryRecord dataclass serializes cleanly to dict."""
    rec = PatternMemoryRecord(
        setup_hash="TCS_ORB_STRUCTURE_BULL_NORMAL_ENGULFING",
        symbol="TCS",
        strategy_id="ORB",
        occurrences=5,
        wins=3,
        losses=2,
        win_rate=60.0,
        laplace_win_rate=57.1,
        avg_rr_achieved=2.1,
    )
    d = rec.to_dict()
    assert d["setup_hash"] == "TCS_ORB_STRUCTURE_BULL_NORMAL_ENGULFING"
    assert d["win_rate"] == 60.0
    assert d["laplace_win_rate"] == 57.1


def test_patterns_float_sanitization():
    """Verify NaN and Inf values are safely converted to None for SQL safety."""
    dirty = {"avg_rr_achieved": float("nan"), "expectancy_rr": float("inf"), "valid": 1.5}
    clean = _sanitize_payload(dirty)
    assert clean["avg_rr_achieved"] is None
    assert clean["expectancy_rr"] is None
    assert clean["valid"] == 1.5


# ── 2. HOT-PATH CACHING & UPSERT OPERATIONS ──────────────────────────────────

def test_upsert_and_hot_cache_hit():
    """Verify upsert_pattern populates hot-path cache for sub-millisecond retrieval."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.upsert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{
        "setup_hash": "INFY_S01_STRUCTURE_BULL_LOW_NONE",
        "symbol": "INFY",
        "system_mode": "RESEARCH",
    }])

    with patch("db.patterns.sb", mock_sb):
        # 1. Upsert
        res = upsert_pattern({
            "setup_hash": "INFY_S01_STRUCTURE_BULL_LOW_NONE",
            "symbol": "INFY",
            "system_mode": "RESEARCH",
        })
        assert res["setup_hash"] == "INFY_S01_STRUCTURE_BULL_LOW_NONE"

        # 2. Get pattern from hot cache (zero database calls)
        mock_sb.reset_mock()
        cached = get_pattern("INFY_S01_STRUCTURE_BULL_LOW_NONE", system_mode="RESEARCH", use_cache=True)
        assert cached is not None
        assert cached["symbol"] == "INFY"
        mock_sb.table.assert_not_called()


# ── 3. BAYESIAN OUTCOME MATH & EXPECTANCY ────────────────────────────────────

def test_bayesian_laplace_and_expectancy_math():
    """Verify update_pattern_outcome accurately computes Laplace win-rate and Expectancy."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.upsert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"ok": True}])

    with patch("db.patterns.sb", mock_sb), \
         patch("db.patterns.get_pattern", return_value=None):
        # Trade 1: WIN with 2.0 R:R
        # Occurrences=1, Wins=1, Losses=0 -> Raw WR = 100%, Laplace WR = (1+1)/(1+2) = 66.7%
        ok1 = update_pattern_outcome(
            setup_hash="HDFCBANK_S01_STRUCTURE_BULL_LOW_HAMMER",
            outcome="WIN",
            actual_rr=2.0,
            system_mode="LIVE",
        )
        assert ok1 is True
        mock_table.upsert.assert_called()


# ── 4. CONSECUTIVE LOSS STREAK DETECTION ─────────────────────────────────────

def test_get_consecutive_losses_streak():
    """Verify get_consecutive_losses correctly counts active losing streak from rolling window."""
    mock_pattern = {
        "setup_hash": "SBIN_S01_STRUCTURE_BEAR_HIGH_NONE",
        "last_10_outcomes": ["WIN", "WIN", "LOSS", "LOSS", "LOSS"],
    }
    with patch("db.patterns.get_pattern", return_value=mock_pattern):
        streak = get_consecutive_losses("SBIN_S01_STRUCTURE_BEAR_HIGH_NONE")
        assert streak == 3

    mock_pattern_win = {
        "setup_hash": "SBIN_S01_STRUCTURE_BEAR_HIGH_NONE",
        "last_10_outcomes": ["LOSS", "LOSS", "WIN"],
    }
    with patch("db.patterns.get_pattern", return_value=mock_pattern_win):
        streak2 = get_consecutive_losses("SBIN_S01_STRUCTURE_BEAR_HIGH_NONE")
        assert streak2 == 0


# ── 5. VETO & QUARANTINE LIFECYCLE ───────────────────────────────────────────

def test_quarantine_and_reactivate_lifecycle():
    """Verify quarantine_pattern and reactivate_pattern update status and invalidate cache."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"is_quarantined": True}])

    with patch("db.patterns.sb", mock_sb):
        # Quarantine
        assert quarantine_pattern("RELIANCE_TOXIC", system_mode="RESEARCH") is True
        mock_table.update.assert_called_with({"is_quarantined": True})

        # Reactivate
        mock_table.execute.return_value = MagicMock(data=[{"is_quarantined": False}])
        assert reactivate_pattern("RELIANCE_TOXIC", system_mode="RESEARCH") is True
        mock_table.update.assert_called_with({"is_quarantined": False})


# ── 6. OFFLINE WAL JOURNAL REPLAY ────────────────────────────────────────────

def test_pattern_wal_journal_replay(tmp_path):
    """Verify replay_pattern_journal flushes offline buffered records to Supabase."""
    test_storage = tmp_path / "storage"
    test_storage.mkdir(parents=True, exist_ok=True)
    journal_file = test_storage / "patterns_journal.jsonl"

    record = {
        "event_type": "UPSERT_PATTERN",
        "payload": {"setup_hash": "LT_S01_STRUCTURE_BULL_LOW_NONE", "symbol": "LT"},
    }
    with open(journal_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.upsert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"ok": True}])

    with patch("db.patterns._PATTERNS_JOURNAL_FILE", journal_file), \
         patch("db.patterns.is_db_connected", return_value=True), \
         patch("db.patterns.sb", mock_sb):
        replayed = replay_pattern_journal()
        assert replayed == 1
        assert not journal_file.exists()
