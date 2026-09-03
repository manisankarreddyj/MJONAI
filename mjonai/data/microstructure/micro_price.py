"""
Module: data/microstructure/micro_price.py
Purpose: SOTA Institutional Market Microstructure & Order Book Micro-Price Engine.
         Implements Sasha Stoikov's (2018) Micro-Price and Kyle's (1985) Lambda:
         1. Stoikov Micro-Price:
            - Weighted mid-price adjusted for Level-2 bid/ask depth imbalance:
              P_micro = Bid * (Q_ask / (Q_bid + Q_ask)) + Ask * (Q_bid / (Q_bid + Q_ask))
            - Captures the exact probability of the next tick direction before price trades.
         2. Kyle's Lambda (Price Impact Coefficient):
            - Measures price displacement per unit volume traded: Lambda = |Delta P| / Traded Volume
            - Flags thin liquidity and high-slippage execution traps.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from mjonai.core.time_utils import now_ist

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MicrostructureSnapshot:
    """
    Immutable Order Book Micro-Price & Liquidity Impact Snapshot.
    """
    symbol: str
    best_bid: float
    best_ask: float
    bid_qty: int
    ask_qty: int
    mid_price: float
    micro_price: float
    micro_price_edge_bps: float        # (MicroPrice - MidPrice) / MidPrice * 10,000
    order_book_imbalance: float        # (BidQty - AskQty) / (BidQty + AskQty)
    kyles_lambda: float                # Price impact coefficient
    is_buying_pressure: bool
    is_selling_pressure: bool
    timestamp: datetime
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "best_bid": round(self.best_bid, 2),
            "best_ask": round(self.best_ask, 2),
            "bid_qty": self.bid_qty,
            "ask_qty": self.ask_qty,
            "mid_price": round(self.mid_price, 2),
            "micro_price": round(self.micro_price, 2),
            "micro_price_edge_bps": round(self.micro_price_edge_bps, 2),
            "order_book_imbalance": round(self.order_book_imbalance, 3),
            "kyles_lambda": round(self.kyles_lambda, 6),
            "is_buying_pressure": self.is_buying_pressure,
            "is_selling_pressure": self.is_selling_pressure,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
        }


def calculate_micro_price_and_impact(
    symbol: str,
    best_bid: float,
    best_ask: float,
    bid_qty: int,
    ask_qty: int,
    recent_price_change: float = 0.50,
    recent_traded_volume: int = 25000,
) -> MicrostructureSnapshot:
    """
    Compute Stoikov Micro-Price and Kyle's Lambda price impact.
    """
    clean_sym = symbol.strip().upper()
    now = now_ist()

    b_price = max(0.01, float(best_bid))
    a_price = max(b_price, float(best_ask))
    b_qty = max(1, int(bid_qty))
    a_qty = max(1, int(ask_qty))
    tot_qty = float(b_qty + a_qty)

    mid = (b_price + a_price) / 2.0

    # Stoikov (2018) Micro-Price Formula:
    # If ask_qty is small and bid_qty is large, price will jump to ask.
    # MicroPrice = Bid * (AskQty / TotalQty) + Ask * (BidQty / TotalQty)
    micro = (b_price * (a_qty / tot_qty)) + (a_price * (b_qty / tot_qty))
    edge_bps = ((micro - mid) / mid) * 10000.0 if mid > 0 else 0.0

    imbalance = (b_qty - a_qty) / tot_qty

    # Kyle's Lambda: Price change per share traded
    vol = max(1, recent_traded_volume)
    kyles_lambda = abs(recent_price_change) / float(vol)

    is_buy = imbalance >= 0.25 and edge_bps >= 2.0
    is_sell = imbalance <= -0.25 and edge_bps <= -2.0

    if is_buy:
        msg = f"Aggressive Bid Pressure on {clean_sym} (Micro-Price: ₹{micro:.2f} > Mid: ₹{mid:.2f} | Imbalance: +{imbalance*100:.1f}%)"
    elif is_sell:
        msg = f"Aggressive Ask Dumping on {clean_sym} (Micro-Price: ₹{micro:.2f} < Mid: ₹{mid:.2f} | Imbalance: {imbalance*100:.1f}%)"
    else:
        msg = f"Balanced Order Book on {clean_sym} (Mid: ₹{mid:.2f} | Edge: {edge_bps:+.1f} bps)"

    return MicrostructureSnapshot(
        symbol=clean_sym,
        best_bid=b_price,
        best_ask=a_price,
        bid_qty=b_qty,
        ask_qty=a_qty,
        mid_price=mid,
        micro_price=micro,
        micro_price_edge_bps=edge_bps,
        order_book_imbalance=imbalance,
        kyles_lambda=kyles_lambda,
        is_buying_pressure=is_buy,
        is_selling_pressure=is_sell,
        timestamp=now,
        message=msg,
    )
