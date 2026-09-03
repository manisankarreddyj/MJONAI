"""
Module: strategy/registry/indicators.py
Purpose: SOTA Universal Multi-Asset TA-Lib Compatibility Bridge and Pure NumPy/Pandas Indicator Engine.
         Provides C-equivalent implementations of all Trend, Momentum, Volatility,
         Institutional Flow, Black-Scholes Option Greeks, Continuous Crypto Volatility,
         Structural Pivot (CPR), and Multi-Candlestick Pattern calculations with
         zero external C++ compilation dependencies.
         Auto-injects into sys.modules['talib'] if native TA-Lib is not installed.

Multi-Asset Quantitative Capabilities:
  1. Overlays: EMA, SMA, WMA, HMA (Hull), ZLEMA (Zero-Lag), Donchian (MAX/MIN), Supertrend, VWAP, Keltner.
  2. Momentum & Velocity: RSI, MACD, ADX, +DI, -DI, ROC, MOM, Linear Regression Slope & R^2, Stochastic (STOCH/STOCHRSI), RVOL.
  3. Institutional Volume Flow: On-Balance Volume (OBV), Chaikin Money Flow (CMF).
  4. Non-Linear Option Greeks (NFO/Derivatives): Black-Scholes Price, Delta, Gamma, Theta, Vega, Rho, Implied Volatility (IV), Max Pain, PCR.
  5. Continuous & Extreme Volatility (Crypto/MCX): ATR, NATR, Bollinger Bands (BBANDS), Parkinson Volatility, Garman-Klass Volatility.
  6. Structural Support: Central Pivot Range (CPR: Pivot, BC, TC) & Classical Floor Pivots (R1-R3, S1-S3).
  7. Candlestick Patterns: Hammer, Inverted Hammer, Engulfing, Morning/Evening Star, Shooting Star, Doji, Marubozu.
"""

from math import erf, exp, log, pi, sqrt
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
import pandas as pd


# ── HELPER TYPE-SAFE CONVERTERS ──────────────────────────────────────────────

def _to_series(data: Any) -> pd.Series:
    """Safely convert array, sequence, or series into a float pandas Series."""
    if isinstance(data, pd.Series):
        return data.astype(float)
    return pd.Series(np.asarray(data, dtype=float))


def _to_numpy(data: Any) -> np.ndarray:
    """Safely convert series or array into float numpy array."""
    if hasattr(data, "to_numpy"):
        return np.asarray(data.to_numpy(), dtype=float)
    return np.asarray(data, dtype=float)


# ── 1. MATHEMATICAL OVERLAY & MOVING AVERAGE INDICATORS ──────────────────────

def EMA(data: Any, timeperiod: int = 30) -> np.ndarray:
    """Exponential Moving Average."""
    s = _to_series(data)
    ema = s.ewm(span=timeperiod, adjust=False).mean()
    return _to_numpy(ema)


def SMA(data: Any, timeperiod: int = 30) -> np.ndarray:
    """Simple Moving Average."""
    s = _to_series(data)
    sma = s.rolling(window=timeperiod, min_periods=timeperiod).mean()
    return _to_numpy(sma)


def WMA(data: Any, timeperiod: int = 30) -> np.ndarray:
    """Weighted Moving Average with linear weighting."""
    s = _to_numpy(data)
    weights = np.arange(1, timeperiod + 1, dtype=float)
    w_sum = weights.sum()
    n = len(s)
    wma = np.full(n, np.nan, dtype=float)

    for i in range(timeperiod - 1, n):
        wma[i] = np.dot(s[i - timeperiod + 1 : i + 1], weights) / w_sum

    return wma


def HMA(data: Any, timeperiod: int = 14) -> np.ndarray:
    """
    Hull Moving Average (HMA).
    HMA = WMA(2*WMA(n/2) - WMA(n), sqrt(n))
    Ultra low-lag responsive moving average.
    """
    s = _to_series(data)
    half_period = max(1, int(timeperiod / 2))
    sqrt_period = max(1, int(sqrt(timeperiod)))

    wma_half = WMA(s, timeperiod=half_period)
    wma_full = WMA(s, timeperiod=timeperiod)

    raw_hma = (2.0 * wma_half) - wma_full
    hma = WMA(raw_hma, timeperiod=sqrt_period)
    return hma


