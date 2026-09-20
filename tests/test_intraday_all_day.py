"""
Unit and Institutional Test Suite for S08 All-Day Intraday & Scalping Strategy
(strategy/registry/intraday_all_day.py)
"""

import numpy as np
import pandas as pd
import pytest

from mjonai.strategy.registry.intraday_all_day import IntradayAllDayStrategy
from mjonai.strategy.registry.base import StrategySignalResult


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def intraday_bullish_box_breakout_df():
    """
    Generates a 50-row synthetic 5m intraday candle DataFrame:
    - Bars 0..40: Steady upward baseline establishing VWAP at ~200.0, EMA9 > EMA21 > VWAP.
    - Bars 41..48: Tight horizontal consolidation box between 204.0 and 206.0 (range ~1.0%).
    - Bar 49 (Final bar): Price breaks out explosively to 208.5 (above box high 206.0 & VWAP +1σ)
      with a 1.8x volume surge.
    """
    np.random.seed(42)
    n = 50

    close = np.linspace(195.0, 205.0, n)
    # Tight consolidation over bars 41..48
    close[41:49] = 205.0 + np.random.normal(0, 0.2, 8)

    open_ = close.copy()
    high = close + 0.5
    low = close - 0.5

    # Final breakout bar
    open_[-1] = 205.5
    close[-1] = 208.5
    high[-1] = 209.0
    low[-1] = 205.2

    volume = np.full(n, 10000.0, dtype=float)
    volume[-1] = 22000.0  # 2.2x volume surge

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })
    return df


@pytest.fixture
def intraday_bearish_box_breakdown_df():
    """
    Generates a 50-row synthetic 5m intraday candle DataFrame:
    - Bars 0..40: Steady downward baseline establishing VWAP at ~200.0, EMA9 < EMA21 < VWAP.
    - Bars 41..48: Tight horizontal consolidation box between 194.0 and 196.0 (range ~1.0%).
    - Bar 49 (Final bar): Price breaks down to 191.5 (below box low 194.0 & VWAP -1σ)
      with a 1.8x volume surge.
    """
    np.random.seed(99)
    n = 50

    close = np.linspace(205.0, 195.0, n)
    # Tight consolidation over bars 41..48
    close[41:49] = 195.0 + np.random.normal(0, 0.2, 8)

    open_ = close.copy()
    high = close + 0.5
    low = close - 0.5

    # Final breakdown bar
    open_[-1] = 194.5
    close[-1] = 191.5
    high[-1] = 194.8
    low[-1] = 191.0

    volume = np.full(n, 10000.0, dtype=float)
    volume[-1] = 22000.0  # 2.2x volume surge

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })
    return df


# ── Tests ────────────────────────────────────────────────────────────────────

def test_intraday_strategy_initialization_and_metadata():
    """Verify strategy metadata, parameters, and description."""
    strategy = IntradayAllDayStrategy()
    params = strategy.get_parameters()
    desc = strategy.get_description()

    assert strategy.name == "S08_IntradayAllDay"
    assert strategy.version == "2.3"
    assert strategy.timeframe == "INTRADAY"
    assert params["box_lookback"] == 8
    assert params["volume_multiplier"] == 1.40
    assert params["risk_reward_ratio"] == 1.8
    assert "Intraday" in desc


