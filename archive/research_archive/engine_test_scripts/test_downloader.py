from datetime import datetime

from engine.common.enums import Provider

from engine.instruments.master import InstrumentMaster
from engine.instruments.providers.angel_provider import (
    AngelInstrumentProvider,
)

from engine.market_data.downloader.historical_downloader import (
    HistoricalDownloader,
)

from engine.market_data.downloader.jobs import DownloadJob

from engine.market_data.providers.yahoo_provider import (
    YahooProvider,
)

from engine.market_data.service import (
    MarketDataService,
)

from engine.market_data.timeframe import TimeFrame

from engine.storage.parquet_store import ParquetStore
from engine.storage.service import StorageService


print("=" * 80)
print("Loading Instrument Master")

master = InstrumentMaster()

master.load(
    AngelInstrumentProvider().download()
)

symbols = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
]

instruments = []

for symbol in symbols:

    instrument = master.get_by_symbol(symbol)[0]

    instrument.yahoo_symbol = f"{symbol}.NS"

    instruments.append(instrument)

print(f"Loaded : {len(instruments)} instruments")

print()

service = MarketDataService()

service.register(
    YahooProvider()
)

storage = StorageService()

storage.register(
    ParquetStore()
)

service.register_storage(
    storage
)

downloader = HistoricalDownloader(service)

job = DownloadJob(
    instruments=instruments,
    provider=Provider.YAHOO,
    timeframe=TimeFrame.DAY_1,
    start=datetime(2024, 1, 1),
    end=datetime(2025, 1, 1),
)

result = downloader.download(job)

print()
print("=" * 80)
print("Verification")
print()

assert result.failed == 0

print("Downloader completed successfully.")