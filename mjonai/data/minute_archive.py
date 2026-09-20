"""
Module: data/minute_archive.py
Purpose: Durable, regime-tagged one-minute bar archive (minute pipeline, Phase 1).
         Sinks closed 1-minute bars from LiveCandleBuilder into the standard
         parquet cache under the ANGEL/RAW identity:
             storage/parquet/angel/NSE/{SYMBOL}/1m_raw.parquet
         so research, the scanner, and intraday strategies can read real
         minute history through the same cache layer as daily bars.

         The identity collides deliberately with what AngelOneIntradayProvider
         would write for a 1m RAW fetch, so live-captured bars merge with
         provider history instead of living in a parallel world.

         Capture is telemetry accumulation - never a trading-risk gate.
         Failures in the tick listener are contained by the websocket's own
         listener contract (logged, feed continues), matching the running
         engine's fail-open posture for non-risk data collection.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Dict, List, Optional

from mjonai.core.enums import AdjustmentMode, Provider
from mjonai.data.angelone.token_map import TOKEN_MAP
from mjonai.data.candle_builder import GLOBAL_CANDLE_BUILDER, LiveCandle
from mjonai.data.instruments.models import Instrument
from mjonai.research.data.models import Candle, HistoricalData
from mjonai.research.data.timeframe import TimeFrame
from mjonai.storage.models import StorageKey
from mjonai.storage.parquet_store import ParquetStore

logger = logging.getLogger(__name__)

_MINUTE_TF = TimeFrame.MIN_1  # "1m"
_RAW = AdjustmentMode.RAW     # "raw"
_ARCHIVE_TF = TimeFrame.MIN_1


def _make_instrument(symbol: str) -> Instrument:
    clean = symbol.strip().upper()
    return Instrument(
        instrument_id=f"1_{clean}",
        symbol=clean,
        name=clean,
        provider="ANGEL",
        provider_type="SMARTAPI",
        provider_exchange="NSE",
        exchange="NSE",
        asset_type="EQUITY",
        angel_symbol=clean,
    )


def _to_candles(closed: List[LiveCandle]) -> List[Candle]:
    return [
        Candle(
            timestamp=c.open_time,
            open=float(c.open),
            high=float(c.high),
            low=float(c.low),
            close=float(c.close),
            volume=float(c.volume or 0.0),
        )
        for c in closed
    ]


class MinuteBarArchive:
    """Durable, regime-tagged one-minute bar archive.

    Buffers closed 1-minute bars per symbol in RAM and flushes them to the
    ANGEL/RAW parquet cache in bounded batches (default every 60 bars per
    symbol) so per-bar disk rewrites never touch the tick hot path. Restores
    history through the same ParquetStore identity research reads.
    """

    def __init__(self, root: str = "storage/parquet", flush_threshold: int = 60):
        self._store = ParquetStore(root)
        self._flush_threshold = max(1, int(flush_threshold))
        self._pending: Dict[str, List[LiveCandle]] = {}
        self._lock = threading.Lock()

    def _key(self, symbol: str) -> StorageKey:
        return StorageKey(
            provider=Provider.ANGEL,
            instrument=_make_instrument(symbol),
            timeframe=_MINUTE_TF,
            adjustment_mode=_RAW,
        )

    def path_for(self, symbol: str) -> str:
        """Absolute cache path a symbol's 1m RAW history lives at.

        Public read/write identity surface - used by tests and operators to
        pin the documented cache layout, never by the persistence path.
        """
        return str(self._store._path(self._key(symbol)))

    def sink_closed(self, candle: LiveCandle) -> None:
        """Accept a closed 1-minute bar for durable persistence.

        Open/in-flight bars and 5-minute aggregates are ignored - 5m history
        is derivable from 1m and open bars are not complete records.
        """
        if not getattr(candle, "is_closed", False):
            return
        if getattr(candle, "interval_minutes", 0) != 1:
            return

        sym = candle.symbol.strip().upper()
        should_flush = False
        with self._lock:
            bucket = self._pending.setdefault(sym, [])
            bucket.append(candle)
            should_flush = len(bucket) >= self._flush_threshold
        if should_flush:
            self.flush(sym)

    def flush(self, symbol: Optional[str] = None) -> None:
        """Persist buffered closed bars for one symbol (or all when None)."""
        to_save: List[str] = []
        with self._lock:
            if symbol is None:
                to_save = list(self._pending)
            else:
                sym = symbol.strip().upper()
                to_save = [sym] if sym in self._pending else []

            for sym in to_save:
                buckets = self._pending.pop(sym, [])
                if not buckets:
                    continue
                candles = _to_candles(buckets)
                try:
                    self._store.save(
                        self._key(sym),
                        HistoricalData(
                            instrument=_make_instrument(sym),
                            timeframe=_ARCHIVE_TF,
                            candles=candles,
                        ),
                    )
                except Exception:
                    # Requeue so a transient failure (or a regime mismatch that
                    # ParquetStore rejects fail-closed) is never silently lost,
                    # then re-raise: a corrupted/conflicting cache must stay
                    # visible to the operator, not retried invisibly forever.
                    logger.exception("[MinuteArchive] flush failed for %s", sym)
                    self._pending.setdefault(sym, []).extend(buckets)
                    raise

    def load(self, symbol: str) -> Optional[HistoricalData]:
        """Load persisted 1m RAW history for a symbol (None when absent)."""
        return self._store.load(self._key(symbol))

    @property
    def pending_count(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._pending.values())


def minute_archive_tick_listener(
    archive: Optional[MinuteBarArchive] = None,
    builder: Optional[object] = None,
    token_to_symbol: Optional[Callable[[str], Optional[str]]] = None,
) -> Callable[[dict], None]:
    """Build the websocket tick-listener that feeds the candle builder and
    archives closed 1-minute bars.

    Defaults resolve to the engine-wide singletons (GLOBAL_CANDLE_BUILDER and
    this module's default archive) so apps/runtime/main.py can register the
    listener with zero wiring, while offline tests inject their own parts.
    """
    archive = archive if archive is not None else _DEFAULT_ARCHIVE
    builder = builder if builder is not None else GLOBAL_CANDLE_BUILDER
    resolver = token_to_symbol if token_to_symbol is not None else lambda t: TOKEN_MAP.get(t)
    builder.closed_bar_callback = archive.sink_closed

    def _on_tick(tick_event: dict) -> None:
        token = str(tick_event.get("token") or "")
        symbol = resolver(token)
        ltp = tick_event.get("ltp")
        if not symbol or not ltp:
            return
        try:
            builder.on_tick(
                symbol,
                float(ltp),
                int(float(tick_event.get("volume") or 0)),
                tick_event.get("timestamp"),
            )
        except Exception:
            logger.exception("[MinuteArchive] tick dropped (feed continues)")

    return _on_tick


_DEFAULT_ARCHIVE = MinuteBarArchive()