"""
Unit and Institutional Test Suite for S01 Momentum RSI Strategy
(strategy/registry/momentum_rsi.py)
"""

import numpy as np
import pandas as pd
import pytest

from strategy.registry.momentum_rsi import MomentumRSI
from strategy.registry.base import StrategySignalResult


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def bullish_ohlcv_df():
    """
    G6 settlement: tuned to pass the LIVE v6.0 gate stack — net uptrend
    (EMA20 > EMA50 > EMA200), RSI ~71 inside the 55-72 momentum window,
    Wilder ADX ~36 >= 20, oscillating lows for fractal pivots, and a final
    fresh 20-bar resistance breakout bar with an RVOL surge. The previous
    v2.x-era fixture (steep monotonic drift + hammer) fails the RSI window.
    """
    rng = np.random.default_rng(42)
    n = 250
    drift = np.linspace(100.0, 160.0, n)
    wave = np.sin(np.arange(n) * 0.5) * 2.0
    noise = rng.normal(0, 0.08, n)
    close = drift + wave + noise
    open_ = close - 0.05
    high = np.maximum(open_, close) + 0.3
    low = np.minimum(open_, close) - 0.3
    volume = rng.uniform(50000, 150000, n)

    # Final bar: strong green breakout close above the recent range + RVOL surge
    close[-1] = close[-2] + float(np.abs(wave[-10:]).max()) + 1.0
    open_[-1] = close[-1] - 0.8
    high[-1] = close[-1] + 0.2
    low[-1] = open_[-1] - 0.3
    volume[-1] = float(np.mean(volume[-20:])) * 1.9

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })
    return df


@pytest.fixture
def flat_bearish_df():
    """Generates a 250-row downward trending/choppy DataFrame."""
    np.random.seed(101)
    n = 250
    drift = np.linspace(300.0, 100.0, n)
    noise = np.random.normal(0, 1.0, n)
    close = drift + noise
    open_ = close + 0.5
    high = np.maximum(open_, close) + 1.0
    low = np.minimum(open_, close) - 1.0
    volume = np.random.uniform(20000, 40000, n)

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })
    return df


# ── Tests ────────────────────────────────────────────────────────────────────

def test_momentum_rsi_initialization_and_metadata():
    """Verify strategy instantiation, parameter dictionary, and description."""
    strategy = MomentumRSI()
    params = strategy.get_parameters()
    desc = strategy.get_description()

    assert strategy.name == "S01_MomentumRSI"
    # G6 settlement: v6.0 is the live registry version (20-bar resistance
    # breakout rebuild); the old v2.1 pin was stale drift.
    assert strategy.version == "6.0"
    assert strategy.timeframe == "SWING"
    assert params["rsi_period"] == 14
    assert params["ema_long"] == 200
    assert "S01 Momentum RSI" in desc


