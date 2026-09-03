"""
Unit and Institutional Test Suite for S02 Mean Reversion Long Strategy
(strategy/registry/mean_reversion.py)
"""

import numpy as np
import pandas as pd
import pytest

from mjonai.strategy.registry.mean_reversion import MeanReversion
from mjonai.strategy.registry.base import StrategySignalResult


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def oversold_dip_in_bull_trend_ohlcv_df():
    """
    Generates a 250-row synthetic DataFrame:
    - Bars 0..240: Strong secular uptrend establishing EMA200 at ~150.0 and EMA20 at ~230.0.
    - Bars 241..248: 3+ consecutive sharp red down-days pulling price down to 215.0 (oversold dip).
    - Bar 249 (Final bar): Price tests lower Bollinger Band (~210.0), RSI drops < 30 (RSI2 < 10),
      forms a Bullish Hammer with a 1.6x capitulation volume spike, while remaining far above EMA200 (150.0).
    """
    np.random.seed(42)
    n = 250

    # Strong secular bull trend: 100 -> 250
    base = np.linspace(100.0, 250.0, n)
    close = base + np.random.normal(0, 0.5, n)

    # Sharp 4-day pullback on final bars (consecutive down days)
    close[-5] = close[-6] - 4.0
    close[-4] = close[-5] - 4.0
    close[-3] = close[-4] - 4.0
    close[-2] = close[-3] - 4.0
    close[-1] = close[-2] + 1.0  # Hammer bounce

    open_ = close.copy()
    open_[-5] = close[-5] + 3.0
    open_[-4] = close[-4] + 3.0
    open_[-3] = close[-3] + 3.0
    open_[-2] = close[-2] + 3.0
    open_[-1] = close[-1] - 0.2  # tiny body for Hammer

    high = np.maximum(open_, close) + 0.5
    low = np.minimum(open_, close) - 0.5
    low[-1] = open_[-1] - 3.5    # long lower shadow (>= 2x body)
    high[-1] = close[-1] + 0.1   # tiny upper wick

    volume = np.full(n, 50000.0, dtype=float)
    volume[-1] = 85000.0         # 1.7x capitulation volume spike

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })
    return df


@pytest.fixture
def downtrend_df():
    """Generates a 250-row secular downtrending DataFrame far below EMA200."""
    np.random.seed(99)
    n = 250
    close = np.linspace(250.0, 100.0, n)
    open_ = close + 0.5
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

def test_mean_reversion_initialization_and_metadata():
    """Verify strategy metadata, parameters, and description."""
    strategy = MeanReversion()
    params = strategy.get_parameters()
    desc = strategy.get_description()

    assert strategy.name == "S02_MeanReversion"
    assert strategy.version == "2.2"
    assert strategy.timeframe == "SWING"
    assert params["rsi_period"] == 14
    assert params["rsi_fast_period"] == 2
    assert params["ema_long"] == 200
    assert "Mean Reversion" in desc


