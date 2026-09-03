from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.enums import Provider
from data.instruments.models import Instrument
from research.data.timeframe import TimeFrame


@dataclass(slots=True)
class HistoricalDataRequest:

    provider: Provider

    instrument: Instrument

    timeframe: TimeFrame

    start: datetime

    end: datetime

    force_refresh: bool = False