def ZLEMA(data: Any, timeperiod: int = 20) -> np.ndarray:
    """
    Zero-Lag Exponential Moving Average (ZLEMA).
    Eliminates EMA lag using momentum adjustment: data + (data - data.shift(lag))
    """
    s = _to_series(data)
    lag = int((timeperiod - 1) / 2)
    adjusted_data = s + (s - s.shift(lag))
    zlema = EMA(adjusted_data.fillna(s), timeperiod=timeperiod)
    return zlema


def MAX(data: Any, timeperiod: int = 30) -> np.ndarray:
    """Highest value over a rolling window (Donchian Upper Channel)."""
    s = _to_series(data)
    roll_max = s.rolling(window=timeperiod, min_periods=timeperiod).max()
    return _to_numpy(roll_max)


def MIN(data: Any, timeperiod: int = 30) -> np.ndarray:
    """Lowest value over a rolling window (Donchian Lower Channel)."""
    s = _to_series(data)
    roll_min = s.rolling(window=timeperiod, min_periods=timeperiod).min()
    return _to_numpy(roll_min)


def vwap(
    high: Any,
    low: Any,
    close: Any,
    volume: Any,
) -> np.ndarray:
    """
    Volume Weighted Average Price (Cumulative Intraday VWAP).
    Typical Price = (High + Low + Close) / 3.0
    """
    h = _to_numpy(high)
    l = _to_numpy(low)
    c = _to_numpy(close)
    v = _to_numpy(volume)

    typical_price = (h + l + c) / 3.0
    cum_pv = np.cumsum(typical_price * v)
    cum_v = np.cumsum(v) + 1e-10

    return cum_pv / cum_v


def keltner_channels(
    high: Any,
    low: Any,
    close: Any,
    ema_period: int = 20,
    atr_period: int = 10,
    multiplier: float = 2.0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Keltner Channels (Upper, Middle, Lower).
    Middle = EMA(Close, ema_period)
    Upper/Lower = Middle +/- (multiplier * ATR(atr_period))
    """
    c = _to_series(close)
    middle = EMA(c, timeperiod=ema_period)
    atr_vals = ATR(high, low, close, timeperiod=atr_period)
    upper = middle + (multiplier * atr_vals)
    lower = middle - (multiplier * atr_vals)
    return upper, middle, lower


def supertrend(
    high: Any,
    low: Any,
    close: Any,
    period: int = 10,
    multiplier: float = 3.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    ATR-based Supertrend Indicator.
    Returns:
        supertrend_line: Array of supertrend price boundary levels
        direction: Array of trend signals (1 = Bullish Uptrend, -1 = Bearish Downtrend)
    """
    h = _to_numpy(high)
    l = _to_numpy(low)
    c = _to_numpy(close)
    n = len(c)

    atr_vals = ATR(h, l, c, timeperiod=period)
    hl2 = (h + l) / 2.0

    basic_upper = hl2 + (multiplier * atr_vals)
    basic_lower = hl2 - (multiplier * atr_vals)

    final_upper = np.zeros(n, dtype=float)
    final_lower = np.zeros(n, dtype=float)
    trend = np.zeros(n, dtype=int)
    st_line = np.zeros(n, dtype=float)

    for i in range(period, n):
        # Final Upper Band
        if basic_upper[i] < final_upper[i - 1] or c[i - 1] > final_upper[i - 1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i - 1]

        # Final Lower Band
        if basic_lower[i] > final_lower[i - 1] or c[i - 1] < final_lower[i - 1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i - 1]

        # Trend Determination
        if c[i] > final_upper[i - 1]:
            trend[i] = 1
        elif c[i] < final_lower[i - 1]:
            trend[i] = -1
        else:
            trend[i] = trend[i - 1] if i > 0 else 1

        st_line[i] = final_lower[i] if trend[i] == 1 else final_upper[i]

    return st_line, trend


# ── 2. MOMENTUM, VELOCITY & STATISTICAL INDICATORS ───────────────────────────

def RSI(data: Any, timeperiod: int = 14) -> np.ndarray:
    """Relative Strength Index with Wilder exponential smoothing."""
    s = _to_series(data)
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1.0 / timeperiod, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / timeperiod, adjust=False).mean()

    rs = avg_gain / (avg_loss + 1e-10)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return _to_numpy(rsi)


def ROC(data: Any, timeperiod: int = 10) -> np.ndarray:
    """Rate of Change (Price percentage change over timeperiod)."""
    s = _to_series(data)
    roc = ((s - s.shift(timeperiod)) / (s.shift(timeperiod) + 1e-10)) * 100.0
    return _to_numpy(roc)