def test_mean_reversion_generates_valid_signal_on_oversold_dip(oversold_dip_in_bull_trend_ohlcv_df):
    """Verify valid StrategySignalResult emitted on oversold pullback in bull trend."""
    strategy = MeanReversion()
    signal = strategy.generate_signal(
        df=oversold_dip_in_bull_trend_ohlcv_df,
        symbol="TCS",
        vix=15.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is not None
    assert isinstance(signal, StrategySignalResult)
    assert signal.is_valid() is True
    assert signal.symbol == "TCS"
    assert signal.strategy_id == "S02_MeanReversion"
    assert signal.signal_direction == "LONG"
    assert signal.signal_type == "BUY"
    assert signal.technical_score >= 70.0
    assert signal.confidence >= 70.0
    assert signal.atr is not None and signal.atr > 0
    assert signal.entry_price is not None and signal.entry_price > 0
    assert "rsi" in signal.indicator_values
    assert len(signal.reasons) > 0


def test_mean_reversion_hard_sentry_below_ema200_rejection(downtrend_df):
    """Verify Hard Sentry 1: Rejects trades immediately if price is below EMA200 (falling knife)."""
    strategy = MeanReversion()
    signal = strategy.generate_signal(
        df=downtrend_df,
        symbol="INFY",
        vix=20.0,
        market_state="BEAR",
        mqi_level="LOW",
    )

    assert signal is None


def test_mean_reversion_hard_sentry_rsi_not_oversold_rejection():
    """Verify Hard Sentry 2: Rejects trades if RSI is not in oversold pullback territory."""
    strategy = MeanReversion()
    # Create steadily rising data where RSI is ~65 (not oversold)
    n = 250
    close = np.linspace(100.0, 300.0, n)
    open_ = close - 0.5
    high = close + 1.0
    low = close - 1.0
    volume = np.full(n, 50000.0)

    non_oversold_df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })

    signal = strategy.generate_signal(
        df=non_oversold_df,
        symbol="RELIANCE",
        vix=13.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is None


def test_mean_reversion_insufficient_history_returns_none(oversold_dip_in_bull_trend_ohlcv_df):
    """Verify generate_signal rejects dataframes with fewer than 210 candles."""
    strategy = MeanReversion()
    short_df = oversold_dip_in_bull_trend_ohlcv_df.iloc[-100:].copy()

    signal = strategy.generate_signal(
        df=short_df,
        symbol="LT",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is None


def test_mean_reversion_precomputed_indicators_fast_path(oversold_dip_in_bull_trend_ohlcv_df):
    """Verify precomputed indicators bypass recalculation and emit valid signal."""
    strategy = MeanReversion()
    precomputed = {
        "ema_long": 150.0,
        "rsi": 25.0,
        "rsi_fast": 8.0,
        "bb_upper": 240.0,
        "bb_middle": 225.0,
        "bb_lower": 210.0,
        "rvol": 1.6,
        "cmf": 0.08,
        "atr": 4.2,
    }

    signal = strategy.generate_signal(
        df=oversold_dip_in_bull_trend_ohlcv_df,
        symbol="WIPRO",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
        precomputed_indicators=precomputed,
    )

    assert signal is not None
    assert signal.technical_score >= 70.0
    assert signal.indicator_values["rsi"] == 25.0
    assert signal.indicator_values["rvol"] == 1.6


def test_mean_reversion_higher_timeframe_filter(oversold_dip_in_bull_trend_ohlcv_df):
    """Verify Higher Timeframe Filter applies penalty if Daily HTF is below EMA50."""
    strategy = MeanReversion()
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
        df=oversold_dip_in_bull_trend_ohlcv_df,
        symbol="HDFCBANK",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
        higher_tf_df=htf_df,
    )

    if signal is not None:
        assert any("Higher timeframe" in r for r in signal.reasons)


def test_mean_reversion_execute_safe_integration(oversold_dip_in_bull_trend_ohlcv_df):
    """Verify BaseStrategy.execute_safe wrapper runs smoothly with telemetry."""
    strategy = MeanReversion()
    signal = strategy.execute_safe(
        df=oversold_dip_in_bull_trend_ohlcv_df,
        symbol="SBIN",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is not None
    assert "compute_latency_ms" in signal.extra_metadata
    assert signal.extra_metadata["compute_latency_ms"] >= 0


def test_mean_reversion_execute_safe_blocks_unsupported_regime(oversold_dip_in_bull_trend_ohlcv_df):
    """Verify execute_safe blocks execution during CRASH or non-allowed regime."""
    strategy = MeanReversion()
    signal = strategy.execute_safe(
        df=oversold_dip_in_bull_trend_ohlcv_df,
        symbol="MARUTI",
        vix=45.0,
        market_state="CRASH",  # Not in allowed_regimes
        mqi_level="LOW",
    )

    assert signal is None


def test_mean_reversion_nan_data_handling(oversold_dip_in_bull_trend_ohlcv_df):
    """Verify NaN corruption in close prices does not crash the strategy."""
    strategy = MeanReversion()
    corrupt_df = oversold_dip_in_bull_trend_ohlcv_df.copy()
    corrupt_df.iloc[-5:, corrupt_df.columns.get_loc("Close")] = np.nan

    signal = strategy.generate_signal(
        df=corrupt_df,
        symbol="AXISBANK",
        vix=15.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is None
