"""
Unit and Institutional Test Suite for S09 Options Delta-Neutral & Theta Decay Strategy
(strategy/registry/options_theta_decay.py)
"""

import numpy as np
import pandas as pd
import pytest

from strategy.registry.options_theta_decay import OptionsThetaDecay
from strategy.registry.base import StrategySignalResult


@pytest.fixture
def non_trending_chop_df():
    """
    Generates a 100-row synthetic range-bound sideways DataFrame:
    - ADX < 18 (low directional trend).
    - Price well-contained inside Bollinger Bands around 200.0.
    - RSI near 50.0 (equilibrium).
    """
    np.random.seed(42)
    n = 100
    close = 200.0 + np.random.normal(0, 1.0, n)
    open_ = close + np.random.normal(0, 0.5, n)
    high = np.maximum(open_, close) + 1.0
    low = np.minimum(open_, close) - 1.0
    volume = np.full(n, 50000.0)

    return pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })


@pytest.fixture
def violent_trend_df():
    """Generates a 100-row steep trend with ADX > 40."""
    np.random.seed(99)
    n = 100
    close = np.linspace(100.0, 300.0, n)
    open_ = close - 1.0
    high = close + 2.0
    low = close - 2.0
    volume = np.full(n, 50000.0)

    return pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })


def test_options_theta_decay_metadata():
    strategy = OptionsThetaDecay()
    assert strategy.name == "S09_OptionsThetaDecay"
    assert strategy.version == "1.1"
    assert strategy.timeframe == "INTRADAY"
    assert strategy.asset_class == "OPTIONS"


def test_options_theta_decay_valid_signal(non_trending_chop_df):
    strategy = OptionsThetaDecay()
    signal = strategy.generate_signal(
        df=non_trending_chop_df,
        symbol="NIFTY",
        vix=16.0,
        market_state="NEUTRAL",
        mqi_level="HIGH",
    )

    assert signal is not None
    assert isinstance(signal, StrategySignalResult)
    assert signal.is_valid() is True
    assert signal.signal_direction == "NON_DIRECTIONAL"
    assert signal.option_type == "STRANGLE"
    assert "short_ce_strike" in signal.indicator_values
    assert "short_pe_strike" in signal.indicator_values
    assert signal.technical_score >= 70.0


def test_options_theta_decay_blocks_strong_trend(violent_trend_df):
    strategy = OptionsThetaDecay()
    signal = strategy.generate_signal(
        df=violent_trend_df,
        symbol="BANKNIFTY",
        vix=16.0,
        market_state="BULL",
        mqi_level="HIGH",
    )
    assert signal is None


def test_options_theta_decay_blocks_low_vix(non_trending_chop_df):
    strategy = OptionsThetaDecay()
    signal = strategy.generate_signal(
        df=non_trending_chop_df,
        symbol="NIFTY",
        vix=9.0,  # Below VIX_MIN_THRESHOLD (12.0)
        market_state="NEUTRAL",
        mqi_level="HIGH",
    )
    assert signal is None