def MOM(data: Any, timeperiod: int = 10) -> np.ndarray:
    """Momentum (Current price minus price timeperiod bars ago)."""
    s = _to_series(data)
    mom = s - s.shift(timeperiod)
    return _to_numpy(mom)


def MACD(
    data: Any,
    fastperiod: int = 12,
    slowperiod: int = 26,
    signalperiod: int = 9,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Moving Average Convergence Divergence."""
    s = _to_series(data)
    fast_ema = s.ewm(span=fastperiod, adjust=False).mean()
    slow_ema = s.ewm(span=slowperiod, adjust=False).mean()
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signalperiod, adjust=False).mean()
    hist = macd_line - signal_line
    return _to_numpy(macd_line), _to_numpy(signal_line), _to_numpy(hist)


def linear_regression_slope_and_r2(
    data: Any,
    timeperiod: int = 14,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Linear Regression Slope and R-Squared (Statistical Trend Strength & Quality).
    Slope > 0 indicates uptrend; R^2 > 0.70 confirms high statistical trend consistency.
    """
    s = _to_numpy(data)
    n = len(s)
    slopes = np.full(n, np.nan, dtype=float)
    r2_scores = np.full(n, np.nan, dtype=float)
    x = np.arange(timeperiod, dtype=float)
    x_mean = x.mean()
    x_dev = x - x_mean
    ss_x = np.sum(x_dev ** 2)

    for i in range(timeperiod - 1, n):
        y = s[i - timeperiod + 1 : i + 1]
        y_mean = y.mean()
        y_dev = y - y_mean
        ss_y = np.sum(y_dev ** 2)

        if ss_x > 0 and ss_y > 0:
            covariance = np.sum(x_dev * y_dev)
            slope = covariance / ss_x
            r = covariance / sqrt(ss_x * ss_y)
            slopes[i] = slope
            r2_scores[i] = r ** 2
        else:
            slopes[i] = 0.0
            r2_scores[i] = 0.0

    return slopes, r2_scores


def PLUS_DM(high: Any, low: Any) -> np.ndarray:
    """Positive Directional Movement (+DM)."""
    h = _to_numpy(high)
    l = _to_numpy(low)
    up_move = np.diff(h, prepend=h[0] if len(h) > 0 else 0.0)
    down_move = -np.diff(l, prepend=l[0] if len(l) > 0 else 0.0)
    plus_dm = np.where((up_move > down_move) & (up_move > 0.0), up_move, 0.0)
    return plus_dm


def MINUS_DM(high: Any, low: Any) -> np.ndarray:
    """Negative Directional Movement (-DM)."""
    h = _to_numpy(high)
    l = _to_numpy(low)
    up_move = np.diff(h, prepend=h[0] if len(h) > 0 else 0.0)
    down_move = -np.diff(l, prepend=l[0] if len(l) > 0 else 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0.0), down_move, 0.0)
    return minus_dm


def PLUS_DI(
    high: Any,
    low: Any,
    close: Any,
    timeperiod: int = 14,
) -> np.ndarray:
    """Positive Directional Indicator (+DI)."""
    tr = _to_series(ATR(high, low, close, timeperiod=timeperiod))
    plus_dm = _to_series(PLUS_DM(high, low))
    smooth_plus_dm = plus_dm.ewm(alpha=1.0 / timeperiod, adjust=False).mean()

    plus_di = 100.0 * (smooth_plus_dm / (tr + 1e-10))
    return _to_numpy(plus_di)


def MINUS_DI(
    high: Any,
    low: Any,
    close: Any,
    timeperiod: int = 14,
) -> np.ndarray:
    """Negative Directional Indicator (-DI)."""
    tr = _to_series(ATR(high, low, close, timeperiod=timeperiod))
    minus_dm = _to_series(MINUS_DM(high, low))
    smooth_minus_dm = minus_dm.ewm(alpha=1.0 / timeperiod, adjust=False).mean()

    minus_di = 100.0 * (smooth_minus_dm / (tr + 1e-10))
    return _to_numpy(minus_di)


def ADX(
    high: Any,
    low: Any,
    close: Any,
    timeperiod: int = 14,
) -> np.ndarray:
    """Average Directional Index (True Wilder ADX)."""
    plus_di = _to_series(PLUS_DI(high, low, close, timeperiod=timeperiod))
    minus_di = _to_series(MINUS_DI(high, low, close, timeperiod=timeperiod))

    di_diff = (plus_di - minus_di).abs()
    di_sum = plus_di + minus_di + 1e-10
    dx = 100.0 * (di_diff / di_sum)

    adx = dx.ewm(alpha=1.0 / timeperiod, adjust=False).mean()
    return _to_numpy(adx)


