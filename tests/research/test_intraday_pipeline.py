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


def build_service(tmp_path, stub_fetch, archive=None):
    from mjonai.data.minute_archive import MinuteBarArchive

    provider = AngelOneIntradayProvider(
        client_factory=lambda: object(),
        # Hermetic-by-default: an EMPTY archive rooted in tmp_path so the
        # pre-existing broker-path tests are not coupled to any real archive
        # that happens to exist on the machine (the production default reads
        # storage/parquet live-captured bars).
        archive=archive if archive is not None else MinuteBarArchive(root=str(tmp_path / "archive")),
    )

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


def test_provider_refuses_yfinance_fallback_as_raw_regime(tmp_path, monkeypatch):
    """P0.2: when the fetcher silently falls back to yfinance (auto_adjust =>
    ADJUSTED), the ANGEL/RAW-native provider must fail closed rather than let
    adjusted bars be stored under the RAW cache key."""
    def stub_fetch(symbol, **kwargs):
        frame = make_minute_frame(datetime(2026, 6, 2, 9, 15), 100)
        frame.attrs["data_provider"] = "YFINANCE"
        return frame

    monkeypatch.setattr(
        "mjonai.research.data.providers.angelone_intraday.fetch_historical_candles",
        stub_fetch,
    )

    service = build_service(tmp_path, None)
    resp = service.get_historical_data(
        request(datetime(2026, 6, 2, 9, 15), datetime(2026, 6, 2, 10, 15))
    )

    assert not resp.success
    assert "YFINANCE" in (resp.error or "")
    # Nothing may have been persisted for the RAW key.
    assert not (tmp_path / "parquet").joinpath("angel").exists() or not any(
        (tmp_path / "parquet").rglob("*.parquet")
    )


def test_provider_accepts_smartapi_tagged_bars(tmp_path, monkeypatch):
    """The same frame, correctly tagged SMART_API, flows through unchanged."""
    def stub_fetch(symbol, **kwargs):
        frame = make_minute_frame(datetime(2026, 6, 2, 9, 15), 100)
        frame.attrs["data_provider"] = "SMART_API"
        return frame

    monkeypatch.setattr(
        "mjonai.research.data.providers.angelone_intraday.fetch_historical_candles",
        stub_fetch,
    )

    service = build_service(tmp_path, None)
    resp = service.get_historical_data(
        request(datetime(2026, 6, 2, 9, 15), datetime(2026, 6, 2, 10, 15))
    )

    assert resp.success, resp.error
    assert len(resp.data.candles) == 61


# ── PHASE 3: RESEARCH-READ OF THE LIVE MINUTE ARCHIVE ────────────────────────
# The intraday provider prefers the persisted live minute archive (ANGEL/RAW
# identity) over a broker pull when the archive covers the request. A captured
# minute frame is served resampled to the requested cadence — never fabricated,
# never mixed with the broker regime.

def archive_seed_helper(tmp_path, symbol="RELIANCE", bars=75):
    """Persist `bars` closed 1-minute bars through the PUBLIC sink path."""
    from mjonai.data.candle_builder import LiveCandleBuilder
    from mjonai.data.minute_archive import MinuteBarArchive

    archive = MinuteBarArchive(root=str(tmp_path / "archive"))
    builder = LiveCandleBuilder(closed_bar_callback=archive.sink_closed)
    base = datetime(2026, 6, 2, 9, 15, 0)
    for i in range(bars):
        bar_start = base + timedelta(minutes=i)
        price = float(1000.0 + i * 0.25)
        for sec in (10, 30, 55):
            builder.on_tick(symbol, price + sec / 100.0, int(100 + i), bar_start.replace(second=sec))
        nxt = bar_start + timedelta(minutes=1)
        builder.on_tick(symbol, float(1000.0 + (i + 1) * 0.25), int(100 + i + 1), nxt.replace(second=5))
    archive.flush(symbol)
    return archive


def test_provider_serves_1m_from_archive_before_broker(tmp_path, monkeypatch):
    """Phase 3: a 1m request inside the archive's span is served from the
    live archive — the broker fetcher is never called."""
    archive = archive_seed_helper(tmp_path, bars=75)

    broker_calls = {"n": 0}

    def stub_fetch(symbol, **kwargs):
        broker_calls["n"] += 1
        raise AssertionError("broker must not be reached when archive covers the request")

    monkeypatch.setattr(
        "mjonai.research.data.providers.angelone_intraday.fetch_historical_candles",
        stub_fetch,
    )

    service = build_service(tmp_path, None, archive=archive)

    resp = service.get_historical_data(
        request(datetime(2026, 6, 2, 9, 30), datetime(2026, 6, 2, 10, 0))
    )

    assert resp.success, resp.error
    assert resp.source == "ANGEL", f"archive-served frames are ANGEL/RAW native: {resp.source}"
    assert broker_calls["n"] == 0
    # 09:30..10:00 inclusive = 31 minutes
    assert len(resp.data.candles) == 31
    assert resp.data.candles[0].timestamp == datetime(2026, 6, 2, 9, 30)
    # The 09:30 bar is seeded by the 09:30:05 rollover tick -> open 1003.75
    assert resp.data.candles[0].open == pytest.approx(1003.75)


