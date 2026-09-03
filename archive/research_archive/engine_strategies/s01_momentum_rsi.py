"""
S01 - Momentum RSI Strategy
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


class S01MomentumRSI(Strategy):

    def __init__(self) -> None:

        self._ema_fast = 50
        self._ema_slow = 200
        self._rsi_period = 14
        self._rsi_level = 55

    @property
    def name(self) -> str:
        return "S01_MomentumRSI"

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def timeframe(self) -> str:
        return TimeFrame.DAY_1.value

    @property
    def description(self) -> str:
        return "EMA Trend + RSI Momentum"

    @property
    def markets(self) -> list[str]:
        return [
            "EQUITY",
        ]

    @property
    def direction(self) -> str:
        return "LONG"

    @property
    def parameters(
        self,
    ) -> list[ParameterDefinition]:

        return [
            ParameterDefinition(
                name="ema_fast",
                values=[
                    50,
                ],
            ),
            ParameterDefinition(
                name="ema_slow",
                values=[
                    200,
                ],
            ),
            ParameterDefinition(
                name="rsi_period",
                values=[
                    14,
                ],
            ),
            ParameterDefinition(
                name="rsi_level",
                values=[
                    55,
                ],
            ),
        ]

    def configure(
        self,
        parameters: ParameterSet,
    ) -> None:

        self._ema_fast = parameters.get(
            "ema_fast",
            self._ema_fast,
        )

        self._ema_slow = parameters.get(
            "ema_slow",
            self._ema_slow,
        )

        self._rsi_period = parameters.get(
            "rsi_period",
            self._rsi_period,
        )

        self._rsi_level = parameters.get(
            "rsi_level",
            self._rsi_level,
        )

    def generate_signal(
        self,
        data: pd.DataFrame,
    ) -> StrategyResult | None:

        minimum_bars = max(
            self._ema_fast,
            self._ema_slow,
        ) + 20

        if len(data) < minimum_bars:
            return None

        close = data["Close"]

        ema_fast = ema(
            close,
            self._ema_fast,
        )

        ema_slow = ema(
            close,
            self._ema_slow,
        )

        rsi_values = rsi(
            close,
            self._rsi_period,
        )

        current = len(data) - 1
        previous = current - 1

        if (
            ema_fast.iloc[current]
            <= ema_slow.iloc[current]
        ):
            return None

        if (
            close.iloc[current]
            <= ema_fast.iloc[current]
        ):
            return None

        crossed = (
            rsi_values.iloc[previous]
            <= self._rsi_level
            and
            rsi_values.iloc[current]
            > self._rsi_level
        )

        if not crossed:
            return None

        return StrategyResult(
            symbol="",
            strategy_id=self.name,
            signal="LONG",
            score=float(
                rsi_values.iloc[current],
            ),
            index=current,
            metadata={
                "ema_fast": self._ema_fast,
                "ema_slow": self._ema_slow,
                "rsi_period": self._rsi_period,
                "rsi_level": self._rsi_level,
                "ema_fast_value": float(
                    ema_fast.iloc[current],
                ),
                "ema_slow_value": float(
                    ema_slow.iloc[current],
                ),
                "rsi": float(
                    rsi_values.iloc[current],
                ),
            },
        )