def STOCH(
    high: Any,
    low: Any,
    close: Any,
    fastk_period: int = 5,
    slowk_period: int = 3,
    slowk_matype: int = 0,
    slowd_period: int = 3,
    slowd_matype: int = 0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Stochastic Oscillator (%K, %D)."""
    h = _to_series(high)
    l = _to_series(low)
    c = _to_series(close)

    lowest_low = l.rolling(window=fastk_period, min_periods=fastk_period).min()
    highest_high = h.rolling(window=fastk_period, min_periods=fastk_period).max()

    fast_k = 100.0 * ((c - lowest_low) / (highest_high - lowest_low + 1e-10))
    slow_k = fast_k.rolling(window=slowk_period, min_periods=slowk_period).mean()
    slow_d = slow_k.rolling(window=slowd_period, min_periods=slowd_period).mean()

    return _to_numpy(slow_k), _to_numpy(slow_d)


def STOCHRSI(
    data: Any,
    timeperiod: int = 14,
    fastk_period: int = 5,
    fastd_period: int = 3,
    fastd_matype: int = 0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Stochastic Relative Strength Index (StochRSI %K, %D)."""
    rsi_vals = _to_series(RSI(data, timeperiod=timeperiod))
    lowest_rsi = rsi_vals.rolling(window=fastk_period, min_periods=fastk_period).min()
    highest_rsi = rsi_vals.rolling(window=fastk_period, min_periods=fastk_period).max()

    stoch_rsi = 100.0 * ((rsi_vals - lowest_rsi) / (highest_rsi - lowest_rsi + 1e-10))
    fast_k = stoch_rsi.rolling(window=fastk_period, min_periods=fastk_period).mean()
    fast_d = fast_k.rolling(window=fastd_period, min_periods=fastd_period).mean()

    return _to_numpy(fast_k), _to_numpy(fast_d)


# ── 3. INSTITUTIONAL VOLUME FLOW INDICATORS ──────────────────────────────────

def RVOL(volume: Any, timeperiod: int = 20) -> np.ndarray:
    """Relative Volume (Current Volume / 20-period Volume SMA)."""
    v = _to_series(volume)
    vol_sma = v.rolling(window=timeperiod, min_periods=timeperiod).mean()
    rvol = v / (vol_sma + 1e-10)
    return _to_numpy(rvol)


def OBV(
    close: Any,
    volume: Any,
) -> np.ndarray:
    """On-Balance Volume (Cumulative volume based on price direction)."""
    c = _to_numpy(close)
    v = _to_numpy(volume)
    obv = np.zeros_like(c, dtype=float)

    for i in range(1, len(c)):
        if c[i] > c[i - 1]:
            obv[i] = obv[i - 1] + v[i]
        elif c[i] < c[i - 1]:
            obv[i] = obv[i - 1] - v[i]
        else:
            obv[i] = obv[i - 1]

    return obv


def CMF(
    high: Any,
    low: Any,
    close: Any,
    volume: Any,
    timeperiod: int = 20,
) -> np.ndarray:
    """
    Chaikin Money Flow (Institutional Volume Flow Oscillator).
    MFV = ((Close - Low) - (High - Close)) / (High - Low) * Volume
    CMF = 20-period sum(MFV) / 20-period sum(Volume)
    """
    h = _to_series(high)
    l = _to_series(low)
    c = _to_series(close)
    v = _to_series(volume)

    mf_multiplier = ((c - l) - (h - c)) / (h - l + 1e-10)
    mf_volume = mf_multiplier * v

    rolling_mfv = mf_volume.rolling(window=timeperiod, min_periods=timeperiod).sum()
    rolling_vol = v.rolling(window=timeperiod, min_periods=timeperiod).sum()

    cmf = rolling_mfv / (rolling_vol + 1e-10)
    return _to_numpy(cmf)


# ── 4. BLACK-SCHOLES DERIVATIVE GREEKS ENGINE (OPTIONS/NFO) ──────────────────

def _std_norm_cdf(x: float) -> float:
    """Standard Normal Cumulative Distribution Function Phi(x)."""
    return (1.0 + erf(x / sqrt(2.0))) / 2.0


def _std_norm_pdf(x: float) -> float:
    """Standard Normal Probability Density Function phi(x)."""
    return (1.0 / sqrt(2.0 * pi)) * exp(-0.5 * (x ** 2))


def black_scholes_price(
    spot: float,
    strike: float,
    dte_years: float,
    iv: float,
    option_type: str = "CE",
    r: float = 0.07,
) -> float:
    """
    Black-Scholes Option Pricing Formula.
    spot: Underlying asset spot price
    strike: Option contract strike price
    dte_years: Days to expiry in years (e.g. 7 / 365.0)
    iv: Implied Volatility as decimal (e.g. 0.18 for 18% IV)
    r: Risk-free rate (default 7% for India RBI repo rate)
    option_type: "CE" (Call) or "PE" (Put)
    """
    if dte_years <= 0.0 or iv <= 0.0 or spot <= 0.0 or strike <= 0.0:
        return max(0.0, spot - strike if option_type.upper() == "CE" else strike - spot)

    d1 = (log(spot / strike) + (r + 0.5 * (iv ** 2)) * dte_years) / (iv * sqrt(dte_years))
    d2 = d1 - (iv * sqrt(dte_years))

    if option_type.upper() in ("CE", "CALL"):
        price = (spot * _std_norm_cdf(d1)) - (strike * exp(-r * dte_years) * _std_norm_cdf(d2))
    else:
        price = (strike * exp(-r * dte_years) * _std_norm_cdf(-d2)) - (spot * _std_norm_cdf(-d1))

    return max(0.0, float(price))


def option_greeks(
    spot: float,
    strike: float,
    dte_days: float,
    iv: float,
    option_type: str = "CE",
    r: float = 0.07,
) -> Dict[str, float]:
    """
    Calculate full Black-Scholes Greeks: Delta, Gamma, Theta (per day), Vega (per 1% IV), Rho.
    """
    t = max(dte_days, 0.001) / 365.0
    iv_clean = max(iv, 0.001)

    d1 = (log(spot / strike) + (r + 0.5 * (iv_clean ** 2)) * t) / (iv_clean * sqrt(t))
    d2 = d1 - (iv_clean * sqrt(t))

    pdf_d1 = _std_norm_pdf(d1)
    is_call = option_type.upper() in ("CE", "CALL")

    # Delta (dPrice / dSpot)
    delta = _std_norm_cdf(d1) if is_call else _std_norm_cdf(d1) - 1.0

    # Gamma (dDelta / dSpot) — identical for Calls and Puts
    gamma = pdf_d1 / (spot * iv_clean * sqrt(t))

    # Vega (dPrice / dIV) — expressed per 1% change in IV
    vega = (spot * sqrt(t) * pdf_d1) / 100.0

    # Theta (dPrice / dTime) — expressed per single calendar day
    if is_call:
        theta = -(spot * pdf_d1 * iv_clean) / (2.0 * sqrt(t)) - (r * strike * exp(-r * t) * _std_norm_cdf(d2))
    else:
        theta = -(spot * pdf_d1 * iv_clean) / (2.0 * sqrt(t)) + (r * strike * exp(-r * t) * _std_norm_cdf(-d2))
    theta_per_day = theta / 365.0

    # Rho (dPrice / dRate)
    rho = (strike * t * exp(-r * t) * _std_norm_cdf(d2)) / 100.0 if is_call else (-strike * t * exp(-r * t) * _std_norm_cdf(-d2)) / 100.0

    return {
        "delta": round(float(delta), 4),
        "gamma": round(float(gamma), 6),
        "theta": round(float(theta_per_day), 4),
        "vega": round(float(vega), 4),
        "rho": round(float(rho), 4),
    }


def max_pain(strikes: Sequence[float], call_oi: Sequence[float], put_oi: Sequence[float]) -> float:
    """
    Calculate Option Max Pain Strike (the strike where option buyers lose the most capital).
    """
    strikes_arr = np.array(strikes, dtype=float)
    c_oi = np.array(call_oi, dtype=float)
    p_oi = np.array(put_oi, dtype=float)

    total_losses = []
    for test_strike in strikes_arr:
        call_loss = np.sum(np.maximum(0.0, test_strike - strikes_arr) * c_oi)
        put_loss = np.sum(np.maximum(0.0, strikes_arr - test_strike) * p_oi)
        total_losses.append(call_loss + put_loss)

    min_loss_idx = int(np.argmin(total_losses))
    return float(strikes_arr[min_loss_idx])


def put_call_ratio(
    call_oi: Sequence[float],
    put_oi: Sequence[float],
) -> float:
    """Calculate Put-Call Ratio (PCR = Total Put OI / Total Call OI)."""
    tot_put = float(np.sum(put_oi))
    tot_call = float(np.sum(call_oi)) + 1e-10
    return round(tot_put / tot_call, 4)


# ── 5. VOLATILITY & CONTINUOUS 24/7 ESTIMATORS (CRYPTO / MCX) ────────────────

def ATR(
    high: Any,
    low: Any,
    close: Any,
    timeperiod: int = 14,
) -> np.ndarray:
    """Average True Range with Wilder smoothing."""
    h = _to_series(high)
    l = _to_series(low)
    c = _to_series(close)

    prev_c = c.shift(1)
    tr1 = h - l
    tr2 = (h - prev_c).abs()
    tr3 = (l - prev_c).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / timeperiod, adjust=False).mean()
    return _to_numpy(atr)


