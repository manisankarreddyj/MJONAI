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

import pandas as pd

from mjonai.core.enums import AdjustmentMode, Provider
from mjonai.data.angelone.historical import _resample_to_interval
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


def _to_resample_anchor(cadence: str) -> Optional[str]:
    """Normalize a scanner/registry cadence label to a pandas resample anchor.

    Accepts scanner-style shorthand ("5m", "15m", "30m", "1h") or the pandas
    anchor already ("5min", "15min"). Anything else returns None so callers
    fail closed rather than silently resampling with an unexpected rule.
    """
    if not cadence:
        return None
    c = str(cadence).strip().lower()
    if c in ("5min", "10min", "15min", "30min", "1h", "2h"):
        return c
    shorthand = {"5m": "5min", "10m": "10min", "15m": "15min", "30m": "30min"}
    return shorthand.get(c)


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

    def to_dataframe(self, symbol: str) -> Optional[pd.DataFrame]:
        """Read persisted 1m RAW history as a standard pandas OHLCV frame
        (DatetimeIndex, columns Open/High/Low/Close/Volume), ascending.

        Returns None when the symbol has no archived bars — the honest
        no-data sentinel; an empty archive and a missing file are the same
        condition from the consumer's perspective.
        """
        history = self.load(symbol)
        if history is None or not history.candles:
            return None
        rows = []
        for c in history.candles:
            rows.append(
                {
                    "Open": float(c.open),
                    "High": float(c.high),
                    "Low": float(c.low),
                    "Close": float(c.close),
                    "Volume": float(c.volume or 0.0),
                }
            )
        df = pd.DataFrame(rows, index=[c.timestamp for c in history.candles])
        df.index.name = "timestamp"
        df = df.sort_index()
        df = df[~df.index.duplicated(keep="last")]
        return df

    def load_cadence(
        self,
        symbol: str,
        cadence: str = "15m",
        min_bars: Optional[int] = None,
    ) -> Optional[pd.DataFrame]:
        """Read archived 1m RAW history resampled UP to a scanning cadence.

        cadence is either a scanner-style string ("5m", "15m", "30m", "1h")
        or a pandas resample anchor ("5min", "15min", "1h"). Returns None when
        the archive has no bars for the symbol, or when the resampled frame is
        shorter than `min_bars` (fail-closed: an intraday strategy must never
        be fed a thin, honor-bound frame it will misread as a signal — and
        never a daily frame labeled as an intraday one).
        """
        df = self.to_dataframe(symbol)
        if df is None or df.empty:
            return None
        resample_anchor = _to_resample_anchor(cadence)
        if resample_anchor is None:
            logger.warning("[MinuteArchive] unsupported cadence %r for %s", cadence, symbol)
            return None
        try:
            resampled = _resample_to_interval(df, resample_anchor)
        except Exception:
            logger.exception("[MinuteArchive] cadence resample failed for %s@%s", symbol, cadence)
            return None
        if resampled is None or resampled.empty or len(resampled) <= 1:
            return None
        if min_bars is not None and len(resampled) < min_bars:
            return None
        return resampled

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

    # P0-DATA-1: AngelOne ticks carry CUMULATIVE day volume
    # (volume_trade_for_the_day), but LiveCandle.update() ACCUMULATES per
    # tick — feeding the raw value multiplied one day's volume by the tick
    # count. Track the last cumulative per symbol and feed only the
    # non-negative DELTA. First sighting emits 0 (prior volume unobserved —
    # never invented); a counter reset (new day) emits the full reading.
    _last_cumulative: Dict[str, int] = {}

    def _on_tick(tick_event: dict) -> None:
        token = str(tick_event.get("token") or "")
        symbol = resolver(token)
        ltp = tick_event.get("ltp")
        if not symbol or not ltp:
            return
        try:
            raw_vol = tick_event.get("volume")
            cumulative = int(float(raw_vol)) if raw_vol is not None else None
            if cumulative is None:
                delta = 0
            else:
                last = _last_cumulative.get(symbol)
                if last is None:
                    delta = 0
                elif cumulative >= last:
                    delta = cumulative - last
                else:
                    delta = cumulative  # day rollover: counter restarted
                _last_cumulative[symbol] = cumulative
            builder.on_tick(
                symbol,
                float(ltp),
                delta,
                tick_event.get("timestamp"),
            )
        except Exception:
            logger.exception("[MinuteArchive] tick dropped (feed continues)")

    return _on_tick


_DEFAULT_ARCHIVE = MinuteBarArchive()