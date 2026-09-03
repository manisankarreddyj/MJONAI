from __future__ import annotations

from datetime import datetime

from engine.common.enums import Provider
from engine.instruments.models import Instrument
from engine.market_data.downloader.historical_downloader import (
    HistoricalDownloader,
)
from engine.market_data.downloader.jobs import DownloadJob
from engine.market_data.service import MarketDataService
from engine.market_data.timeframe import TimeFrame


class UpdateService:

    def __init__(
        self,
        downloader: HistoricalDownloader,
    ):

        self.downloader = downloader

    def update_daily(
        self,
        instruments: list[Instrument],
        provider: Provider = Provider.YAHOO,
    ):

        job = DownloadJob(
            instruments=instruments,
            provider=provider,
            timeframe=TimeFrame.DAY_1,
            start=datetime(2000, 1, 1),
            end=datetime.now(),
            force_refresh=False,
        )

        return self.downloader.download(job)