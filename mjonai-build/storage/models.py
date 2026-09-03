from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from data.instruments.models import Instrument
from research.data.timeframe import TimeFrame


@dataclass(slots=True)
class StorageKey:

    provider: str

    instrument: Instrument

    timeframe: TimeFrame


@dataclass(slots=True)
class StorageRange:

    start: datetime

    end: datetime