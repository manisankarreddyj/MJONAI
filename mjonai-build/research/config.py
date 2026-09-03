from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.enums import Provider
from research.data.timeframe import TimeFrame


@dataclass(slots=True)
class ResearchConfig:

    provider: Provider

    timeframe: TimeFrame

    start: datetime

    end: datetime

    max_holding_bars: int