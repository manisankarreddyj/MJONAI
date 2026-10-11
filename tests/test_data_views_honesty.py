"""Honesty + hit-rate contract for the interactive-app data views.

Pins the two fixes: build_ai_debates must render REAL recorded agent output (nulls when
absent) and never re-emit the fabricated theses/verdicts/models of the old view; and
build_signal_track_record must compute a direction-adjusted hit-rate (a LONG that rose or
a SHORT that fell counts as a hit), returning null rates — never a fabricated 0% — on no data.
"""
from unittest.mock import patch

from apps.web import data_views as dv

# Strings the OLD fabricated boardroom emitted; none may ever reappear.
_FABRICATED = (
    "DeepSeek-Distill",
    "Claude-3.5",
    "Confluent momentum",
    "Overhead liquidity resistance",
    "comprehensive Devil risk sentry clearance",
)


def test_debates_empty_db_returns_empty_never_fabricates():
    with patch("mjonai.db.repository.get_signals_intelligence_recent", return_value=[]):
        assert dv.build_ai_debates(limit=6) == []


def test_debates_reflect_real_columns_not_defaults():
    row = {
        "id": "s1", "symbol": "INFY", "strategy_id": "S01_MomentumRSI",
        "signal_direction": "LONG", "final_confidence": 71.0,
        "supervisor_decision": "APPROVED", "supervisor_reason": "Clean gates",
        "bull_verdict": "BUY", "bull_confidence": 78.0,
        "bull_key_reasons": ["volume breakout"], "bull_concerns": ["VIX high"],
        "bull_model_used": "RealModel", "was_executed": True,
        "generated_at": "2026-10-01T10:00:00+05:30",
    }
    with patch("mjonai.db.repository.get_signals_intelligence_recent", return_value=[row]):
        out = dv.build_ai_debates(limit=6)[0]
    assert out["bull_agent"]["verdict"] == "BUY"
    assert out["bull_agent"]["confidence"] == 78.0
    assert out["bull_agent"]["model"] == "RealModel"
    assert out["supervisor_cio"]["reason"] == "Clean gates"
    for f in _FABRICATED:
        assert f not in str(out), f"fabricated string leaked: {f}"


def test_debates_missing_reasoning_is_null_not_invented():
    row = {"id": "s2", "symbol": "TCS", "signal_direction": "SHORT"}
    with patch("mjonai.db.repository.get_signals_intelligence_recent", return_value=[row]):
        out = dv.build_ai_debates(limit=6)[0]
    assert out["bull_agent"]["verdict"] is None
    assert out["bull_agent"]["confidence"] is None
    assert out["supervisor_cio"]["reason"] is None
    for f in _FABRICATED:
        assert f not in str(out), f"fabricated string leaked: {f}"


def test_track_record_direction_adjusted():
    rows = [
        {"strategy_id": "S01", "signal_direction": "LONG",  "forward_return_1d": 0.02,  "forward_return_5d": 0.05},
        {"strategy_id": "S01", "signal_direction": "LONG",  "forward_return_1d": -0.01, "forward_return_5d": 0.01},
        {"strategy_id": "S02", "signal_direction": "SHORT", "forward_return_1d": -0.03, "forward_return_5d": 0.02},  # short that fell = hit
    ]
    with patch("mjonai.db.repository.get_signals_for_alphalens", return_value=rows):
        tr = dv.build_signal_track_record(days=90)
    s01 = next(s for s in tr["strategies"] if s["strategy_id"] == "S01")
    assert s01["n"] == 2
    assert s01["hit_rate_1d"] == 0.5            # only 1 of the 2 longs rose
    s02 = next(s for s in tr["strategies"] if s["strategy_id"] == "S02")
    assert s02["hit_rate_1d"] == 1.0           # the short fell → a hit
    assert tr["overall"]["n"] == 3


def test_track_record_no_data_is_null_not_zero():
    with patch("mjonai.db.repository.get_signals_for_alphalens", return_value=[]):
        tr = dv.build_signal_track_record(days=90)
    assert tr["overall"]["n"] == 0
    assert tr["overall"]["hit_rate_1d"] is None
    assert tr["strategies"] == []
