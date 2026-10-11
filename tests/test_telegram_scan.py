"""Telegram /scan command contract (PKScreener on-demand scanner pattern).

The command must be usage-helpful with no args, fail closed on DB errors (never a
fabricated scan), filter to the requested symbol, and render the recorded rows.
"""
from unittest.mock import patch

import mjonai.communication.telegram_commands as tc


def test_scan_requires_a_symbol():
    out = tc.handle_scan("")
    assert "Usage: /scan SYMBOL" in out


def test_scan_reports_recorded_signals():
    rows = [
        {"symbol": "INFY", "strategy_id": "S01_MomentumRSI", "signal_direction": "LONG",
         "final_confidence": 71.5, "supervisor_decision": "APPROVED"},
        {"symbol": "RELIANCE", "strategy_id": "S03_TurtleBreakout"},
    ]
    with patch("mjonai.db.repository.get_signals_today", return_value=rows):
        out = tc.handle_scan(" infy ")
    assert "INFY" in out and "S01_MomentumRSI" in out and "72%" in out
    assert "RELIANCE" not in out                      # filtered to the requested symbol
    assert "1 recorded signal" in out


def test_scan_no_signals_is_honest():
    with patch("mjonai.db.repository.get_signals_today", return_value=[]):
        out = tc.handle_scan("TCS")
    assert "no recorded signals today" in out


def test_scan_db_failure_fails_closed():
    with patch("mjonai.db.repository.get_signals_today", side_effect=RuntimeError("db down")):
        out = tc.handle_scan("TCS")
    assert "/scan failed" in out and "db down" in out
