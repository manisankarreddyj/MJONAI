"""
G2 strategy-repair regression tests (2026-08-24):
  - C1: S01 MomentumRSI can actually emit signals again (prior_20_high NameError)
  - C2: pipeline honors the strategy-emitted stop exactly (swing_low/high contract)
  - H5: pipeline trend-strength uses real Wilder ADX, not a mislabeled ratio
  - S08 stays disabled until the minute pipeline feeds it native bars
"""

import numpy as np
import pandas as pd
import pytest

from mjonai.strategy.registry.momentum_rsi import MomentumRSI
from mjonai.strategy.registry.intraday_all_day import IntradayAllDayStrategy
from mjonai.strategy.registry.options_theta_decay import OptionsThetaDecay
from mjonai.strategy.registry.pairs_trading import PairsTrading
from mjonai.strategy.pipeline import (
    _compute_trend_strength,
    _resolve_structure_reference,
)


@pytest.fixture
def trending_bull_df() -> pd.DataFrame:
    """250 bars engineered to pass S01's real gates: net uptrend (EMA20>EMA50>
    EMA200), RSI ~71 (55-72 window), Wilder ADX ~36 (>=20), oscillating lows
    that give fractal pivots, final green breakout bar with RVOL surge."""
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

    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume}
    )


def test_s01_emits_signal_with_breakout_level(trending_bull_df):
    """C1 regression: the prior_20_high NameError swallowed every S01 signal.

    With the fix, a gate-passing dataframe must yield a StrategySignalResult
    whose indicator_values carry a sane breakout_level."""
    result = MomentumRSI().generate_signal(
        df=trending_bull_df,
        symbol="TEST",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
    )
    assert result is not None, "S01 must emit after C1 fix (no swallowed NameError)"
    assert result.strategy_id == "S01_MomentumRSI"
    breakout = result.indicator_values.get("breakout_level")
    assert breakout is not None and breakout > 0


def test_pipeline_trend_strength_is_real_adx(trending_bull_df):
    """H5 regression: _compute_trend_strength returns true Wilder ADX.

    A persistent uptrend must produce a meaningful positive ADX; a flat
    series must produce None (neutral market weight), never the old
    fabricated default of 25."""
    df = trending_bull_df
    adx = _compute_trend_strength(df["High"].squeeze(), df["Low"].squeeze(), df["Close"].squeeze())
    assert adx is not None
    assert 10.0 < adx < 100.0

    flat = pd.DataFrame({
        "Open": np.full(120, 100.0),
        "High": np.full(120, 100.2),
        "Low": np.full(120, 99.8),
        "Close": np.full(120, 100.0),
    })
    assert _compute_trend_strength(flat["High"].squeeze(), flat["Low"].squeeze(), flat["Close"].squeeze()) is None


def test_pipeline_honors_strategy_emitted_stop_exactly(trending_bull_df):
    """C2 regression: an explicit strategy stop (e.g. S03 TURTLE_2N riding the
    swing_low slot) flows through untouched; absent emission falls back to the
    generic fractal swing low."""
    df = trending_bull_df

    emitted = {"swing_low": 275.55, "sl_method": "TURTLE_2N"}
    ref, explicit = _resolve_structure_reference(emitted, df, "LONG")
    assert explicit is True
    assert ref == pytest.approx(275.55)

    empty = {}
    ref2, explicit2 = _resolve_structure_reference(empty, df, "LONG")
    assert explicit2 is False
    # Oscillating fixture has fractal pivots; on pivotless series None is valid.
    if ref2 is not None:
        assert ref2 < float(df["Close"].iloc[-1])

    short_ref, short_explicit = _resolve_structure_reference(empty, df, "SHORT")
    assert short_explicit is False
    # Geometry sanity (a pivot ABOVE a breakout close is NOT guaranteed on
    # strong rallies; trade_risk's wrong-side guard owns final validation).
    if short_ref is not None:
        assert short_ref > 0


def test_s08_disabled_until_minute_feed():
    """G2 decision: S08 was designed for intraday bars but traded daily bars.
    It must stay inactive until wired to the minute pipeline."""
    s08 = IntradayAllDayStrategy()
    assert s08.is_active is False
    df = pd.DataFrame({
        "Open": np.linspace(100, 101, 40),
        "High": np.linspace(101, 102, 40),
        "Low": np.linspace(99, 100, 40),
        "Close": np.linspace(100.5, 101.5, 40),
        "Volume": np.full(40, 1000.0),
    })
    assert s08.execute_safe(df=df, symbol="TEST", vix=15.0, market_state="BULL", mqi_level="HIGH") is None


def test_s09_s10_disabled_until_option_and_pair_wiring():
    """2026-09-17: S09 (options theta decay) and S10 (pairs trading) were
    is_active=True in code while the docs described them as disabled. S09
    is an OPTIONS strategy that needs real option-chain infrastructure; S10
    fell back to a yfinance fetch of NIFTY inside the scanner cycle when no
    benchmark was supplied — a blocking I/O timebomb in the 15-min loop.
    Both must stay inactive until their real wiring exists."""
    frames = [
        (OptionsThetaDecay(), "S09_OptionsThetaDecay"),
        (PairsTrading(), "S10_PairsTrading"),
    ]
    for strat, expected_name in frames:
        assert strat.name == expected_name
        assert strat.is_active is False
        df = pd.DataFrame({
            "Open": np.linspace(100, 101, 60),
            "High": np.linspace(101, 102, 60),
            "Low": np.linspace(99, 100, 60),
            "Close": np.linspace(100.5, 101.5, 60),
            "Volume": np.full(60, 1000.0),
        })
        # execute_safe must short-circuit BEFORE the strategy body runs —
        # S10's body performs a network benchmark fetch when active.
        assert strat.execute_safe(df=df, symbol="TEST", vix=15.0, market_state="BULL", mqi_level="HIGH") is None
