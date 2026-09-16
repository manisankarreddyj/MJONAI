"""Regression tests: adjusted (Yahoo) and raw (Angel) price regimes
must never merge in one cache series. Every bar written to parquet
carries its adjustment_mode tag; the merge path fails closed on
a regime mismatch instead of silently corrupting levels."""

from datetime import date, datetime, timedelta

import pytest

from mjonai.core.enums import AdjustmentMode, Provider
from mjonai.data.instruments.models import Instrument
from mjonai.research.data.corporate_actions import CorporateActionFactor
from mjonai.research.data.models import Candle, HistoricalData
from mjonai.research.data.market_data import MarketDataService
from mjonai.research.data.requests import HistoricalDataRequest
from mjonai.research.data.timeframe import TimeFrame
from mjonai.storage.models import StorageKey
from mjonai.storage.parquet_store import ParquetStore
from mjonai.storage.service import StorageService


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


def make_candles(start: datetime, days: int, base=100.0):
    candles = []
    current = start
    price = base
    for _ in range(days):
        price += 1.0
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


def make_data(start: datetime, days: int, base=100.0):
    return HistoricalData(
        instrument=make_instrument(),
        timeframe=TimeFrame.DAY_1,
        candles=make_candles(start, days, base),
    )


def test_raw_and_adjusted_resolve_to_distinct_files(tmp_path):
    store = ParquetStore(root=str(tmp_path))
    instr = make_instrument()

    raw_key = StorageKey(
        provider=Provider.ANGEL,
        instrument=instr,
        timeframe=TimeFrame.DAY_1,
        adjustment_mode=AdjustmentMode.RAW,
    )
    adj_key = StorageKey(
        provider=Provider.YAHOO,
        instrument=instr,
        timeframe=TimeFrame.DAY_1,
        adjustment_mode=AdjustmentMode.ADJUSTED,
    )

    start = datetime(2024, 1, 1)
    store.save(raw_key, make_data(start, 5, base=100.0))
    store.save(adj_key, make_data(start, 5, base=50.0))

    raw_loaded = store.load(raw_key)
    adj_loaded = store.load(adj_key)

    assert raw_loaded is not None
    assert adj_loaded is not None
    # Same symbol/timeframe, different regime -> independent levels.
    assert raw_loaded.candles[0].close == 101.0
    assert adj_loaded.candles[0].close == 51.0
    assert store._path(raw_key) != store._path(adj_key)


def test_merge_across_regimes_fails_closed(tmp_path):
    """A tampered/legacy file tagged 'adjusted' under a raw key must
    never be merged with incoming raw bars — fail closed instead."""
    import pandas as pd

    store = ParquetStore(root=str(tmp_path))
    start = datetime(2024, 1, 1)
    key = StorageKey(
        provider=Provider.ANGEL,
        instrument=make_instrument(),
        timeframe=TimeFrame.DAY_1,
        adjustment_mode=AdjustmentMode.RAW,
    )

    # Simulate a corrupt cache: raw path, but every stored bar claims
    # to be 'adjusted' (e.g. written by a legacy sloppy writer).
    path = store._path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        {
            "timestamp": [start + timedelta(days=i) for i in range(3)],
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.0, 101.0, 102.0],
            "volume": [1000.0, 1000.0, 1000.0],
            "adjustment_mode": [AdjustmentMode.ADJUSTED.value] * 3,
        }
    )
    df.to_parquet(path, index=False)

    with pytest.raises(ValueError, match="Refusing to merge adjustment regimes"):
        store.save(key, make_data(start + timedelta(days=3), 3, base=200.0))


def test_same_regime_merges_append_only(tmp_path):
    store = ParquetStore(root=str(tmp_path))
    start = datetime(2024, 1, 1)

    key = StorageKey(
        provider=Provider.ANGEL,
        instrument=make_instrument(),
        timeframe=TimeFrame.DAY_1,
        adjustment_mode=AdjustmentMode.RAW,
    )

    store.save(key, make_data(start, 3, base=100.0))
    store.save(key, make_data(start + timedelta(days=3), 3, base=200.0))

    loaded = store.load(key)
    assert loaded is not None
    assert len(loaded.candles) == 6
    assert loaded.candles[0].close == 101.0
    assert loaded.candles[-1].close == 203.0


