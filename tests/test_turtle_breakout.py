"""
Unit and Institutional Test Suite for S03 Turtle Breakout Positional Strategy
(strategy/registry/turtle_breakout.py)
"""

import numpy as np
import pandas as pd
import pytest

from mjonai.strategy.registry.turtle_breakout import TurtleBreakout
from mjonai.strategy.registry.base import StrategySignalResult


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def donchian_breakout_ohlcv_df():
    """
    Generates a 250-row synthetic DataFrame:
    - Bars 0..225: Steady upward drift above EMA200.
    - Bars 226..248: Tight horizontal consolidation base (20-day high at 240.0).
    - Bar 249 (Final bar): Price breaks out explosively to 248.0 (new 20-day and 55-day high)
      with clean close near high (High=249.0), 1.8x volume surge, expanding ATR, and high ADX.
    """
    np.random.seed(42)
    n = 250

    # Trend up to 230
    base = np.linspace(100.0, 230.0, n)
    close = base + np.random.normal(0, 0.4, n)

    # Tight horizontal base over bars 226..248 around 235..239
    close[226:249] = 238.0 + np.random.normal(0, 0.5, 23)
    open_ = close.copy()
    high = close + 1.0
    low = close - 1.0

    # Ensure confirmed 20-day high before final bar is 240.0
    high[235] = 240.0

    # Final bar: Explosive breakout to 248.0
    open_[-1] = 241.0
    close[-1] = 248.0
    high[-1] = 249.0  # Clean close: 248.0 >= 249.0 - 0.25*ATR
    low[-1] = 240.5
    volume = np.full(n, 50000.0, dtype=float)
    volume[-1] = 90000.0  # 1.8x volume surge

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

def test_turtle_breakout_initialization_and_metadata():
    """Verify strategy metadata, parameters, and description."""
    strategy = TurtleBreakout()
    params = strategy.get_parameters()
    desc = strategy.get_description()

    assert strategy.name == "S03_TurtleBreakout"
    assert strategy.version == "3.0"
    assert strategy.timeframe == "POSITIONAL"
    assert params["breakout_period_s1"] == 20
    assert params["breakout_period_s2"] == 55
    assert params["sl_period"] == 10
    # Original Turtle N-calibration
    assert params["n_atr_period"] == 20
    assert params["risk_multiple_n"] == 2.0
    assert "Turtle Breakout" in desc


