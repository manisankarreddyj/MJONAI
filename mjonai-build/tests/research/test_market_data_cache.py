"""Regression tests: the market-data cache must serve only ranges
it actually covers, and merges fetched history instead of
overwriting it. Guards against walk-forward windows silently
backtesting the wrong date slice."""

from datetime import datetime, timedelta

from core.enums import Provider
from data.instruments.models import Instrument
from research.data.base_provider import HistoricalDataProvider
from research.data.models import Candle, HistoricalData
from research.data.requests import HistoricalDataRequest
from research.data.responses import HistoricalDataResponse
from research.data.market_data import MarketDataService
from research.data.timeframe import TimeFrame
from storage.models import StorageKey
from storage.parquet_store import ParquetStore
from storage.service import StorageService


def make_instrument(symbol="TEST"):
    return Instrument(
        instrument_id=f"1_{symbol}",
        symbol=symbol,
        name=symbol,
        provider="YAHOO",
        provider_type="YAHOO",
        provider_exchange="NSE",
        exchange="NSE",
        asset_type="EQUITY",
        yahoo_symbol=f"{symbol}.NS",
    )


def make_candles(start: datetime, end: datetime):
    candles = []
    current = start
    price = 100.0
    while current <= end:
        price += 0.1
        candles.append(
            Candle(
                timestamp=current,
                open=price,
                high=price + 1,
                low=price - 1,
                close=price,
                volume=1000.0,
            )
        )
        current += timedelta(days=1)
    return candles


class StubProvider(HistoricalDataProvider):
    """Returns the full requested range and records every call."""

    def __init__(self):
        self.calls: list[tuple[datetime, datetime]] = []

    @property
    def provider(self) -> Provider:
        return Provider.YAHOO

    def fetch(self, request) -> HistoricalDataResponse:
        self.calls.append((request.start, request.end))
        return HistoricalDataResponse(
            success=True,
            data=HistoricalData(
                instrument=request.instrument,
                timeframe=request.timeframe,
                candles=make_candles(request.start, request.end),
            ),
        )


def build_service(tmp_path):
    provider = StubProvider()

    storage = StorageService()
    storage.register(ParquetStore(root=str(tmp_path / "parquet")))

    service = MarketDataService()
    service.register(provider)
    service.register_storage(storage)

    return service, provider


def request(start: datetime, end: datetime, symbol="TEST"):
    return HistoricalDataRequest(
        provider=Provider.YAHOO,
        instrument=make_instrument(symbol),
        timeframe=TimeFrame.DAY_1,
        start=start,
        end=end,
    )


JAN = datetime(2024, 1, 1)
FEB = datetime(2024, 2, 1)
MAR = datetime(2024, 3, 1)
APR = datetime(2024, 4, 15)


def test_subset_request_is_served_from_cache(tmp_path):
    service, provider = build_service(tmp_path)

    first = service.get_historical_data(request(JAN, MAR))
    assert first.success and not first.cached
    assert len(provider.calls) == 1

    second = service.get_historical_data(request(FEB, MAR))
    assert second.success and second.cached
    # No new fetch: the cached range fully covers the subset.
    assert len(provider.calls) == 1
    # Only the requested slice is served, not the whole cache.
    assert second.data.candles[0].timestamp == FEB
    assert second.data.candles[-1].timestamp <= MAR


def test_uncovered_range_refetches_and_merges(tmp_path):
    service, provider = build_service(tmp_path)

    service.get_historical_data(request(JAN, MAR))
    assert len(provider.calls) == 1

    # Extends beyond the cached range -> must refetch...
    third = service.get_historical_data(request(JAN, APR))
    assert not third.cached
    assert len(provider.calls) == 2
    assert third.data.candles[-1].timestamp <= APR

    # ...and now the merged cache serves the full span.
    fourth = service.get_historical_data(request(JAN, APR))
    assert fourth.cached
    assert len(provider.calls) == 2


def test_earlier_start_also_counts_as_uncovered(tmp_path):
    service, provider = build_service(tmp_path)

    service.get_historical_data(request(FEB, MAR))

    shifted = service.get_historical_data(request(JAN, MAR))
    assert not shifted.cached
    assert len(provider.calls) == 2


def test_end_within_grace_period_is_covered(tmp_path):
    service, provider = build_service(tmp_path)

    service.get_historical_data(request(JAN, MAR))

    # Ends 3 days after the last cached candle -> grace period
    # applies (today's bar not closed / holidays), no refetch.
    near_end = service.get_historical_data(
        request(JAN, MAR + timedelta(days=3))
    )
    assert near_end.cached
    assert len(provider.calls) == 1


def test_symbols_do_not_share_cache(tmp_path):
    service, provider = build_service(tmp_path)

    service.get_historical_data(request(JAN, MAR, symbol="AAA"))

    other = service.get_historical_data(request(JAN, MAR, symbol="BBB"))
    assert not other.cached
    assert other.data.instrument.symbol == "BBB"
