"""
Unit and Institutional Test Suite for S04 Bollinger Squeeze & TTM Compression Strategy
(strategy/registry/bollinger_squeeze.py)
"""

import numpy as np
import pandas as pd
import pytest

from mjonai.strategy.registry.bollinger_squeeze import BollingerSqueeze
from mjonai.strategy.registry.base import StrategySignalResult


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def squeeze_and_expansion_ohlcv_df():
    """
    Generates a 100-row synthetic DataFrame with:
    - Bars 0..85: Tight sideways consolidation (Bandwidth Compression / Squeeze)
    - Bars 86..99: Explosive upward breakout through the Upper Bollinger Band with RVOL surge.
    """
    np.random.seed(42)
    n = 100
    base_price = 500.0

    close = np.full(n, base_price, dtype=float)
    # Tight consolidation (small noise)
    close[:85] = base_price + np.random.normal(0, 0.2, 85)
    # Explosive upward breakout
    close[85:] = base_price + np.linspace(0.5, 20.0, 15)

    open_ = close - 0.3
    high = np.maximum(open_, close) + 0.5
    low = np.minimum(open_, close) - 0.5
    volume = np.full(n, 50000.0, dtype=float)
    # 2x volume expansion on final bars
    volume[85:] = 120000.0

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })
    return df


@pytest.fixture
def wide_noisy_df():
    """
    Generates a 100-row volatile expanding DataFrame with wide swings and NO squeeze.
    Bollinger Bands are continuously wide and never compressed.
    """
    np.random.seed(99)
    n = 100
    base_price = 500.0
    # Wide accelerating sinusoidal swings
    t = np.linspace(0, 10 * np.pi, n)
    close = base_price + (np.sin(t) * 40.0)
    open_ = close - 1.0
    high = np.maximum(open_, close) + 2.0
    low = np.minimum(open_, close) - 2.0
    volume = np.random.uniform(30000, 60000, n)

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })
    return df


# ── Tests ────────────────────────────────────────────────────────────────────

def test_bollinger_squeeze_initialization_and_metadata():
    """Verify strategy metadata, parameter configuration, and description."""
    strategy = BollingerSqueeze()
    params = strategy.get_parameters()
    desc = strategy.get_description()

    assert strategy.name == "S04_BollingerSqueeze"
    assert strategy.version == "2.1"
    assert strategy.timeframe == "SWING"
    assert params["bb_period"] == 20
    assert params["keltner_ema"] == 20
    assert "Bollinger Squeeze" in desc


def test_bollinger_squeeze_generates_valid_signal_on_expansion(squeeze_and_expansion_ohlcv_df):
    """Verify valid StrategySignalResult emitted on genuine TTM squeeze and breakout expansion."""
    strategy = BollingerSqueeze()
    signal = strategy.generate_signal(
        df=squeeze_and_expansion_ohlcv_df,
        symbol="BAJFINANCE",
        vix=13.5,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is not None
    assert isinstance(signal, StrategySignalResult)
    assert signal.is_valid() is True
    assert signal.symbol == "BAJFINANCE"
    assert signal.strategy_id == "S04_BollingerSqueeze"
    assert signal.signal_direction == "LONG"
    assert signal.signal_type == "BUY"
    assert signal.technical_score >= 70.0
    assert signal.confidence >= 70.0
    assert signal.atr is not None and signal.atr > 0
    assert signal.entry_price is not None and signal.entry_price > 0
    assert "squeeze_pct" in signal.indicator_values
    assert len(signal.reasons) > 0


def test_bollinger_squeeze_hard_sentry_no_squeeze_rejection(wide_noisy_df):
    """Verify Hard Sentry: Rejects trades immediately if no volatility compression occurred."""
    strategy = BollingerSqueeze()
    signal = strategy.generate_signal(
        df=wide_noisy_df,
        symbol="TATASTEEL",
        vix=26.0,
        market_state="NEUTRAL",
        mqi_level="MEDIUM",
    )

    assert signal is None


def test_bollinger_squeeze_insufficient_history_returns_none(squeeze_and_expansion_ohlcv_df):
    """Verify generate_signal rejects dataframes with fewer than 50 candles."""
    strategy = BollingerSqueeze()
    short_df = squeeze_and_expansion_ohlcv_df.iloc[-30:].copy()

    signal = strategy.generate_signal(
        df=short_df,
        symbol="KOTAKBANK",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is None


def test_bollinger_squeeze_precomputed_indicators_fast_path(squeeze_and_expansion_ohlcv_df):
    """Verify precomputed indicators bypass recalculation and emit valid signal."""
    strategy = BollingerSqueeze()
    precomputed = {
        "bb_upper": 520.0,
        "bb_middle": 500.0,
        "bb_lower": 480.0,
        "kelt_upper": 525.0,
        "kelt_lower": 475.0,
        "bb_width_curr": 0.08,
        "bb_width_prev": 0.05,
        "bb_width_avg": 0.09,
        "recent_min_width": 0.04,  # Compressed (< 75% of avg)
        "is_ttm_squeezed": True,
        "macd_hist": 1.2,
        "macd_hist_prev": 0.6,
        "rsi": 63.0,
        "rvol": 1.6,
        "cmf": 0.15,
        "atr": 6.5,
    }

    signal = strategy.generate_signal(
        df=squeeze_and_expansion_ohlcv_df,
        symbol="LT",
        vix=12.5,
        market_state="BULL",
        mqi_level="HIGH",
        precomputed_indicators=precomputed,
    )

    assert signal is not None
    assert signal.technical_score >= 70.0
    assert signal.indicator_values["rvol"] == 1.6
    assert signal.indicator_values["atr"] == 6.5


def test_bollinger_squeeze_execute_safe_integration(squeeze_and_expansion_ohlcv_df):
    """Verify BaseStrategy.execute_safe wrapper runs smoothly with telemetry."""
    strategy = BollingerSqueeze()
    signal = strategy.execute_safe(
        df=squeeze_and_expansion_ohlcv_df,
        symbol="AXISBANK",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is not None
    assert "compute_latency_ms" in signal.extra_metadata
    assert signal.extra_metadata["compute_latency_ms"] >= 0


def test_bollinger_squeeze_execute_safe_blocks_unsupported_regime(squeeze_and_expansion_ohlcv_df):
    """Verify execute_safe blocks execution during CRASH or non-allowed regime."""
    strategy = BollingerSqueeze()
    signal = strategy.execute_safe(
        df=squeeze_and_expansion_ohlcv_df,
        symbol="TITAN",
        vix=40.0,
        market_state="CRASH",  # Not in allowed_regimes
        mqi_level="LOW",
    )

    assert signal is None


def test_bollinger_squeeze_nan_data_handling(squeeze_and_expansion_ohlcv_df):
    """Verify NaN corruption in close prices does not crash the strategy."""
    strategy = BollingerSqueeze()
    corrupt_df = squeeze_and_expansion_ohlcv_df.copy()
    corrupt_df.iloc[-5:, corrupt_df.columns.get_loc("Close")] = np.nan

    signal = strategy.generate_signal(
        df=corrupt_df,
        symbol="MARUTI",
        vix=15.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is None