def test_turtle_breakout_generates_valid_signal(donchian_breakout_ohlcv_df):
    """Verify valid StrategySignalResult emitted on 20-Day Donchian Breakout."""
    strategy = TurtleBreakout()
    signal = strategy.generate_signal(
        df=donchian_breakout_ohlcv_df,
        symbol="TATASTEEL",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is not None
    assert isinstance(signal, StrategySignalResult)
    assert signal.is_valid() is True
    assert signal.symbol == "TATASTEEL"
    assert signal.strategy_id == "S03_TurtleBreakout"
    assert signal.signal_direction == "LONG"
    assert signal.signal_type == "BUY"
    assert signal.timeframe == "POSITIONAL"
    assert signal.technical_score >= 75.0
    assert signal.confidence >= 75.0
    assert signal.sl_method == "TURTLE_2N"
    assert signal.swing_low is not None and signal.swing_low > 0
    # v3.0: risk stop = entry - 2N (original Turtle calibration)
    assert signal.indicator_values["hard_stop_2n"] == pytest.approx(
        signal.entry_price - 2 * signal.atr, abs=0.05
    )
    assert signal.extra_metadata["exit_rule"] == "TRAIL_10_DAY_LOW"
    assert "pyramid_step" in signal.indicator_values
    assert len(signal.reasons) > 0


def test_turtle_breakout_hard_sentry_no_breakout_rejection(donchian_breakout_ohlcv_df):
    """Verify Hard Sentry 1: Rejects trades if price does not break above 20-day high."""
    strategy = TurtleBreakout()
    no_breakout_df = donchian_breakout_ohlcv_df.copy()
    # Pull back final close below the 20-day high (240.0)
    no_breakout_df.iloc[-1, no_breakout_df.columns.get_loc("Close")] = 237.0

    signal = strategy.generate_signal(
        df=no_breakout_df,
        symbol="JINDALSTEL",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is None


def test_turtle_breakout_hard_sentry_below_ema200_rejection(downtrend_df):
    """Verify Hard Sentry 2: Rejects trades if price is below EMA200."""
    strategy = TurtleBreakout()
    signal = strategy.generate_signal(
        df=downtrend_df,
        symbol="SAIL",
        vix=18.0,
        market_state="BEAR",
        mqi_level="LOW",
    )

    assert signal is None


def test_turtle_breakout_insufficient_history_returns_none(donchian_breakout_ohlcv_df):
    """Verify generate_signal rejects dataframes with fewer than 240 candles."""
    strategy = TurtleBreakout()
    short_df = donchian_breakout_ohlcv_df.iloc[-100:].copy()

    signal = strategy.generate_signal(
        df=short_df,
        symbol="NMDC",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is None


def test_turtle_breakout_precomputed_indicators_fast_path(donchian_breakout_ohlcv_df):
    """Verify precomputed indicators bypass recalculation and emit valid signal."""
    strategy = TurtleBreakout()
    precomputed = {
        "donchian_high_20": 240.0,
        "ema_long": 180.0,
        "atr": 4.5,
        "atr_avg": 3.8,
        "rvol": 1.7,
        "cmf": 0.15,
        "adx": 26.0,
        "plus_di": 32.0,
        "minus_di": 10.0,
    }

    signal = strategy.generate_signal(
        df=donchian_breakout_ohlcv_df,
        symbol="VEDL",
        vix=13.5,
        market_state="BULL",
        mqi_level="HIGH",
        precomputed_indicators=precomputed,
    )

    assert signal is not None
    assert signal.technical_score >= 75.0
    assert signal.indicator_values["rvol"] == 1.7
    assert signal.indicator_values["lookback_high_20"] == 240.0


def test_turtle_breakout_higher_timeframe_filter(donchian_breakout_ohlcv_df):
    """Verify Higher Timeframe Filter applies penalty if Daily HTF is below EMA50."""
    strategy = TurtleBreakout()
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
        df=donchian_breakout_ohlcv_df,
        symbol="NATIONALUM",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
        higher_tf_df=htf_df,
    )

    if signal is not None:
        assert any("Higher timeframe" in r for r in signal.reasons)


def test_turtle_breakout_execute_safe_integration(donchian_breakout_ohlcv_df):
    """Verify BaseStrategy.execute_safe wrapper runs smoothly with telemetry."""
    strategy = TurtleBreakout()
    signal = strategy.execute_safe(
        df=donchian_breakout_ohlcv_df,
        symbol="HINDALCO",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is not None
    assert "compute_latency_ms" in signal.extra_metadata
    assert signal.extra_metadata["compute_latency_ms"] >= 0


def test_turtle_breakout_execute_safe_blocks_unsupported_regime(donchian_breakout_ohlcv_df):
    """Verify execute_safe blocks execution during CRASH or non-allowed regime."""
    strategy = TurtleBreakout()
    signal = strategy.execute_safe(
        df=donchian_breakout_ohlcv_df,
        symbol="COALINDIA",
        vix=40.0,
        market_state="CRASH",  # Not in allowed_regimes
        mqi_level="LOW",
    )

    assert signal is None


def test_turtle_breakout_nan_data_handling(donchian_breakout_ohlcv_df):
    """Verify NaN corruption in close prices does not crash the strategy."""
    strategy = TurtleBreakout()
    corrupt_df = donchian_breakout_ohlcv_df.copy()
    corrupt_df.iloc[-5:, corrupt_df.columns.get_loc("Close")] = np.nan

    signal = strategy.generate_signal(
        df=corrupt_df,
        symbol="APOLLOTYRE",
        vix=15.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is None


# ── v3.0 rebuild regression tests (original Turtle rules) ───────────────────


def test_turtle_breakout_rejects_sub_daily_candles():
    """v3.0 timeframe guard: 20/55/10-day periods are meaningless on
    intraday bars (the v2.2 unit-mismatch bug). Must refuse outright."""
    strategy = TurtleBreakout()

    n = 300
    base = np.linspace(100.0, 230.0, n)
    close = base + np.random.normal(0, 0.4, n)
    close[-30:] = 235.0 + np.random.normal(0, 0.5, 30)
    high, low = close + 1.0, close - 1.0
    high[280] = 240.0

    hourly_df = pd.DataFrame(
        {
            "Open": close - 0.2,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": np.full(n, 50000.0),
        },
        index=pd.date_range("2026-08-17", periods=n, freq="h"),  # HOURLY bars
    )

    signal = strategy.generate_signal(
        df=hourly_df,
        symbol="TATASTEEL",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is None


def test_turtle_breakout_rejects_sub_daily_candles():
    """v3.0 timeframe guard: 20/55/10-day periods are meaningless on
    intraday bars (the v2.2 unit-mismatch bug). Must refuse outright."""
    strategy = TurtleBreakout()

    n = 300
    base = np.linspace(100.0, 230.0, n)
    close = base + np.random.normal(0, 0.4, n)
    close[-30:] = 235.0 + np.random.normal(0, 0.5, 30)
    high, low = close + 1.0, close - 1.0
    high[280] = 240.0

    hourly_df = pd.DataFrame(
        {
            "Open": close - 0.2,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": np.full(n, 50000.0),
        },
        index=pd.date_range("2026-08-17", periods=n, freq="h"),  # HOURLY bars
    )

    signal = strategy.generate_signal(
        df=hourly_df,
        symbol="TATASTEEL",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is None
