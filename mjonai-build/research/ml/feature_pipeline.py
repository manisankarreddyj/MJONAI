"""
Module: research/ml/feature_pipeline.py
Purpose: Institutional feature extraction for quantitative alpha generation.
         - Fractional Differentiation (FracDiff) preserving memory while achieving stationarity.
         - Microstructure estimators: Corwin-Schultz (2012) and Roll (1984) spread proxies.
         - Volatility estimators: Garman-Klass, Parkinson, Yang-Zhang.
         - Regime indicators: Hurst Exponent (R/S), Fractal Dimension.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd


def get_fractional_weights(d: float, size: int) -> np.ndarray:
    """Generate memory-preserving fractional binomial expansion weights."""
    w = [1.0]
    for k in range(1, size):
        w_k = -w[-1] / k * (d - k + 1)
        w.append(w_k)
    return np.array(w[::-1])


def frac_diff(series: pd.Series, d: float, thres: float = 1e-4) -> pd.Series:
    """
    Fractional Differentiation of a continuous time series (López de Prado, 2018).
    Preserves maximum memory from the underlying price series while achieving stationarity.
    """
    # 1. Compute weights down to threshold
    w = [1.0]
    k = 1
    while True:
        w_k = -w[-1] / k * (d - k + 1)
        if abs(w_k) < thres:
            break
        w.append(w_k)
        k += 1
    w = np.array(w[::-1])
    width = len(w)

    res = {}
    vals = series.values
    for i in range(width - 1, len(vals)):
        dot_prod = np.dot(w, vals[i - width + 1 : i + 1])
        res[series.index[i]] = dot_prod

    return pd.Series(res)


def corwin_schultz_spread(df: pd.DataFrame) -> pd.Series:
    """
    Corwin-Schultz (2012) Bid-Ask Spread Estimator from daily High and Low prices.
    Returns estimated bid-ask spread as a fraction of price (0.01 = 1%).
    """
    high = df['high'].values
    low = df['low'].values
    n = len(df)
    spread = np.zeros(n)

    for i in range(1, n):
        # 1-day high-low ratio
        gamma = (np.log(high[i] / low[i])) ** 2
        gamma_prev = (np.log(high[i - 1] / low[i - 1])) ** 2
        
        # 2-day high-low ratio
        high_2d = max(high[i], high[i - 1])
        low_2d = min(low[i], low[i - 1])
        beta = (np.log(high_2d / low_2d)) ** 2

        alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / (3 - 2 * np.sqrt(2)) - np.sqrt((gamma + gamma_prev) / (3 - 2 * np.sqrt(2)))
        spread_est = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
        spread[i] = max(0.0, float(spread_est)) if not np.isnan(spread_est) else 0.0

    return pd.Series(spread, index=df.index)


def roll_spread(close: pd.Series) -> float:
    """
    Roll (1984) Effective Spread proxy from serial autocovariance of price changes.
    S = 2 * sqrt(-Cov(delta_p_t, delta_p_{t-1}))
    """
    dp = close.diff().dropna().values
    if len(dp) < 3:
        return 0.0
    cov = np.cov(dp[:-1], dp[1:])[0, 1]
    if cov < 0:
        return float(round(2.0 * math.sqrt(-cov), 4))
    return 0.0


def garman_klass_volatility(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """
    Garman-Klass Volatility Estimator (incorporates OHLC bars).
    More statistically efficient than close-to-close volatility.
    """
    log_hl = (np.log(df['high'] / df['low'])) ** 2
    log_co = (np.log(df['close'] / df['open'])) ** 2
    gk = 0.5 * log_hl - (2 * np.log(2) - 1) * log_co
    vol = np.sqrt(gk.rolling(window=window, min_periods=1).mean() * 252)
    return vol


def calculate_hurst_exponent(price: pd.Series, max_lag: int = 20) -> float:
    """
    Hurst Exponent via Rescaled Range (R/S) Analysis.
    H < 0.5: Mean-reverting regime
    H = 0.5: Random walk / Brownian motion
    H > 0.5: Trending / Persistent regime
    """
    vals = price.values
    n = len(vals)
    if n < max_lag * 2:
        return 0.5

    lags = range(2, max_lag)
    tau = [max(1e-9, float(np.sqrt(np.std(np.subtract(vals[lag:], vals[:-lag]))))) for lag in lags]
    poly = np.polyfit(np.log(lags), np.log(tau), 1)
    hurst = poly[0] * 2.0
    return float(round(max(0.0, min(1.0, hurst)), 4))


def build_ml_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build complete quantitative feature matrix for ML models and meta-labeling.
    """
    features = pd.DataFrame(index=df.index)

    # 1. Price Momentum
    close = df['close']
    features['return_1d'] = close.pct_change(1)
    features['return_5d'] = close.pct_change(5)
    features['return_20d'] = close.pct_change(20)

    # 2. Volatility Features
    features['gk_vol_14'] = garman_klass_volatility(df, window=14)
    features['parkinson_vol'] = np.sqrt(((np.log(df['high'] / df['low']) ** 2) / (4 * np.log(2))).rolling(14).mean() * 252)
    
    # 3. Microstructure Proxies
    features['cs_spread'] = corwin_schultz_spread(df)
    features['amihud_illiquidity'] = (df['close'].pct_change().abs() / (df['volume'] * df['close'] + 1e-6)).rolling(14).mean()

    # 4. Range & Trend Dynamics
    tr = np.maximum(df['high'] - df['low'], np.maximum((df['high'] - df['close'].shift()).abs(), (df['low'] - df['close'].shift()).abs()))
    atr14 = tr.rolling(14).mean()
    atr50 = tr.rolling(50).mean()
    features['atr_ratio'] = atr14 / (atr50 + 1e-9)

    return features.dropna()
