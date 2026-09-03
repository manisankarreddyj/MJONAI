"""
Module: research/ml/triple_barrier.py
Purpose: Marcos López de Prado's Triple Barrier Method for institutional meta-labeling.
         Evaluates whether candidate trading signals hit profit-taking, stop-loss,
         or vertical expiration barriers first.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List
import pandas as pd
import numpy as np


@dataclass(slots=True)
class BarrierEvent:
    """Represents a single trade signal labeled by the Triple Barrier Method."""
    event_time: datetime
    symbol: str
    direction: str  # "LONG" or "SHORT"
    entry_price: float
    take_profit_price: float
    stop_loss_price: float
    expiration_time: datetime
    exit_time: datetime
    exit_price: float
    exit_barrier: str  # "TAKE_PROFIT", "STOP_LOSS", "EXPIRATION"
    label: int  # 1 = profitable execution, 0 = unprofitable/loss
    net_return_pct: float


def apply_triple_barrier(
    df: pd.DataFrame,
    events: pd.DataFrame,
    pt_multiplier: float = 2.0,
    sl_multiplier: float = 1.5,
    max_holding_bars: int = 15,
    atr_period: int = 14,
) -> List[BarrierEvent]:
    """
    Apply Triple Barrier labeling to a dataframe of candles and signal events.

    Args:
        df: Price DataFrame with DatetimeIndex and columns ['open', 'high', 'low', 'close', 'volume'].
        events: DataFrame with candidate signals: ['timestamp', 'direction', 'entry_price'].
        pt_multiplier: ATR multiple for upper profit barrier.
        sl_multiplier: ATR multiple for lower stop barrier.
        max_holding_bars: Number of bars before vertical expiration barrier.
        atr_period: Period for ATR calculation.

    Returns:
        List of labeled BarrierEvent instances.
    """
    if df.empty or events.empty:
        return []

    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    n = len(df)

    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))

    atr = pd.Series(tr, index=df.index).rolling(window=atr_period, min_periods=1).mean().values
    df_with_atr = df.copy()
    df_with_atr['atr'] = atr

    labeled_events: List[BarrierEvent] = []
    dt_index = df.index

    for _, row in events.iterrows():
        t = row['timestamp']
        direction = str(row.get('direction', 'LONG')).upper()
        symbol = str(row.get('symbol', 'UNKNOWN'))

        if t not in dt_index:
            loc = dt_index.get_indexer([t], method='nearest')[0]
        else:
            loc = dt_index.get_loc(t)

        if loc < 0 or loc >= n:
            continue

        entry_price = float(row.get('entry_price', close[loc]))
        vol = float(df_with_atr['atr'].iloc[loc])
        if vol <= 0:
            vol = entry_price * 0.015

        if direction == "LONG":
            tp_price = entry_price + (pt_multiplier * vol)
            sl_price = entry_price - (sl_multiplier * vol)
        else:
            tp_price = entry_price - (pt_multiplier * vol)
            sl_price = entry_price + (sl_multiplier * vol)

        exp_loc = min(n - 1, loc + max_holding_bars)
        exp_time = dt_index[exp_loc]

        exit_time = exp_time
        exit_price = close[exp_loc]
        exit_barrier = "EXPIRATION"

        for bar_idx in range(loc + 1, exp_loc + 1):
            bar_h = high[bar_idx]
            bar_l = low[bar_idx]
            bar_t = dt_index[bar_idx]

            if direction == "LONG":
                if bar_l <= sl_price:
                    exit_barrier = "STOP_LOSS"
                    exit_price = sl_price
                    exit_time = bar_t
                    break
                elif bar_h >= tp_price:
                    exit_barrier = "TAKE_PROFIT"
                    exit_price = tp_price
                    exit_time = bar_t
                    break
            else:
                if bar_h >= sl_price:
                    exit_barrier = "STOP_LOSS"
                    exit_price = sl_price
                    exit_time = bar_t
                    break
                elif bar_l <= tp_price:
                    exit_barrier = "TAKE_PROFIT"
                    exit_price = tp_price
                    exit_time = bar_t
                    break

        if direction == "LONG":
            net_return = (exit_price - entry_price) / entry_price * 100.0
            label = 1 if exit_barrier == "TAKE_PROFIT" or (exit_barrier == "EXPIRATION" and net_return > 0) else 0
        else:
            net_return = (entry_price - exit_price) / entry_price * 100.0
            label = 1 if exit_barrier == "TAKE_PROFIT" or (exit_barrier == "EXPIRATION" and net_return > 0) else 0

        labeled_events.append(
            BarrierEvent(
                event_time=t,
                symbol=symbol,
                direction=direction,
                entry_price=round(entry_price, 2),
                take_profit_price=round(tp_price, 2),
                stop_loss_price=round(sl_price, 2),
                expiration_time=exp_time,
                exit_time=exit_time,
                exit_price=round(exit_price, 2),
                exit_barrier=exit_barrier,
                label=label,
                net_return_pct=round(net_return, 2),
            )
        )

    return labeled_events
