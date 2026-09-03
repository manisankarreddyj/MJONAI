"""
Module: engine/research/dynamic_exits.py
Purpose: Dynamic Volatility-Based Stop-Loss and Profit Target Calculator.
         Replaces static/hardcoded percentages with true market-driven Average True Range (ATR)
         and risk-reward multiples.
"""

import pandas as pd
import numpy as np


def calculate_dynamic_atr(df: pd.DataFrame, index: int, period: int = 14) -> float:
    """Calculate 14-period Average True Range (ATR) up to current bar."""
    start_idx = max(0, index - period - 5)
    sub = df.iloc[start_idx:index + 1]
    if len(sub) < 2:
        return float(df["Close"].iloc[index]) * 0.02

    high = sub["High"].values
    low = sub["Low"].values
    close = sub["Close"].values
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]

    tr = np.maximum(
        high - low,
        np.maximum(np.abs(high - prev_close), np.abs(low - prev_close))
    )
    atr_val = float(np.mean(tr[-period:])) if len(tr) >= period else float(np.mean(tr))
    return max(0.1, atr_val)


def dynamic_stop_loss(
    df: pd.DataFrame,
    signal_index: int,
    entry_price: float,
    direction: str,
    atr_multiplier: float = 2.0,
) -> float:
    """
    Calculate dynamic volatility-adjusted stop-loss.

    ATR is computed from bars up to the signal bar only (no look-ahead),
    and the stop is anchored to the actual fill price (`entry_price`,
    i.e. next-bar open).
    """
    atr_val = calculate_dynamic_atr(df, signal_index, period=14)
    risk_distance = atr_val * atr_multiplier

    # Guardrails: Min 1.0% stop, Max 5.0% stop to preserve capital
    min_dist = entry_price * 0.01
    max_dist = entry_price * 0.05
    clamped_dist = max(min_dist, min(max_dist, risk_distance))

    if direction == "LONG":
        return round(entry_price - clamped_dist, 2)
    else:
        return round(entry_price + clamped_dist, 2)


def dynamic_target(
    entry_price: float,
    stop_loss_price: float,
    direction: str,
    risk_reward_ratio: float = 2.0,
) -> float:
    """
    Calculate dynamic profit target based on asymmetric risk-reward ratio.
    Target = Entry +- (Risk * R:R)
    """
    risk = abs(entry_price - stop_loss_price)
    if direction == "LONG":
        return round(entry_price + (risk * risk_reward_ratio), 2)
    else:
        return round(entry_price - (risk * risk_reward_ratio), 2)
