"""
Module: strategy/registry/quant_math.py
Purpose: SOTA Quantitative Mathematical Models & Statistical Microstructure Estimators.
         Features:
         1. Hurst Exponent (H): Rescaled Range (R/S) Structural Regime Memory Classifier
         2. Yang-Zhang Realized Volatility (2000): Minimum-variance unbiased multi-period volatility
         3. 1D Recursive State-Space Kalman Filter: Zero-lag adaptive trend & velocity estimation
         4. Amihud Illiquidity Ratio (2002): Cross-asset price impact & liquidity shock sentry
         5. Corwin-Schultz (2012): High-Low Bid-Ask Spread Estimator
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd


def _to_numpy(data: Any) -> np.ndarray:
    if hasattr(data, "to_numpy"):
        return np.asarray(data.to_numpy(), dtype=float)
    return np.asarray(data, dtype=float)


# ── 1. HURST EXPONENT (STRUCTURAL REGIME CLASSIFIER) ─────────────────────────

def calculate_hurst_exponent(
    price_series: Any,
    min_lag: int = 10,
    max_lag: int = 100,
) -> float:
    """
    Calculate the Hurst Exponent (H) via Rescaled Range (R/S) analysis.

    Interpretation:
      - H < 0.45: Anti-Persistent / Mean-Reverting Regime (Ideal for S01 RSI, S04 Mean Reversion)
      - 0.45 <= H <= 0.55: Geometric Brownian Motion / Random Walk (Ideal for S09 Options Theta Decay)
      - H > 0.55: Persistent / Strong Trending Momentum (Ideal for S03 Turtle Breakout, S10 Momentum)
    """
    prices = _to_numpy(price_series)
    if len(prices) < max_lag:
        return 0.50

    # Log returns
    returns = np.diff(np.log(np.maximum(1e-6, prices)))
    n = len(returns)
    lags = np.unique(np.logspace(np.log10(min_lag), np.log10(min(max_lag, n // 2)), num=10).astype(int))

    rs_values = []
    valid_lags = []

    for lag in lags:
        if lag < 2 or lag > n:
            continue
        # Split into chunks of size lag
        num_chunks = n // lag
        if num_chunks < 1:
            continue

        chunk_rs = []
        for c in range(num_chunks):
            sub = returns[c * lag : (c + 1) * lag]
            sub_mean = np.mean(sub)
            dev = sub - sub_mean
            cum_dev = np.cumsum(dev)
            r = np.max(cum_dev) - np.min(cum_dev)
            s = np.std(sub, ddof=1)
            if s > 1e-10 and r > 0:
                chunk_rs.append(r / s)

        if chunk_rs:
            rs_values.append(np.mean(chunk_rs))
            valid_lags.append(lag)

    if len(valid_lags) < 3:
        return 0.50

    # Fit line: log(R/S) = H * log(lag) + c
    log_lags = np.log(valid_lags)
    log_rs = np.log(rs_values)
    poly = np.polyfit(log_lags, log_rs, 1)
    h_val = float(poly[0])

    return max(0.0, min(1.0, round(h_val, 4)))


# ── 2. YANG-ZHANG REALIZED VOLATILITY (2000) ──────────────────────────────────

def yang_zhang_volatility(
    open_: Any,
    high: Any,
    low: Any,
    close: Any,
    timeperiod: int = 20,
    trading_periods_per_year: int = 252,
) -> np.ndarray:
    """
    Yang-Zhang (2000) Minimum-Variance Unbiased Realized Volatility Estimator.
    Handles overnight price jumps, continuous drift, and intraday high-low range.

    Formula:
        sigma^2 = sigma_open^2 + k * sigma_close^2 + (1-k) * sigma_RS^2
        k = 0.34 / (1.34 + (n+1)/(n-1))
    """
    o = pd.Series(_to_numpy(open_))
    h = pd.Series(_to_numpy(high))
    l = pd.Series(_to_numpy(low))
    c = pd.Series(_to_numpy(close))

    prev_c = c.shift(1)

    # 1. Overnight jump variance (open / prev_close)
    log_oc = np.log(np.maximum(1e-6, o) / np.maximum(1e-6, prev_c))
    var_open = log_oc.rolling(window=timeperiod, min_periods=timeperiod).var(ddof=1)

    # 2. Open to Close variance (close / open)
    log_co = np.log(np.maximum(1e-6, c) / np.maximum(1e-6, o))
    var_close = log_co.rolling(window=timeperiod, min_periods=timeperiod).var(ddof=1)

    # 3. Rogers-Satchell drift-independent variance
    log_ho = np.log(np.maximum(1e-6, h) / np.maximum(1e-6, o))
    log_hc = np.log(np.maximum(1e-6, h) / np.maximum(1e-6, c))
    log_lo = np.log(np.maximum(1e-6, l) / np.maximum(1e-6, o))
    log_lc = np.log(np.maximum(1e-6, l) / np.maximum(1e-6, c))

    rs_term = (log_ho * log_hc) + (log_lo * log_lc)
    var_rs = rs_term.rolling(window=timeperiod, min_periods=timeperiod).mean()

    # Weighting parameter k
    k = 0.34 / (1.34 + ((timeperiod + 1.0) / (timeperiod - 1.0)))

    yz_var = var_open + (k * var_close) + ((1.0 - k) * var_rs)
    yz_vol = np.sqrt(np.maximum(0.0, yz_var)) * math.sqrt(trading_periods_per_year) * 100.0

    return yz_vol.to_numpy()


# ── 3. 1D RECURSIVE STATE-SPACE KALMAN FILTER ────────────────────────────────

def kalman_filter_1d(
    prices: Any,
    process_noise: float = 1e-4,
    measurement_noise: float = 1e-2,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    1D Recursive Adaptive Kalman Filter.
    Estimates the true latent asset price and instantaneous trend velocity with zero lookahead bias.

    Returns:
        (filtered_price, velocity)
    """
    p = _to_numpy(prices)
    n = len(p)
    filtered = np.zeros(n, dtype=float)
    velocity = np.zeros(n, dtype=float)

    if n == 0:
        return filtered, velocity

    # Initialize state
    x_est = p[0]
    p_est = 1.0

    for t in range(n):
        z = p[t]
        # Predict step
        x_pred = x_est
        p_pred = p_est + process_noise

        # Update step
        k_gain = p_pred / (p_pred + measurement_noise)
        x_est = x_pred + k_gain * (z - x_pred)
        p_est = (1.0 - k_gain) * p_pred

        filtered[t] = x_est
        velocity[t] = x_est - filtered[t - 1] if t > 0 else 0.0

    return filtered, velocity


