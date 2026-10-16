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

root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import mjonai.db.patterns as patterns
from mjonai.db.patterns import (
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
    with patch("mjonai.db.patterns._STORAGE_DIR", test_storage), \
         patch("mjonai.db.patterns._PATTERNS_JOURNAL_FILE", test_storage / "patterns_journal.jsonl"):
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

    with patch("mjonai.db.patterns.sb", mock_sb):
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

    with patch("mjonai.db.patterns.sb", mock_sb), \
         patch("mjonai.db.patterns.get_pattern", return_value=None):
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


# ── 3b. IDENTITY-COLUMN INTEGRITY (2026-10-15 engine-log defect) ──────────────

def test_update_pattern_outcome_first_sighting_carries_symbol_and_strategy():
    """
    A trade can close before any scan-time upsert_pattern recorded the row, so the
    INSERT leg of the update upsert must carry the NOT-NULL identity columns.
    Verified against the 2026-10-15 engine log: every first-sighting pattern write
    failed with 'null value in column "symbol"' (23502) and buffered to WAL.
    """
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.upsert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"ok": True}])

    with patch("mjonai.db.patterns.sb", mock_sb), \
         patch("mjonai.db.patterns.get_pattern", return_value=None):
        assert update_pattern_outcome(
            setup_hash="ULTRACEMCO_S18_GAPFILLFVG_STRUCTURE_SHORT_NEUTRAL_MEDIUM_NONE_V1",
            outcome="WIN",
            actual_rr=1.4975,
            system_mode="RESEARCH",
        ) is True

    payload = mock_table.upsert.call_args[0][0]
    assert payload["symbol"] == "ULTRACEMCO"
    assert payload["strategy_id"] == "S18"
    assert payload["first_seen"]
    # Stat math is unaffected by the identity propagation.
    assert payload["occurrences"] == 1
    assert payload["wins"] == 1
    assert payload["laplace_win_rate"] == 66.7


def test_update_pattern_outcome_existing_row_keeps_db_identity():
    """An already-recorded row keeps its DB symbol/strategy_id/first_seen on update."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.upsert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"ok": True}])

    existing_row = {
        "setup_hash": "MARUTI_S06_MOMENTUMSHORT_STRUCTURE_SHORT_NEUTRAL_MEDIUM_SHOOTING_STAR_V1",
        "symbol": "MARUTI",
        "strategy_id": "S06",
        "first_seen": "2026-10-01",
        "occurrences": 3,
        "wins": 2,
        "losses": 1,
        "avg_rr_achieved": 1.2,
    }

    with patch("mjonai.db.patterns.sb", mock_sb), \
         patch("mjonai.db.patterns.get_pattern", return_value=existing_row):
        assert update_pattern_outcome(
            setup_hash="MARUTI_S06_MOMENTUMSHORT_STRUCTURE_SHORT_NEUTRAL_MEDIUM_SHOOTING_STAR_V1",
            outcome="LOSS",
            actual_rr=-1.0,
            system_mode="RESEARCH",
        ) is True

    payload = mock_table.upsert.call_args[0][0]
    assert payload["symbol"] == "MARUTI"
    assert payload["strategy_id"] == "S06"
    assert payload["first_seen"] == "2026-10-01"
    assert payload["occurrences"] == 4
    assert payload["losses"] == 2


def test_update_pattern_outcome_hash_without_underscore_does_not_write_null_symbol():
    """A malformed hash (no underscore) still writes non-null identity columns."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.upsert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"ok": True}])

    with patch("mjonai.db.patterns.sb", mock_sb), \
         patch("mjonai.db.patterns.get_pattern", return_value=None):
        assert update_pattern_outcome(
            setup_hash="MALFORMEDHASH",
            outcome="WIN",
            actual_rr=1.0,
            system_mode="RESEARCH",
        ) is True

    payload = mock_table.upsert.call_args[0][0]
    assert payload["symbol"] == "UNKNOWN"
    assert payload["strategy_id"] == "UNKNOWN"


# ── 4. CONSECUTIVE LOSS STREAK DETECTION ─────────────────────────────────────

def test_get_consecutive_losses_streak():
    """Verify get_consecutive_losses correctly counts active losing streak from rolling window."""
    mock_pattern = {
        "setup_hash": "SBIN_S01_STRUCTURE_BEAR_HIGH_NONE",
        "last_10_outcomes": ["WIN", "WIN", "LOSS", "LOSS", "LOSS"],
    }
    with patch("mjonai.db.patterns.get_pattern", return_value=mock_pattern):
        streak = get_consecutive_losses("SBIN_S01_STRUCTURE_BEAR_HIGH_NONE")
        assert streak == 3

    mock_pattern_win = {
        "setup_hash": "SBIN_S01_STRUCTURE_BEAR_HIGH_NONE",
        "last_10_outcomes": ["LOSS", "LOSS", "WIN"],
    }
    with patch("mjonai.db.patterns.get_pattern", return_value=mock_pattern_win):
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

    with patch("mjonai.db.patterns.sb", mock_sb):
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

    with patch("mjonai.db.patterns._PATTERNS_JOURNAL_FILE", journal_file), \
         patch("mjonai.db.patterns.is_db_connected", return_value=True), \
         patch("mjonai.db.patterns.sb", mock_sb):
        replayed = replay_pattern_journal()
        assert replayed == 1
        assert not journal_file.exists()


def test_replay_outcome_rows_use_outcome_path_not_raw_patch(tmp_path):
    """WAL UPDATE_PATTERN_OUTCOME rows carry {setup_hash, outcome} — outcome
    is NOT a table column, so the old raw-PATCH replay 400d forever (14 rows
    stuck on 2026-10-16 boot). Replay must route through
    update_pattern_outcome, never PATCH an 'outcome' key."""
    test_storage = tmp_path / "storage"
    test_storage.mkdir(parents=True, exist_ok=True)
    journal_file = test_storage / "patterns_journal.jsonl"
    with open(journal_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "event_type": "UPDATE_PATTERN_OUTCOME",
            "payload": {"setup_hash": "X_S06_Y", "outcome": "WIN"},
        }) + "\n")

    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table

    with patch("mjonai.db.patterns._PATTERNS_JOURNAL_FILE", journal_file), \
         patch("mjonai.db.patterns.is_db_connected", return_value=True), \
         patch("mjonai.db.patterns.sb", mock_sb), \
         patch("mjonai.db.patterns.update_pattern_outcome", return_value=True) as mock_upd:
        assert replay_pattern_journal() == 1
        mock_upd.assert_called_once_with("X_S06_Y", "WIN", system_mode="RESEARCH")
        assert not journal_file.exists()
    # No raw PATCH carrying the non-column key was ever attempted.
    for call in mock_table.update.call_args_list:
        assert "outcome" not in (call[0][0] if call[0] else {})
