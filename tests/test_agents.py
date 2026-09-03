"""
Comprehensive Unit & Institutional Test Suite for db/agents.py
Tests Multi-LLM Committee Telemetry, Vectorized Ingestion,
Directional Role Attribution, Laplace Accuracy, and WAL Replay.
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

import mjonai.db.agents as agents
from mjonai.db.agents import (
    AgentLogRecord,
    insert_agent_log,
    insert_agent_logs_bulk,
    update_agent_log_outcome,
    get_agent_accuracy,
    get_all_agents_accuracy_summary,
    get_agent_telemetry_summary,
    evaluate_verdict_accuracy,
    replay_agent_journal,
    _sanitize_payload,
)


@pytest.fixture(autouse=True)
def clean_agent_storage(tmp_path):
    """Isolate local storage for agent WAL tests."""
    test_storage = tmp_path / "storage"
    test_storage.mkdir(parents=True, exist_ok=True)
    with patch("mjonai.db.agents._STORAGE_DIR", test_storage), \
         patch("mjonai.db.agents._AGENT_JOURNAL_FILE", test_storage / "agent_logs_journal.jsonl"):
        yield


# ── 1. CONTRACT & SANITIZATION TESTS ─────────────────────────────────────────

def test_agent_log_record_contract():
    """Verify AgentLogRecord dataclass creates clean dictionaries omitting None."""
    rec = AgentLogRecord(
        agent_name="BULL",
        signal_id="sig-101",
        raw_verdict="BUY",
        confidence_given=0.88,
        key_reasons=["EMA20 crossover", "High RVOL"],
        concerns=["Overhead resistance at 2550"],
        latency_ms=340.5,
        prompt_tokens=450,
        completion_tokens=120,
    )
    d = rec.to_dict()
    assert d["agent_name"] == "BULL"
    assert d["confidence_given"] == 0.88
    assert d["latency_ms"] == 340.5
    assert "was_correct" not in d


def test_agent_float_sanitization():
    """Verify NaN and Inf values are safely converted to None."""
    dirty = {"latency_ms": float("nan"), "actual_rr": float("inf"), "valid": 0.85}
    clean = _sanitize_payload(dirty)
    assert clean["latency_ms"] is None
    assert clean["actual_rr"] is None
    assert clean["valid"] == 0.85


# ── 2. INSERTION & BATCH OPERATIONS ──────────────────────────────────────────

def test_insert_agent_log_success():
    """Verify insert_agent_log executes insert with timestamp population."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"id": "log-1", "agent_name": "SUPERVISOR"}])

    with patch("mjonai.db.agents.sb", mock_sb):
        res = insert_agent_log({
            "agent_name": "SUPERVISOR",
            "signal_id": "sig-101",
            "raw_verdict": "APPROVE",
            "confidence_given": 0.92,
        })
        assert res["id"] == "log-1"
        mock_table.insert.assert_called_once()


def test_insert_agent_logs_bulk_success():
    """Verify insert_agent_logs_bulk performs single vectorized insert for full debate."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[
        {"id": "log-1", "agent_name": "BULL"},
        {"id": "log-2", "agent_name": "BEAR"},
        {"id": "log-3", "agent_name": "SUPERVISOR"},
    ])

    batch = [
        AgentLogRecord(agent_name="BULL", signal_id="sig-101", raw_verdict="BUY", confidence_given=0.85),
        AgentLogRecord(agent_name="BEAR", signal_id="sig-101", raw_verdict="HIGH_RISK", confidence_given=0.60),
        AgentLogRecord(agent_name="SUPERVISOR", signal_id="sig-101", raw_verdict="APPROVE", confidence_given=0.88),
    ]

    with patch("mjonai.db.agents.sb", mock_sb):
        res = insert_agent_logs_bulk(batch)
        assert len(res) == 3
        mock_table.insert.assert_called_once()


# ── 3. MULTI-ROLE DIRECTIONAL EVALUATION ─────────────────────────────────────

def test_evaluate_verdict_accuracy():
    """Verify directional role accuracy for Bull, Bear, and Supervisor agents."""
    # Bull BUY on WIN -> Correct
    assert evaluate_verdict_accuracy("BULL", "BUY", "WIN") is True
    # Bull BUY on LOSS -> Wrong
    assert evaluate_verdict_accuracy("BULL", "BUY", "LOSS") is False

    # Bear WARN / HIGH_RISK on LOSS -> Correct
    assert evaluate_verdict_accuracy("BEAR", "HIGH_RISK", "LOSS") is True
    # Bear WARN on WIN -> Wrong
    assert evaluate_verdict_accuracy("BEAR", "HIGH_RISK", "WIN") is False

    # Supervisor APPROVE on WIN -> Correct
    assert evaluate_verdict_accuracy("SUPERVISOR", "APPROVE", "WIN") is True
    # Supervisor REJECT on LOSS -> Correct
    assert evaluate_verdict_accuracy("SUPERVISOR", "REJECT", "LOSS") is True

    # Breakeven trade -> Inconclusive (None)
    assert evaluate_verdict_accuracy("BULL", "BUY", "BREAKEVEN") is None


def test_update_agent_log_outcome_success():
    """Verify update_agent_log_outcome fetches rows and updates was_correct."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.update.return_value = mock_table

    mock_table.execute.side_effect = [
        MagicMock(data=[
            {"id": "log-1", "agent_name": "BULL", "raw_verdict": "BUY"},
            {"id": "log-2", "agent_name": "BEAR", "raw_verdict": "HIGH_RISK"},
        ]),
        MagicMock(data=[{"ok": True}]),
        MagicMock(data=[{"ok": True}]),
    ]

    with patch("mjonai.db.agents.sb", mock_sb):
        ok = update_agent_log_outcome("sig-101", actual_outcome="WIN", actual_rr=2.5)
        assert ok is True
        assert mock_table.update.call_count == 2


