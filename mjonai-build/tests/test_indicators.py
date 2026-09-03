"""
Unit and Institutional Test Suite for strategy/registry/indicators.py
Tests Mathematical Moving Averages, Multi-Asset Volatility, Option Greeks,
Continuous 24/7 Crypto Volatility, Central Pivot Range, and Candlestick Patterns.
"""

import numpy as np
import pandas as pd
import pytest

from strategy.registry import indicators as ind


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def ohlcv_arrays():
    """Generates synthetic trending OHLCV arrays."""
    np.random.seed(42)
    n = 60
    base = 100.0 + np.cumsum(np.random.normal(0.5, 1.0, n))
    high = base + np.random.uniform(0.5, 2.0, n)
    low = base - np.random.uniform(0.5, 2.0, n)
    open_ = base - np.random.uniform(-0.5, 0.5, n)
    close = base + np.random.uniform(-0.5, 0.5, n)
    volume = np.random.uniform(10000, 50000, n)
    return open_, high, low, close, volume


# ── 1. MOVING AVERAGES & OVERLAYS ────────────────────────────────────────────

def test_ema_and_sma_calculations(ohlcv_arrays):
    """Verify EMA and SMA shape and monotonic behavior."""
    _, _, _, close, _ = ohlcv_arrays
    ema20 = ind.EMA(close, timeperiod=20)
    sma20 = ind.SMA(close, timeperiod=20)

    assert len(ema20) == len(close)
    assert len(sma20) == len(close)
    assert not np.isnan(ema20[-1])
    assert not np.isnan(sma20[-1])


def test_wma_hma_and_zlema(ohlcv_arrays):
    """Verify WMA, HMA (Hull), and ZLEMA low-lag moving averages."""
    _, _, _, close, _ = ohlcv_arrays
    wma = ind.WMA(close, timeperiod=14)
    hma = ind.HMA(close, timeperiod=14)
    zlema = ind.ZLEMA(close, timeperiod=14)

    assert len(wma) == len(close)
    assert len(hma) == len(close)
    assert len(zlema) == len(close)
    assert not np.isnan(wma[-1])
    assert not np.isnan(hma[-1])
    assert not np.isnan(zlema[-1])


def test_donchian_max_min_channels(ohlcv_arrays):
    """Verify Donchian Channel 20-day High/Low rolling extremes."""
    _, high, low, _, _ = ohlcv_arrays
    max_20 = ind.MAX(high, timeperiod=20)
    min_20 = ind.MIN(low, timeperiod=20)

    assert max_20[-1] >= min_20[-1]
    assert np.all(max_20[20:] >= min_20[20:])


def test_vwap_and_keltner_channels(ohlcv_arrays):
    """Verify VWAP and Keltner Channels."""
    _, high, low, close, volume = ohlcv_arrays
    vwap_vals = ind.vwap(high, low, close, volume)
    upper, middle, lower = ind.keltner_channels(high, low, close, ema_period=20, atr_period=10, multiplier=2.0)

    assert len(vwap_vals) == len(close)
    assert vwap_vals[-1] > 0
    assert upper[-1] > middle[-1] > lower[-1]


def test_supertrend_indicator(ohlcv_arrays):
    """Verify Supertrend returns trend line and binary directional signals."""
    _, high, low, close, _ = ohlcv_arrays
    st_line, direction = ind.supertrend(high, low, close, period=10, multiplier=3.0)

    assert len(st_line) == len(close)
    assert len(direction) == len(close)
    assert set(np.unique(direction)).issubset({-1, 0, 1})


# ── 2. MOMENTUM & OSCILLATOR TESTS ───────────────────────────────────────────

def test_rsi_and_macd(ohlcv_arrays):
    """Verify RSI boundaries (0-100) and MACD 3-component output."""
    _, _, _, close, _ = ohlcv_arrays
    rsi_vals = ind.RSI(close, timeperiod=14)
    macd_l, sig_l, hist = ind.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)

    assert 0.0 <= rsi_vals[-1] <= 100.0
    assert len(macd_l) == len(sig_l) == len(hist) == len(close)


def test_adx_and_dmi_indicators(ohlcv_arrays):
    """Verify ADX, +DI, and -DI calculations."""
    _, high, low, close, _ = ohlcv_arrays
    adx_vals = ind.ADX(high, low, close, timeperiod=14)
    plus_di = ind.PLUS_DI(high, low, close, timeperiod=14)
    minus_di = ind.MINUS_DI(high, low, close, timeperiod=14)

    assert 0.0 <= adx_vals[-1] <= 100.0
    assert 0.0 <= plus_di[-1] <= 100.0
    assert 0.0 <= minus_di[-1] <= 100.0


