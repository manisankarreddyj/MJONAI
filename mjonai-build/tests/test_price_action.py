"""
Unit and Institutional Test Suite for S05 Price Action Candles Strategy
(strategy/registry/price_action.py)
"""

import numpy as np
import pandas as pd
import pytest

from strategy.registry.price_action import PriceActionCandles
from strategy.registry.base import StrategySignalResult


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def hammer_at_support_ohlcv_df():
    """
    Generates an 80-row synthetic DataFrame:
    - Overall upward trend above EMA50 and EMA200
    - Final bar is a textbook Bullish Hammer candle with 1.7x volume surge.
    """
    np.random.seed(42)
    n = 80
    base = np.linspace(100.0, 200.0, n)
    close = base + np.random.normal(0, 0.5, n)
    open_ = close - 0.5
    high = np.maximum(open_, close) + 1.0
    low = np.minimum(open_, close) - 1.0
    volume = np.full(n, 50000.0, dtype=float)

    # Final bar: Bullish Hammer near dynamic support
    close[-1] = close[-2] + 1.0
    open_[-1] = close[-1] - 0.2  # tiny body
    high[-1] = close[-1] + 0.1   # tiny upper wick
    low[-1] = open_[-1] - 3.0    # long lower shadow (>= 2x body)
    volume[-1] = 85000.0         # 1.7x volume surge

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })
    return df


@pytest.fixture
def liquidity_sweep_ohlcv_df():
    """
    Generates an 80-row synthetic DataFrame with a textbook Liquidity Sweep (Turtle Soup):
    - Prior 10-day swing low is formed
    - Current bar plunges below the prior swing low to sweep retail stops, then closes strongly back above.
    """
    np.random.seed(42)
    n = 80
    base = np.linspace(100.0, 200.0, n)
    close = base + np.random.normal(0, 0.5, n)
    open_ = close - 0.5
    high = np.maximum(open_, close) + 1.0
    low = np.minimum(open_, close) - 1.0
    volume = np.full(n, 50000.0, dtype=float)

    # Establish a swing low at bar -5
    prior_low = float(np.min(low[-11:-1]))
    # Final bar sweeps below prior_low and closes high (Textbook Bullish Hammer / Liquidity Sweep)
    close[-1] = prior_low + 2.0
    open_[-1] = close[-1] - 0.3  # tiny body (0.3)
    high[-1] = close[-1] + 0.1   # tiny upper wick (0.1)
    low[-1] = prior_low - 2.5    # long lower shadow swept below prior_low (4.2 >= 2x body)
    volume[-1] = 95000.0

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
    """Generates an 80-row downtrending DataFrame below EMA50."""
    np.random.seed(99)
    n = 80
    close = np.linspace(200.0, 100.0, n)
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

def test_price_action_initialization_and_metadata():
    """Verify strategy metadata, parameters, and description."""
    strategy = PriceActionCandles()
    params = strategy.get_parameters()
    desc = strategy.get_description()

    assert strategy.name == "S05_PriceAction"
    assert strategy.version == "2.2"
    assert strategy.timeframe == "SWING"
    assert params["ema_mid"] == 50
    assert params["patterns_tested"] > 10
    assert "Price Action" in desc


