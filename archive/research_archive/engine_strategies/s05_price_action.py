"""
S05 - Price Action Candlestick Reversal Strategy (Research Engine)
"""

from __future__ import annotations

import pandas as pd

from engine.core.strategy import Strategy, StrategyResult
from engine.indicators.momentum import ema
from research.data.timeframe import TimeFrame
from research.optimization.models import (
    ParameterDefinition,
    ParameterSet,
)


class S05PriceAction(Strategy):

    def __init__(self) -> None:
        self._trend_ema = 50

    @property
    def name(self) -> str:
        return "S05_PriceAction"

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def timeframe(self) -> str:
        return TimeFrame.DAY_1.value

    @property
    def description(self) -> str:
        return "Pinbar & Bullish Engulfing Candlesticks at Trend Support"

    @property
    def markets(self) -> list[str]:
        return ["EQUITY"]

    @property
    def direction(self) -> str:
        return "LONG"

    @property
    def parameters(self) -> list[ParameterDefinition]:
        return [
            ParameterDefinition(name="trend_ema", values=[30, 50, 100]),
        ]

    def configure(self, parameters: ParameterSet) -> None:
        self._trend_ema = parameters.get("trend_ema", self._trend_ema)

    def set_parameters(self, parameters: ParameterSet) -> None:
        self.configure(parameters)

    def generate_signal(self, data: pd.DataFrame) -> StrategyResult | None:
        if len(data) < self._trend_ema + 5:
            return None

        open_ = data["Open"]
        high = data["High"]
        low = data["Low"]
        close = data["Close"]

        trend = ema(close, self._trend_ema)
        curr = len(data) - 1
        prev = curr - 1

        c_open, c_high, c_low, c_close = open_.iloc[curr], high.iloc[curr], low.iloc[curr], close.iloc[curr]
        p_open, p_close = open_.iloc[prev], close.iloc[prev]

        # Candle body & shadows
        body = abs(c_close - c_open)
        total_range = c_high - c_low
        lower_shadow = min(c_open, c_close) - c_low

        if total_range <= 0:
            return None

        # Pattern 1: Hammer / Pinbar (Lower shadow > 60% of candle, closing near high)
        is_hammer = (lower_shadow / total_range >= 0.60) and (c_close > trend.iloc[curr])

        # Pattern 2: Bullish Engulfing
        is_engulfing = (p_close < p_open) and (c_close > c_open) and (c_close > p_open) and (c_open < p_close) and (c_close > trend.iloc[curr])

        if not (is_hammer or is_engulfing):
            return None

        return StrategyResult(
            symbol="",
            strategy_id=self.name,
            signal="LONG",
            score=80.0,
            index=curr,
            metadata={
                "pattern": "HAMMER" if is_hammer else "ENGULFING",
                "trend_ema": float(trend.iloc[curr]),
            },
        )
