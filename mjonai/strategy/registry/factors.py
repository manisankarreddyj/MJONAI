"""
Module: strategy/registry/factors.py
Purpose: Pre-registered cross-sectional equity factors for multi-factor strategies.

These are pure NumPy/Pandas factor functions with no external dependencies.
Designed for cross-sectional ranking within a universe (dates x symbols panel).

Each factor function takes a panel (dates x symbols) DataFrame and returns
a DataFrame of the same shape with factor values. NaN handling is the
caller's responsibility.

Inspired by qlib's Alpha158/Alpha360 and Qbot's cross_sectional.py — clean-room reimplementation.
"""

from __future__ import annotations

from typing import Dict, Any

import numpy as np
import pandas as pd


def _mom(panel: pd.DataFrame, lookback: int, skip: int) -> pd.DataFrame:
    """Momentum: (Price_t-skip / Price_t-lookback) - 1."""
    return panel.shift(skip) / panel.shift(lookback) - 1.0


def factor_momentum_12_1(panel: pd.DataFrame) -> pd.DataFrame:
    """12-month momentum skipping 1 month (standard 12-1 momentum)."""
    return _mom(panel, 252, 21)


def factor_momentum_6_1(panel: pd.DataFrame) -> pd.DataFrame:
    """6-month momentum skipping 1 month."""
    return _mom(panel, 126, 21)


def factor_momentum_3_12(panel: pd.DataFrame) -> pd.DataFrame:
    """3-12 momentum (intermediate-term momentum)."""
    return _mom(panel, 252, 63)


def factor_momentum_12(panel: pd.DataFrame) -> pd.DataFrame:
    """12-month momentum (no skip)."""
    return _mom(panel, 252, 0)


def factor_momentum_6(panel: pd.DataFrame) -> pd.DataFrame:
    """6-month momentum (no skip)."""
    return _mom(panel, 126, 0)


def factor_reversal_1(panel: pd.DataFrame) -> pd.DataFrame:
    """Short-term reversal (1-month momentum, expect negative)."""
    return _mom(panel, 21, 0)


def factor_reversal_3(panel: pd.DataFrame) -> pd.DataFrame:
    """3-month reversal."""
    return _mom(panel, 63, 0)


def factor_low_vol(panel: pd.DataFrame) -> pd.DataFrame:
    """Low volatility (negative rolling std -> high rank = low vol)."""
    r = panel.pct_change()
    return -r.rolling(60, min_periods=40).std()


def factor_trend_strength(panel: pd.DataFrame) -> pd.DataFrame:
    """Trend strength: fraction of positive days over 1 year."""
    r = (panel > panel.shift(1)).astype(float)
    return r.rolling(252, min_periods=120).mean()


def factor_low_vol_120(panel: pd.DataFrame) -> pd.DataFrame:
    """Low volatility (120-day window)."""
    r = panel.pct_change()
    return -r.rolling(120, min_periods=80).std()


def factor_low_vol_250(panel: pd.DataFrame) -> pd.DataFrame:
    """Low volatility (250-day window)."""
    r = panel.pct_change()
    return -r.rolling(250, min_periods=150).std()


def factor_lowvol_mom(panel: pd.DataFrame) -> pd.DataFrame:
    """Combined low-vol + momentum (rank-average of the two best standalone factors)."""
    from mjonai.strategy.registry.factors import factor_low_vol
    lv = _zrank(factor_low_vol(panel))
    mm = _zrank(_mom(panel, 126, 0))
    return (lv + mm) / 2.0


def factor_lowvol_rev(panel: pd.DataFrame) -> pd.DataFrame:
    """Low-vol combined with short-term reversal."""
    from mjonai.strategy.registry.factors import factor_low_vol
    lv = _zrank(factor_low_vol(panel))
    rv = _zrank(factor_reversal_1(panel))
    return (lv + rv) / 2.0


def _zrank(x: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional rank normalization (percentile rank 0-1)."""
    return x.rank(axis=1, pct=True)


# Pre-registered factor registry (name -> function of the panel).
# This is the trial universe that the Deflated Sharpe pays for.
FACTORS = {
    "mom_12_1": factor_momentum_12_1,
    "mom_6_1": factor_momentum_6_1,
    "mom_3_12": factor_momentum_3_12,
    "mom_12": factor_momentum_12,
    "mom_6": factor_momentum_6,
    "rev_1": factor_reversal_1,
    "rev_3": factor_reversal_3,
    "low_vol": factor_low_vol,
    "trend_strength": factor_trend_strength,
    "low_vol_120": factor_low_vol_120,
    "low_vol_250": factor_low_vol_250,
    "lowvol_mom": factor_lowvol_mom,
    "lowvol_rev": factor_lowvol_rev,
}

# Factor metadata for config
FACTOR_METADATA = {
    "mom_12_1": {"description": "12-month momentum skipping 1 month", "category": "momentum"},
    "mom_6_1": {"description": "6-month momentum skipping 1 month", "category": "momentum"},
    "mom_3_12": {"description": "3-12 month momentum", "category": "momentum"},
    "mom_12": {"description": "12-month momentum", "category": "momentum"},
    "mom_6": {"description": "6-month momentum", "category": "momentum"},
    "rev_1": {"description": "1-month reversal", "category": "reversal"},
    "rev_3": {"description": "3-month reversal", "category": "reversal"},
    "low_vol": {"description": "Low volatility (60d)", "category": "volatility"},
    "trend_strength": {"description": "Trend consistency (1y positive day fraction)", "category": "trend"},
    "low_vol_120": {"description": "Low volatility (120d)", "category": "volatility"},
    "low_vol_250": {"description": "Low volatility (250d)", "category": "volatility"},
    "lowvol_mom": {"description": "Low-vol + momentum combo", "category": "combo"},
    "lowvol_rev": {"description": "Low-vol + reversal combo", "category": "combo"},
}


def _zrank(x: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional rank normalization (percentile rank 0-1)."""
    return x.rank(axis=1, pct=True)


def _zscore_cross_section(series: pd.Series) -> pd.Series:
    """Cross-sectional z-score normalization (mean=0, std=1) per bar."""
    mean = series.mean()
    std = series.std(ddof=0)
    if std < 1e-12:
        return pd.Series(0.0, index=series.index)
    return (series - mean) / std