def test_momentum_rsi_generates_valid_signal_on_bullish_df(bullish_ohlcv_df):
    """Verify generate_signal returns a validated StrategySignalResult on bullish data."""
    strategy = MomentumRSI()
    signal = strategy.generate_signal(
        df=bullish_ohlcv_df,
        symbol="RELIANCE",
        vix=14.2,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is not None
    assert isinstance(signal, StrategySignalResult)
    assert signal.is_valid() is True
    assert signal.symbol == "RELIANCE"
    assert signal.strategy_id == "S01_MomentumRSI"
    assert signal.signal_direction == "LONG"
    assert signal.signal_type == "BUY"
    assert signal.technical_score >= 65.0
    assert signal.confidence >= 65.0
    assert signal.atr is not None and signal.atr > 0
    assert signal.entry_price is not None and signal.entry_price > 0
    assert len(signal.reasons) > 0


def test_momentum_rsi_hard_sentry_ema200_rejection(bullish_ohlcv_df):
    """Verify Hard Sentry 2: Price below 200 EMA is instantly rejected."""
    strategy = MomentumRSI()
    downtrend_df = bullish_ohlcv_df.copy()
    # Crash the final close far below EMA200
    downtrend_df.iloc[-1, downtrend_df.columns.get_loc("Close")] = 50.0

    signal = strategy.generate_signal(
        df=downtrend_df,
        symbol="TCS",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is None


def test_momentum_rsi_rejects_bearish_market_data(flat_bearish_df):
    """Verify generate_signal returns None when conditions do not meet minimum score."""
    strategy = MomentumRSI()
    signal = strategy.generate_signal(
        df=flat_bearish_df,
        symbol="HDFCBANK",
        vix=22.0,
        market_state="BEAR",
        mqi_level="LOW",
    )

    assert signal is None


def test_momentum_rsi_insufficient_history_returns_none(bullish_ohlcv_df):
    """Verify generate_signal rejects dataframes below min_candles_required
    (100 for v6.0; was written against a 210-bar era)."""
    strategy = MomentumRSI()
    short_df = bullish_ohlcv_df.iloc[-99:].copy()

    signal = strategy.generate_signal(
        df=short_df,
        symbol="INFY",
        vix=13.5,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is None


def test_momentum_rsi_precomputed_indicators_fast_path(bullish_ohlcv_df):
    """G6 settlement: the v2.x 'fast path' (caller-supplied indicator values
    echoed into the result) no longer exists — v6.0 computes everything from
    the frame and ACCEPTS-BUT-IGNORES precomputed_indicators. Pin that
    contract: results must be identical with or without the dict, so a
    future partial re-application of stale values cannot slip in."""
    strategy = MomentumRSI()
    precomputed = {
        "rsi": 62.5,          # deliberately WRONG vs computed (~71) — if this
        "adx": 25.0,           # value ever surfaces in indicator_values, the
        "rvol": 1.5,           # ignore-contract is broken
        "atr": 4.5,
    }

    with_precomputed = strategy.generate_signal(
        df=bullish_ohlcv_df,
        symbol="TCS",
        vix=12.8,
        market_state="BULL",
        mqi_level="HIGH",
        precomputed_indicators=precomputed,
    )
    without = strategy.generate_signal(
        df=bullish_ohlcv_df,
        symbol="TCS",
        vix=12.8,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert with_precomputed is not None  # fixture passes gates
    assert without is not None
    assert with_precomputed.indicator_values == without.indicator_values
    assert with_precomputed.indicator_values["rsi"] != 62.5
    assert with_precomputed.indicator_values["atr"] != 4.5


def test_momentum_rsi_higher_timeframe_filter(bullish_ohlcv_df):
    """Verify Higher Timeframe Filter applies a penalty if HTF is below Daily EMA50."""
    strategy = MomentumRSI()
    # Create HTF df in downtrend (Close < EMA50)
    htf_n = 100
    htf_close = np.linspace(200.0, 50.0, htf_n)
    htf_df = pd.DataFrame({
        "Open": htf_close + 1.0,
        "High": htf_close + 2.0,
        "Low": htf_close - 2.0,
        "Close": htf_close,
        "Volume": np.full(htf_n, 100000),
    })

    signal = strategy.generate_signal(
        df=bullish_ohlcv_df,
        symbol="WIPRO",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
        higher_tf_df=htf_df,
    )

    # Should either reduce score or have penalty reason
    if signal is not None:
        assert any("Higher timeframe" in r for r in signal.reasons)


def test_momentum_rsi_execute_safe_integration(bullish_ohlcv_df):
    """Verify BaseStrategy.execute_safe wrapper runs smoothly with telemetry."""
    strategy = MomentumRSI()
    signal = strategy.execute_safe(
        df=bullish_ohlcv_df,
        symbol="SBIN",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is not None
    assert "compute_latency_ms" in signal.extra_metadata
    assert signal.extra_metadata["compute_latency_ms"] >= 0


def test_momentum_rsi_execute_safe_blocks_unsupported_regime(bullish_ohlcv_df):
    """Verify execute_safe blocks execution during CRASH or non-allowed regime."""
    strategy = MomentumRSI()
    signal = strategy.execute_safe(
        df=bullish_ohlcv_df,
        symbol="TATAMOTORS",
        vix=35.0,
        market_state="CRASH",  # Not in allowed_regimes
        mqi_level="LOW",
    )

    assert signal is None


def test_momentum_rsi_nan_data_handling(bullish_ohlcv_df):
    """Verify NaN corruption in close prices does not crash the strategy."""
    strategy = MomentumRSI()
    corrupt_df = bullish_ohlcv_df.copy()
    corrupt_df.iloc[-5:, corrupt_df.columns.get_loc("Close")] = np.nan

    signal = strategy.generate_signal(
        df=corrupt_df,
        symbol="ICICIBANK",
        vix=15.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is None
