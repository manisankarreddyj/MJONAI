"""
Module: data/depth_archive.py
Purpose: Durable 5-level market-depth snapshot archive (depth pipeline).
         Sinks SNAP_QUOTE depth frames from the AngelOne WebSocket tick stream
         into per-symbol, per-day parquet files:
             storage/parquet/angel_depth/NSE/{SYMBOL}/{YYYY-MM-DD}.parquet
         Long-format schema (one row per book level):
             timestamp · symbol · side (bid/ask) · level (1-5) · price (₹) · quantity · orders

         Capture is telemetry accumulation — never a trading-risk gate.
         Consecutive identical snapshots are deduplicated so quiet symbols do
         not bloat the archive with redundant rows. Failures are contained by
         the websocket's listener contract (logged, feed continues).
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

from mjonai.data.angelone.token_map import TOKEN_MAP

logger = logging.getLogger(__name__)

_DEPTH_COLUMNS = [
    "timestamp",
    "symbol",
    "side",
    "level",
    "price",
    "quantity",
    "orders",
]


def _snapshot_fingerprint(
    bids: Optional[List[Dict[str, Any]]],
    asks: Optional[List[Dict[str, Any]]],
) -> Optional[Tuple]:
    """Build a hashable fingerprint of a depth snapshot for dedup.

    Returns None when both sides are empty/None (nothing to store).
    Two snapshots with the same fingerprint are identical — skip the second.
    """
    def _side_fp(levels: Optional[List[Dict[str, Any]]]) -> Tuple:
        if not levels:
            return ()
        return tuple(
            (lv.get("price"), lv.get("quantity"), lv.get("orders"))
            for lv in levels
        )

    b = _side_fp(bids)
    a = _side_fp(asks)
    if not b and not a:
        return None
    return (b, a)


def _snapshot_to_rows(
    timestamp: datetime,
    symbol: str,
    bids: Optional[List[Dict[str, Any]]],
    asks: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Flatten one depth snapshot into long-format rows (≤10 rows)."""
    rows: List[Dict[str, Any]] = []
    for side, levels in (("bid", bids), ("ask", asks)):
        if not levels:
            continue
        for i, lv in enumerate(levels[:5], start=1):
            rows.append({
                "timestamp": timestamp,
                "symbol": symbol,
                "side": side,
                "level": i,
                "price": lv.get("price"),
                "quantity": lv.get("quantity"),
                "orders": lv.get("orders"),
            })
    return rows


