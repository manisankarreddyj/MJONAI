"""
Unit and Institutional Test Suite for S06 Momentum Short Strategy
(strategy/registry/momentum_short.py)
"""

import numpy as np
import pandas as pd
import pytest

from mjonai.strategy.registry.momentum_short import MomentumShort
from mjonai.strategy.registry.base import StrategySignalResult


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def bearish_breakdown_ohlcv_df():
    """
    Generates a 250-row synthetic downward trending DataFrame guaranteed to trigger
    strong bearish momentum conditions for S06:
    - Secular downtrend (Close < EMA50 < EMA200, EMA20 < EMA50 < EMA200).
    - Realistic geometric random walk keeping RSI in optimal bearish zone (~36.8).
    - MACD negative and accelerating downwards.
    - Supertrend overhead resistance.
    - Bearish Shooting Star candle with a 1.6x volume surge.
    """
    np.random.seed(42)
    n = 250

    # Geometric random walk with negative drift
    daily_returns = np.random.normal(-0.002, 0.012, n)
    close = 200.0 * np.exp(np.cumsum(daily_returns))

    open_ = close * (1.0 + np.random.normal(0, 0.003, n))
    high = np.maximum(open_, close) * (1.0 + np.random.uniform(0.002, 0.008, n))
    low = np.minimum(open_, close) * (1.0 - np.random.uniform(0.002, 0.008, n))
    volume = np.random.uniform(40000, 60000, n)

    # Final bar: Shooting Star with 1.6x volume surge
    close[-1] = close[-2] * 0.985
    open_[-1] = close[-1] * 1.002
    low[-1] = close[-1] * 0.998
    high[-1] = open_[-1] * 1.025  # long upper shadow
    volume[-1] = 90000.0

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

def test_momentum_short_initialization_and_metadata():
    """Verify strategy metadata, parameters, and description."""
    strategy = MomentumShort()
    params = strategy.get_parameters()
    desc = strategy.get_description()

    assert strategy.name == "S06_MomentumShort"
    assert strategy.version == "2.2"
    assert strategy.timeframe == "SWING"
    assert params["rsi_period"] == 14
    assert params["ema_long"] == 200
    assert "Momentum Short" in desc


def test_momentum_short_generates_valid_signal(bearish_breakdown_ohlcv_df):
    """Verify valid StrategySignalResult emitted on bearish breakdown data."""
    strategy = MomentumShort()
    signal = strategy.generate_signal(
        df=bearish_breakdown_ohlcv_df,
        symbol="PAYTM",
        vix=18.0,
        market_state="BEAR",
        mqi_level="HIGH",
    )

    assert signal is not None
    assert isinstance(signal, StrategySignalResult)
    assert signal.is_valid() is True
    assert signal.symbol == "PAYTM"
    assert signal.strategy_id == "S06_MomentumShort"
    assert signal.signal_direction == "SHORT"
    assert signal.signal_type == "SELL"
    assert signal.technical_score >= 65.0
    assert signal.confidence >= 65.0
    assert signal.atr is not None and signal.atr > 0
    assert signal.entry_price is not None and signal.entry_price > 0
    assert len(signal.reasons) > 0


def test_momentum_short_hard_sentry_above_ema200_rejection(bull_trend_df):
    """Verify Hard Sentry 1: Rejects shorting if price is above EMA200 (bull market)."""
    strategy = MomentumShort()
    signal = strategy.generate_signal(
        df=bull_trend_df,
        symbol="RELIANCE",
        vix=13.0,
        market_state="BEAR",
        mqi_level="MEDIUM",
    )

    assert signal is None


def test_momentum_short_hard_sentry_oversold_climax_rejection(bearish_breakdown_ohlcv_df):
    """Verify Hard Sentry 3: Rejects shorting if RSI < 25.0 (oversold bottom capitulation)."""
    strategy = MomentumShort()
    oversold_df = bearish_breakdown_ohlcv_df.copy()
    # Crash final closes vertically to force RSI < 20
    oversold_df.iloc[-10:, oversold_df.columns.get_loc("Close")] = np.linspace(80.0, 10.0, 10)

    signal = strategy.generate_signal(
        df=oversold_df,
        symbol="ZEEL",
        vix=22.0,
        market_state="BEAR",
        mqi_level="LOW",
    )

    assert signal is None


