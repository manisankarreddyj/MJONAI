"""
Comprehensive Unit & Institutional Test Suite for db/system.py
Tests Scan Funnel Logging, Multi-Timeframe Filtering, Infrastructure Health Probes,
Strategy Performance Attribution, Agent Dynamic Weight Governance, and WAL Replay.
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

import db.system as system
from db.system import (
    ScanLogRecord,
    SystemHealthRecord,
    StrategyPerformanceRecord,
    AgentWeightRecord,
    insert_scan_log,
    get_scan_history,
    insert_health_log,
    get_health_summary,
    upsert_strategy_performance,
    get_strategy_performance,
    insert_weight_log,
    get_latest_weights,
    insert_risk_event,
    insert_system_log,
    replay_system_journal,
    _sanitize_payload,
)


@pytest.fixture(autouse=True)
def clean_system_storage(tmp_path):
    """Isolate local storage for system WAL tests."""
    test_storage = tmp_path / "storage"
    test_storage.mkdir(parents=True, exist_ok=True)
    with patch("db.system._STORAGE_DIR", test_storage), \
         patch("db.system._SYSTEM_JOURNAL_FILE", test_storage / "system_journal.jsonl"):
        yield


# ── 1. CONTRACT & FLOAT SANITIZATION TESTS ───────────────────────────────────

def test_system_contracts_and_serialization():
    """Verify dataclasses serialize cleanly to dictionaries omitting None values."""
    scan = ScanLogRecord(
        symbols_scanned=500,
        signals_generated=15,
        signals_approved=2,
        scan_duration_ms=450.2,
        timeframe="15m",
        asset_class="EQUITY",
    )
    scan_d = scan.to_dict()
    assert scan_d["symbols_scanned"] == 500
    assert scan_d["timeframe"] == "15m"

    strat = StrategyPerformanceRecord(
        strategy_id="ORB_15M",
        strategy_version="v2.1",
        period_start="2026-08-01",
        period_end="2026-08-15",
        win_rate=65.5,
        profit_factor=2.1,
    )
    strat_d = strat.to_dict()
    assert strat_d["strategy_id"] == "ORB_15M"
    assert strat_d["profit_factor"] == 2.1


def test_system_float_sanitization():
    """Verify NaN and Inf values are safely converted to None for SQL safety."""
    dirty = {"sharpe_ratio": float("nan"), "profit_factor": float("inf"), "valid": 1.45}
    clean = _sanitize_payload(dirty)
    assert clean["sharpe_ratio"] is None
    assert clean["profit_factor"] is None
    assert clean["valid"] == 1.45


# ── 2. SCAN FUNNEL & TIMEFRAME FILTERING ─────────────────────────────────────

def test_insert_and_get_scan_history_with_timeframe():
    """Verify insert_scan_log and get_scan_history with timeframe filtering."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.gte.return_value = mock_table
    mock_table.order.return_value = mock_table

    mock_table.execute.side_effect = [
        MagicMock(data=[{"id": "scan-1", "symbols_scanned": 500}]),
        MagicMock(data=[
            {"id": "scan-1", "timeframe": "15m", "symbols_scanned": 500},
            {"id": "scan-2", "timeframe": "1m", "symbols_scanned": 50},
        ]),
    ]

    with patch("db.system.sb", mock_sb):
        # 1. Insert
        res = insert_scan_log(ScanLogRecord(
            symbols_scanned=500,
            signals_generated=12,
            signals_approved=2,
            scan_duration_ms=620.0,
            timeframe="15m"
        ))
        assert res["symbols_scanned"] == 500

        # 2. Get history with timeframe filter
        scans_1m = get_scan_history(hours=24, timeframe="1m")
        assert len(scans_1m) == 1
        assert scans_1m[0]["timeframe"] == "1m"


# ── 3. INFRASTRUCTURE HEALTH PROBES & AGGREGATION ────────────────────────────