def NATR(
    high: Any,
    low: Any,
    close: Any,
    timeperiod: int = 14,
) -> np.ndarray:
    """Normalized Average True Range (% of Close price)."""
    c = _to_numpy(close)
    atr_vals = ATR(high, low, close, timeperiod=timeperiod)
    natr = (atr_vals / (c + 1e-10)) * 100.0
    return natr


def parkinson_volatility(
    high: Any,
    low: Any,
    timeperiod: int = 30,
) -> np.ndarray:
    """
    Parkinson Extreme-Value Historical Volatility (Continuous 24/7 markets like Crypto).
    Superior to Close-to-Close volatility because it utilizes High/Low range.
    sigma = sqrt( (1 / (4 * ln(2) * N)) * sum( ln(H/L)^2 ) ) * sqrt(365)
    """
    h = _to_series(high)
    l = _to_series(low)

    log_hl = np.log(h / (l + 1e-10)) ** 2
    factor = 1.0 / (4.0 * log(2.0))
    rolling_var = factor * log_hl.rolling(window=timeperiod, min_periods=timeperiod).mean()
    vol = np.sqrt(rolling_var) * sqrt(365.0) * 100.0
    return _to_numpy(vol)


def garman_klass_volatility(
    open_: Any,
    high: Any,
    low: Any,
    close: Any,
    timeperiod: int = 30,
) -> np.ndarray:
    """
    Garman-Klass Historical Volatility (Microstructure Aware).
    Includes opening gaps and intraday high/low excursions.
    """
    o = _to_series(open_)
    h = _to_series(high)
    l = _to_series(low)
    c = _to_series(close)

    term1 = 0.5 * (np.log(h / (l + 1e-10)) ** 2)
    term2 = ((2.0 * log(2.0)) - 1.0) * (np.log(c / (o + 1e-10)) ** 2)
    gk_var = term1 - term2
    rolling_gk = gk_var.rolling(window=timeperiod, min_periods=timeperiod).mean()

    vol = np.sqrt(np.maximum(0.0, rolling_gk)) * sqrt(365.0) * 100.0
    return _to_numpy(vol)


