"""Regression tests: durable 1-minute bar archive (minute pipeline, Phase 1).

Pins the contract that closed 1-minute bars from LiveCandleBuilder are
persisted under the ANGEL/RAW cache identity (colliding deliberately with the
research intraday provider path), survive a reload, and never mix regimes.
All OFFLINE - synthetic ticks only, temp parquet root."""

from datetime import datetime, timedelta

import pytest

from mjonai.core.enums import AdjustmentMode, Provider
from mjonai.data.candle_builder import LiveCandleBuilder
from mjonai.data.instruments.models import Instrument
from mjonai.data.minute_archive import (
    MinuteBarArchive,
    _make_instrument,
    minute_archive_tick_listener,
)
from mjonai.research.data.timeframe import TimeFrame
from mjonai.storage.models import StorageKey
from mjonai.storage.parquet_store import ParquetStore


def tick_series(symbol="RELIANCE", start="09:15", bars=3):
    """Synthetic per-minute tick timestamps ending each bar with a rollover."""
    ticks = []
    base = datetime(2026, 9, 21, 9, 15, 0)
    for i in range(bars):
        bar_start = base + timedelta(minutes=i)
        for sec in (10, 30, 55):
            ticks.append(
                (symbol, float(1000 + i * 10 + sec / 100.0), int(100 + i), bar_start.replace(second=sec))
            )
        # First tick of the NEXT minute forces the previous bar to close.
        nxt = bar_start + timedelta(minutes=1)
        ticks.append((symbol, float(1000 + (i + 1) * 10), int(100 + i + 1), nxt.replace(second=5)))
    return ticks


def make_instrument(symbol):
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


def test_path_identity_matches_documentation(tmp_path):
    from pathlib import Path

    archive = MinuteBarArchive(root=str(tmp_path))
    got = Path(archive.path_for("RELIANCE")).as_posix()
    assert got.endswith("angel/NSE/RELIANCE/1m_raw.parquet")

    # Same identity the research intraday provider writes under.
    key = StorageKey(
        provider=Provider.ANGEL,
        instrument=make_instrument("RELIANCE"),
        timeframe=TimeFrame.MIN_1,
        adjustment_mode=AdjustmentMode.RAW,
    )
    expected = Path(str(ParquetStore(root=str(tmp_path))._path(key))).as_posix()
    assert got == expected


def test_closed_1m_bars_persist_and_reload(tmp_path):
    archive = MinuteBarArchive(root=str(tmp_path), flush_threshold=1000)
    builder = LiveCandleBuilder(closed_bar_callback=archive.sink_closed)

    for symbol, price, vol, ts in tick_series(bars=3):
        builder.on_tick(symbol, price, vol, ts)

    assert archive.pending_count > 0

    archive.flush("RELIANCE")
    assert archive.pending_count == 0

    history = archive.load("RELIANCE")
    assert history is not None
    assert history.timeframe == TimeFrame.MIN_1
    assert len(history.candles) == 3

    closes = [c.close for c in history.candles]
    assert closes[0] == pytest.approx(1000.55)  # last tick of 09:15 bar
    assert closes[1] == pytest.approx(1010.55)
    assert history.candles[0].timestamp == datetime(2026, 9, 21, 9, 15, 0)
    assert history.candles[0].open == pytest.approx(1000.1)
    assert history.candles[0].volume == pytest.approx(300.0)


def test_open_bars_and_5m_aggregates_not_archived(tmp_path):
    archive = MinuteBarArchive(root=str(tmp_path))
    builder = LiveCandleBuilder(closed_bar_callback=archive.sink_closed)

    # One minute alone: the 09:15 1m bar never closes (no next-minute tick yet)
    # and the 5m bar is never closed either - nothing should be archived.
    builder.on_tick("RELIANCE", 1000.0, 100, datetime(2026, 9, 21, 9, 15, 30))

    archive.flush("RELIANCE")
    assert archive.load("RELIANCE") is None