def test_get_health_summary_aggregation():
    """Verify get_health_summary calculates clean averages and failure counts."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.gte.return_value = mock_table

    mock_table.execute.return_value = MagicMock(data=[
        {"oracle_cpu_pct": 20.0, "oracle_ram_pct": 45.0, "oracle_disk_pct": 30.0, "websocket_healthy": True, "internet_ok": True, "groq_latency_ms": 300},
        {"oracle_cpu_pct": 40.0, "oracle_ram_pct": 55.0, "oracle_disk_pct": 30.0, "websocket_healthy": False, "internet_ok": True, "groq_latency_ms": 500},
    ])

    with patch("db.system.sb", mock_sb):
        summary = get_health_summary(hours=24)
        assert summary["total_readings"] == 2
        assert summary["avg_cpu_pct"] == 30.0
        assert summary["avg_ram_pct"] == 50.0
        assert summary["avg_groq_latency_ms"] == 400.0
        assert summary["websocket_failures"] == 1
        assert summary["internet_failures"] == 0


# ── 4. STRATEGY PERFORMANCE CURVES ───────────────────────────────────────────

def test_upsert_and_get_strategy_performance():
    """Verify upsert_strategy_performance and get_strategy_performance."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.upsert.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.order.return_value = mock_table

    mock_table.execute.side_effect = [
        MagicMock(data=[{"strategy_id": "ORB_15M", "win_rate": 70.0}]),
        MagicMock(data=[{"strategy_id": "ORB_15M", "win_rate": 70.0}]),
    ]

    with patch("db.system.sb", mock_sb):
        res = upsert_strategy_performance({
            "strategy_id": "ORB_15M",
            "strategy_version": "v1.0",
            "period_start": "2026-08-01",
            "period_end": "2026-08-15",
            "win_rate": 70.0,
        })
        assert res["strategy_id"] == "ORB_15M"

        perf = get_strategy_performance(strategy_id="ORB_15M", system_mode="LIVE")
        assert len(perf) == 1
        assert perf[0]["win_rate"] == 70.0


# ── 5. AGENT WEIGHT GOVERNANCE & ENVIRONMENT ISOLATION ───────────────────────

def test_get_latest_weights_environment_isolation():
    """Verify get_latest_weights isolates weights by system_mode and defaults missing agents to 1.0."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.limit.return_value = mock_table

    mock_table.execute.return_value = MagicMock(data=[
        {"agent_name": "BULL", "new_weight": 1.35},
        {"agent_name": "BEAR", "new_weight": 0.75},
    ])

    with patch("db.system.sb", mock_sb):
        weights = get_latest_weights(system_mode="LIVE")
        assert weights["BULL"] == 1.35
        assert weights["BEAR"] == 0.75
        assert weights["SUPERVISOR"] == 1.0  # Default un-calibrated
        mock_table.eq.assert_called_once_with("system_mode", "LIVE")


# ── 6. RISK AUDIT & OFFLINE WAL REPLAY ───────────────────────────────────────

def test_insert_risk_event_and_system_log():
    """Verify insert_risk_event and insert_system_log execute cleanly."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"ok": True}])

    with patch("db.system.sb", mock_sb):
        assert insert_risk_event("KILL_LINE_TRIGGERED", "Drawdown hit 15.1%", level="EMERGENCY") is True
        assert insert_system_log("BOT_STARTUP", "Engine initialized cleanly", level="INFO") is True


def test_system_wal_journal_replay(tmp_path):
    """Verify replay_system_journal drains buffered offline records to Supabase."""
    test_storage = tmp_path / "storage"
    test_storage.mkdir(parents=True, exist_ok=True)
    journal_file = test_storage / "system_journal.jsonl"

    record = {
        "event_type": "INSERT_RISK_EVENT",
        "payload": {"event_type": "MARGIN_CALL", "message": "Low margin warning"},
    }
    with open(journal_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"ok": True}])

    with patch("db.system._SYSTEM_JOURNAL_FILE", journal_file), \
         patch("db.system.is_db_connected", return_value=True), \
         patch("db.system.sb", mock_sb):
        replayed = replay_system_journal()
        assert replayed == 1
        assert not journal_file.exists()