# ── 4. AMIHUD ILLIQUIDITY RATIO (2002) ───────────────────────────────────────

def amihud_illiquidity_ratio(
    close: Any,
    volume: Any,
    timeperiod: int = 20,
) -> np.ndarray:
    """
    Amihud (2002) Microstructure Illiquidity Ratio.
    Measures absolute percentage price change per million rupees turnover:
    ILLIQ = (|Return_t| / (Price_t * Volume_t)) * 1e6
    High ILLIQ indicates wide spreads, poor order book depth, and high slippage penalty.
    """
    c = pd.Series(_to_numpy(close))
    v = pd.Series(_to_numpy(volume))

    ret = c.pct_change().abs()
    turnover = c * v + 1e-6
    raw_illiq = (ret / turnover) * 1e6

    illiq_ma = raw_illiq.rolling(window=timeperiod, min_periods=timeperiod).mean()
    return illiq_ma.to_numpy()


# ── 5. CORWIN-SCHULTZ SPREAD ESTIMATOR (2012) ────────────────────────────────

def corwin_schultz_spread(
    high: Any,
    low: Any,
    timeperiod: int = 14,
) -> np.ndarray:
    """
    Corwin-Schultz (2012) High-Low Bid-Ask Spread Estimator (in basis points).
    Extracts effective bid-ask spread directly from 2-period daily high and low range.
    """
    h = pd.Series(_to_numpy(high))
    l = pd.Series(_to_numpy(low))

    gamma = (np.log(h / np.maximum(1e-6, l)) ** 2).rolling(2).sum()
    h2 = h.rolling(2).max()
    l2 = l.rolling(2).min()
    beta = np.log(h2 / np.maximum(1e-6, l2)) ** 2

    k2 = 8.0 / math.pi
    alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / (3.0 - (2.0 * np.sqrt(2.0))) - np.sqrt(gamma / (3.0 - (2.0 * np.sqrt(2.0))))
    spread = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha)) * 10000.0  # in basis points

    spread_ma = pd.Series(np.maximum(0.0, spread)).rolling(window=timeperiod, min_periods=timeperiod).mean()
    return spread_ma.to_numpy()


