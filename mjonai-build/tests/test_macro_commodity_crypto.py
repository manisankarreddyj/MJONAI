"""
Unit and Institutional Test Suite for S12 Macro Commodity & Crypto Trend Strategy
(strategy/registry/macro_commodity_crypto.py)
"""

import numpy as np
import pandas as pd
import pytest

from strategy.registry.macro_commodity_crypto import MacroCommodityCrypto
from strategy.registry.base import StrategySignalResult


@pytest.fixture
def macro_bull_trend_df():
    """
    Generates a 450-row secular macro uptrending DataFrame with high ADX (>25)
    and aligned EMA20 > EMA50 > EMA200.

    450 rows: S12 requires >=400 candles so its EMA200 carries real
    history (2026-08-23 audit fix — was 120, leaving the EMA200
    seed-dominated).
    """
    np.random.seed(42)
    n = 450
    # Ramp for the first 200 bars (EMA200 warmup), then a steady uptrend
    # so price stays above every EMA and the trend pillars align.
    close = np.concatenate([
        np.linspace(60.0, 100.0, 200),
        100.0 + np.linspace(0.0, 150.0, n - 200),
    ]) + np.random.normal(0, 0.5, n)
    open_ = close - 0.5
    high = close + 1.5
    low = close - 1.5
    volume = np.full(n, 50000.0)

    return pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })


def test_macro_commodity_crypto_metadata():
    strategy = MacroCommodityCrypto()
    assert strategy.name == "S12_MacroCommodityCrypto"
    assert strategy.version == "1.0"
    assert strategy.timeframe == "POSITIONAL"


def test_macro_commodity_crypto_valid_signal(macro_bull_trend_df):
    strategy = MacroCommodityCrypto()
    signal = strategy.generate_signal(
        df=macro_bull_trend_df,
        symbol="CRUDEOIL",
        vix=18.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is not None
    assert isinstance(signal, StrategySignalResult)
    assert signal.is_valid() is True
    assert signal.signal_direction == "LONG"
    assert signal.timeframe == "POSITIONAL"
    assert signal.technical_score >= 75.0
