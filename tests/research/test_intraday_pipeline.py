"""Intraday research pipeline: Angel One provider mapping, range
clipping, lazy login, and minute-candle flow through the coverage-aware
parquet cache — all verified OFFLINE with a stubbed fetcher."""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from mjonai.core.enums import Provider
from mjonai.research.data.market_data import MarketDataService
from mjonai.research.data.models import Candle, HistoricalData
from mjonai.research.data.providers.angelone_intraday import (
    AngelOneIntradayProvider,
    TIMEFRAME_TO_INTERVAL,
)
from mjonai.research.data.providers.yahoo import YahooProvider
from mjonai.research.data.requests import HistoricalDataRequest
from mjonai.research.data.timeframe import TimeFrame
from mjonai.research.data.responses import HistoricalDataResponse
from mjonai.storage.parquet_store import ParquetStore
from mjonai.storage.service import StorageService


def make_instrument(symbol="RELIANCE"):
    from mjonai.data.instruments.models import Instrument

    return Instrument(
        instrument_id=f"1_{symbol}",
        symbol=symbol,
        name=symbol,
        provider="ANGEL",
        provider_type="SMARTAPI",
        provider_exchange="NSE",
        exchange="NSE",
        asset_type="EQUITY",
    )


def make_minute_frame(start: datetime, bars: int):
    idx = pd.date_range(start, periods=bars, freq="min")
    return pd.DataFrame(
        {
            "Open": [100.0 + i * 0.01 for i in range(bars)],
            "High": [101.0 + i * 0.01 for i in range(bars)],
            "Low": [99.0 + i * 0.01 for i in range(bars)],
            "Close": [100.5 + i * 0.01 for i in range(bars)],
            "Volume": [1000.0] * bars,
        },
        index=idx,
    )


def build_service(tmp_path, stub_fetch):
    provider = AngelOneIntradayProvider(client_factory=lambda: object())

    storage = StorageService()
    storage.register(ParquetStore(root=str(tmp_path / "parquet")))

    service = MarketDataService()
    service.register(provider)
    service.register_storage(storage)

    return service


def request(start, end, timeframe="1m", symbol="RELIANCE"):
    return HistoricalDataRequest(
        provider=Provider.ANGEL,
        instrument=make_instrument(symbol),
        timeframe=TimeFrame(timeframe),
        start=start,
        end=end,
    )


def test_provider_maps_candles_and_clips_range(tmp_path, monkeypatch):
    frame = make_minute_frame(datetime(2026, 6, 2, 9, 15), 375)

    captured = {}

    def stub_fetch(symbol, **kwargs):
        captured["interval"] = kwargs.get("interval")
        captured["days_back"] = kwargs.get("days_back")
        return frame

    monkeypatch.setattr(
        "mjonai.research.data.providers.angelone_intraday.fetch_historical_candles",
        stub_fetch,
    )

    service = build_service(tmp_path, stub_fetch)

    resp = service.get_historical_data(
        request(datetime(2026, 6, 2, 10, 0), datetime(2026, 6, 2, 10, 30))
    )

    assert resp.success
    assert resp.data is not None
    assert len(resp.data.candles) == 31  # inclusive minute range
    first = resp.data.candles[0]
    assert first.timestamp == datetime(2026, 6, 2, 10, 0)
    assert first.open == pytest.approx(100.0 + 45 * 0.01)
    # 1m maps to the SmartAPI ONE_MINUTE interval
    assert captured["interval"].value == "ONE_MINUTE"


def test_login_is_lazy_and_cached(tmp_path, monkeypatch):
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return object()

    monkeypatch.setattr(
        "mjonai.research.data.providers.angelone_intraday.fetch_historical_candles",
        lambda symbol, **kw: make_minute_frame(datetime(2026, 6, 2, 9, 15), 100),
    )

    provider = AngelOneIntradayProvider(client_factory=factory)

    assert calls["n"] == 0  # construction must NOT log in

    req = request(datetime(2026, 6, 2, 9, 15), datetime(2026, 6, 2, 10, 15))
    provider.fetch(req)
    provider.fetch(req)

    assert calls["n"] == 1  # logged in exactly once


def test_unsupported_timeframe_fails_honestly(tmp_path):
    provider = AngelOneIntradayProvider(client_factory=lambda: None)

    resp = provider.fetch(request(datetime(2026, 6, 1), datetime(2026, 6, 2), timeframe="1wk"))

    assert not resp.success
    assert "Unsupported" in (resp.error or "")


def test_minute_candles_flow_through_coverage_cache(tmp_path, monkeypatch):
    """The full loop: 1m fetch -> parquet -> coverage-aware HIT on a
    subset range -> exact slice served (the bug that once corrupted
    daily research must not exist for minutes either)."""
    frame = make_minute_frame(datetime(2026, 6, 1, 9, 15), 375 * 2)  # ~2 sessions

    monkeypatch.setattr(
        "mjonai.research.data.providers.angelone_intraday.fetch_historical_candles",
        lambda symbol, **kw: frame,
    )

    service = build_service(tmp_path, None)

    first = service.get_historical_data(
        request(datetime(2026, 6, 1, 9, 15), datetime(2026, 6, 2, 15, 30))
    )
    assert first.success and not first.cached

    second = service.get_historical_data(
        request(datetime(2026, 6, 1, 11, 0), datetime(2026, 6, 1, 12, 0))
    )
    assert second.success and second.cached
    # Served slice must be EXACTLY the requested hour, not the whole cache
    assert second.data.candles[0].timestamp == datetime(2026, 6, 1, 11, 0)
    assert second.data.candles[-1].timestamp == datetime(2026, 6, 1, 12, 0)
    assert len(second.data.candles) == 61


def test_timeframe_interval_map_complete():
    for tf in ("1m", "5m", "15m"):
        assert tf in TIMEFRAME_TO_INTERVAL


def test_tz_aware_broker_stamps_normalized_to_naive_ist(tmp_path, monkeypatch):
    """Live broker returns tz-aware IST stamps; the research stack uses
    naive IST. Mixed comparison raised TypeError before the fix."""
    idx = pd.date_range(
        datetime(2026, 6, 2, 9, 15), periods=100, freq="min", tz="Asia/Kolkata"
    )
    frame = pd.DataFrame(
        {
            "Open": np.linspace(100, 101, 100),
            "High": np.linspace(101, 102, 100),
            "Low": np.linspace(99, 100, 100),
            "Close": np.linspace(100.5, 101.5, 100),
            "Volume": [1000.0] * 100,
        },
        index=idx,
    )

    monkeypatch.setattr(
        "mjonai.research.data.providers.angelone_intraday.fetch_historical_candles",
        lambda symbol, **kw: frame,
    )

    service = build_service(tmp_path, None)

    resp = service.get_historical_data(
        request(datetime(2026, 6, 2, 9, 15), datetime(2026, 6, 2, 10, 30))
    )

    assert resp.success, resp.error
    assert len(resp.data.candles) == 76  # 09:15..10:30 inclusive
    # Emitted timestamps are NAIVE IST, consistent with the daily stack.
    assert resp.data.candles[0].timestamp.tzinfo is None
    assert resp.data.candles[0].timestamp.hour == 9