# ── 6. MARCOS LÓPEZ DE PRADO FRACTIONAL DIFFERENTIATION ───────────────────────

def fractional_differentiation_weights(d: float, size: int) -> np.ndarray:
    """
    Generate binomial expansion weights for fractional differentiation of order d.
    w_0 = 1, w_k = -w_{k-1} * (d - k + 1) / k
    """
    w = [1.0]
    for k in range(1, size):
        w_k = -w[-1] / float(k) * (d - float(k) + 1.0)
        w.append(w_k)
    return np.array(w[::-1])


def fractional_differentiation(series: np.ndarray, d: float = 0.40, threshold: float = 1e-4) -> np.ndarray:
    """
    Apply fractional differentiation of order d to preserve maximal memory while achieving stationarity.
    (Marcos López de Prado - Advances in Financial Machine Learning, Chapter 5).
    """
    arr = np.asarray(series, dtype=float)
    if len(arr) < 10:
        return arr

    weights = fractional_differentiation_weights(d, len(arr))
    # Filter small weights to truncate memory window
    weights = weights[np.abs(weights) >= threshold]
    w_len = len(weights)
    if w_len > len(arr):
        w_len = len(arr)
        weights = weights[-w_len:]

    res = np.convolve(arr, weights, mode="valid")
    # Pad leading with NaNs to match original length
    pad = np.full(len(arr) - len(res), np.nan)
    return np.concatenate([pad, res])


# ── 7. REALIZED SEMI-VARIANCE (GOOD VS BAD VOLATILITY) ────────────────────────

def realized_semivariance(returns: np.ndarray) -> Tuple[float, float, float]:
    """
    Decompose total realized variance into Upside (Good) and Downside (Bad) Semi-Variance.
    (Barndorff-Nielsen, Kinnebrock, and Shephard, 2010).
    Returns: (Total Realized Volatility, Upside Vol RS+, Downside Vol RS-)
    """
    r = np.asarray(returns, dtype=float)
    if len(r) == 0:
        return 0.0, 0.0, 0.0

    pos_r = np.where(r > 0, r, 0.0)
    neg_r = np.where(r < 0, r, 0.0)

    rs_plus = float(np.sqrt(np.sum(pos_r ** 2)))
    rs_minus = float(np.sqrt(np.sum(neg_r ** 2)))
    total_vol = float(np.sqrt(np.sum(r ** 2)))

    return total_vol, rs_plus, rs_minus


# ── 8. DEFLECTED SHARPE RATIO ──────────────────────────────────────────────────
# The Deflated Sharpe Ratio that used to live here as `deflated_sharpe_ratio`
# was consolidated 2026-10-04 into the canonical Sharpe-validation home,
# `mjonai.analytics.statistical_validation`, as `deflated_sharpe_pvalue`.
#
# It was removed rather than shimmed because the two implementations were NOT
# drop-in equivalents: this one took a precomputed Sharpe and returned a
# p-VALUE in [0, 1], while the canonical `deflated_sharpe_ratio` takes a return
# series and returns an unbounded z-SCORE. A delegating shim could not have
# preserved both signatures and meanings honestly, and two same-named
# functions with different return types is a live misreading trap.
# Import `deflated_sharpe_ratio` (z-score) or `deflated_sharpe_pvalue` from
# `mjonai.analytics.statistical_validation` instead.
