"""
Unit and Institutional Test Suite for FII / DII Net Flow Intelligence Engine
(intelligence/fii_dii.py)
"""

import pytest

from mjonai.intelligence.fii_dii import (
    calculate_fii_long_short_ratio,
    calculate_cumulative_flow_velocity,
    analyze_fii_dii_flow,
    FIIDIIFlowResult,
)


def test_calculate_fii_long_short_ratio():
    """Verify FII Index Futures Long/Short ratio and squeeze alert signals."""
    # 1. Extreme Oversold (<=20% Longs) -> Short Squeeze Alert
    squeeze = calculate_fii_long_short_ratio(fii_long_contracts=15000, fii_short_contracts=85000)
    assert squeeze["long_percentage"] == 15.0
    assert squeeze["positioning"] == "EXTREME_OVERSOLD_SQUEEZE_ALERT"

    # 2. Extreme Overbought (>=75% Longs) -> Pullback Alert
    overbought = calculate_fii_long_short_ratio(fii_long_contracts=80000, fii_short_contracts=20000)
    assert overbought["long_percentage"] == 80.0
    assert overbought["positioning"] == "OVERBOUGHT_PULLBACK_ALERT"

    # 3. Balanced Stance
    balanced = calculate_fii_long_short_ratio(fii_long_contracts=50000, fii_short_contracts=50000)
    assert balanced["long_percentage"] == 50.0
    assert balanced["positioning"] == "BALANCED"


def test_calculate_cumulative_flow_velocity():
    """Verify multi-day flow trend velocity."""
    history = [
        {"fii_net_cr": 1200.0, "dii_net_cr": 800.0},
        {"fii_net_cr": 1500.0, "dii_net_cr": 900.0},
        {"fii_net_cr": 2000.0, "dii_net_cr": 1100.0},
        {"fii_net_cr": 800.0, "dii_net_cr": 600.0},
        {"fii_net_cr": 1000.0, "dii_net_cr": 700.0},
    ]
    # Total FII 5D = 6500 Cr -> Strong Accumulation
    velocity = calculate_cumulative_flow_velocity(history, window_days=5)
    assert velocity["fii_5d_net_cr"] == 6500.0
    assert velocity["trend"] == "STRONG_GLOBAL_ACCUMULATION"


def test_analyze_fii_dii_flow_mega_bullish_and_severe_drain():
    """Verify cash flow regime classifications."""
    # 1. Both buying > 500 Cr -> MEGA_BULLISH
    res_bull = analyze_fii_dii_flow(fii_cash_net_cr=1200.0, dii_cash_net_cr=800.0)
    assert res_bull["flow_regime"] == "MEGA_BULLISH"
    assert res_bull["confidence"] >= 90
    assert res_bull["total_institutional_net_cr"] == 2000.0

    # 2. Both selling < -500 Cr -> SEVERE_DRAIN
    res_bear = analyze_fii_dii_flow(fii_cash_net_cr=-1200.0, dii_cash_net_cr=-800.0)
    assert res_bear["flow_regime"] == "SEVERE_DRAIN"
    assert res_bear["confidence"] >= 80


def test_analyze_fii_dii_flow_domestic_absorption_with_squeeze_alert():
    """Verify DII absorption regime with FII short-squeeze booster."""
    res = analyze_fii_dii_flow(
        fii_cash_net_cr=-1500.0,
        dii_cash_net_cr=1800.0,
        fii_index_futures_longs=12000,
        fii_index_futures_shorts=88000,  # 12% Longs -> Squeeze Alert
    )
    assert res["flow_regime"] == "DOMESTIC_ABSORPTION"
    assert res["fii_positioning_regime"] == "EXTREME_OVERSOLD_SQUEEZE_ALERT"
    assert res["confidence"] >= 85
    assert "SHORT-SQUEEZE" in res["recommendation"]
