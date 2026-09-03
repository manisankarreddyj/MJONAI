"""
S04 - Bollinger Squeeze Strategy (Research Engine)
"""

from __future__ import annotations

import pandas as pd

from engine.core.strategy import Strategy, StrategyResult
from engine.indicators.momentum import bollinger_bands, atr
from research.data.timeframe import TimeFrame
from research.optimization.models import (
    ParameterDefinition,
    ParameterSet,
)


class S04BollingerSqueeze(Strategy):

    def __init__(self) -> None:
        self._bb_period = 20
        self._bb_std = 2.0
        self._kc_mult = 1.5
        self._atr_period = 14

    @property
    def name(self) -> str:
        return "S04_BollingerSqueeze"

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def timeframe(self) -> str:
        return TimeFrame.DAY_1.value

    @property
    def description(self) -> str:
        return "Volatility Squeeze Expansion Breakout"

    @property
    def markets(self) -> list[str]:
        return ["EQUITY"]

    @property
    def direction(self) -> str:
        return "LONG"

    @property
    def parameters(self) -> list[ParameterDefinition]:
        return [
            ParameterDefinition(name="bb_period", values=[15, 20, 25]),
        ]

    def configure(self, parameters: ParameterSet) -> None:
        self._bb_period = parameters.get("bb_period", self._bb_period)

    def set_parameters(self, parameters: ParameterSet) -> None:
        self.configure(parameters)

    def generate_signal(self, data: pd.DataFrame) -> StrategyResult | None:
        if len(data) < self._bb_period + 10:
            return None

        high = data["High"]
        low = data["Low"]
        close = data["Close"]

        upper, middle, lower = bollinger_bands(close, self._bb_period, self._bb_std)
        atr_vals = atr(high, low, close, self._atr_period)

        # Keltner Channel
        kc_upper = middle + (atr_vals * self._kc_mult)

        curr = len(data) - 1
        prev = curr - 1

        # Squeeze fire: BB was inside Keltner Channel (squeeze), now expands outside with upward momentum
        was_squeezed = upper.iloc[prev] <= kc_upper.iloc[prev]
        fires_long = upper.iloc[curr] > kc_upper.iloc[curr] and close.iloc[curr] > middle.iloc[curr]

        if not (was_squeezed and fires_long):
            return None

        return StrategyResult(
            symbol="",
            strategy_id=self.name,
            signal="LONG",
            score=85.0,
            index=curr,
            metadata={
                "bb_upper": float(upper.iloc[curr]),
                "kc_upper": float(kc_upper.iloc[curr]),
            },
        )
