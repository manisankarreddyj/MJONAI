"""
Unit and Institutional Test Suite for Pre-Flight Startup Health Sentry
(orchestration/startup.py)
"""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from apps.runtime.orchestration.startup import (
    startup_health_check,
    _is_pid_running,
    _acquire_process_lock,
    StartupHealthReport,
)


def test_is_pid_running():
    """Verify cross-platform PID running sentry."""
    current_pid = os.getpid()
    assert _is_pid_running(current_pid) is True
    assert _is_pid_running(0) is False
    assert _is_pid_running(-1) is False


def test_acquire_process_lock_and_stale_cleanup(tmp_path):
    """Verify single-instance lock file writing and stale PID cleanup."""
    temp_lock = str(tmp_path / "mjonai_test.lock")

    with patch("apps.runtime.orchestration.startup.LOCK_FILE", temp_lock):
        # 1. First acquisition succeeds
        ok, err = _acquire_process_lock()
        assert ok is True
        assert err is None
        assert os.path.exists(temp_lock)

        with open(temp_lock, "r", encoding="utf-8") as f:
            saved_pid = int(f.read().strip())
        assert saved_pid == os.getpid()

        # 2. Writing inactive/stale PID cleans up and acquires
        with open(temp_lock, "w", encoding="utf-8") as f:
            f.write("999999")  # Non-existent PID

        with patch("apps.runtime.orchestration.startup._is_pid_running", return_value=False):
            ok2, err2 = _acquire_process_lock()
            assert ok2 is True
            assert err2 is None


def test_acquire_process_lock_blocks_duplicate(tmp_path):
    """Verify lock acquisition blocks if another active PID holds the lock."""
    temp_lock = str(tmp_path / "mjonai_test.lock")

    with open(temp_lock, "w", encoding="utf-8") as f:
        f.write("12345")

    with patch("apps.runtime.orchestration.startup.LOCK_FILE", temp_lock), \
         patch("apps.runtime.orchestration.startup._is_pid_running", return_value=True):
        ok, err = _acquire_process_lock()
        assert ok is False
        assert "already running" in str(err)


def test_startup_health_check_research_mode(tmp_path):
    """Verify pre-flight health check succeeds in RESEARCH mode."""
    temp_lock = str(tmp_path / "mjonai_test.lock")
    mock_risk = {"peak_equity": 1000000.0, "risk_stop_restored": False, "kill_line_restored": False}

    with patch("apps.runtime.orchestration.startup.LOCK_FILE", temp_lock), \
         patch("apps.runtime.orchestration.startup.SYSTEM_MODE", "RESEARCH"), \
         patch("mjonai.db.repository.insert_system_log"), \
         patch("mjonai.risk.emergency_triggers.restore_risk_state", return_value=mock_risk), \
         patch("mjonai.data.angelone.token_map.sync_instrument_master", return_value=True), \
         patch("requests.get"):

        report: StartupHealthReport = startup_health_check()
        assert report.is_ready is True
        assert report.system_mode == "RESEARCH"
        assert report.peak_equity_restored == 1000000.0
        assert "Process Mutex Lock Acquired" in report.checks_passed
        assert "Database Connected" in str(report.checks_passed)


def test_startup_health_check_live_mode_missing_keys(tmp_path):
    """Verify pre-flight health check flags fatal errors if required keys missing in LIVE mode."""
    temp_lock = str(tmp_path / "mjonai_test.lock")

    with patch("apps.runtime.orchestration.startup.LOCK_FILE", temp_lock), \
         patch("apps.runtime.orchestration.startup.SYSTEM_MODE", "LIVE"), \
         patch("os.getenv", return_value=None), \
         patch("mjonai.db.repository.insert_system_log"), \
         patch("mjonai.risk.emergency_triggers.restore_risk_state", return_value={}), \
         patch("requests.get"):

        report: StartupHealthReport = startup_health_check()
        assert report.is_ready is False
        assert len(report.errors) > 0
        assert any("Missing required live credentials" in e for e in report.errors)