def test_archive_merges_across_flushes_without_duplicates(tmp_path):
    archive = MinuteBarArchive(root=str(tmp_path))
    builder = LiveCandleBuilder(closed_bar_callback=archive.sink_closed)

    for symbol, price, vol, ts in tick_series(bars=2):
        builder.on_tick(symbol, price, vol, ts)
    archive.flush("RELIANCE")

    # Re-run the same ticks on a fresh builder (as if the feed replayed them)
    # and flush again - the cache must dedup, not balloon.
    builder = LiveCandleBuilder(closed_bar_callback=archive.sink_closed)
    for symbol, price, vol, ts in tick_series(bars=2):
        builder.on_tick(symbol, price, vol, ts)
    archive.flush("RELIANCE")

    history = archive.load("RELIANCE")
    assert history is not None
    assert len(history.candles) == 2  # deduped, not appended twice


def test_regime_mixing_fails_closed(tmp_path):
    from pathlib import Path

    # Corrupt-cache scenario: an ADJUSTED-tagged file sitting under the RAW
    # identity path (stale or mis-written cache). A RAW archive flush must
    # refuse to merge and leave the history queued, never silently overwritten.
    from mjonai.research.data.models import Candle, HistoricalData

    raw_path = Path(tmp_path) / "angel" / "NSE" / "RELIANCE" / "1m_raw.parquet"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    import pandas as pd

    pd.DataFrame(
        [
            {
                "timestamp": datetime(2026, 9, 21, 9, 15, 0),
                "open": 1000.0,
                "high": 1001.0,
                "low": 999.0,
                "close": 1000.5,
                "volume": 100.0,
                "open_interest": None,
                "adjustment_mode": "adjusted",  # corrupt regime tag
            }
        ]
    ).to_parquet(raw_path, index=False)

    archive = MinuteBarArchive(root=str(tmp_path))
    builder = LiveCandleBuilder(closed_bar_callback=archive.sink_closed)
    for symbol, price, vol, ts in tick_series(bars=1):
        builder.on_tick(symbol, price, vol, ts)

    with pytest.raises(ValueError, match="Refusing to merge adjustment regimes"):
        archive.flush("RELIANCE")

    # The buffered history stays queued, never silently dropped.
    assert archive.pending_count == 1


def test_tick_listener_feeds_builder_and_archive(tmp_path):
    archive = MinuteBarArchive(root=str(tmp_path))
    builder = LiveCandleBuilder()
    resolver = {"2885": "RELIANCE"}
    listener = minute_archive_tick_listener(
        archive=archive,
        builder=builder,
        token_to_symbol=lambda t: resolver.get(t),
    )

    base = datetime(2026, 9, 21, 9, 15, 0)
    for sec in (10, 55):
        listener(
            {
                "token": "2885",
                "ltp": float(1000 + sec / 100.0),
                "volume": 100,
                "timestamp": base.replace(second=sec),
            }
        )
    # First tick of next minute closes the 09:15 bar.
    listener(
        {
            "token": "2885",
            "ltp": 1010.0,
            "volume": 200,
            "timestamp": base.replace(hour=9, minute=16, second=5),
        }
    )

    archive.flush("RELIANCE")
    history = archive.load("RELIANCE")
    assert history is not None
    assert history.candles[0].close == pytest.approx(1000.55)


def test_tick_listener_ignores_unknown_token_and_missing_ltp(tmp_path):
    archive = MinuteBarArchive(root=str(tmp_path))
    builder = LiveCandleBuilder()
    resolver = {"2885": "RELIANCE"}
    listener = minute_archive_tick_listener(
        archive=archive,
        builder=builder,
        token_to_symbol=lambda t: resolver.get(t),
    )

    listener({"token": "999999", "ltp": 100.0, "volume": 1, "timestamp": datetime(2026, 9, 21, 9, 15, 1)})
    listener({"token": "2885", "volume": 1, "timestamp": datetime(2026, 9, 21, 9, 15, 1)})
    archive.flush("RELIANCE")
    assert archive.load("RELIANCE") is None