def test_provider_resamples_archive_to_15m(tmp_path, monkeypatch):
    """A 15m request against the archive is served as an aggregate of the
    captured 1m bars (Open=first/High=max/Low=min/Close=last/Vol=sum)."""
    archive = archive_seed_helper(tmp_path, bars=75)

    broker_calls = {"n": 0}

    def stub_fetch(symbol, **kwargs):
        broker_calls["n"] += 1
        raise AssertionError("broker must not be reached when archive covers the request")

    monkeypatch.setattr(
        "mjonai.research.data.providers.angelone_intraday.fetch_historical_candles",
        stub_fetch,
    )

    service = build_service(tmp_path, None, archive=archive)

    resp = service.get_historical_data(
        request(datetime(2026, 6, 2, 9, 15), datetime(2026, 6, 2, 10, 15), timeframe="15m")
    )

    assert resp.success, resp.error
    assert broker_calls["n"] == 0
    # t+1 rollover closes the last minute -> 5 complete 15m buckets 09:15..10:00
    assert len(resp.data.candles) == 5
    first = resp.data.candles[0]
    assert first.timestamp == datetime(2026, 6, 2, 9, 15)
    # Bucket 0 aggregates 1m bars i=0..14, seeded as 1000 + 0.25*i + sec/100
    assert first.open == pytest.approx(1000.0 + 0.10, abs=1e-6)
    assert first.high == pytest.approx(1000.0 + 14 * 0.25 + 0.55, abs=1e-6)
    assert first.low == pytest.approx(1000.0 + 0.10, abs=1e-6)
    assert first.close == pytest.approx(1000.0 + 14 * 0.25 + 0.55, abs=1e-6)
    # each bar i carries 3 ticks of volume (100+i); bar i>=1 also absorbs the
    # prior rollover tick (100+i): bar0=300, bars1..14 = 4*(100+i)
    expected_volume = 3 * 100 + 4 * sum(100 + i for i in range(1, 15))
    assert first.volume == pytest.approx(expected_volume, abs=1e-6)


def test_provider_falls_through_to_broker_when_archive_absent(tmp_path, monkeypatch):
    """Empty archive (no captured bars for the symbol) falls through to the
    broker path exactly as before — including the P0.2 SMART_API acceptance."""
    archive = archive_seed_helper(tmp_path, symbol="OTHER", bars=10)

    def stub_fetch(symbol, **kwargs):
        frame = make_minute_frame(datetime(2026, 6, 2, 9, 15), 100)
        frame.attrs["data_provider"] = "SMART_API"
        return frame

    monkeypatch.setattr(
        "mjonai.research.data.providers.angelone_intraday.fetch_historical_candles",
        stub_fetch,
    )

    service = build_service(tmp_path, None, archive=archive)
    resp = service.get_historical_data(
        request(datetime(2026, 6, 2, 9, 15), datetime(2026, 6, 2, 10, 15))
    )

    assert resp.success, resp.error
    assert len(resp.data.candles) == 61
    assert resp.source == "ANGEL"


def test_provider_falls_through_to_broker_on_unsupported_archive_cadence(tmp_path, monkeypatch):
    """3m is not a resample target of the archive (1m/5m/10m/15m/30m/1h only),
    so the request falls through to the broker instead of inventing bars."""
    archive = archive_seed_helper(tmp_path, bars=75)

    def stub_fetch(symbol, **kwargs):
        frame = make_minute_frame(datetime(2026, 6, 2, 9, 15), 100)
        frame.attrs["data_provider"] = "SMART_API"
        return frame

    monkeypatch.setattr(
        "mjonai.research.data.providers.angelone_intraday.fetch_historical_candles",
        stub_fetch,
    )

    service = build_service(tmp_path, None, archive=archive)
    resp = service.get_historical_data(
        request(datetime(2026, 6, 2, 9, 15), datetime(2026, 6, 2, 10, 15), timeframe="3m")
    )

    assert resp.success, resp.error
    assert len(resp.data.candles) == 61
    assert resp.source == "ANGEL"


def test_provider_archive_clips_to_request_window(tmp_path, monkeypatch):
    """Archive covers more minutes than the request: only the requested window
    is served (like the broker path), never the whole captured span."""
    archive = archive_seed_helper(tmp_path, bars=75)

    broker_calls = {"n": 0}

    def stub_fetch(symbol, **kwargs):
        broker_calls["n"] += 1
        raise AssertionError("broker must not be reached")

    monkeypatch.setattr(
        "mjonai.research.data.providers.angelone_intraday.fetch_historical_candles",
        stub_fetch,
    )

    service = build_service(tmp_path, None, archive=archive)
    resp = service.get_historical_data(
        request(datetime(2026, 6, 2, 10, 0), datetime(2026, 6, 2, 10, 15))
    )

    assert resp.success, resp.error
    assert broker_calls["n"] == 0
    assert len(resp.data.candles) == 16  # 10:00..10:15 inclusive from archive
    assert resp.data.candles[0].timestamp == datetime(2026, 6, 2, 10, 0)
    assert resp.data.candles[-1].timestamp == datetime(2026, 6, 2, 10, 15)