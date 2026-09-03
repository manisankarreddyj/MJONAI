"""
Unit and Institutional Test Suite for Options Volatility Engine & IV Rank
(options/volatility.py)
"""

import pytest

from options.volatility import (
    calculate_iv_rank,
    calculate_iv_percentile,
    classify_volatility_regime,
    calculate_iv_crush,
    analyze_volatility_term_structure,
    calculate_volatility_skew,
    get_strike_delta_adjustment,
    VolatilitySkewResult,
    VolatilityRegimeResult,
)


def test_calculate_iv_rank():
    """Verify IV Rank formula (Current - Min) / (Max - Min) * 100."""
    # Min = 10%, Max = 30%, Current = 20% -> IVR = 50.0%
    assert calculate_iv_rank(current_iv=0.20, min_iv=0.10, max_iv=0.30) == 50.0

    # Current at 52-week high -> IVR = 100.0%
    assert calculate_iv_rank(current_iv=0.35, min_iv=0.10, max_iv=0.30) == 100.0

    # Current at 52-week low -> IVR = 0.0%
    assert calculate_iv_rank(current_iv=0.08, min_iv=0.10, max_iv=0.30) == 0.0


def test_calculate_iv_percentile():
    """Verify IV Percentile calculation over historical series."""
    history = [0.10, 0.12, 0.14, 0.16, 0.18, 0.20, 0.22, 0.24, 0.26, 0.28]
    # Current IV = 0.20 -> 5 items are strictly lower out of 10 -> IVP = 50.0%
    assert calculate_iv_percentile(current_iv=0.20, historical_iv_series=history) == 50.0

    # Current IV = 0.29 -> 100% percentile
    assert calculate_iv_percentile(current_iv=0.29, historical_iv_series=history) == 100.0


def test_classify_volatility_regime():
    """Verify volatility regime classification and strategy recommendation."""
    # Low Vol -> Option Buying
    low = classify_volatility_regime(iv_percentile=20.0, vix=12.0)
    assert low["regime"] == "LOW_VOLATILITY"
    assert low["recommended_action"] == "OPTION_BUYING_MOMENTUM"

    # High Vol -> S09 Theta Selling / Iron Condors
    high = classify_volatility_regime(iv_percentile=80.0, vix=18.0)
    assert high["regime"] == "HIGH_VOLATILITY"
    assert high["recommended_action"] == "OPTION_WRITING_THETA_DECAY"

    # Extreme Vol -> Wide Defined Risk
    extreme = classify_volatility_regime(iv_percentile=90.0, vix=26.0)
    assert extreme["regime"] == "EXTREME_VOLATILITY"


def test_calculate_iv_crush():
    """Verify post-event IV collapse calculation."""
    res = calculate_iv_crush(pre_event_iv=0.40, expected_crush_pct=0.35)
    assert res["pre_event_iv"] == 0.40
    assert res["post_event_iv"] == 0.26
    assert res["crush_pct"] == 35.0


def test_analyze_volatility_term_structure():
    """Verify Contango vs Backwardation term structure identification."""
    # Normal Contango: Monthly IV (18%) > Weekly IV (15%)
    contango = analyze_volatility_term_structure(near_term_iv=0.15, next_term_iv=0.18)
    assert contango["structure"] == "CONTANGO_NORMAL"

    # Backwardation Inversion: Weekly IV (22%) > Monthly IV (16%)
    backwardation = analyze_volatility_term_structure(near_term_iv=0.22, next_term_iv=0.16)
    assert backwardation["structure"] == "BACKWARDATION_INVERTED"


def test_calculate_volatility_skew():
    """Verify Put/Call skew ratio and smile curvature calculation."""
    # Steep Put Skew (e.g. Put 25D IV = 18%, Call 25D IV = 12%, ATM = 14%)
    steep = calculate_volatility_skew(call_25d_iv=0.12, put_25d_iv=0.18, atm_iv=0.14)
    assert steep.put_call_skew_ratio == 1.50
    assert steep.skew_regime == "STEEP_PUT_SKEW"
    assert "ASYMMETRIC" in steep.recommended_strike_bias

    # Normal Index Skew (Put 25D IV = 15%, Call 25D IV = 12.5%, ATM = 13%)
    normal = calculate_volatility_skew(call_25d_iv=0.125, put_25d_iv=0.15, atm_iv=0.13)
    assert normal.put_call_skew_ratio == 1.20
    assert normal.skew_regime == "NORMAL_INDEX_SKEW"
    assert normal.recommended_strike_bias == "SYMMETRIC_STRANGLE"


def test_get_strike_delta_adjustment():
    """Verify dynamic delta offsets under skewed volatility smiles."""
    # Under steep fear skew (1.50x), Put delta pushed to 0.12, Call delta pulled to 0.24
    call_d, put_d = get_strike_delta_adjustment(skew_ratio=1.50, base_delta=0.20)
    assert put_d == 0.12
    assert call_d == 0.24

    # Under normal skew (1.20x), symmetric 0.20 delta
    call_d, put_d = get_strike_delta_adjustment(skew_ratio=1.20, base_delta=0.20)
    assert put_d == 0.20
    assert call_d == 0.20
