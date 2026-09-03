"""
Unit and Institutional Test Suite for S10 Statistical Arbitrage Pairs Trading Strategy
(strategy/registry/pairs_trading.py)
"""

import numpy as np
import pandas as pd
import pytest

from strategy.registry.pairs_trading import PairsTrading
from strategy.registry.base import StrategySignalResult


@pytest.fixture
def pairs_spread_dislocation_df():
    """
    Generates synthetic cointegrated pair series:
    - Asset A and Asset B share 95% return correlation.
    - Final 2 bars: Asset A drops 5% creating a -2.5σ oversold spread dislocation.
    """
    np.random.seed(42)
    n = 120
    shared_returns = np.random.normal(0.001, 0.01, n)
    ret_a = shared_returns + np.random.normal(0, 0.001, n)
    ret_b = shared_returns + np.random.normal(0, 0.001, n)

    close_a = 100.0 * np.exp(np.cumsum(ret_a))
    close_b = 100.0 * np.exp(np.cumsum(ret_b))

    # Temporary dislocation on last bar
    close_a[-1] = close_a[-1] * 0.94

    open_a = close_a + 0.2
    high_a = close_a + 0.8
    low_a  = close_a - 0.8
    vol_a  = np.full(n, 50000.0)

    df_a = pd.DataFrame({
        "Open": open_a,
        "High": high_a,
        "Low": low_a,
        "Close": close_a,
        "Volume": vol_a,
    })

    df_b = pd.DataFrame({
        "Open": close_b + 0.2,
        "High": close_b + 0.8,
        "Low": close_b - 0.8,
        "Close": close_b,
        "Volume": vol_a,
    })

    return df_a, df_b


def test_pairs_trading_metadata():
    strategy = PairsTrading()
    assert strategy.name == "S10_PairsTrading"
    assert strategy.version == "2.1"
    assert strategy.timeframe == "SWING"


def test_pairs_trading_valid_signal(pairs_spread_dislocation_df):
    df_a, df_b = pairs_spread_dislocation_df
    strategy = PairsTrading()
    signal = strategy.generate_signal(
        df=df_a,
        symbol="HDFCBANK",
        vix=15.0,
        market_state="NEUTRAL",
        mqi_level="HIGH",
        higher_tf_df=df_b,
    )

    assert signal is not None
    assert isinstance(signal, StrategySignalResult)
    assert signal.is_valid() is True
    assert signal.signal_direction == "LONG"
    assert "spread_zscore" in signal.indicator_values
    assert signal.indicator_values["spread_zscore"] <= -1.8
    assert signal.technical_score >= 70.0
