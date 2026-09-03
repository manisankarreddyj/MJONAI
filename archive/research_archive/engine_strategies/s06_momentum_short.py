"""
S06 - Momentum Short Strategy (Research Engine)
"""

from __future__ import annotations

import pandas as pd

from engine.core.strategy import Strategy, StrategyResult
from engine.indicators.momentum import ema, rsi
from research.data.timeframe import TimeFrame
from research.optimization.models import (
    ParameterDefinition,
    ParameterSet,
)


class S06MomentumShort(Strategy):

    def __init__(self) -> None:
        self._ema_fast = 20
        self._ema_slow = 50
        self._rsi_period = 14
        self._rsi_bear_level = 45

    @property
    def name(self) -> str:
        return "S06_MomentumShort"

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def timeframe(self) -> str:
        return TimeFrame.DAY_1.value

    @property
    def description(self) -> str:
        return "Bearish EMA Cross + RSI Breakdown Short"

    @property
    def markets(self) -> list[str]:
        return ["EQUITY", "FNO"]

    @property
    def direction(self) -> str:
        return "SHORT"

    @property
    def parameters(self) -> list[ParameterDefinition]:
        return [
            ParameterDefinition(name="ema_fast", values=[15, 20, 25]),
            ParameterDefinition(name="rsi_bear_level", values=[40, 45, 50]),
        ]

    def configure(self, parameters: ParameterSet) -> None:
        self._ema_fast = parameters.get("ema_fast", self._ema_fast)
        self._rsi_bear_level = parameters.get("rsi_bear_level", self._rsi_bear_level)

    def set_parameters(self, parameters: ParameterSet) -> None:
        self.configure(parameters)

    def generate_signal(self, data: pd.DataFrame) -> StrategyResult | None:
        minimum_bars = max(self._ema_slow, self._rsi_period) + 5
        if len(data) < minimum_bars:
            return None

        close = data["Close"]
        ema_f = ema(close, self._ema_fast)
        ema_s = ema(close, self._ema_slow)
        rsi_vals = rsi(close, self._rsi_period)

        curr = len(data) - 1
        prev = curr - 1

        if ema_f.iloc[curr] >= ema_s.iloc[curr]:
            return None

        if close.iloc[curr] >= ema_f.iloc[curr]:
            return None

        crossed_down = rsi_vals.iloc[prev] >= self._rsi_bear_level and rsi_vals.iloc[curr] < self._rsi_bear_level
        if not crossed_down:
            return None

        return StrategyResult(
            symbol="",
            strategy_id=self.name,
            signal="SHORT",
            score=float(100 - rsi_vals.iloc[curr]),
            index=curr,
            metadata={
                "rsi": float(rsi_vals.iloc[curr]),
                "ema_fast": float(ema_f.iloc[curr]),
                "ema_slow": float(ema_s.iloc[curr]),
            },
        )