def test_intraday_long_box_breakout_generates_valid_signal(intraday_bullish_box_breakout_df):
    """Verify valid StrategySignalResult emitted on Long Intraday Box Breakout."""
    strategy = IntradayAllDayStrategy()
    signal = strategy.generate_signal(
        df=intraday_bullish_box_breakout_df,
        symbol="NIFTY",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is not None
    assert isinstance(signal, StrategySignalResult)
    assert signal.is_valid() is True
    assert signal.symbol == "NIFTY"
    assert signal.strategy_id == "S08_IntradayAllDay"
    assert signal.signal_direction == "LONG"
    assert signal.signal_type == "BUY"
    assert signal.timeframe == "INTRADAY"
    assert signal.technical_score >= 70.0
    assert signal.confidence >= 70.0
    assert signal.entry_price == 208.5
    assert signal.swing_low is not None and signal.swing_low > 0
    assert "vwap" in signal.indicator_values
    assert len(signal.reasons) > 0


def test_intraday_short_box_breakdown_generates_valid_signal(intraday_bearish_box_breakdown_df):
    """Verify valid StrategySignalResult emitted on Short Intraday Box Breakdown."""
    strategy = IntradayAllDayStrategy()
    signal = strategy.generate_signal(
        df=intraday_bearish_box_breakdown_df,
        symbol="BANKNIFTY",
        vix=17.0,
        market_state="BEAR",
        mqi_level="HIGH",
    )

    assert signal is not None
    assert isinstance(signal, StrategySignalResult)
    assert signal.is_valid() is True
    assert signal.symbol == "BANKNIFTY"
    assert signal.strategy_id == "S08_IntradayAllDay"
    assert signal.signal_direction == "SHORT"
    assert signal.signal_type == "SELL"
    assert signal.timeframe == "INTRADAY"
    assert signal.technical_score >= 70.0
    assert signal.confidence >= 70.0
    assert signal.entry_price == 191.5
    assert signal.swing_high is not None and signal.swing_high > 0
    assert "vwap" in signal.indicator_values
    assert len(signal.reasons) > 0


def test_intraday_insufficient_history_returns_none(intraday_bullish_box_breakout_df):
    """Verify generate_signal rejects dataframes with fewer than min candles."""
    strategy = IntradayAllDayStrategy()
    short_df = intraday_bullish_box_breakout_df.iloc[:10].copy()

    signal = strategy.generate_signal(
        df=short_df,
        symbol="RELIANCE",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is None


def test_intraday_cpr_confluence_bonus(intraday_bullish_box_breakout_df):
    """Verify Daily CPR Central Pivot confluence is recognized."""
    strategy = IntradayAllDayStrategy()
    precomputed = {
        "cpr_pivot": 200.0,
        "cpr_tc": 202.0,
        "cpr_bc": 198.0,
    }

    signal = strategy.generate_signal(
        df=intraday_bullish_box_breakout_df,
        symbol="HDFCBANK",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
        precomputed_indicators=precomputed,
    )

    assert signal is not None
    assert any("Central Pivot" in r for r in signal.reasons)


def test_intraday_execute_safe_integration(intraday_bullish_box_breakout_df):
    """Verify S08 execute_safe executes cleanly and generates valid signal.

    S4 (canonical verification wave 2026-09-03): S08 was parameterized for 5m
    bars while the production runtime only scheduled 15m scans — its
    "40-minute box" read as 2 hours on 15m bars. Re-enabled 2026-09-20
    (minute pipeline Phase 2b) on the NEW native 5m slot only; the
    scan_cadences=("5m",) gate makes a 15m read impossible by construction.
    The instance-level opt-in below is now redundant-but-harmless; it pins
    that execute_safe itself is exercised with a 5m-shaped fixture.
    """
    strategy = IntradayAllDayStrategy()
    strategy.is_active = True  # instance-level opt-in for this machinery test only

    signal = strategy.execute_safe(
        df=intraday_bullish_box_breakout_df,
        symbol="SBIN",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
    )
    assert signal is not None
    assert signal.is_valid() is True


def test_intraday_nan_data_handling(intraday_bullish_box_breakout_df):
    """Verify NaN corruption in close prices does not crash the strategy."""
    strategy = IntradayAllDayStrategy()
    corrupt_df = intraday_bullish_box_breakout_df.copy()
    corrupt_df.iloc[-5:, corrupt_df.columns.get_loc("Close")] = np.nan

    signal = strategy.generate_signal(
        df=corrupt_df,
        symbol="INFY",
        vix=15.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is None