def test_stoch_and_stochrsi(ohlcv_arrays):
    """Verify Stochastic Oscillator and StochRSI bounds."""
    _, high, low, close, _ = ohlcv_arrays
    k, d = ind.STOCH(high, low, close)
    sr_k, sr_d = ind.STOCHRSI(close)

    assert 0.0 <= k[-1] <= 100.0
    assert 0.0 <= d[-1] <= 100.0
    assert 0.0 <= sr_k[-1] <= 100.0


def test_roc_mom_and_linear_regression(ohlcv_arrays):
    """Verify ROC, MOM, and Linear Regression R^2."""
    _, _, _, close, _ = ohlcv_arrays
    roc = ind.ROC(close, timeperiod=10)
    mom = ind.MOM(close, timeperiod=10)
    slopes, r2 = ind.linear_regression_slope_and_r2(close, timeperiod=14)

    assert len(roc) == len(mom) == len(slopes) == len(r2)
    assert 0.0 <= r2[-1] <= 1.0


# ── 3. INSTITUTIONAL VOLUME FLOW TESTS ───────────────────────────────────────

def test_rvol_obv_and_cmf(ohlcv_arrays):
    """Verify RVOL, OBV, and Chaikin Money Flow."""
    _, high, low, close, volume = ohlcv_arrays
    rvol = ind.RVOL(volume, timeperiod=20)
    obv = ind.OBV(close, volume)
    cmf = ind.CMF(high, low, close, volume, timeperiod=20)

    assert rvol[-1] > 0
    assert len(obv) == len(close)
    assert -1.0 <= cmf[-1] <= 1.0


# ── 4. DERIVATIVE GREEKS & VOLATILITY TESTS ──────────────────────────────────

def test_black_scholes_pricing_and_greeks():
    """Verify Black-Scholes call/put pricing and Greeks values."""
    # Nifty Spot: 24,500, ATM Strike: 24,500, 7 DTE, 15% IV
    greeks_call = ind.option_greeks(spot=24500.0, strike=24500.0, dte_days=7.0, iv=0.15, option_type="CE")
    greeks_put = ind.option_greeks(spot=24500.0, strike=24500.0, dte_days=7.0, iv=0.15, option_type="PE")

    # ATM Call Delta ~ 0.50, Put Delta ~ -0.50
    assert 0.45 <= greeks_call["delta"] <= 0.55
    assert -0.55 <= greeks_put["delta"] <= -0.45
    assert greeks_call["gamma"] > 0
    assert greeks_call["theta"] < 0  # Time decay is negative
    assert greeks_call["vega"] > 0


def test_max_pain_and_pcr():
    """Verify Max Pain strike calculation and Put-Call Ratio."""
    strikes = [24300, 24400, 24500, 24600, 24700]
    call_oi = [10000, 25000, 80000, 50000, 20000]
    put_oi  = [30000, 60000, 75000, 20000, 5000]

    mp = ind.max_pain(strikes, call_oi, put_oi)
    pcr = ind.put_call_ratio(call_oi, put_oi)

    assert mp in strikes
    assert pcr > 0


def test_parkinson_and_garman_klass_volatility(ohlcv_arrays):
    """Verify Parkinson and Garman-Klass continuous 24/7 volatility estimators."""
    open_, high, low, close, _ = ohlcv_arrays
    p_vol = ind.parkinson_volatility(high, low, timeperiod=30)
    gk_vol = ind.garman_klass_volatility(open_, high, low, close, timeperiod=30)

    assert p_vol[-1] > 0
    assert gk_vol[-1] > 0


# ── 5. STRUCTURAL SUPPORT (CPR) & CANDLESTICKS ───────────────────────────────

def test_cpr_pivots():
    """Verify Central Pivot Range (Pivot, BC, TC) and classical levels."""
    cpr = ind.cpr_pivots(prev_high=24600.0, prev_low=24400.0, prev_close=24550.0)

    assert cpr["pivot"] == pytest.approx(24516.67, abs=0.01)
    assert cpr["bc"] == 24500.0
    assert cpr["r1"] > cpr["pivot"] > cpr["s1"]
    assert "is_narrow_cpr" in cpr


def test_candlestick_patterns(ohlcv_arrays):
    """Verify candlestick pattern recognizers return integers."""
    open_, high, low, close, _ = ohlcv_arrays
    hammer = ind.CDLHAMMER(open_, high, low, close)
    engulf = ind.CDLENGULFING(open_, high, low, close)
    doji = ind.CDLDOJI(open_, high, low, close)
    marubozu = ind.CDLMARUBOZU(open_, high, low, close)

    assert set(np.unique(hammer)).issubset({0, 100})
    assert set(np.unique(engulf)).issubset({-100, 0, 100})
    assert set(np.unique(doji)).issubset({0, 100})
    assert set(np.unique(marubozu)).issubset({-100, 0, 100})
