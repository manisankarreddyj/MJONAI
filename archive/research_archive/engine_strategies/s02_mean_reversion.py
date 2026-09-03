"""
S02 - Mean Reversion Strategy (Research Engine)
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


class S02MeanReversion(Strategy):

    def __init__(self) -> None:
        self._bb_period = 20
        self._bb_std = 2.0
        self._rsi_period = 14
        self._rsi_oversold = 35
        self._trend_ema = 200

    @property
    def name(self) -> str:
        return "S02_MeanReversion"

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def timeframe(self) -> str:
        return TimeFrame.DAY_1.value

    @property
    def description(self) -> str:
        return "Bollinger Oversold Dip Buying with Trend Filter"

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
            ParameterDefinition(name="rsi_oversold", values=[30, 35, 40]),
        ]

    def configure(self, parameters: ParameterSet) -> None:
        self._bb_period = parameters.get("bb_period", self._bb_period)
        self._rsi_oversold = parameters.get("rsi_oversold", self._rsi_oversold)

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

        # Trend filter: stock is in secular uptrend above 200 EMA
        if close.iloc[curr] < trend.iloc[curr]:
            return None

        # Mean reversion trigger: close was below lower band and bounced, RSI oversold
        oversold_bounce = (
            close.iloc[prev] <= lower.iloc[prev]
            and close.iloc[curr] > lower.iloc[curr]
            and rsi_vals.iloc[curr] <= self._rsi_oversold + 10
        )

        if not oversold_bounce:
            return None

        return StrategyResult(
            symbol="",
            strategy_id=self.name,
            signal="LONG",
            score=float(100 - rsi_vals.iloc[curr]),
            index=curr,
            metadata={
                "rsi": float(rsi_vals.iloc[curr]),
                "bb_lower": float(lower.iloc[curr]),
                "bb_middle": float(middle.iloc[curr]),
            },
        )