# ── 4. STATISTICAL ACCURACY & TELEMETRY ──────────────────────────────────────

def test_get_agent_accuracy_standard_and_laplace():
    """Verify get_agent_accuracy computes both raw win-rate and Bayesian Laplace smoothed accuracy."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.gte.return_value = mock_table
    mock_table.not_.is_.return_value = mock_table

    # 8 correct out of 10 calls -> Raw = 80.0%, Laplace = (8+1)/(10+2) = 75.0%
    mock_table.execute.return_value = MagicMock(data=[
        {"was_correct": True}, {"was_correct": True}, {"was_correct": True},
        {"was_correct": True}, {"was_correct": True}, {"was_correct": True},
        {"was_correct": True}, {"was_correct": True}, {"was_correct": False},
        {"was_correct": False},
    ])

    with patch("mjonai.db.agents.sb", mock_sb):
        res = get_agent_accuracy("SUPERVISOR", system_mode="LIVE")
        assert res["total_calls"] == 10
        assert res["correct_calls"] == 8
        assert res["accuracy_pct"] == 80.0
        assert res["laplace_accuracy_pct"] == 75.0


def test_get_agent_telemetry_summary():
    """Verify get_agent_telemetry_summary aggregates token consumption and cost."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.gte.return_value = mock_table

    mock_table.execute.return_value = MagicMock(data=[
        {"latency_ms": 300, "prompt_tokens": 500, "completion_tokens": 100},
        {"latency_ms": 400, "prompt_tokens": 600, "completion_tokens": 150},
    ])

    with patch("mjonai.db.agents.sb", mock_sb):
        summary = get_agent_telemetry_summary(system_mode="LIVE")
        assert summary["total_calls"] == 2
        assert summary["total_prompt_tokens"] == 1100
        assert summary["total_completion_tokens"] == 250
        assert summary["avg_latency_ms"] == 350.0


def test_get_all_agents_accuracy_summary_dynamic():
    """Verify get_all_agents_accuracy_summary discovers novel agents dynamically."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.gte.return_value = mock_table
    mock_table.not_.is_.return_value = mock_table

    mock_table.execute.return_value = MagicMock(data=[
        {"agent_name": "BULL", "was_correct": True},
        {"agent_name": "SENTIMENT_AGENT", "was_correct": True},
        {"agent_name": "ORDER_FLOW_AGENT", "was_correct": False},
    ])

    with patch("mjonai.db.agents.sb", mock_sb):
        scoreboard = get_all_agents_accuracy_summary(system_mode="LIVE")
        names = {item["agent_name"] for item in scoreboard}
        assert "BULL" in names
        assert "SENTIMENT_AGENT" in names
        assert "ORDER_FLOW_AGENT" in names


# ── 5. OFFLINE WAL JOURNAL REPLAY ────────────────────────────────────────────

def test_agent_wal_journal_replay(tmp_path):
    """Verify replay_agent_journal drains buffered offline records to Supabase."""
    test_storage = tmp_path / "storage"
    test_storage.mkdir(parents=True, exist_ok=True)
    journal_file = test_storage / "agent_logs_journal.jsonl"

    record = {
        "event_type": "INSERT_AGENT_LOG",
        "payload": {"agent_name": "BULL", "signal_id": "sig-101", "raw_verdict": "BUY"},
    }
    with open(journal_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"ok": True}])

    with patch("mjonai.db.agents._AGENT_JOURNAL_FILE", journal_file), \
         patch("mjonai.db.agents.is_db_connected", return_value=True), \
         patch("mjonai.db.agents.sb", mock_sb):
        replayed = replay_agent_journal()
        assert replayed == 1
        assert not journal_file.exists()