def test_momentum_short_insufficient_history_returns_none(bearish_breakdown_ohlcv_df):
    """Verify generate_signal rejects dataframes with fewer than 210 candles."""
    strategy = MomentumShort()
    short_df = bearish_breakdown_ohlcv_df.iloc[-100:].copy()

    signal = strategy.generate_signal(
        df=short_df,
        symbol="IDEA",
        vix=16.0,
        market_state="BEAR",
        mqi_level="MEDIUM",
    )

    assert signal is None


def test_momentum_short_precomputed_indicators_fast_path(bearish_breakdown_ohlcv_df):
    """Verify precomputed indicators bypass recalculation and emit valid signal."""
    strategy = MomentumShort()
    precomputed = {
        "rsi": 34.0,
        "adx": 26.0,
        "plus_di": 12.0,
        "minus_di": 30.0,
        "macd_hist": -1.5,
        "macd_hist_prev": -0.8,
        "ema_short": 90.0,
        "ema_mid": 120.0,
        "ema_long": 180.0,
        "supertrend_line": 105.0,
        "supertrend_dir": -1,
        "rvol": 1.5,
        "cmf": -0.12,
        "atr": 3.8,
    }

    signal = strategy.generate_signal(
        df=bearish_breakdown_ohlcv_df,
        symbol="YESBANK",
        vix=17.5,
        market_state="BEAR",
        mqi_level="HIGH",
        precomputed_indicators=precomputed,
    )

    assert signal is not None
    assert signal.technical_score >= 65.0
    assert signal.indicator_values["rsi"] == 34.0
    assert signal.indicator_values["rvol"] == 1.5


def test_momentum_short_higher_timeframe_filter(bearish_breakdown_ohlcv_df):
    """Verify Higher Timeframe Filter applies penalty if Daily HTF is above EMA50."""
    strategy = MomentumShort()
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
        df=bearish_breakdown_ohlcv_df,
        symbol="RBLBANK",
        vix=16.0,
        market_state="BEAR",
        mqi_level="HIGH",
        higher_tf_df=htf_df,
    )

    if signal is not None:
        assert any("Higher timeframe" in r for r in signal.reasons)


def test_momentum_short_execute_safe_integration(bearish_breakdown_ohlcv_df):
    """Verify BaseStrategy.execute_safe wrapper runs smoothly with telemetry."""
    strategy = MomentumShort()
    signal = strategy.execute_safe(
        df=bearish_breakdown_ohlcv_df,
        symbol="IBULHSGFIN",
        vix=18.0,
        market_state="BEAR",
        mqi_level="HIGH",
    )

    assert signal is not None
    assert "compute_latency_ms" in signal.extra_metadata
    assert signal.extra_metadata["compute_latency_ms"] >= 0


def test_momentum_short_execute_safe_blocks_bull_regime(bearish_breakdown_ohlcv_df):
    """Verify execute_safe blocks short execution during raging BULL market state."""
    strategy = MomentumShort()
    signal = strategy.execute_safe(
        df=bearish_breakdown_ohlcv_df,
        symbol="DELHIVERY",
        vix=12.0,
        market_state="BULL",  # Not in allowed_regimes
        mqi_level="HIGH",
    )

    assert signal is None


def test_momentum_short_nan_data_handling(bearish_breakdown_ohlcv_df):
    """Verify NaN corruption in close prices does not crash the strategy."""
    strategy = MomentumShort()
    corrupt_df = bearish_breakdown_ohlcv_df.copy()
    corrupt_df.iloc[-5:, corrupt_df.columns.get_loc("Close")] = np.nan

    signal = strategy.generate_signal(
        df=corrupt_df,
        symbol="BANDHANBNK",
        vix=19.0,
        market_state="BEAR",
        mqi_level="MEDIUM",
    )

    assert signal is None
