"""
S03 - Turtle Breakout Strategy (Research Engine)
"""

from __future__ import annotations

import pandas as pd

from engine.core.strategy import Strategy, StrategyResult
from engine.indicators.momentum import donchian_channel, atr
from research.data.timeframe import TimeFrame
from research.optimization.models import (
    ParameterDefinition,
    ParameterSet,
)


class S03TurtleBreakout(Strategy):

    def __init__(self) -> None:
        self._breakout_period = 20
        self._exit_period = 10
        self._atr_period = 14

    @property
    def name(self) -> str:
        return "S03_TurtleBreakout"

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def timeframe(self) -> str:
        return TimeFrame.DAY_1.value

    @property
    def description(self) -> str:
        return "20-day Donchian High Breakout with ATR trailing risk"

    @property
    def markets(self) -> list[str]:
        return ["EQUITY"]

    @property
    def direction(self) -> str:
        return "LONG"

    @property
    def parameters(self) -> list[ParameterDefinition]:
        return [
            ParameterDefinition(name="breakout_period", values=[15, 20, 30]),
        ]

    def configure(self, parameters: ParameterSet) -> None:
        self._breakout_period = parameters.get("breakout_period", self._breakout_period)

    def set_parameters(self, parameters: ParameterSet) -> None:
        self.configure(parameters)

    def generate_signal(self, data: pd.DataFrame) -> StrategyResult | None:
        if len(data) < self._breakout_period + 10:
            return None

        high = data["High"]
        low = data["Low"]
        close = data["Close"]

        upper, _ = donchian_channel(high, low, self._breakout_period)
        atr_vals = atr(high, low, close, self._atr_period)

        curr = len(data) - 1
        prev = curr - 1

        # Breakout: Previous candle below 20-day high, current candle closes above 20-day high
        breakout = (
            close.iloc[prev] <= upper.iloc[prev]
            and close.iloc[curr] > upper.iloc[prev]
        )

        if not breakout:
            return None

        return StrategyResult(
            symbol="",
            strategy_id=self.name,
            signal="LONG",
            score=80.0,
            index=curr,
            metadata={
                "donchian_high": float(upper.iloc[prev]),
                "atr": float(atr_vals.iloc[curr]),
            },
        )
