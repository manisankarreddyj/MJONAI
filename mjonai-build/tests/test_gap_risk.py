"""
Unit and Institutional Test Suite for risk/gap_risk.py
Tests Directional Adverse Gap Sizing, GARCH Volatility Clustering,
Weekend Scaling (sqrt(3)), Intraday Auto-Bypass, and GapRiskResult Contracts.
"""

from datetime import datetime, timezone
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from risk.gap_risk import (
    GapRiskResult,
    calculate_overnight_gap_risk,
    evaluate_gap_risk,
)


def _generate_mock_df(num_bars=40, base_price=1000.0, avg_gap_pct=0.01):
    """Helper to generate mock OHLC daily candles."""
    records = []
    curr_close = base_price
    for i in range(num_bars):
        gap = curr_close * (avg_gap_pct * (1 if i % 2 == 0 else -1))
        open_price = curr_close + gap
        high_price = max(open_price, curr_close) + 5.0
        low_price = min(open_price, curr_close) - 5.0
        curr_close = open_price + (2.0 if i % 2 == 0 else -2.0)
        records.append({
            "Open": open_price,
            "High": high_price,
            "Low": low_price,
            "Close": curr_close,
        })
    return records


# ── 1. CONTRACT & BACKWARD COMPATIBILITY TESTS ───────────────────────────────

def test_gap_risk_result_contract():
    """Verify GapRiskResult dataclass serializes cleanly to dict."""
    res = GapRiskResult(
        risk_level="LOW",
        expected_gap_rs=5.5,
        expected_gap_pct=0.0055,
        size_multiplier=1.0,
        is_vetoed=False,
        is_weekend_scaled=False,
        is_intraday=False,
        reason="Low Gap Risk",
    )
    d = res.to_dict()
    assert d["risk_level"] == "LOW"
    assert d["size_multiplier"] == 1.0


def test_tuple_unpacking_backwards_compatibility():
    """Verify legacy 4-tuple unpacking works seamlessly."""
    df = _generate_mock_df()
    level, exp_gap, size_mult, reason = calculate_overnight_gap_risk(
        df=df,
        entry_price=1000.0,
        stop_loss=980.0,
        direction="LONG",
    )
    assert level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert isinstance(exp_gap, float)
    assert size_mult in (1.0, 0.75, 0.5, 0.0)
    assert isinstance(reason, str)


# ── 2. INTRADAY (MIS) AUTO-BYPASS TESTS ──────────────────────────────────────

def test_intraday_auto_bypass():
    """Verify intraday positions incur zero gap risk and full position size."""
    df = _generate_mock_df()
    res = evaluate_gap_risk(
        df=df,
        entry_price=1000.0,
        stop_loss=995.0,  # Tight 5-pt SL
        direction="LONG",
        is_intraday=True,
    )
    assert res.risk_level == "LOW"
    assert res.expected_gap_rs == 0.0
    assert res.size_multiplier == 1.0
    assert res.is_intraday is True
    assert "Intraday position" in res.reason


# ── 3. DIRECTIONAL ADVERSE GAP TESTS ─────────────────────────────────────────

def test_directional_gap_evaluation():
    """Verify LONG evaluates downside gaps and SHORT evaluates upside jumps."""
    # Data with consistent downward gaps
    down_records = []
    price = 1000.0
    for _ in range(40):
        o = price - 15.0  # Gap down
        c = o + 2.0
        price = c
        down_records.append({"Open": o, "High": o + 5, "Low": o - 5, "Close": c})

    # For LONG: Large expected downside jump -> High or Critical risk
    res_long = evaluate_gap_risk(
        df=down_records,
        entry_price=1000.0,
        stop_loss=990.0,  # SL distance 10
        direction="LONG",
    )
    assert res_long.risk_level in ("HIGH", "CRITICAL")

    # For SHORT: Downward gaps are favorable -> Expected adverse jump is lower
    res_short = evaluate_gap_risk(
        df=down_records,
        entry_price=1000.0,
        stop_loss=1010.0,  # SL distance 10
        direction="SHORT",
    )
    assert res_short.expected_gap_rs <= res_long.expected_gap_rs


# ── 4. WEEKEND & HOLIDAY SCALING TESTS ───────────────────────────────────────

def test_friday_weekend_gap_scaling():
    """Verify Friday evaluations apply sqrt(3) scaling multiplier."""
    df = _generate_mock_df()

    # Wednesday evaluation (weekday = 2)
    wed_time = datetime(2026, 8, 19, 14, 0, tzinfo=timezone.utc)
    res_wed = evaluate_gap_risk(
        df=df,
        entry_price=1000.0,
        stop_loss=980.0,
        eval_time=wed_time,
    )
    assert res_wed.is_weekend_scaled is False

    # Friday evaluation (weekday = 4)
    fri_time = datetime(2026, 8, 21, 14, 0, tzinfo=timezone.utc)
    res_fri = evaluate_gap_risk(
        df=df,
        entry_price=1000.0,
        stop_loss=980.0,
        eval_time=fri_time,
    )
    assert res_fri.is_weekend_scaled is True
    assert res_fri.expected_gap_rs > res_wed.expected_gap_rs


# ── 5. POSITION SIZING LADDER TESTS ──────────────────────────────────────────

def test_critical_gap_risk_vetoes_trade():
    """Verify expected gap > 1.5x SL distance results in CRITICAL veto (size = 0.0)."""
    # Create volatile gap data
    df = _generate_mock_df(avg_gap_pct=0.04)  # 4% overnight gaps
    res = evaluate_gap_risk(
        df=df,
        entry_price=1000.0,
        stop_loss=995.0,  # Tight 0.5% SL distance (5 pts) vs 40 pt gap
        direction="LONG",
    )
    assert res.risk_level == "CRITICAL"
    assert res.size_multiplier == 0.0
    assert res.is_vetoed is True
