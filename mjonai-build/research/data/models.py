from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.enums import Provider
from data.instruments.models import Instrument
from research.data.timeframe import TimeFrame


@dataclass(slots=True)
class Candle:

    timestamp: datetime

    open: float

    high: float

    low: float

    close: float

    volume: float = 0

    open_interest: float | None = None


@dataclass(slots=True)
class HistoricalData:

    instrument: Instrument

    timeframe: TimeFrame

    candles: list[Candle]