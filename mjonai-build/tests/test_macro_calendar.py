"""
Unit and Institutional Test Suite for Macroeconomic Event Sentry & Policy Risk Engine
(intelligence/macro_calendar.py)
"""

from datetime import date
import pytest

from intelligence.macro_calendar import (
    evaluate_macro_event_risk,
    MacroEventRiskResult,
)


def test_evaluate_macro_event_risk_none():
    """Verify normal trading mode when no events are scheduled."""
    res = evaluate_macro_event_risk(check_date="2026-08-18", custom_events=[])
    assert res["has_event_today"] is False
    assert res["impact_level"] == "NONE"
    assert res["risk_action"] == "NORMAL_TRADING"


def test_evaluate_macro_event_risk_rbi_mpc():
    """Verify RBI MPC policy day triggers defense actions."""
    events = [
        {"date": "2026-08-18", "event": "RBI_MPC_RATE_DECISION", "time": "10:00", "title": "RBI Monetary Policy Committee Rate Decision"}
    ]
    res = evaluate_macro_event_risk(check_date="2026-08-18", custom_events=events)
    assert res["has_event_today"] is True
    assert res["impact_level"] == "CRITICAL"
    assert res["risk_action"] == "REDUCE_50_PCT"
    assert "RBI" in res["event_description"]
