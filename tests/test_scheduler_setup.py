"""
Unit and Institutional Test Suite for Scheduler Lifecycle Setup
(orchestration/scheduler_setup.py)
"""

import pytest
from unittest.mock import patch, MagicMock

from apps.runtime.orchestration.scheduler_setup import (
    setup_scheduler,
    _safe_job,
    get_scheduled_jobs_summary,
    clear_all_jobs,
)


@pytest.fixture(autouse=True)
def clean_scheduler():
    """Ensure scheduler is clear before and after each test."""
    clear_all_jobs()
    yield
    clear_all_jobs()


def test_safe_job_wrapper_catches_exceptions():
    """Verify _safe_job catches exceptions without crashing the process."""
    def failing_job():
        raise ValueError("Simulated network/DB failure in scheduled job")

    wrapped = _safe_job(failing_job, "failing_test_job")
    result = wrapped()
    assert result is None  # Caught cleanly and returned None


def test_safe_job_wrapper_returns_value():
    """Verify _safe_job executes successfully and returns expected result."""
    def successful_job():
        return {"status": "SUCCESS", "records": 42}

    wrapped = _safe_job(successful_job, "successful_test_job")
    result = wrapped()
    assert result == {"status": "SUCCESS", "records": 42}


def test_setup_scheduler_registers_all_jobs():
    """Verify setup_scheduler registers the complete daily and intraday market lifecycle."""
    mock_callbacks = {
        "reset_daily_state": MagicMock(),
        "connect_angelone": MagicMock(),
        "morning_routine": MagicMock(),
        "eod_routine": MagicMock(),
        "calculate_forward_returns": MagicMock(),
        "generate_daily_report": MagicMock(),
        "generate_weekly_report": MagicMock(),
        "monitor_trades": MagicMock(),
        "scan_and_execute": MagicMock(),
        "is_trading_day": MagicMock(return_value=True),
    }

    count = setup_scheduler(**mock_callbacks)
    assert count >= 8

    summary = get_scheduled_jobs_summary()
    assert len(summary) == count
    assert any("reset_daily_state" in str(j) for j in summary)


def test_clear_all_jobs():
    """Verify clear_all_jobs resets scheduler state cleanly."""
    mock_callbacks = {k: MagicMock() for k in [
        "reset_daily_state", "connect_angelone", "morning_routine",
        "eod_routine", "calculate_forward_returns", "generate_daily_report",
        "generate_weekly_report", "monitor_trades", "scan_and_execute",
    ]}
    mock_callbacks["is_trading_day"] = MagicMock(return_value=True)

    setup_scheduler(**mock_callbacks)
    assert len(get_scheduled_jobs_summary()) > 0

    clear_all_jobs()
    assert len(get_scheduled_jobs_summary()) == 0
