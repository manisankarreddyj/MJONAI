from __future__ import annotations

from data.instruments.master import InstrumentMaster
from data.angelone.scrip_master import (
    AngelInstrumentProvider,
)

from research.data.providers.yahoo import (
    YahooProvider,
)
from research.data.providers.angelone_intraday import (
    AngelOneIntradayProvider,
)
from research.data.market_data import MarketDataService

from research.context import ResearchContext
from research.factory import ResearchFactory
from research.universe import UniverseManager

from storage.parquet_store import ParquetStore
from storage.service import StorageService


class ResearchBootstrap:

    @staticmethod
    def build(
        context: ResearchContext,
    ):

        master = InstrumentMaster()

        master.load(
            AngelInstrumentProvider().download()
        )

        universe = UniverseManager(
            master,
        )

        instruments = universe.symbols(
            context.symbols,
        )

        for instrument in instruments:

            instrument.yahoo_symbol = (
                f"{instrument.symbol}.NS"
            )

        storage = StorageService()

        storage.register(
            ParquetStore(),
        )

        market = MarketDataService()

        market.register(
            YahooProvider(),
        )

        # Intraday research (1m/5m/15m...) routes to the Angel One
        # provider; login happens lazily on first real fetch.
        market.register(
            AngelOneIntradayProvider(),
        )

        market.register_storage(
            storage,
        )

        pipeline = ResearchFactory.build_pipeline(
            market,
        )

        return (
            pipeline,
            instruments,
        )