def test_make_instrument_is_angel_nse_equity():
    inst = _make_instrument("hdfc")
    assert inst.symbol == "HDFC"
    assert inst.provider == "ANGEL"
    assert inst.exchange == "NSE"
    assert inst.asset_type == "EQUITY"


# ── PHASE 2: NATIVE FRAME READER (scanner on native minutes) ────────────────

def seed_archive(tmp_path, symbol="RELIANCE", bars=75):
    """Persist `bars` closed 1-minute bars covering ~75 real minutes."""
    archive = MinuteBarArchive(root=str(tmp_path))
    builder = LiveCandleBuilder(closed_bar_callback=archive.sink_closed)
    base = datetime(2026, 9, 21, 9, 15, 0)
    for i in range(bars):
        bar_start = base + timedelta(minutes=i)
        price = float(1000 + i * 10)
        for sec in (10, 30, 55):
            builder.on_tick(symbol, price + sec / 100.0, int(100 + i), bar_start.replace(second=sec))
        nxt = bar_start + timedelta(minutes=1)
        builder.on_tick(symbol, float(1000 + (i + 1) * 10), int(100 + i + 1), nxt.replace(second=5))
    archive.flush(symbol)
    return archive


def test_to_dataframe_roundtrip_matches_persisted_bars(tmp_path):
    archive = seed_archive(tmp_path, bars=3)
    df = archive.to_dataframe("RELIANCE")
    assert df is not None
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 3
    assert df.index.name == "timestamp"
    # Ascending deterministic order, first 09:15 bar OHLCV intact
    assert df.iloc[0]["Open"] == pytest.approx(1000.1)
    assert df.iloc[0]["High"] == pytest.approx(1000.55)
    assert df.iloc[0]["Close"] == pytest.approx(1000.55)
    assert df.iloc[0]["Volume"] == pytest.approx(300.0)


def test_to_dataframe_none_when_symbol_absent(tmp_path):
    archive = MinuteBarArchive(root=str(tmp_path))
    assert archive.to_dataframe("MISSING") is None


def test_load_cadence_resamples_to_15m(tmp_path):
    # 75 x 1m bars -> 5 complete 15m buckets (t+1 rollover closes last minute).
    archive = seed_archive(tmp_path, bars=75)
    frame = archive.load_cadence("RELIANCE", cadence="15m")
    assert frame is not None
    assert len(frame) == 5
    # First 15m bucket: OHLC aggregation over bars 09:15..09:29 (i=0..14)
    first = frame.iloc[0]
    assert first["Open"] == pytest.approx(1000.1)
    assert first["Close"] == pytest.approx(1140.55)  # last 1m close inside bucket (i=14)
    # Bar 0 = 3 ticks of vol 100; bars i>=1 = 4 ticks of vol (100+i).
    # Sum i=0..14 = 300 + sum_{1..14}(400+4i) = 300 + 5600 + 4*105
    assert first["Volume"] == pytest.approx(6320.0)


def test_load_cadence_min_bars_fail_closed(tmp_path):
    archive = seed_archive(tmp_path, bars=75)
    # Requesting >= 6 resampled buckets when only 5 exist -> None (thin frame)
    assert archive.load_cadence("RELIANCE", cadence="15m", min_bars=6) is None
    assert archive.load_cadence("RELIANCE", cadence="15m", min_bars=5) is not None


def test_load_cadence_absent_and_unsupported_fail_closed(tmp_path):
    archive = MinuteBarArchive(root=str(tmp_path))
    assert archive.load_cadence("MISSING", cadence="15m") is None
    assert archive.load_cadence("RELIANCE", cadence="weekly") is None
    assert archive.load_cadence("RELIANCE", cadence="") is None