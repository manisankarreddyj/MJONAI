from __future__ import annotations

from datetime import datetime

from mjonai.core.enums import AdjustmentMode, Provider
from mjonai.data.instruments.models import Instrument
from mjonai.research.data.models import HistoricalData
from mjonai.research.data.requests import HistoricalDataRequest
from mjonai.research.data.market_data import MarketDataService
from mjonai.research.data.timeframe import TimeFrame


class ResearchDataLoader:

    def __init__(
        self,
        market_data: MarketDataService,
    ):

        self._market_data = market_data

    def load(
        self,
        *,
        instruments: list[Instrument],
        provider: Provider,
        timeframe: TimeFrame,
        start: datetime,
        end: datetime,
        adjustment_mode: AdjustmentMode | None = None,
    ) -> list[HistoricalData]:

        historical_data_list: list[HistoricalData] = []

        for instrument in instruments:

            response = self._market_data.get_historical_data(
                HistoricalDataRequest(
                    provider=provider,
                    instrument=instrument,
                    timeframe=timeframe,
                    start=start,
                    end=end,
                    adjustment_mode=adjustment_mode,
                )
            )

            if not response.success:
                continue

            historical_data_list.append(
                response.data
            )

        return historical_data_list