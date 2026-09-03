from datetime import datetime

from engine.instruments.master import InstrumentMaster
from engine.instruments.providers.angel_provider import AngelInstrumentProvider

from engine.market_data.service import MarketDataService
from engine.market_data.providers.yahoo_provider import YahooProvider

from engine.market_data.requests import HistoricalDataRequest
from engine.market_data.timeframe import TimeFrame

from engine.storage.service import StorageService
from engine.storage.parquet_store import ParquetStore

print("=" * 80)
print("Loading Instrument Master")

instrument_master = InstrumentMaster()

instrument_master.load(
    AngelInstrumentProvider().download()
)

print(f"Instruments : {len(instrument_master.all()):,}")

print()

print("=" * 80)
print("Finding RELIANCE")

instrument = instrument_master.get_by_symbol("RELIANCE")[0]

instrument.yahoo_symbol = "RELIANCE.NS"

print(instrument)

print()

print("=" * 80)
print("Registering Yahoo Provider")

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

print("Registered")

print()

from engine.common.enums import Provider

request = HistoricalDataRequest(
    provider=Provider.YAHOO,
    instrument=instrument,
    timeframe=TimeFrame.DAY_1,
    start=datetime(2024, 1, 1),
    end=datetime(2025, 1, 1),
)

print("=" * 80)
print("Downloading Historical Data")

response = service.get_historical_data(
    request,
)

assert response.success

history = response.data

print(f"Candles : {len(history.candles):,}")

print()

print("First Candle")

print(history.candles[0])

print()

print("Last Candle")

print(history.candles[-1])

print()
print("=" * 80)
print("SECOND REQUEST (CACHE TEST)")

response = service.get_historical_data(request)

assert response.success

print(f"Cached : {response.cached}")
print(f"Source : {response.source}")
print(f"Candles: {len(response.data.candles)}")