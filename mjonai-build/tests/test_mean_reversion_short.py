"""
Unit and Institutional Test Suite for S07 Mean Reversion Short Strategy
(strategy/registry/mean_reversion_short.py)
"""

import numpy as np
import pandas as pd
import pytest

from strategy.registry.mean_reversion_short import MeanReversionShort
from strategy.registry.base import StrategySignalResult


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def overbought_rip_in_downtrend_ohlcv_df():
    """
    Generates a 250-row synthetic downward trending DataFrame with an overbought relief rip:
    - Secular downtrend (Price < EMA200).
    - 4 consecutive sharp green up-days surging into upper Bollinger Band (~138.0).
    - RSI14 rises to ~66.0 (Fast RSI2 > 90.0).
    - Final bar: Wyckoff Upthrust / Shooting Star with 1.6x volume surge.
    """
    np.random.seed(42)
    n = 250

    # Secular downtrend from 250 down to 120
    drift = np.linspace(250.0, 120.0, n)
    close = drift + np.random.normal(0, 0.4, n)

    # Sharp 4-day relief rally on final bars (consecutive up days)
    close[-5] = close[-6] + 3.0
    close[-4] = close[-5] + 3.0
    close[-3] = close[-4] + 3.0
    close[-2] = close[-3] + 3.0
    close[-1] = close[-2] - 0.5  # Shooting star close

    open_ = close.copy()
    open_[-5] = close[-5] - 2.5
    open_[-4] = close[-4] - 2.5
    open_[-3] = close[-3] - 2.5
    open_[-2] = close[-2] - 2.5
    open_[-1] = close[-1] + 0.2  # tiny body

    high = np.maximum(open_, close) + 0.5
    low = np.minimum(open_, close) - 0.5
    high[-1] = open_[-1] + 3.5   # long upper shadow (>= 2x body)
    low[-1] = close[-1] - 0.1    # tiny lower shadow

    volume = np.full(n, 50000.0, dtype=float)
    volume[-1] = 85000.0         # 1.7x buying climax volume spike

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })
    return df


@pytest.fixture
def bull_trend_df():
    """Generates a 250-row secular uptrending DataFrame far above EMA200."""
    np.random.seed(101)
    n = 250
    close = np.linspace(100.0, 300.0, n)
    open_ = close - 0.5
    high = np.maximum(open_, close) + 1.0
    low = np.minimum(open_, close) - 1.0
    volume = np.full(n, 40000.0, dtype=float)

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })
    return df


# ── Tests ────────────────────────────────────────────────────────────────────

def test_mean_reversion_short_initialization_and_metadata():
    """Verify strategy metadata, parameters, and description."""
    strategy = MeanReversionShort()
    params = strategy.get_parameters()
    desc = strategy.get_description()

    assert strategy.name == "S07_MeanReversionShort"
    assert strategy.version == "2.3"
    assert strategy.timeframe == "SWING"
    assert params["rsi_period"] == 14
    assert params["rsi_fast_period"] == 2
    assert params["ema_long"] == 200
    assert "Mean Reversion Short" in desc


def test_mean_reversion_short_generates_valid_signal(overbought_rip_in_downtrend_ohlcv_df):
    """Verify valid StrategySignalResult emitted on overbought relief rip in downtrend."""
    strategy = MeanReversionShort()
    signal = strategy.generate_signal(
        df=overbought_rip_in_downtrend_ohlcv_df,
        symbol="INDUSINDBK",
        vix=18.0,
        market_state="BEAR",
        mqi_level="HIGH",
    )

    assert signal is not None
    assert isinstance(signal, StrategySignalResult)
    assert signal.is_valid() is True
    assert signal.symbol == "INDUSINDBK"
    assert signal.strategy_id == "S07_MeanReversionShort"
    assert signal.signal_direction == "SHORT"
    assert signal.signal_type == "SELL"
    assert signal.technical_score >= 70.0
    assert signal.confidence >= 70.0
    assert signal.atr is not None and signal.atr > 0
    assert signal.entry_price is not None and signal.entry_price > 0
    assert "rsi" in signal.indicator_values
    assert len(signal.reasons) > 0


def test_mean_reversion_short_hard_sentry_above_ema200_rejection(bull_trend_df):
    """Verify Hard Sentry 1: Rejects trades if price is above EMA200 (bull trend)."""
    strategy = MeanReversionShort()
    signal = strategy.generate_signal(
        df=bull_trend_df,
        symbol="TCS",
        vix=13.0,
        market_state="BEAR",
        mqi_level="MEDIUM",
    )

    assert signal is None