class DepthArchive:
    """Durable 5-level market-depth snapshot archive.

    Buffers depth snapshots per symbol in RAM and flushes them to
    per-day parquet files in bounded batches (default every 200 snapshots
    per symbol) so per-snapshot disk rewrites never touch the tick hot path.
    Consecutive identical snapshots are deduplicated at buffer time.
    """

    def __init__(
        self,
        root: str = "storage/parquet/angel_depth",
        flush_threshold: int = 200,
    ):
        self._root = Path(root)
        self._flush_threshold = max(1, int(flush_threshold))
        self._pending: Dict[str, List[Tuple[datetime, List[Dict], List[Dict]]]] = {}
        self._last_fp: Dict[str, Tuple] = {}
        self._lock = threading.Lock()

    def _path(self, symbol: str, day: date) -> Path:
        return (
            self._root
            / "NSE"
            / symbol.strip().upper()
            / f"{day.isoformat()}.parquet"
        )

    def path_for(self, symbol: str, day: date) -> str:
        """Absolute parquet path a symbol's depth snapshots for a day live at."""
        return str(self._path(symbol, day))

    def sink_snapshot(
        self,
        symbol: str,
        timestamp: datetime,
        bids: Optional[List[Dict[str, Any]]],
        asks: Optional[List[Dict[str, Any]]],
    ) -> None:
        """Accept one depth snapshot for durable persistence.

        Deduplicates consecutive identical snapshots (same bid/ask levels)
        so quiet symbols don't accumulate redundant rows.
        """
        sym = symbol.strip().upper()
        fp = _snapshot_fingerprint(bids, asks)
        if fp is None:
            return  # Nothing to store (both sides empty)

        should_flush = False
        with self._lock:
            if self._last_fp.get(sym) == fp:
                return  # Identical to previous snapshot — skip
            self._last_fp[sym] = fp
            bucket = self._pending.setdefault(sym, [])
            bucket.append((timestamp, bids or [], asks or []))
            should_flush = len(bucket) >= self._flush_threshold
        if should_flush:
            self.flush(sym)

    def flush(self, symbol: Optional[str] = None) -> None:
        """Persist buffered depth snapshots for one symbol (or all when None).

        Each flush merges into the per-day parquet file for the snapshot's
        date (the buffer can span midnight only if the engine runs past
        close — practically it flushes within one session).
        """
        to_save: List[str] = []
        with self._lock:
            if symbol is None:
                to_save = list(self._pending)
            else:
                sym = symbol.strip().upper()
                to_save = [sym] if sym in self._pending else []

            for sym in to_save:
                snapshots = self._pending.pop(sym, [])
                if not snapshots:
                    continue
                # Group by calendar date so each day lands in its own file
                by_day: Dict[date, List[Tuple[datetime, List, List]]] = {}
                for ts, b, a in snapshots:
                    d = ts.date() if hasattr(ts, "date") else date.today()
                    by_day.setdefault(d, []).append((ts, b, a))

                for day, day_snaps in by_day.items():
                    rows: List[Dict[str, Any]] = []
                    for ts, b, a in day_snaps:
                        rows.extend(_snapshot_to_rows(ts, sym, b, a))
                    if not rows:
                        continue
                    df = pd.DataFrame(rows, columns=_DEPTH_COLUMNS)
                    path = self._path(sym, day)
                    try:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        if path.exists():
                            existing = pd.read_parquet(path)
                            df = pd.concat([existing, df], ignore_index=True)
                        df.to_parquet(path, index=False)
                    except Exception:
                        # Requeue so a transient failure is never silently lost
                        logger.exception("[DepthArchive] flush failed for %s@%s", sym, day)
                        self._pending.setdefault(sym, []).extend(snapshots)
                        raise

    def to_dataframe(
        self,
        symbol: str,
        day: Optional[date] = None,
    ) -> Optional[pd.DataFrame]:
        """Read persisted depth snapshots as a long-format DataFrame.

        Returns None when no file exists for the symbol (and day, if given).
        """
        sym = symbol.strip().upper()
        if day is not None:
            path = self._path(sym, day)
            if not path.exists():
                return None
            return pd.read_parquet(path)

        # No day given: merge all available days for the symbol
        symbol_dir = self._root / "NSE" / sym
        if not symbol_dir.exists():
            return None
        frames = []
        for f in sorted(symbol_dir.glob("*.parquet")):
            try:
                frames.append(pd.read_parquet(f))
            except Exception:
                logger.exception("[DepthArchive] unreadable file %s", f)
        if not frames:
            return None
        return pd.concat(frames, ignore_index=True)

    @property
    def pending_count(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._pending.values())


def depth_archive_tick_listener(
    archive: Optional[DepthArchive] = None,
    token_to_symbol: Optional[Callable[[str], Optional[str]]] = None,
    min_interval_seconds: float = 0.0,
) -> Callable[[dict], None]:
    """Build the websocket tick-listener that sinks 5-level depth snapshots
    into a DepthArchive.

    Defaults resolve to the engine-wide singletons so apps/runtime/main.py
    can register the listener with zero wiring, while offline tests inject
    their own archive.

    min_interval_seconds throttles per-symbol writes (0.0 = store every
    distinct snapshot; Angel One's own push cadence already limits rate).
    """
    archive = archive if archive is not None else _DEFAULT_DEPTH_ARCHIVE
    resolver = token_to_symbol if token_to_symbol is not None else lambda t: TOKEN_MAP.get(t)
    last_written: Dict[str, datetime] = {}
    min_interval = float(min_interval_seconds or 0.0)

    def _on_tick(tick_event: dict) -> None:
        token = str(tick_event.get("token") or "")
        bids = tick_event.get("depth_bids")
        asks = tick_event.get("depth_asks")
        if not bids and not asks:
            return  # No depth in this frame (Mode 1/2)
        symbol = resolver(token)
        if not symbol:
            return
        ts = tick_event.get("timestamp")
        if ts is None:
            return
        if min_interval > 0:
            prev = last_written.get(symbol)
            if prev is not None and (ts - prev).total_seconds() < min_interval:
                return
            last_written[symbol] = ts
        try:
            archive.sink_snapshot(symbol, ts, bids, asks)
        except Exception:
            logger.exception("[DepthArchive] snapshot dropped (feed continues)")

    return _on_tick


_DEFAULT_DEPTH_ARCHIVE = DepthArchive()
