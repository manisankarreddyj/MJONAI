"""
S07 - Mean Reversion Short Strategy (Research Engine)
"""

from __future__ import annotations

import pandas as pd

from engine.core.strategy import Strategy, StrategyResult
from engine.indicators.momentum import ema, rsi, bollinger_bands
from research.data.timeframe import TimeFrame
from research.optimization.models import (
    ParameterDefinition,
    ParameterSet,
)


class S07MeanReversionShort(Strategy):

    def __init__(self) -> None:
        self._bb_period = 20
        self._bb_std = 2.0
        self._rsi_period = 14
        self._rsi_overbought = 70
        self._trend_ema = 200

    @property
    def name(self) -> str:
        return "S07_MeanReversionShort"

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def timeframe(self) -> str:
        return TimeFrame.DAY_1.value

    @property
    def description(self) -> str:
        return "Overbought Upper Bollinger Rejection Short"

    @property
    def markets(self) -> list[str]:
        return ["EQUITY", "FNO"]

    @property
    def direction(self) -> str:
        return "SHORT"

    @property
    def parameters(self) -> list[ParameterDefinition]:
        return [
            ParameterDefinition(name="bb_period", values=[15, 20]),
            ParameterDefinition(name="rsi_overbought", values=[65, 70, 75]),
        ]

    def configure(self, parameters: ParameterSet) -> None:
        self._bb_period = parameters.get("bb_period", self._bb_period)
        self._rsi_overbought = parameters.get("rsi_overbought", self._rsi_overbought)

    def set_parameters(self, parameters: ParameterSet) -> None:
        self.configure(parameters)

    def generate_signal(self, data: pd.DataFrame) -> StrategyResult | None:
        minimum_bars = max(self._trend_ema, self._bb_period) + 10
        if len(data) < minimum_bars:
            return None

        close = data["Close"]
        trend = ema(close, self._trend_ema)
        upper, middle, lower = bollinger_bands(close, self._bb_period, self._bb_std)
        rsi_vals = rsi(close, self._rsi_period)

        curr = len(data) - 1
        prev = curr - 1

        # Bear trend filter: stock is trading below 200 EMA
        if close.iloc[curr] > trend.iloc[curr]:
            return None

        # Overbought rejection: previous close above upper band, current closes back below upper band
        rejection = (
            close.iloc[prev] >= upper.iloc[prev]
            and close.iloc[curr] < upper.iloc[curr]
            and rsi_vals.iloc[curr] >= self._rsi_overbought - 5
        )

        if not rejection:
            return None

        return StrategyResult(
            symbol="",
            strategy_id=self.name,
            signal="SHORT",
            score=float(rsi_vals.iloc[curr]),
            index=curr,
            metadata={
                "rsi": float(rsi_vals.iloc[curr]),
                "bb_upper": float(upper.iloc[curr]),
            },
        )
