from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from mjonai.core.enums import Provider
from mjonai.data.instruments.models import Instrument
from mjonai.research.data.timeframe import TimeFrame


@dataclass(slots=True)
class HistoricalDataRequest:

    provider: Provider

    instrument: Instrument

    timeframe: TimeFrame

    start: datetime

    end: datetime

    force_refresh: bool = False