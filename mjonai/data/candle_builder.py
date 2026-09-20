"""
Module: data/candle_builder.py
Purpose: Real-Time In-Memory Multi-Timeframe OHLCV Candle Aggregator.
         Synthesizes incoming WebSocket ticks into rolling 1-minute and 5-minute
         candles in RAM with zero REST API overhead during live market hours.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import threading
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from mjonai.core.time_utils import now_ist

logger = logging.getLogger(__name__)


@dataclass
class LiveCandle:
    """Mutable in-memory candle bar currently accumulating ticks."""
    symbol: str
    interval_minutes: int
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    ticks_count: int = 0
    is_closed: bool = False

    def update(self, price: float, volume: int = 0) -> None:
        """Update candle with incoming tick."""
        if price > self.high:
            self.high = price
        if price < self.low:
            self.low = price
        self.close = price
        self.volume += volume
        self.ticks_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.open_time.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "ticks_count": self.ticks_count,
            "is_closed": self.is_closed,
        }


class LiveCandleBuilder:
    """
    Thread-Safe Multi-Timeframe Real-Time Candle Synthesizer.
    Maintains active in-flight candles and historical rolling buffer in RAM.
    """

    def __init__(
        self,
        max_history_bars: int = 500,
        closed_bar_callback: Optional[object] = None,
    ):
        self.max_history = max_history_bars
        # Optional durable-archive sink: invoked (outside the lock) with each
        # closed LiveCandle so the RAM-only builder can feed a persistence layer
        # without blocking the tick loop. Phase 1 of the minute pipeline.
        self.closed_bar_callback = closed_bar_callback
        # Map: (symbol, interval_min) -> current LiveCandle
        self._active_candles: Dict[Tuple[str, int], LiveCandle] = {}
        # Map: (symbol, interval_min) -> List[LiveCandle]
        self._completed_candles: Dict[Tuple[str, int], List[LiveCandle]] = {}
        self._lock = threading.RLock()

    def _get_bar_open_time(self, ts: datetime, interval_minutes: int) -> datetime:
        """Align timestamp to the start of the interval bar (e.g. 09:15, 09:16, 09:20)."""
        minute = (ts.minute // interval_minutes) * interval_minutes
        return ts.replace(minute=minute, second=0, microsecond=0)

    def on_tick(self, symbol: str, price: float, volume: int = 0, timestamp: Optional[datetime] = None) -> None:
        """
        Process a new real-time tick for 1-minute and 5-minute bar aggregation.
        """
        if price <= 0.0:
            return

        ts = timestamp or now_ist()
        clean_sym = symbol.strip().upper()

        closed_candles: List[LiveCandle] = []

        with self._lock:
            for interval in (1, 5):
                key = (clean_sym, interval)
                bar_start = self._get_bar_open_time(ts, interval)

                active = self._active_candles.get(key)
                if active is None:
                    # Initialize new candle
                    self._active_candles[key] = LiveCandle(
                        symbol=clean_sym,
                        interval_minutes=interval,
                        open_time=bar_start,
                        open=price,
                        high=price,
                        low=price,
                        close=price,
                        volume=volume,
                        ticks_count=1,
                    )
                elif active.open_time == bar_start:
                    # Accumulate tick into active candle
                    active.update(price, volume)
                else:
                    # Bar completed: close active candle and roll over to new bar
                    active.is_closed = True
                    closed_candles.append(active)
                    if key not in self._completed_candles:
                        self._completed_candles[key] = []
                    self._completed_candles[key].append(active)
                    if len(self._completed_candles[key]) > self.max_history:
                        self._completed_candles[key].pop(0)

                    # Start new bar
                    self._active_candles[key] = LiveCandle(
                        symbol=clean_sym,
                        interval_minutes=interval,
                        open_time=bar_start,
                        open=price,
                        high=price,
                        low=price,
                        close=price,
                        volume=volume,
                        ticks_count=1,
                    )

        # Dispatch closed bars to the optional durable-archive sink outside the
        # lock so persistence IO can never delay an incoming tick.
        if closed_candles and self.closed_bar_callback is not None:
            for closed in closed_candles:
                try:
                    self.closed_bar_callback(closed)
                except Exception as ex:
                    logger.warning(f"[CandleBuilder] closed-bar callback error: {ex}")

    def get_candles_dataframe(self, symbol: str, interval_minutes: int = 1) -> pd.DataFrame:
        """
        Export completed and current in-flight candle series as a standardized pandas DataFrame.
        """
        clean_sym = symbol.strip().upper()
        key = (clean_sym, interval_minutes)

        with self._lock:
            completed = self._completed_candles.get(key, [])
            active = self._active_candles.get(key)

            rows = [c.to_dict() for c in completed]
            if active:
                rows.append(active.to_dict())

        if not rows:
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

        df = pd.DataFrame(rows)
        df["Timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("Timestamp", inplace=True)
        df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
        return df[["Open", "High", "Low", "Close", "Volume"]]

    def clear(self) -> None:
        """Clear all active and completed in-memory candle series."""
        with self._lock:
            self._active_candles.clear()
            self._completed_candles.clear()


# Global Singleton Real-Time Candle Synthesizer
GLOBAL_CANDLE_BUILDER = LiveCandleBuilder()