def test_market_data_defaults_adjusted_for_yahoo_raw_for_angel(tmp_path):
    from mjonai.research.data.base_provider import HistoricalDataProvider
    from mjonai.research.data.responses import HistoricalDataResponse

    store = ParquetStore(root=str(tmp_path / "parquet"))
    storage = StorageService()
    storage.register(store)
    service = MarketDataService()
    service.register_storage(storage)

    class AngleProvider(HistoricalDataProvider):
        @property
        def provider(self) -> Provider:
            return Provider.ANGEL

        def fetch(self, request):
            return HistoricalDataResponse(
                success=True,
                data=HistoricalData(
                    instrument=request.instrument,
                    timeframe=request.timeframe,
                    candles=make_candles(request.start, 5),
                ),
            )

    class YahooProvider(HistoricalDataProvider):
        @property
        def provider(self) -> Provider:
            return Provider.YAHOO

        def fetch(self, request):
            return HistoricalDataResponse(
                success=True,
                data=HistoricalData(
                    instrument=request.instrument,
                    timeframe=request.timeframe,
                    candles=make_candles(request.start, 5),
                ),
            )

    for provider, expected in (
        (AngleProvider(), AdjustmentMode.RAW),
        (YahooProvider(), AdjustmentMode.ADJUSTED),
    ):
        service.register(provider)
        request = HistoricalDataRequest(
            provider=provider.provider,
            instrument=make_instrument(symbol=provider.provider.value),
            timeframe=TimeFrame.DAY_1,
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 5),
        )
        response = service.get_historical_data(request)
        assert response.success
        # The parquet file written for this provider carries the
        # expected regime tag on every bar.
        path = store._path(
            StorageKey(
                provider=provider.provider,
                instrument=request.instrument,
                timeframe=TimeFrame.DAY_1,
                adjustment_mode=expected,
            )
        )
        df = __import__("pandas").read_parquet(path)
        assert (df["adjustment_mode"] == expected).all()


SPLIT_FACTOR_2X = [
    CorporateActionFactor(
        ex_date=date(2024, 2, 1),
        action_type="split",
        share_multiplier=2.0,
    )
]

DIVIDEND_5RS = [
    CorporateActionFactor(
        ex_date=date(2024, 2, 1),
        action_type="dividend",
        dividend_per_share=5.0,
    )
]


def _run_angel_adjusted(tmp_path, factor_provider, close_prices, timestamps):
    """Request ADJUSTED regime from the native-RAW Angel provider."""
    from mjonai.research.data.base_provider import HistoricalDataProvider
    from mjonai.research.data.responses import HistoricalDataResponse

    store = ParquetStore(root=str(tmp_path / "parquet"))
    storage = StorageService()
    storage.register(store)
    service = MarketDataService(
        adjustment_factor_provider=factor_provider,
    )
    service.register_storage(storage)

    _ts_iter = iter(timestamps)

    class AngleProvider(HistoricalDataProvider):
        @property
        def provider(self) -> Provider:
            return Provider.ANGEL

        def fetch(self, request):
            candles = []
            for ts, p in zip(_ts_iter, close_prices):
                candles.append(
                    Candle(
                        timestamp=ts,
                        open=p,
                        high=p * 1.01,
                        low=p * 0.99,
                        close=p,
                        volume=1000.0,
                    )
                )
            return HistoricalDataResponse(
                success=True,
                data=HistoricalData(
                    instrument=request.instrument,
                    timeframe=request.timeframe,
                    candles=candles,
                ),
            )

    service.register(AngleProvider())
    instrument = make_instrument(symbol="TEST")
    request = HistoricalDataRequest(
        provider=Provider.ANGEL,
        instrument=instrument,
        timeframe=TimeFrame.DAY_1,
        start=min(timestamps),
        end=max(timestamps),
        adjustment_mode=AdjustmentMode.ADJUSTED,
    )
    response = service.get_historical_data(request)
    return store, service, response, instrument, request


