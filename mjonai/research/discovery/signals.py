"""
Module: research/discovery/signals.py
Purpose: Pre-registered, DISTINCT low-turnover index signal families.

Each family is a genuinely different hypothesis about where (or whether) a
cost-viable index edge exists, NOT a parameter variant of another. This
separation is the whole point: the 2026-09-26 intraday battery tested 18
"configurations" that were really only ~4 ideas, and all failed net. Here we
register ~6-7 honest ideas and let the deflated-Sharpe gate judge them.

Signal contract: ``fn(df, params) -> pd.Series`` of target position in
{-1, 0, +1} decided on the CLOSE of each bar (the harness applies it one bar
later, so no lookahead). Index is df.index (trade_date). Column 'close'/'high'
/'low' available.
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# A1. Time-series momentum: long when trailing N-day return exceeds a threshold.
#      The single most robust documented anomaly class (Moskowitz et al.).
# ---------------------------------------------------------------------------
def sig_ts_momentum(df: pd.DataFrame, p: Dict) -> pd.Series:
    px = df["close"]
    mom = px / px.shift(p["lookback"]) - 1.0
    sig = (mom > p.get("thr", 0.0)).astype(float)
    if p.get("allow_short"):
        sig = np.where(mom < -abs(p.get("thr", 0.0)), -1.0, sig)
    return pd.Series(sig, index=df.index)


# ---------------------------------------------------------------------------
# A2. Donchian channel breakout ("break/resistance") with an explicit exit
#      channel. True crossing (state), long holds — the daily, low-turnover
#      cousin of the failed intraday Donchian.
# ---------------------------------------------------------------------------
def sig_donchian(df: pd.DataFrame, p: Dict) -> pd.Series:
    # Channel EXCLUDES the current bar (.shift(1)); otherwise close can never
    # exceed a max that already contains today's high -> zero triggers.
    hi = df["high"].rolling(p["entry"], min_periods=p["entry"]).max().shift(1)
    lo = df["low"].rolling(p["entry"], min_periods=p["entry"]).min().shift(1)
    ex_hi = df["high"].rolling(p["exit"], min_periods=p["exit"]).max().shift(1)
    ex_lo = df["low"].rolling(p["exit"], min_periods=p["exit"]).min().shift(1)
    c = df["close"]
    state = 0.0
    out = []
    for i in range(len(c)):
        if np.isnan(hi.iloc[i]) or np.isnan(ex_lo.iloc[i]):
            out.append(state)
            continue
        if state <= 0 and c.iloc[i] > hi.iloc[i]:
            state = 1.0
        elif state >= 1.0 and c.iloc[i] < ex_lo.iloc[i]:
            state = -1.0 if p.get("allow_short") else 0.0
        elif state == 0.0 and c.iloc[i] < lo.iloc[i]:
            state = -1.0 if p.get("allow_short") else 0.0
        out.append(state)
    return pd.Series(out, index=df.index)


# ---------------------------------------------------------------------------
# A3. SMA crossover trend filter.
# ---------------------------------------------------------------------------
def sig_sma_cross(df: pd.DataFrame, p: Dict) -> pd.Series:
    c = df["close"]
    f = c.rolling(p["fast"], min_periods=p["fast"]).mean()
    s = c.rolling(p["slow"], min_periods=p["slow"]).mean()
    sig = (f > s).astype(float)
    if p.get("allow_short"):
        sig = np.where(f < s, -1.0, 0.0)
    return pd.Series(sig, index=df.index)


# ---------------------------------------------------------------------------
# A4. 200-day "don't lose money" trend filter on buy-and-hold: long above the
#      long MA, cash below. The classic retail risk filter.
# ---------------------------------------------------------------------------
def sig_ma_filter_bh(df: pd.DataFrame, p: Dict) -> pd.Series:
    c = df["close"]
    ma = c.rolling(p["ma"], min_periods=p["ma"]).mean()
    sig = (c > ma).astype(float)
    return pd.Series(sig, index=df.index)


# ---------------------------------------------------------------------------
# A5. Volatility targeting on buy-and-hold: always long, but size inversely to
#      trailing realized vol toward a target, rebalanced when the size changes
#      materially. Reduces DD/Sharpe; a RISK overlay, not alpha.
# ---------------------------------------------------------------------------
def sig_vol_target(df: pd.DataFrame, p: Dict) -> pd.Series:
    # Honest de-risking overlay: size is capped at 1.0 (NO leverage) because a
    # Rs 1L account cannot hold 2x notional. Vol targeting with leverage would
    # just scale B&H returns linearly (Sharpe unchanged) -- a fake "edge" that
    # is untradeable at this capital. Capped, it can only REDUCE risk.
    c = df["close"]
    r = c.pct_change()
    rv = r.rolling(p["vol_win"], min_periods=p["vol_win"]).std() * np.sqrt(252)
    max_size = p.get("max_size", 1.0)
    size = (p["target_vol"] / rv).clip(lower=0.0, upper=max_size).fillna(0.0)
    # rebalance monthly to keep turnover low: hold size constant within a month
    month = pd.Series(c.index.year * 12 + c.index.month, index=c.index)
    held = size.groupby(month).transform("first")
    return pd.Series(held, index=c.index).fillna(0.0)


# ---------------------------------------------------------------------------
# A6. Calendar/seasonality: long only in historically stronger calendar months.
#      Likely noise; included as an honest registered hypothesis.
# ---------------------------------------------------------------------------
def sig_calendar(df: pd.DataFrame, p: Dict) -> pd.Series:
    months = set(p["months"])
    sig = pd.Series([1.0 if m in months else 0.0 for m in df.index.month],
                    index=df.index)
    return sig


# ---------------------------------------------------------------------------
# A7. Day-of-week effect (e.g., the documented Indian "Friday/Saturday" or
#      month-end turn). Registered as a cheap-to-test, likely-noise hypothesis.
# ---------------------------------------------------------------------------
def sig_dayofweek(df: pd.DataFrame, p: Dict) -> pd.Series:
    dows = set(p["days"])
    sig = pd.Series([1.0 if d in dows else 0.0 for d in df.index.dayofweek],
                    index=df.index)
    return sig


# ---------------------------------------------------------------------------
# A8. Smart Money Concepts structural bias: long inside a confirmed bullish
#     fair-value-gap zone, short inside a bearish one. Features are LEAKAGE-SAFE
#     (research/discovery/smc_features.py lags the vendored library's forward-
#     looking swing/FVG detection) so bar t only ever encodes bars <= t. This is
#     a raw research primitive -- no scoring/stop/regime layer (that's the point);
#     the deflated-Sharpe/WFE gate is its sole judge.
# ---------------------------------------------------------------------------
def sig_smc_structure(df: pd.DataFrame, p: Dict) -> pd.Series:
    from mjonai.research.discovery.smc_features import smc_features
    feat = smc_features(df, swing_length=int(p.get("swing_length", 20)))
    in_bull = feat["smc_in_bull_fvg"] > 0
    in_bear = feat["smc_in_bear_fvg"] > 0
    allow_short = bool(p.get("allow_short", True))
    sig = np.where(in_bull, 1.0, np.where(in_bear & allow_short, -1.0, 0.0))
    return pd.Series(sig, index=df.index).astype(float)
