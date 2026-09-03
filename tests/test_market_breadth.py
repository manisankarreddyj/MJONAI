"""
Unit and Institutional Test Suite for Market Breadth & Distribution Divergence Engine
(intelligence/market_breadth.py)
"""

import pytest

from mjonai.intelligence.market_breadth import (
    calculate_advance_decline_ratio,
    calculate_mcclellan_oscillator,
    calculate_breadth_divergence,
    analyze_market_breadth,
    MarketBreadthResult,
)


def test_calculate_advance_decline_ratio():
    """Verify Advance-Decline Ratio (ADR) calculation and breadth health."""
    # 1. Strong Bullish (ADR >= 2.0)
    bull = calculate_advance_decline_ratio(advances=350, declines=150)
    assert bull["ad_ratio"] == 2.33
    assert bull["breadth_health"] == "STRONG_BULLISH_BREADTH"

    # 2. Strong Bearish (ADR <= 0.5)
    bear = calculate_advance_decline_ratio(advances=120, declines=380)
    assert bear["ad_ratio"] == 0.32
    assert bear["breadth_health"] == "STRONG_BEARISH_BREADTH"


def test_calculate_mcclellan_oscillator():
    """Verify McClellan oscillator computation."""
    # 40 days of net advances
    series = [50.0 + (i * 2.0) for i in range(45)]
    res = calculate_mcclellan_oscillator(series)
    assert "mcclellan_oscillator" in res
    assert "oscillator_regime" in res


def test_calculate_breadth_divergence_distribution_and_accumulation():
    """Verify smart money institutional divergence detection."""
    # 1. Bearish Distribution Divergence (Index UP +0.8%, but ADR = 0.6)
    dist = calculate_breadth_divergence(index_change_pct=0.80, ad_ratio=0.60)
    assert dist["divergence_type"] == "BEARISH_DISTRIBUTION_DIVERGENCE"
    assert dist["is_divergent"] is True

    # 2. Bullish Accumulation Divergence (Index DOWN -0.7%, but ADR = 1.5)
    acc = calculate_breadth_divergence(index_change_pct=-0.70, ad_ratio=1.50)
    assert acc["divergence_type"] == "BULLISH_ACCUMULATION_DIVERGENCE"
    assert acc["is_divergent"] is True

    # 3. Aligned (Index UP +0.8%, ADR = 2.0)
    aligned = calculate_breadth_divergence(index_change_pct=0.80, ad_ratio=2.0)
    assert aligned["is_divergent"] is False


def test_analyze_market_breadth_contract():
    """Verify complete market breadth synthesis and contract serialization."""
    res = analyze_market_breadth(
        advances=320,
        declines=180,
        advancing_volume=2.5,
        declining_volume=1.0,
        index_change_pct=0.65,
        stocks_above_20ema_pct=68.0,
    )
    assert res["ad_ratio"] == 1.78
    assert res["volume_ratio"] == 2.5
    assert res["stocks_above_20ema_pct"] == 68.0
    assert "mcclellan_oscillator" in res
    assert "reasons" in res
