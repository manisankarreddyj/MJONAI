"""Approval-console contract: the queue is advisory telemetry, the decision journal
writes to system_log, unknown actions fail closed, and no path can place an order.
"""
from unittest.mock import patch

import pytest

from apps.web import data_views as dv


def test_queue_empty_when_no_signals():
    with patch("mjonai.db.repository.get_signals_intelligence_recent", return_value=[]):
        out = dv.build_console_queue()
    assert out["queue"] == [] and out["count"] == 0
    assert "cannot place orders" in out["disclosure"]


def test_queue_lists_approved_unexecuted_only():
    rows = [
        {"id": "a", "symbol": "INFY", "strategy_id": "S01_MomentumRSI", "generated_at": "2026-10-11T10:00:00",
         "signal_direction": "LONG", "final_confidence": 71.0, "supervisor_decision": "APPROVED",
         "supervisor_reason": "clean gates", "was_executed": False,
         "bull_verdict": "BUY", "bull_confidence": 80.0, "bull_key_reasons": ["rv", "mtf"],
         "bull_model_used": "RealModel"},
        {"id": "b", "symbol": "TCS", "supervisor_decision": "APPROVED", "was_executed": True},   # already executed
        {"id": "c", "symbol": "SBIN", "supervisor_decision": "REJECTED", "was_executed": False},  # not approved
    ]
    with patch("mjonai.db.repository.get_signals_intelligence_recent", return_value=rows):
        out = dv.build_console_queue()
    assert [q["symbol"] for q in out["queue"]] == ["INFY"]
    item = out["queue"][0]
    assert item["supervisor_reason"] == "clean gates"
    assert item["bull_key_reasons"] == ["rv", "mtf"]
    assert item["bull_model_used"] == "RealModel"


def test_decision_journal_unknown_action_fails_closed():
    out = dv.record_console_decision("sig-1", "LAUNCH_MISSILES")
    assert out["recorded"] is False and "unknown action" in out["reason"]


def test_decision_journal_writes_system_log():
    calls = {}

    def _fake(event_type, message, level="INFO", system_mode="RESEARCH"):
        calls.update({"event_type": event_type, "message": message})
        return True

    with patch("mjonai.db.repository.insert_system_log", _fake):
        out = dv.record_console_decision("sig-1", "APPROVED_FOR_MANUAL", note="will place at open")
    assert out["recorded"] is True and out["action"] == "APPROVED_FOR_MANUAL"
    assert calls["event_type"] == "OPERATOR_DECISION" and "sig-1" in calls["message"]


def test_decision_journal_writer_failure_is_honest():
    with patch("mjonai.db.repository.insert_system_log", side_effect=RuntimeError("db down")):
        out = dv.record_console_decision("sig-1", "REJECTED")
    assert out["recorded"] is False and "db down" in out["reason"]