def test_mean_reversion_short_hard_sentry_rsi_not_overbought_rejection():
    """Verify Hard Sentry 2: Rejects trades if RSI is not in overbought relief territory."""
    strategy = MeanReversionShort()
    # Create falling data where RSI is ~35 (not overbought)
    n = 250
    close = np.linspace(250.0, 100.0, n)
    open_ = close + 0.5
    high = close + 1.0
    low = close - 1.0
    volume = np.full(n, 50000.0)

    non_overbought_df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })

    signal = strategy.generate_signal(
        df=non_overbought_df,
        symbol="TATAMOTORS",
        vix=17.0,
        market_state="BEAR",
        mqi_level="HIGH",
    )

    assert signal is None


def test_mean_reversion_short_insufficient_history_returns_none(overbought_rip_in_downtrend_ohlcv_df):
    """Verify generate_signal rejects dataframes with fewer than 210 candles."""
    strategy = MeanReversionShort()
    short_df = overbought_rip_in_downtrend_ohlcv_df.iloc[-100:].copy()

    signal = strategy.generate_signal(
        df=short_df,
        symbol="SUNPHARMA",
        vix=16.0,
        market_state="BEAR",
        mqi_level="MEDIUM",
    )

    assert signal is None


def test_mean_reversion_short_precomputed_indicators_fast_path(overbought_rip_in_downtrend_ohlcv_df):
    """Verify precomputed indicators bypass recalculation and emit valid signal."""
    strategy = MeanReversionShort()
    precomputed = {
        "ema_long": 190.0,
        "ema_mid": 140.0,
        "rsi": 68.0,
        "rsi_fast": 92.0,
        "bb_upper": 135.0,
        "bb_middle": 125.0,
        "bb_lower": 115.0,
        "rvol": 1.6,
        "cmf": -0.08,
        "atr": 3.5,
    }

    signal = strategy.generate_signal(
        df=overbought_rip_in_downtrend_ohlcv_df,
        symbol="CIPLA",
        vix=17.5,
        market_state="BEAR",
        mqi_level="HIGH",
        precomputed_indicators=precomputed,
    )

    assert signal is not None
    assert signal.technical_score >= 70.0
    assert signal.indicator_values["rsi"] == 68.0
    assert signal.indicator_values["rvol"] == 1.6


def test_mean_reversion_short_higher_timeframe_filter(overbought_rip_in_downtrend_ohlcv_df):
    """Verify Higher Timeframe Filter applies penalty if Daily HTF is above EMA50."""
    strategy = MeanReversionShort()
    htf_n = 100
    htf_close = np.linspace(100.0, 300.0, htf_n)
    htf_df = pd.DataFrame({
        "Open": htf_close - 1.0,
        "High": htf_close + 2.0,
        "Low": htf_close - 2.0,
        "Close": htf_close,
        "Volume": np.full(htf_n, 100000),
    })

    signal = strategy.generate_signal(
        df=overbought_rip_in_downtrend_ohlcv_df,
        symbol="BAJAJFINSV",
        vix=16.0,
        market_state="BEAR",
        mqi_level="HIGH",
        higher_tf_df=htf_df,
    )

    if signal is not None:
        assert any("Higher timeframe" in r for r in signal.reasons)


def test_mean_reversion_short_execute_safe_integration(overbought_rip_in_downtrend_ohlcv_df):
    """Verify BaseStrategy.execute_safe wrapper runs smoothly with telemetry."""
    strategy = MeanReversionShort()
    signal = strategy.execute_safe(
        df=overbought_rip_in_downtrend_ohlcv_df,
        symbol="MUTHOOTFIN",
        vix=18.0,
        market_state="BEAR",
        mqi_level="HIGH",
    )

    assert signal is not None
    assert "compute_latency_ms" in signal.extra_metadata
    assert signal.extra_metadata["compute_latency_ms"] >= 0


def test_mean_reversion_short_execute_safe_blocks_bull_regime(overbought_rip_in_downtrend_ohlcv_df):
    """Verify execute_safe blocks short execution during raging BULL market state."""
    strategy = MeanReversionShort()
    signal = strategy.execute_safe(
        df=overbought_rip_in_downtrend_ohlcv_df,
        symbol="POLYCAB",
        vix=12.0,
        market_state="BULL",  # Not in allowed_regimes
        mqi_level="HIGH",
    )

    assert signal is None


def test_mean_reversion_short_nan_data_handling(overbought_rip_in_downtrend_ohlcv_df):
    """Verify NaN corruption in close prices does not crash the strategy."""
    strategy = MeanReversionShort()
    corrupt_df = overbought_rip_in_downtrend_ohlcv_df.copy()
    corrupt_df.iloc[-5:, corrupt_df.columns.get_loc("Close")] = np.nan

    signal = strategy.generate_signal(
        df=corrupt_df,
        symbol="CANBK",
        vix=19.0,
        market_state="BEAR",
        mqi_level="MEDIUM",
    )

    assert signal is None
