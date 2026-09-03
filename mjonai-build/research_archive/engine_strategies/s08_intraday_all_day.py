"""
S08 - All-Day Intraday & Scalping Strategy (Research Engine)
"""

from __future__ import annotations

import pandas as pd

from engine.core.strategy import Strategy, StrategyResult
from engine.indicators.momentum import vwap
from research.data.timeframe import TimeFrame
from research.optimization.models import (
    ParameterDefinition,
    ParameterSet,
)


class S08IntradayAllDay(Strategy):

    def __init__(self) -> None:
        self._box_lookback = 8
        self._volume_mult = 1.4

    @property
    def name(self) -> str:
        return "S08_IntradayAllDay"

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def timeframe(self) -> str:
        return TimeFrame.DAY_1.value

    @property
    def description(self) -> str:
        return "All-Day Consolidation Box Breakout with VWAP Alignment"

    @property
    def markets(self) -> list[str]:
        return ["EQUITY", "FNO"]

    @property
    def direction(self) -> str:
        return "LONG"

    @property
    def parameters(self) -> list[ParameterDefinition]:
        return [
            ParameterDefinition(name="box_lookback", values=[5, 8, 12]),
        ]

    def configure(self, parameters: ParameterSet) -> None:
        self._box_lookback = parameters.get("box_lookback", self._box_lookback)

    def set_parameters(self, parameters: ParameterSet) -> None:
        self.configure(parameters)

    def generate_signal(self, data: pd.DataFrame) -> StrategyResult | None:
        if len(data) < self._box_lookback + 10:
            return None

        # Take fast recent slice (last 30 candles)
        sub = data.iloc[-30:] if len(data) > 30 else data
        high = sub["High"].values
        low = sub["Low"].values
        close = sub["Close"].values
        volume = sub["Volume"].values

        vol_avg = float(volume[-21:-1].mean()) if len(volume) > 20 else float(volume.mean())
        if vol_avg <= 0:
            return None

        typical = (high + low + close) / 3.0
        vwap_val = float((typical * volume).sum() / (volume.sum() + 1e-9))

        curr_close = float(close[-1])
        curr_vol = float(volume[-1])
        lb = min(self._box_lookback, len(sub) - 2)

        box_high = float(high[-lb-1:-1].max())
        box_low = float(low[-lb-1:-1].min())

        # Breakout condition
        is_breakout = (
            curr_close > box_high
            and curr_close > vwap_val
            and curr_vol >= (vol_avg * self._volume_mult)
        )

        if not is_breakout:
            return None

        curr_idx = len(data) - 1
        return StrategyResult(
            symbol="",
            strategy_id=self.name,
            signal="LONG",
            score=85.0,
            index=curr_idx,
            metadata={
                "box_high": box_high,
                "vwap": vwap_val,
                "vol_mult": float(curr_vol / max(1.0, vol_avg)),
            },
        )
