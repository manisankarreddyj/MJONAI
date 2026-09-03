"""
Module: execution/algo_execution.py
Purpose: SOTA Institutional Algorithmic Execution Engine for Indian Equities & Derivatives.
         Features:
           1. Implementation Shortfall (IS) Calculator (Arrival Price vs Final Fill Price).
           2. SEBI 10-OPS Token Bucket Rate Limiter (Prevents exchange throttling & bans).
           3. TWAP (Time-Weighted Average Price) Slicing Engine.
           4. VWAP (Volume-Weighted Average Price) Participation Slicer.
           5. Smart Order Routing (SOR) Broker Selector (Shoonya vs Angel One vs OpenAlgo).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import logging
import math
import time
import threading
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# ── 1. SEBI RATE LIMITER (TOKEN BUCKET) ───────────────────────────────────────

class SEBIRateLimiter:
    """
    Token bucket rate limiter enforcing SEBI/NSE 10 Orders Per Second (OPS) limit.
    Ensures algorithmic order dispatches never exceed exchange-permitted velocity.
    """

    def __init__(self, max_ops: int = 10, burst_limit: int = 10):
        self.max_ops = max(1, max_ops)
        self.capacity = burst_limit
        self.tokens = float(burst_limit)
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, tokens_needed: int = 1, timeout: float = 2.0) -> bool:
        """
        Block until required order tokens are available or timeout expires.
        """
        start_time = time.monotonic()
        while time.monotonic() - start_time < timeout:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self.last_refill
                self.tokens = min(float(self.capacity), self.tokens + elapsed * self.max_ops)
                self.last_refill = now

                if self.tokens >= tokens_needed:
                    self.tokens -= tokens_needed
                    return True

            time.sleep(0.02)

        logger.warning(f"[RateLimiter] Timeout waiting for {tokens_needed} order tokens.")
        return False


# Global default rate limiter singleton
GLOBAL_RATE_LIMITER = SEBIRateLimiter(max_ops=10, burst_limit=10)


# ── 2. IMPLEMENTATION SHORTFALL (SLIPPAGE & IMPACT TRACKER) ──────────────────

@dataclass(frozen=True)
class ImplementationShortfallResult:
    """Immutable contract tracking institutional execution quality and slippage."""
    symbol: str
    arrival_price: float
    final_execution_price: float
    total_quantity: int
    direction: str  # LONG / SHORT
    shortfall_rupees: float
    shortfall_bps: float
    market_impact_bps: float
    execution_duration_sec: float
    is_favorable: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calculate_implementation_shortfall(
    symbol: str,
    arrival_price: float,
    execution_price: float,
    quantity: int,
    direction: str = "LONG",
    execution_duration_sec: float = 0.0,
) -> ImplementationShortfallResult:
    """
    Calculate Perot / Almgren-Chriss Implementation Shortfall:
      IS (bps) = ((P_exec - P_arrival) / P_arrival) * 10,000 for BUYs
      IS (bps) = ((P_arrival - P_exec) / P_arrival) * 10,000 for SELLs
    """
    arr = max(0.01, float(arrival_price))
    exe = max(0.01, float(execution_price))
    qty = max(1, int(quantity))
    dir_u = str(direction).upper()

    if dir_u in ("LONG", "BUY"):
        price_diff = exe - arr
        shortfall_bps = (price_diff / arr) * 10000.0
    else:
        price_diff = arr - exe
        shortfall_bps = (price_diff / arr) * 10000.0

    total_shortfall_rupees = round(price_diff * qty, 2)
    is_fav = shortfall_bps <= 0.0  # Zero or negative slippage is favorable

    return ImplementationShortfallResult(
        symbol=symbol,
        arrival_price=round(arr, 2),
        final_execution_price=round(exe, 2),
        total_quantity=qty,
        direction=dir_u,
        shortfall_rupees=total_shortfall_rupees,
        shortfall_bps=round(shortfall_bps, 2),
        market_impact_bps=round(abs(shortfall_bps) * 0.6, 2),
        execution_duration_sec=round(execution_duration_sec, 2),
        is_favorable=is_fav,
    )


# ── 3. TWAP & VWAP ORDER SLICING ENGINES ─────────────────────────────────────

@dataclass(frozen=True)
class AlgoChildSlice:
    """Immutable contract representing a child slice in TWAP/VWAP execution."""
    slice_index: int
    quantity: int
    delay_seconds: float
    target_time_iso: str
    weight_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def generate_twap_slices(
    total_quantity: int,
    duration_minutes: int = 5,
    num_slices: int = 5,
) -> List[AlgoChildSlice]:
    """
    Generate Time-Weighted Average Price (TWAP) equal-distribution child slices.
    """
    qty = max(1, int(total_quantity))
    n = max(1, min(qty, int(num_slices)))
    interval_sec = (duration_minutes * 60.0) / float(n)

    base_qty = qty // n
    remainder = qty % n

    slices: List[AlgoChildSlice] = []
    accum_delay = 0.0

    for i in range(n):
        chunk = base_qty + (1 if i < remainder else 0)
        weight = (chunk / qty) * 100.0
        slices.append(AlgoChildSlice(
            slice_index=i + 1,
            quantity=chunk,
            delay_seconds=round(accum_delay, 1),
            target_time_iso=datetime.now(timezone.utc).isoformat(),
            weight_pct=round(weight, 2),
        ))
        accum_delay += interval_sec

    return slices


def generate_vwap_slices(
    total_quantity: int,
    intraday_volume_profile: Optional[List[float]] = None,
    num_slices: int = 5,
) -> List[AlgoChildSlice]:
    """
    Generate Volume-Weighted Average Price (VWAP) profile-participating child slices.
    Allocates larger slices during peak institutional volume windows (09:15-10:00 & 14:30-15:15).
    """
    qty = max(1, int(total_quantity))
    n = max(1, min(qty, int(num_slices)))

    # Default U-shaped institutional intraday volume curve
    if not intraday_volume_profile or len(intraday_volume_profile) != n:
        # Standard U-curve weights (high at open and close, lower at midday)
        raw_weights = [0.30, 0.15, 0.10, 0.15, 0.30] if n == 5 else [1.0 / n] * n
    else:
        raw_weights = intraday_volume_profile

    norm_weights = [w / sum(raw_weights) for w in raw_weights]

    slices: List[AlgoChildSlice] = []
    allocated_qty = 0

    for i, w in enumerate(norm_weights):
        if i == n - 1:
            chunk = qty - allocated_qty
        else:
            chunk = max(1, int(round(qty * w)))
            allocated_qty += chunk

        weight_pct = (chunk / qty) * 100.0
        slices.append(AlgoChildSlice(
            slice_index=i + 1,
            quantity=chunk,
            delay_seconds=float(i * 60.0),
            target_time_iso=datetime.now(timezone.utc).isoformat(),
            weight_pct=round(weight_pct, 2),
        ))

    return slices


# ── 4. SMART ORDER ROUTING (SOR) BROKER SELECTOR ─────────────────────────────

def select_optimal_broker(
    asset_class: str,
    strategy_id: str,
    num_legs: int = 1,
) -> Tuple[str, str]:
    """
    Smart Order Routing Broker Selection:
      - Options Multi-Leg / Spreads (S09 / S13) -> Routed to Finvasia Shoonya (₹0 brokerage).
      - Equity Cash / High-Beta Breakouts (S01 / S03) -> Routed to Angel One SmartAPI.
      - Default / Multi-Asset -> OpenAlgo Bridge.
    """
    asset_u = str(asset_class).upper()
    strat_u = str(strategy_id).upper()

    if "OPTION" in asset_u or num_legs > 1 or "THETA" in strat_u or "GAMMA" in strat_u:
        return "SHOONYA", "Zero-Brokerage Multi-Leg Options & Futures Gateway"
    elif asset_u == "EQUITY":
        return "ANGELONE", "Direct High-Speed SmartAPI Cash Equity Gateway"
    else:
        return "OPENALGO", "Universal Multi-Broker Execution Gateway"
