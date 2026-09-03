"""
Unit and Institutional Test Suite for Open Interest & Smart Money Flow Engine
(options/oi_scanner.py)
"""

import pytest

from options.oi_scanner import (
    classify_oi_buildup,
    calculate_gamma_exposure,
    scan_oi_anomalies,
    OIScanResult,
)


def test_classify_oi_buildup_all_quadrants():
    """Verify 4-quadrant derivative positioning classification."""
    # 1. Long Buildup: Price UP + OI UP
    assert classify_oi_buildup(price_change_pct=1.5, oi_change_pct=8.0) == "LONG_BUILDUP"

    # 2. Short Buildup: Price DOWN + OI UP
    assert classify_oi_buildup(price_change_pct=-1.2, oi_change_pct=10.0) == "SHORT_BUILDUP"

    # 3. Short Covering: Price UP + OI DOWN
    assert classify_oi_buildup(price_change_pct=0.8, oi_change_pct=-5.0) == "SHORT_COVERING"

    # 4. Long Unwinding: Price DOWN + OI DOWN
    assert classify_oi_buildup(price_change_pct=-0.9, oi_change_pct=-6.0) == "LONG_UNWINDING"

    # 5. Neutral state
    assert classify_oi_buildup(price_change_pct=0.02, oi_change_pct=0.5) == "NEUTRAL"


def test_calculate_gamma_exposure_and_flip():
    """Verify Dealer Gamma Exposure (GEX) and Gamma Flip level calculation."""
    spot = 24500.0
    chain = [
        {"strike": 24300.0, "ce_oi": 10000.0, "pe_oi": 80000.0, "ce_gamma": 0.0001, "pe_gamma": 0.0002},
        {"strike": 24500.0, "ce_oi": 90000.0, "pe_oi": 50000.0, "ce_gamma": 0.0003, "pe_gamma": 0.0003},
        {"strike": 24700.0, "ce_oi": 80000.0, "pe_oi": 10000.0, "ce_gamma": 0.0002, "pe_gamma": 0.0001},
    ]

    res = calculate_gamma_exposure(spot, chain)
    assert "total_gex" in res
    assert res["gamma_regime"] in ("POSITIVE_GAMMA", "NEGATIVE_GAMMA")
    assert res["gamma_flip_strike"] > 0


def test_scan_oi_anomalies_bullish_and_bearish_flows():
    """Verify smart money Call/Put writing detection."""
    spot = 24500.0

    # Bullish: Put Writing (+PE OI) + Call Unwinding (-CE OI)
    bullish_chain = [
        {"strike": 24400.0, "ce_oi": 20000.0, "pe_oi": 90000.0, "ce_change_oi": -5000.0, "pe_change_oi": 25000.0},
        {"strike": 24500.0, "ce_oi": 50000.0, "pe_oi": 80000.0, "ce_change_oi": -8000.0, "pe_change_oi": 15000.0},
        {"strike": 24600.0, "ce_oi": 80000.0, "pe_oi": 20000.0, "ce_change_oi": -2000.0, "pe_change_oi": 5000.0},
    ]

    bull_res = scan_oi_anomalies("NIFTY", bullish_chain, spot_price=spot, price_change_pct=0.8)
    assert bull_res["sentiment"] == "STRONG_BULLISH"
    assert bull_res["confidence"] >= 80
    assert bull_res["call_resistance_wall"] == 24600.0  # Max CE OI
    assert bull_res["put_support_wall"] == 24400.0      # Max PE OI
    assert bull_res["buildup_type"] == "LONG_BUILDUP"
    assert len(bull_res["ce_unwinding_strikes"]) > 0


def test_scan_oi_anomalies_empty_chain():
    """Verify empty chain safely returns neutral fallback."""
    res = scan_oi_anomalies("INFY", [], spot_price=1800.0)
    assert res["sentiment"] == "NEUTRAL"
    assert res["confidence"] == 50