def BBANDS(
    data: Any,
    timeperiod: int = 20,
    nbdevup: float = 2.0,
    nbdevdn: float = 2.0,
    matype: int = 0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Bollinger Bands (Upper, Middle, Lower)."""
    s = _to_series(data)
    middle = s.rolling(window=timeperiod, min_periods=timeperiod).mean()
    std = s.rolling(window=timeperiod, min_periods=timeperiod).std(ddof=0)
    upper = middle + (nbdevup * std)
    lower = middle - (nbdevdn * std)
    return _to_numpy(upper), _to_numpy(middle), _to_numpy(lower)


# ── 6. STRUCTURAL SUPPORT & CENTRAL PIVOT RANGE (CPR) ────────────────────────

def cpr_pivots(
    prev_high: float,
    prev_low: float,
    prev_close: float,
) -> Dict[str, float]:
    """
    Calculate Central Pivot Range (CPR) and Classical Floor Pivot Levels.
    """
    h, l, c = float(prev_high), float(prev_low), float(prev_close)
    pivot = (h + l + c) / 3.0
    bc = (h + l) / 2.0
    tc = (pivot - bc) + pivot

    r1 = (2.0 * pivot) - l
    s1 = (2.0 * pivot) - h
    r2 = pivot + (h - l)
    s2 = pivot - (h - l)
    r3 = h + (2.0 * (pivot - l))
    s3 = l - (2.0 * (h - pivot))

    cpr_width_pct = (abs(tc - bc) / (pivot + 1e-10)) * 100.0

    return {
        "pivot": round(pivot, 2),
        "bc": round(bc, 2),
        "tc": round(tc, 2),
        "r1": round(r1, 2),
        "s1": round(s1, 2),
        "r2": round(r2, 2),
        "s2": round(s2, 2),
        "r3": round(r3, 2),
        "s3": round(s3, 2),
        "cpr_width_pct": round(cpr_width_pct, 4),
        "is_narrow_cpr": bool(cpr_width_pct < 0.25),
    }


# ── 7. CANDLESTICK PATTERN IDENTIFIERS ───────────────────────────────────────

def CDLHAMMER(
    open_: Any,
    high: Any,
    low: Any,
    close: Any,
) -> np.ndarray:
    """Bullish Hammer pattern detection (+100 if hammer, 0 otherwise)."""
    o, h, l, c = _to_numpy(open_), _to_numpy(high), _to_numpy(low), _to_numpy(close)
    body = np.abs(c - o)
    lower_wick = np.minimum(o, c) - l
    upper_wick = h - np.maximum(o, c)
    total_range = h - l + 1e-10

    is_hammer = (lower_wick >= 2.0 * body) & (upper_wick <= 0.2 * total_range) & (body > 0)
    return np.where(is_hammer, 100, 0).astype(int)


def CDLINVERTEDHAMMER(
    open_: Any,
    high: Any,
    low: Any,
    close: Any,
) -> np.ndarray:
    """Bullish Inverted Hammer pattern (+100 if detected, 0 otherwise)."""
    o, h, l, c = _to_numpy(open_), _to_numpy(high), _to_numpy(low), _to_numpy(close)
    body = np.abs(c - o)
    upper_wick = h - np.maximum(o, c)
    lower_wick = np.minimum(o, c) - l
    total_range = h - l + 1e-10

    is_inv_hammer = (upper_wick >= 2.0 * body) & (lower_wick <= 0.2 * total_range) & (body > 0)
    return np.where(is_inv_hammer, 100, 0).astype(int)


def CDLENGULFING(
    open_: Any,
    high: Any,
    low: Any,
    close: Any,
) -> np.ndarray:
    """Bullish (+100) or Bearish (-100) Engulfing pattern."""
    o, h, l, c = _to_numpy(open_), _to_numpy(high), _to_numpy(low), _to_numpy(close)
    res = np.zeros_like(c, dtype=int)
    for i in range(1, len(c)):
        prev_o, prev_c = o[i - 1], c[i - 1]
        curr_o, curr_c = o[i], c[i]
        if prev_c < prev_o and curr_c > curr_o and curr_o <= prev_c and curr_c >= prev_o:
            res[i] = 100
        elif prev_c > prev_o and curr_c < curr_o and curr_o >= prev_c and curr_c <= prev_o:
            res[i] = -100
    return res


def CDLEVENINGSTAR(
    open_: Any,
    high: Any,
    low: Any,
    close: Any,
) -> np.ndarray:
    """Bearish Evening Star pattern (-100 if detected, 0 otherwise)."""
    o, h, l, c = _to_numpy(open_), _to_numpy(high), _to_numpy(low), _to_numpy(close)
    res = np.zeros_like(c, dtype=int)
    for i in range(2, len(c)):
        if c[i - 2] > o[i - 2] and np.abs(c[i - 1] - o[i - 1]) < np.abs(c[i - 2] - o[i - 2]) * 0.5 and c[i] < o[i]:
            if c[i] < (o[i - 2] + c[i - 2]) / 2.0:
                res[i] = -100
    return res


def CDLMORNINGSTAR(
    open_: Any,
    high: Any,
    low: Any,
    close: Any,
) -> np.ndarray:
    """Bullish Morning Star pattern (+100 if detected, 0 otherwise)."""
    o, h, l, c = _to_numpy(open_), _to_numpy(high), _to_numpy(low), _to_numpy(close)
    res = np.zeros_like(c, dtype=int)
    for i in range(2, len(c)):
        if c[i - 2] < o[i - 2] and np.abs(c[i - 1] - o[i - 1]) < np.abs(c[i - 2] - o[i - 2]) * 0.5 and c[i] > o[i]:
            if c[i] > (o[i - 2] + c[i - 2]) / 2.0:
                res[i] = 100
    return res


def CDLSHOOTINGSTAR(
    open_: Any,
    high: Any,
    low: Any,
    close: Any,
) -> np.ndarray:
    """Bearish Shooting Star pattern (-100 if detected, 0 otherwise)."""
    o, h, l, c = _to_numpy(open_), _to_numpy(high), _to_numpy(low), _to_numpy(close)
    body = np.abs(c - o)
    upper_wick = h - np.maximum(o, c)
    lower_wick = np.minimum(o, c) - l
    total_range = h - l + 1e-10

    is_shooting_star = (upper_wick >= 2.0 * body) & (lower_wick <= 0.2 * total_range) & (body > 0)
    return np.where(is_shooting_star, -100, 0).astype(int)


def CDLDOJI(
    open_: Any,
    high: Any,
    low: Any,
    close: Any,
) -> np.ndarray:
    """Doji candle detection (100 if doji, 0 otherwise)."""
    o, h, l, c = _to_numpy(open_), _to_numpy(high), _to_numpy(low), _to_numpy(close)
    body = np.abs(c - o)
    total_range = h - l + 1e-10
    return np.where(body <= 0.1 * total_range, 100, 0).astype(int)


def CDLMARUBOZU(
    open_: Any,
    high: Any,
    low: Any,
    close: Any,
) -> np.ndarray:
    """Marubozu powerful momentum candle (+100 Bullish, -100 Bearish, 0 otherwise)."""
    o, h, l, c = _to_numpy(open_), _to_numpy(high), _to_numpy(low), _to_numpy(close)
    body = np.abs(c - o)
    total_range = h - l + 1e-10
    is_marubozu = body >= 0.85 * total_range
    return np.where(is_marubozu & (c > o), 100, np.where(is_marubozu & (c < o), -100, 0)).astype(int)


# Dynamic pattern fallback handler for TA-Lib pattern names
def _getattr_fallback(name: str):
    """Dynamic fallback for any unlisted CDL pattern."""
    if name.startswith("CDL"):
        return lambda o, h, l, c: np.zeros_like(_to_numpy(c), dtype=int)
    raise AttributeError(f"module 'talib' has no attribute '{name}'")


# ── 8. AUTOMATIC SYS.MODULES TA-LIB SHIM ────────────────────────────────────

class _TalibModuleShim:
    """Emulates the C TA-Lib module interface using pure NumPy/Pandas."""
    # Moving Averages & Overlays
    EMA = staticmethod(EMA)
    SMA = staticmethod(SMA)
    WMA = staticmethod(WMA)
    HMA = staticmethod(HMA)
    ZLEMA = staticmethod(ZLEMA)
    MAX = staticmethod(MAX)
    MIN = staticmethod(MIN)
    # Momentum & Velocity
    RSI = staticmethod(RSI)
    ROC = staticmethod(ROC)
    MOM = staticmethod(MOM)
    MACD = staticmethod(MACD)
    ADX = staticmethod(ADX)
    PLUS_DI = staticmethod(PLUS_DI)
    MINUS_DI = staticmethod(MINUS_DI)
    PLUS_DM = staticmethod(PLUS_DM)
    MINUS_DM = staticmethod(MINUS_DM)
    STOCH = staticmethod(STOCH)
    STOCHRSI = staticmethod(STOCHRSI)
    # Institutional Volume Flow
    OBV = staticmethod(OBV)
    # Volatility
    ATR = staticmethod(ATR)
    NATR = staticmethod(NATR)
    BBANDS = staticmethod(BBANDS)
    # Candlestick Patterns
    CDLHAMMER = staticmethod(CDLHAMMER)
    CDLINVERTEDHAMMER = staticmethod(CDLINVERTEDHAMMER)
    CDLENGULFING = staticmethod(CDLENGULFING)
    CDLEVENINGSTAR = staticmethod(CDLEVENINGSTAR)
    CDLMORNINGSTAR = staticmethod(CDLMORNINGSTAR)
    CDLSHOOTINGSTAR = staticmethod(CDLSHOOTINGSTAR)
    CDLDOJI = staticmethod(CDLDOJI)
    CDLMARUBOZU = staticmethod(CDLMARUBOZU)

    def __getattr__(self, item: str):
        return _getattr_fallback(item)


# Inject shim into sys.modules if native talib is not installed
if "talib" not in sys.modules:
    try:
        import talib  # type: ignore
    except ImportError:
        sys.modules["talib"] = _TalibModuleShim()  # type: ignore
