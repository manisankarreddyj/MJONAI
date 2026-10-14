"""Part 1 of the dev/ops automation wave: update the scheduler regression pins
for the new guarded weekly intraday validation job.

The callback is OPTIONAL (existing callers without it keep their exact job
count); when provided, a Sunday 10:30 job named `weekly_intraday_validation`
must appear in the registry alongside the weekly Alphalens job.
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
        "weekly_intraday_validation": MagicMock(),
    }

    count = setup_scheduler(**mock_callbacks)
    assert count >= 8

    summary = get_scheduled_jobs_summary()
    assert len(summary) == count
    assert any("reset_daily_state" in str(j) for j in summary)
    assert any("weekly_intraday_validation" in str(j) for j in summary)


def test_setup_scheduler_without_validation_callback_keeps_prior_shape():
    """The weekly validation job is OPTIONAL: callers without the callback
    register exactly the pre-Phase-1 jobs (backward compatibility pin)."""
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

    setup_scheduler(**mock_callbacks)
    summary = get_scheduled_jobs_summary()
    assert not any("weekly_intraday_validation" in str(j) for j in summary)


def test_setup_scheduler_registers_price_alerts_check_when_provided():
    """The 5-minute price-alert slot is OPTIONAL like the validation job:
    present with the callback, absent without — existing callers keep shape."""
    base = {
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

    setup_scheduler(**base, price_alerts_check=MagicMock())
    assert any("price_alerts_check" in str(j) for j in get_scheduled_jobs_summary())

    clear_all_jobs()
    setup_scheduler(**base)
    assert not any("price_alerts_check" in str(j) for j in get_scheduled_jobs_summary())


def test_setup_scheduler_registers_delivery_refresh_when_provided():
    """The 18:30 CM-delivery slot is OPTIONAL like the alerts slot:
    present with the callback, absent without."""
    base = {
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

    setup_scheduler(**base, delivery_refresh=MagicMock())
    assert any("delivery_refresh" in str(j) for j in get_scheduled_jobs_summary())

    clear_all_jobs()
    setup_scheduler(**base)
    assert not any("delivery_refresh" in str(j) for j in get_scheduled_jobs_summary())


def test_setup_scheduler_registers_insider_refresh_when_provided():
    """Same optional-slot contract for the 18:35 insider-deals refresh."""
    base = {
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

    setup_scheduler(**base, insider_refresh=MagicMock())
    assert any("insider_refresh" in str(j) for j in get_scheduled_jobs_summary())

    clear_all_jobs()
    setup_scheduler(**base)
    assert not any("insider_refresh" in str(j) for j in get_scheduled_jobs_summary())


def test_setup_scheduler_registers_news_refresh_when_provided():
    """Same optional-slot contract for the 08:35 news-headline refresh."""
    base = {
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

    setup_scheduler(**base, news_refresh=MagicMock())
    assert any("news_refresh" in str(j) for j in get_scheduled_jobs_summary())

    clear_all_jobs()
    setup_scheduler(**base)
    assert not any("news_refresh" in str(j) for j in get_scheduled_jobs_summary())


def test_clear_all_jobs():
    """Verify clear_all_jobs resets scheduler state cleanly."""
    mock_callbacks = {k: MagicMock() for k in [
        "reset_daily_state", "connect_angelone", "morning_routine",
        "eod_routine", "calculate_forward_returns", "generate_daily_report",
        "generate_weekly_report", "monitor_trades", "scan_and_execute",
        "weekly_intraday_validation",
    ]}
    mock_callbacks["is_trading_day"] = MagicMock(return_value=True)

    setup_scheduler(**mock_callbacks)
    assert len(get_scheduled_jobs_summary()) > 0

    clear_all_jobs()
    assert len(get_scheduled_jobs_summary()) == 0