def test_adjusted_request_converts_raw_via_engine(tmp_path):
    ts = [
        datetime(2024, 1, 15),
        datetime(2024, 1, 31),  # last bar strictly before ex 02-01
        datetime(2024, 2, 15),  # ex-date bar + after -> unchanged
    ]
    # SPLIT 2x on 02-01: pre-ex bars halve, ex-date bar untouched.
    store, service, response, instrument, request = _run_angel_adjusted(
        tmp_path,
        lambda _req: SPLIT_FACTOR_2X,
        [200.0, 200.0, 98.0],
        ts,
    )
    assert response.success
    assert response.source == "ANGEL.ADJUSTED"
    adjusted = response.data.candles
    assert adjusted[0].close == pytest.approx(100.0)
    assert adjusted[1].close == pytest.approx(100.0)
    assert adjusted[2].close == pytest.approx(98.0)

    # BOTH regimes are cached from the one fetch.
    adj_path = store._path(
        StorageKey(
            provider=Provider.ANGEL,
            instrument=instrument,
            timeframe=TimeFrame.DAY_1,
            adjustment_mode=AdjustmentMode.ADJUSTED,
        )
    )
    raw_path = store._path(
        StorageKey(
            provider=Provider.ANGEL,
            instrument=instrument,
            timeframe=TimeFrame.DAY_1,
            adjustment_mode=AdjustmentMode.RAW,
        )
    )
    assert adj_path.exists()
    assert raw_path.exists()
    adj_df = __import__("pandas").read_parquet(adj_path)
    raw_df = __import__("pandas").read_parquet(raw_path)
    assert (adj_df["adjustment_mode"] == AdjustmentMode.ADJUSTED.value).all()
    assert (raw_df["adjustment_mode"] == AdjustmentMode.RAW.value).all()
    # Raw cache holds unadjusted closes; adjusted cache holds engine output.
    assert raw_df["close"].iloc[0] == pytest.approx(200.0)
    assert adj_df["close"].iloc[0] == pytest.approx(100.0)


def test_adjusted_request_second_call_hits_cache(tmp_path):
    ts = [
        datetime(2024, 1, 15),
        datetime(2024, 1, 31),
        datetime(2024, 2, 15),
    ]
    store, service, response, instrument, request = _run_angel_adjusted(
        tmp_path,
        lambda _req: SPLIT_FACTOR_2X,
        [200.0, 200.0, 98.0],
        ts,
    )
    assert response.source == "ANGEL.ADJUSTED"

    again = service.get_historical_data(request)
    assert again.success
    assert again.cached is True
    assert again.source == "PARQUET"
    assert again.data.candles[0].close == pytest.approx(100.0)


def test_adjusted_request_fails_closed_on_factor_source_error(tmp_path):
    from mjonai.research.data.corporate_actions import (
        CorporateActionSourceError,
    )

    ts = [
        datetime(2024, 1, 15),
        datetime(2024, 1, 31),
        datetime(2024, 2, 15),
    ]

    def broken_factors(_req):
        raise CorporateActionSourceError("source unreachable")

    store, service, response, instrument, request = _run_angel_adjusted(
        tmp_path,
        broken_factors,
        [200.0, 200.0, 98.0],
        ts,
    )
    assert response.success is False
    assert response.data is None
    assert "ADJUSTED regime unavailable" in response.error
    # No phantom ADJUSTED cache exists - raw must never be tagged adjusted.
    adj_path = store._path(
        StorageKey(
            provider=Provider.ANGEL,
            instrument=instrument,
            timeframe=TimeFrame.DAY_1,
            adjustment_mode=AdjustmentMode.ADJUSTED,
        )
    )
    assert not adj_path.exists()


def test_reverse_adjustment_request_fails_closed(tmp_path):
    """Yahoo is native-ADJUSTED; a RAW request cannot be fabricated (the
    engine is one-directional). Must raise, not serve adjusted as raw."""
    from mjonai.research.data.base_provider import HistoricalDataProvider
    from mjonai.research.data.responses import HistoricalDataResponse

    store = ParquetStore(root=str(tmp_path / "parquet"))
    storage = StorageService()
    storage.register(store)
    service = MarketDataService()
    service.register_storage(storage)

    class YahooProvider(HistoricalDataProvider):
        @property
        def provider(self) -> Provider:
            return Provider.YAHOO

        def fetch(self, request):
            return HistoricalDataResponse(
                success=True,
                data=HistoricalData(
                    instrument=request.instrument,
                    timeframe=request.timeframe,
                    candles=make_candles(request.start, 5),
                ),
            )

    service.register(YahooProvider())
    request = HistoricalDataRequest(
        provider=Provider.YAHOO,
        instrument=make_instrument(symbol="YAHOO"),
        timeframe=TimeFrame.DAY_1,
        start=datetime(2024, 1, 1),
        end=datetime(2024, 1, 5),
        adjustment_mode=AdjustmentMode.RAW,
    )
    with pytest.raises(ValueError, match="never the reverse"):
        service.get_historical_data(request)