def test_price_action_generates_valid_signal(hammer_at_support_ohlcv_df):
    """Verify valid StrategySignalResult emitted on Bullish Hammer at support."""
    strategy = PriceActionCandles()
    signal = strategy.generate_signal(
        df=hammer_at_support_ohlcv_df,
        symbol="HCLTECH",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is not None
    assert isinstance(signal, StrategySignalResult)
    assert signal.is_valid() is True
    assert signal.symbol == "HCLTECH"
    assert signal.strategy_id == "S05_PriceAction"
    assert signal.signal_direction == "LONG"
    assert signal.technical_score >= 65.0
    assert signal.confidence >= 65.0
    assert signal.candle_pattern is not None and len(signal.candle_pattern) > 0
    assert signal.entry_price is not None and signal.entry_price > 0
    assert len(signal.reasons) > 0


def test_price_action_liquidity_sweep_turtle_soup_bonus(liquidity_sweep_ohlcv_df):
    """Verify Institutional Liquidity Sweep (Turtle Soup) awards alpha bonus."""
    strategy = PriceActionCandles()
    signal = strategy.generate_signal(
        df=liquidity_sweep_ohlcv_df,
        symbol="RELIANCE",
        vix=13.5,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is not None
    assert any("Liquidity Sweep" in r or "Stop Hunt" in r for r in signal.reasons)


def test_price_action_hard_sentry_below_ema50_rejection(downtrend_df):
    """Verify Hard Sentry: Rejects trades immediately if price is below EMA50."""
    strategy = PriceActionCandles()
    signal = strategy.generate_signal(
        df=downtrend_df,
        symbol="TECHM",
        vix=18.0,
        market_state="BEAR",
        mqi_level="LOW",
    )

    assert signal is None


def test_price_action_insufficient_history_returns_none(hammer_at_support_ohlcv_df):
    """Verify generate_signal rejects dataframes with fewer than 50 candles."""
    strategy = PriceActionCandles()
    short_df = hammer_at_support_ohlcv_df.iloc[-30:].copy()

    signal = strategy.generate_signal(
        df=short_df,
        symbol="COALINDIA",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is None


def test_price_action_precomputed_indicators_fast_path(hammer_at_support_ohlcv_df):
    """Verify precomputed indicators bypass recalculation and emit valid signal."""
    strategy = PriceActionCandles()
    precomputed = {
        "ema_mid": 170.0,
        "ema_long": 150.0,
        "candle_pattern": "ENGULFING",
        "rvol": 1.5,
        "cmf": 0.12,
        "atr": 3.2,
    }

    signal = strategy.generate_signal(
        df=hammer_at_support_ohlcv_df,
        symbol="NTPC",
        vix=13.0,
        market_state="BULL",
        mqi_level="HIGH",
        precomputed_indicators=precomputed,
    )

    assert signal is not None
    assert signal.technical_score >= 65.0
    assert signal.candle_pattern == "ENGULFING"
    assert signal.indicator_values["rvol"] == 1.5


def test_price_action_higher_timeframe_filter(hammer_at_support_ohlcv_df):
    """Verify Higher Timeframe Filter applies penalty if Daily HTF is below EMA50."""
    strategy = PriceActionCandles()
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
        df=hammer_at_support_ohlcv_df,
        symbol="WIPRO",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
        higher_tf_df=htf_df,
    )

    if signal is not None:
        assert any("Higher timeframe" in r for r in signal.reasons)


def test_price_action_execute_safe_integration(hammer_at_support_ohlcv_df):
    """Verify BaseStrategy.execute_safe wrapper runs smoothly with telemetry."""
    strategy = PriceActionCandles()
    signal = strategy.execute_safe(
        df=hammer_at_support_ohlcv_df,
        symbol="ONGC",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is not None
    assert "compute_latency_ms" in signal.extra_metadata
    assert signal.extra_metadata["compute_latency_ms"] >= 0


def test_price_action_execute_safe_blocks_unsupported_regime(hammer_at_support_ohlcv_df):
    """Verify execute_safe blocks execution during CRASH or non-allowed regime."""
    strategy = PriceActionCandles()
    signal = strategy.execute_safe(
        df=hammer_at_support_ohlcv_df,
        symbol="BPCL",
        vix=42.0,
        market_state="CRASH",  # Not in allowed_regimes
        mqi_level="LOW",
    )

    assert signal is None


def test_price_action_nan_data_handling(hammer_at_support_ohlcv_df):
    """Verify NaN corruption in close prices does not crash the strategy."""
    strategy = PriceActionCandles()
    corrupt_df = hammer_at_support_ohlcv_df.copy()
    corrupt_df.iloc[-5:, corrupt_df.columns.get_loc("Close")] = np.nan

    signal = strategy.generate_signal(
        df=corrupt_df,
        symbol="HINDALCO",
        vix=15.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is None
