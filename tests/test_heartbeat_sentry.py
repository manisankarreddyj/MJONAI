"""
Unit test suite for orchestration/heartbeat_sentry.py
Validates periodic heartbeat serialization, atomic file writing, and dead-man's switch liveness.
"""

from datetime import datetime, timedelta
import json
from pathlib import Path
import pytest

from apps.runtime.orchestration.heartbeat_sentry import (
    emit_heartbeat,
    check_heartbeat_liveness,
    HeartbeatPayload,
    HeartbeatLivenessReport,
)


def test_emit_heartbeat_atomic_write(tmp_path: Path):
    """Verify emit_heartbeat generates structured JSON and writes atomically."""
    hb_file = tmp_path / "heartbeat_test.json"
    payload = emit_heartbeat(
        heartbeat_path=hb_file,
        websocket_healthy=True,
        open_positions_count=3,
        cpu_pct=12.5,
        ram_pct=45.0,
        disk_pct=22.0,
    )

    assert isinstance(payload, HeartbeatPayload)
    assert payload.websocket_healthy is True
    assert payload.open_positions_count == 3
    assert payload.cpu_pct == 12.5
    assert hb_file.exists()

    # Read back and verify JSON integrity
    with open(hb_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["open_positions_count"] == 3
    assert data["pid"] == payload.pid


def test_check_heartbeat_liveness_healthy_and_stale(tmp_path: Path):
    """Verify dead-man switch distinguishes healthy, warning, and critical stall states."""
    hb_file = tmp_path / "heartbeat_liveness.json"
    now = datetime(2026, 9, 3, 10, 0, 0)

    # 1. Fresh heartbeat (10 seconds ago) -> HEALTHY_ACTIVE
    fresh_time = now - timedelta(seconds=10)
    with open(hb_file, "w", encoding="utf-8") as f:
        json.dump({"pid": 1234, "timestamp_ist": fresh_time.isoformat(), "session_state": "REGULAR_MARKET"}, f)

    rep_fresh = check_heartbeat_liveness(hb_file, max_stale_seconds=90.0, now=now)
    assert rep_fresh.is_alive is True
    assert rep_fresh.verdict == "HEALTHY_ACTIVE"
    assert rep_fresh.age_seconds == 10.0

    # 2. Warning heartbeat (60 seconds ago > 45s threshold) -> STALE_WARNING
    warn_time = now - timedelta(seconds=60)
    with open(hb_file, "w", encoding="utf-8") as f:
        json.dump({"pid": 1234, "timestamp_ist": warn_time.isoformat(), "session_state": "REGULAR_MARKET"}, f)

    rep_warn = check_heartbeat_liveness(hb_file, max_stale_seconds=90.0, now=now)
    assert rep_warn.is_alive is True
    assert rep_warn.verdict == "STALE_WARNING"

    # 3. Stalled heartbeat (120 seconds ago > 90s threshold) -> PROCESS_STALLED_CRITICAL
    stalled_time = now - timedelta(seconds=120)
    with open(hb_file, "w", encoding="utf-8") as f:
        json.dump({"pid": 1234, "timestamp_ist": stalled_time.isoformat(), "session_state": "REGULAR_MARKET"}, f)

    rep_stalled = check_heartbeat_liveness(hb_file, max_stale_seconds=90.0, now=now)
    assert rep_stalled.is_alive is False
    assert rep_stalled.verdict == "PROCESS_STALLED_CRITICAL"


def test_check_heartbeat_liveness_missing_and_corrupted(tmp_path: Path):
    """Verify dead-man switch handles missing and corrupted files gracefully."""
    missing_file = tmp_path / "nonexistent.json"
    rep_miss = check_heartbeat_liveness(missing_file)
    assert rep_miss.is_alive is False
    assert rep_miss.verdict == "NO_HEARTBEAT_FOUND"

    corrupt_file = tmp_path / "corrupt.json"
    with open(corrupt_file, "w", encoding="utf-8") as f:
        f.write("{invalid_json: true, broken")
    rep_corrupt = check_heartbeat_liveness(corrupt_file)
    assert rep_corrupt.is_alive is False
    assert rep_corrupt.verdict == "CORRUPTED_HEARTBEAT"
