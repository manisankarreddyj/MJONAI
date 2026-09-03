"""
Unit and Institutional Test Suite for Pre-Market Gift Nifty & Global Macro Engine
(intelligence/gift_nifty.py)
"""

import pytest

from mjonai.intelligence.gift_nifty import (
    classify_gap_type,
    calculate_global_confluence_score,
    analyze_pre_market_gap,
    GiftNiftyGapResult,
)


def test_classify_gap_type():
    """Verify gap dynamics and fill probability rules."""
    # 1. Exhaustion Gap (> 1.2%)
    exhaustion = classify_gap_type(gap_pct=1.45, prev_close=24500.0)
    assert exhaustion["gap_type"] == "EXHAUSTION_GAP"
    assert exhaustion["fill_probability_pct"] == 70.0

    # 2. Breakaway Gap (0.6% breakout)
    breakaway = classify_gap_type(gap_pct=0.65, prev_close=24500.0, is_multi_day_breakout=True)
    assert breakaway["gap_type"] == "BREAKAWAY_GAP"
    assert breakaway["fill_probability_pct"] == 25.0

    # 3. Common Gap (0.1%)
    common = classify_gap_type(gap_pct=0.10, prev_close=24500.0)
    assert common["gap_type"] == "COMMON_GAP"
    assert common["fill_probability_pct"] == 50.0


def test_calculate_global_confluence_score():
    """Verify global macro score and risk climate classification."""
    # 1. Global Risk-On: US Futures +1.5%, Asian +1.0%, Crude -2.0%, DXY -0.5%
    risk_on = calculate_global_confluence_score(
        us_futures_pct=1.5,
        asian_indices_pct=1.0,
        crude_oil_change_pct=-2.0,
        dxy_dollar_change_pct=-0.5,
    )
    assert risk_on["global_macro_score"] >= 65.0
    assert risk_on["global_climate"] == "GLOBAL_RISK_ON"

    # 2. Global Risk-Off: US Futures -1.8%, Asian -1.2%, Crude +3.0%, DXY +0.8%
    risk_off = calculate_global_confluence_score(
        us_futures_pct=-1.8,
        asian_indices_pct=-1.2,
        crude_oil_change_pct=3.0,
        dxy_dollar_change_pct=0.8,
    )
    assert risk_off["global_macro_score"] <= 35.0
    assert risk_off["global_climate"] == "GLOBAL_RISK_OFF"


def test_analyze_pre_market_gap_strong_bullish_and_bearish():
    """Verify opening bias recommendations for strong gaps."""
    # 1. Strong Bullish Gap (+0.82%)
    res_bull = analyze_pre_market_gap(
        gift_nifty_price=24700.0,
        nifty_prev_close=24500.0,
        is_multi_day_breakout=True,
    )
    assert res_bull["opening_bias"] == "STRONG_BULLISH"
    assert res_bull["predicted_gap_points"] == 200.0
    assert res_bull["predicted_gap_pct"] == 0.82
    assert res_bull["gap_type"] == "BREAKAWAY_GAP"

    # 2. Strong Bearish Gap (-1.02%)
    res_bear = analyze_pre_market_gap(
        gift_nifty_price=24250.0,
        nifty_prev_close=24500.0,
    )
    assert res_bear["opening_bias"] == "STRONG_BEARISH"
    assert res_bear["predicted_gap_points"] == -250.0
    assert res_bear["predicted_gap_pct"] == -1.02


def test_analyze_pre_market_gap_flat_and_contract():
    """Verify flat open and complete dictionary contract."""
    res_flat = analyze_pre_market_gap(
        gift_nifty_price=24510.0,
        nifty_prev_close=24500.0,
    )
    assert res_flat["opening_bias"] == "FLAT"
    assert res_flat["gap_type"] == "COMMON_GAP"
    assert "global_macro_score" in res_flat
    assert "fill_probability_pct" in res_flat
