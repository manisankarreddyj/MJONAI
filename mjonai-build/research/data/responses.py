from __future__ import annotations

from dataclasses import dataclass

from research.data.models import HistoricalData


@dataclass(slots=True)
class HistoricalDataResponse:

    success: bool

    data: HistoricalData | None = None

    source: str = ""

    cached: bool = False

    error: str | None = None