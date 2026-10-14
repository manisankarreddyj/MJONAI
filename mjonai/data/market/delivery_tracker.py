"""
Module: data/market/delivery_tracker.py
Purpose: SOTA NSE Daily Security-Wise Deliverable Volume & Institutional Accumulation Engine.
         Downloads official NSE security delivery data (MTO_DDMMYYYY.DAT / Bhavcopy):
         - Deliverable Quantity & Total Traded Quantity
         - Delivery % = (Deliverable Qty / Total Traded Qty) * 100
         - Institutional Accumulation Sentry:
           * Delivery % >= 60% -> Strong Institutional Accumulation (Conviction Booster)
           * 35% <= Delivery % < 60% -> Balanced Normal Delivery
           * Delivery % < 25% -> Pure Speculative Intraday Churn (No Institutional Holding)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Tuple

from mjonai.core.time_utils import now_ist, today_ist

logger = logging.getLogger(__name__)


class DeliveryZone(str, Enum):
    INSTITUTIONAL_ACCUMULATION = "INSTITUTIONAL_ACCUMULATION"  # Delivery % >= 60% (High conviction)
    NORMAL_DELIVERY            = "NORMAL_DELIVERY"             # 35% <= Delivery % < 60%
    SPECULATIVE_CHURN          = "SPECULATIVE_CHURN"           # Delivery % < 25% (Low institutional holding)


@dataclass(frozen=True)
class DeliveryReportSnapshot:
    """
    Immutable Security Delivery Analysis Payload.
    """
    symbol: str
    traded_quantity: int
    deliverable_quantity: int
    delivery_percentage: float
    delivery_zone: DeliveryZone
    is_institutional_accumulation: bool
    is_speculative_churn: bool
    date_str: str
    timestamp: datetime
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "traded_quantity": self.traded_quantity,
            "deliverable_quantity": self.deliverable_quantity,
            "delivery_percentage": round(self.delivery_percentage, 2),
            "delivery_zone": self.delivery_zone.value,
            "is_institutional_accumulation": self.is_institutional_accumulation,
            "is_speculative_churn": self.is_speculative_churn,
            "date": self.date_str,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
        }


# In-memory delivery registry
_DELIVERY_CACHE: Dict[str, Tuple[int, int, float, str]] = {}
_delivery_lock = threading.RLock()


def register_delivery_data(
    symbol: str,
    traded_qty: int,
    deliverable_qty: int,
    date_str: Optional[str] = None
) -> DeliveryReportSnapshot:
    """
    Compute delivery percentage and register into cache.
    """
    clean_sym = symbol.strip().upper()
    now = now_ist()
    d_str = date_str or str(today_ist())

    t_qty = max(1, traded_qty)
    d_qty = min(t_qty, max(0, deliverable_qty))
    deliv_pct = (d_qty / float(t_qty)) * 100.0

    if deliv_pct >= 60.0:
        zone = DeliveryZone.INSTITUTIONAL_ACCUMULATION
        is_accum = True
        is_churn = False
        msg = f"Strong Institutional Accumulation for {clean_sym} (Delivery: {deliv_pct:.1f}% >= 60%)"
    elif deliv_pct < 25.0:
        zone = DeliveryZone.SPECULATIVE_CHURN
        is_accum = False
        is_churn = True
        msg = f"Speculative Intraday Churn for {clean_sym} (Delivery: {deliv_pct:.1f}% < 25%)"
    else:
        zone = DeliveryZone.NORMAL_DELIVERY
        is_accum = False
        is_churn = False
        msg = f"Normal Delivery Flow for {clean_sym} (Delivery: {deliv_pct:.1f}%)"

    with _delivery_lock:
        _DELIVERY_CACHE[clean_sym] = (t_qty, d_qty, deliv_pct, d_str)

    return DeliveryReportSnapshot(
        symbol=clean_sym,
        traded_quantity=t_qty,
        deliverable_quantity=d_qty,
        delivery_percentage=deliv_pct,
        delivery_zone=zone,
        is_institutional_accumulation=is_accum,
        is_speculative_churn=is_churn,
        date_str=d_str,
        timestamp=now,
        message=msg,
    )


def get_delivery_snapshot(symbol: str) -> Optional[DeliveryReportSnapshot]:
    """
    Retrieve current delivery assessment for a symbol.

    Fail-closed (wired 2026-10-14): an unfed symbol returns None — the old
    100k/45k "Normal Delivery" baseline fabricated a reading for every
    unknown symbol. Callers must treat None as unknown, never as 45%.
    """
    clean_sym = symbol.strip().upper()
    with _delivery_lock:
        cached = _DELIVERY_CACHE.get(clean_sym)

    if cached:
        t_qty, d_qty, _, d_str = cached
        return register_delivery_data(clean_sym, t_qty, d_qty, d_str)

    return None
