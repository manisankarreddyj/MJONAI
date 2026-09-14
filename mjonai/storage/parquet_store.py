from __future__ import annotations

from pathlib import Path

import pandas as pd

from mjonai.research.data.models import Candle, HistoricalData
from mjonai.storage.base import StorageBackend
from mjonai.storage.models import StorageKey


class ParquetStore(StorageBackend):

    def __init__(
        self,
        root: str = "storage/parquet",
    ):

        self.root = Path(root)

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _path(
        self,
        key: StorageKey,
    ) -> Path:

        return (
            self.root
            / key.provider.value.lower()
            / key.instrument.exchange
            / key.instrument.symbol
            / f"{key.timeframe.value}_{key.adjustment_mode.value}.parquet"
        )

    def exists(
        self,
        key: StorageKey,
    ) -> bool:

        return self._path(key).exists()

    def save(
        self,
        key: StorageKey,
        data: HistoricalData,
    ) -> None:

        path = self._path(key)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        df = pd.DataFrame(
            [
                {
                    "timestamp": c.timestamp,
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                    "open_interest": c.open_interest,
                    "adjustment_mode": key.adjustment_mode.value,
                }
                for c in data.candles
            ]
        )

        # Merge with any existing history so the cache grows
        # toward full coverage instead of holding only the most
        # recent fetch window. The path already isolates raw vs
        # adjusted series, but this is an explicit fail-closed
        # guard: never merge series whose stored regime differs.
        if path.exists():

            existing = pd.read_parquet(path)

            existing_mode = existing.get("adjustment_mode")
            if existing_mode is not None and len(existing_mode) > 0:
                stored_mode = existing_mode.iloc[0]
                if stored_mode != key.adjustment_mode.value:
                    raise ValueError(
                        f"Refusing to merge adjustment regimes for {path}: "
                        f"stored={stored_mode} incoming={key.adjustment_mode.value}"
                    )

            df = pd.concat(
                [existing, df],
                ignore_index=True,
            )

            df = df.drop_duplicates(
                subset=["timestamp"],
                keep="last",
            )

            df = df.sort_values(
                "timestamp",
            ).reset_index(
                drop=True,
            )

        df.to_parquet(path, index=False)

    def load(
        self,
        key: StorageKey,
    ) -> HistoricalData | None:

        path = self._path(key)

        if not path.exists():
            return None

        df = pd.read_parquet(path)

        candles = [
            Candle(
                timestamp=row.timestamp,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
                open_interest=row.open_interest,
            )
            for row in df.itertuples(index=False)
        ]

        return HistoricalData(
            instrument=key.instrument,
            timeframe=key.timeframe,
            candles=candles,
        )