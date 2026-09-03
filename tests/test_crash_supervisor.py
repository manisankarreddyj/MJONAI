"""
Test Suite: tests/test_crash_supervisor.py
Purpose: Unit tests for CrashSupervisor, Exponential Backoff with Jitter, and Crash Budgeting.
"""

import pytest
from datetime import datetime, timedelta

from apps.runtime.orchestration.crash_supervisor import CrashSupervisor


def test_exponential_backoff_delay_bounds():
    """Verify exponential backoff grows with crash count and respects min/max bounds."""
    sup = CrashSupervisor(base_delay_seconds=2.0, max_delay_seconds=30.0)

    # 0 crashes -> ~2s +- jitter
    sup.consecutive_crashes = 0
    d0 = sup.compute_backoff_delay()
    assert 1.5 <= d0 <= 2.5

    # 3 crashes -> ~16s +- jitter
    sup.consecutive_crashes = 3
    d3 = sup.compute_backoff_delay()
    assert 12.0 <= d3 <= 20.0

    # 10 crashes -> clamped to max 30s +- jitter
    sup.consecutive_crashes = 10
    d10 = sup.compute_backoff_delay()
    assert 24.0 <= d10 <= 36.0


def test_crash_budget_per_hour_limit():
    """Verify restart budget halts when max restarts within the hour are exceeded."""
    from unittest.mock import patch

    sup = CrashSupervisor(base_delay_seconds=1.0, max_restarts_per_hour=3)

    assert sup.can_restart() is True

    # Record 3 crashes with mocked alert dispatch
    with patch("apps.runtime.orchestration.crash_supervisor.send_message"), patch("apps.runtime.orchestration.crash_supervisor.publish_event"):
        for i in range(3):
            res = sup.record_crash(ValueError(f"Crash #{i+1}"), subsystem_name="TEST")
            if i < 2:
                assert res["can_restart"] is True
            else:
                assert res["can_restart"] is False

    assert sup.can_restart() is False

    # Reset counter
    sup.reset_crash_counter()
    assert sup.consecutive_crashes == 0
