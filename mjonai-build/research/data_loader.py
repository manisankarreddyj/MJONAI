from __future__ import annotations

from datetime import datetime

from core.enums import Provider
from data.instruments.models import Instrument
from research.data.models import HistoricalData
from research.data.requests import HistoricalDataRequest
from research.data.market_data import MarketDataService
from research.data.timeframe import TimeFrame


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
                )
            )

            if not response.success:
                continue

            historical_data_list.append(
                response.data
            )

        return historical_data_list