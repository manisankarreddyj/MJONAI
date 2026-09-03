"""
One-off migration: move the scratch Angel One 1-minute cache
(scratch/angelone_1min_cache/*_1min_6m.parquet) into the research
parquet store under proper StorageKeys — both the raw 1-minute base
and a resampled 15-minute variant per symbol.

Idempotent: merge-on-save deduplicates timestamps; re-running is safe.
"""

from pathlib import Path

import pandas as pd

from core.enums import Provider
from data.instruments.models import Instrument
from research.data.models import Candle, HistoricalData
from research.data.timeframe import TimeFrame
from storage.models import StorageKey
from storage.parquet_store import ParquetStore


CACHE_DIR = Path("scratch/angelone_1min_cache")
store = ParquetStore(root="storage/parquet")


def bare_instrument(symbol: str) -> Instrument:
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


def frame_to_historical(df: pd.DataFrame, inst: Instrument, tf: TimeFrame) -> HistoricalData:
    candles = [
        Candle(
            timestamp=ts.to_pydatetime(),
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=float(row.get("Volume", 0.0) or 0.0),
        )
        for ts, row in df.iterrows()
    ]
    return HistoricalData(instrument=inst, timeframe=tf, candles=candles)


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    idx = df.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("Asia/Kolkata").tz_localize(None)
    df.index = idx
    df = df.sort_index()
    return df[~df.index.duplicated(keep="last")]


def main() -> None:
    files = sorted(CACHE_DIR.glob("*_1min_6m.parquet"))
    print(f"Migrating {len(files)} six-month series (skipping _30d duplicates)...")

    migrated = skipped = 0

    for f in files:
        symbol = f.name.split("_1min_")[0]
        inst = bare_instrument(symbol)

        df = normalize(pd.read_parquet(f))
        if len(df) < 100:
            print(f"  {symbol:<12} SKIP ({len(df)} rows)")
            skipped += 1
            continue

        key_1m = StorageKey(provider=Provider.ANGEL, instrument=inst, timeframe=TimeFrame.MIN_1)
        store.save(key_1m, frame_to_historical(df, inst, TimeFrame.MIN_1))

        agg = (
            df.resample("15min")
            .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
            .dropna(subset=["Open", "High", "Low", "Close"])
        )
        key_15 = StorageKey(provider=Provider.ANGEL, instrument=inst, timeframe=TimeFrame.MIN_15)
        store.save(key_15, frame_to_historical(agg, inst, TimeFrame.MIN_15))

        migrated += 1
        print(f"  {symbol:<12} 1m={len(df):>6} rows | 15m={len(agg):>5} bars")

    print(f"\nDone: migrated={migrated} skipped={skipped}")


if __name__ == "__main__":
    main()