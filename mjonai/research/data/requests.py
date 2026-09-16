from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from mjonai.core.enums import AdjustmentMode, Provider
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

    # Requested price-adjustment regime. None (default) = the provider's
    # native regime (RAW for Angel/Shoonya, ADJUSTED for Yahoo) — existing
    # behavior unchanged. Requesting ADJUSTED from a native-RAW provider
    # makes MarketDataService produce the ADJUSTED series through the
    # adjustment engine (Decision 6 Phase 2) instead of serving raw bars.
    adjustment_mode: AdjustmentMode | None = None