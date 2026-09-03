"""
Unit and Institutional Test Suite for Graceful Runtime Teardown Guard
(orchestration/runtime_guard.py)
"""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

import orchestration.runtime_guard as rg


@pytest.fixture(autouse=True)
def reset_guard_state():
    """Reset cleanup flag before and after each test."""
    rg._CLEANUP_CALLED = False
    yield
    rg._CLEANUP_CALLED = False


def test_cleanup_removes_lock_file(tmp_path):
    """Verify cleanup deletes process lock file if it exists."""
    temp_lock = str(tmp_path / "test_mjonai.lock")
    with open(temp_lock, "w", encoding="utf-8") as f:
        f.write("12345")

    with patch("orchestration.runtime_guard.LOCK_FILE", temp_lock):
        assert os.path.exists(temp_lock)
        rg.cleanup(signum=None, should_exit=False)
        assert not os.path.exists(temp_lock)


def test_cleanup_closes_websocket_and_clears_jobs(tmp_path):
    """Verify cleanup triggers WebSocket close, scheduler clear, and shutdown telemetry."""
    temp_lock = str(tmp_path / "test_mjonai.lock")

    with patch("orchestration.runtime_guard.LOCK_FILE", temp_lock), \
         patch("data.angelone.websocket.on_close") as mock_ws_close, \
         patch("orchestration.scheduler_setup.clear_all_jobs") as mock_clear_jobs, \
         patch("communication.events.publish_event") as mock_pub:

        rg.cleanup(signum=15, should_exit=False)

        mock_ws_close.assert_called_once()
        mock_clear_jobs.assert_called_once()
        mock_pub.assert_called_once()
        assert mock_pub.call_args[0][0] == "SYSTEM_SHUTDOWN"


def test_cleanup_idempotent():
    """Verify cleanup only executes once even if called multiple times."""
    with patch("orchestration.runtime_guard.LOCK_FILE", "dummy_path_no_exist"), \
         patch("data.angelone.websocket.on_close") as mock_ws_close:

        rg.cleanup(should_exit=False)
        rg.cleanup(should_exit=False)

        assert mock_ws_close.call_count == 1


def test_register_runtime_guard_execution():
    """Verify register_runtime_guard registers without throwing exceptions."""
    with patch("atexit.register") as mock_atexit:
        rg.register_runtime_guard()
        mock_atexit.assert_called_once()
