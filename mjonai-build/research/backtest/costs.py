"""Round-trip transaction costs for research backtests.

Single source of truth for statutory rates is build's
`execution/tax.py` (STT both sides on delivery, exchange + SEBI
charges, stamp duty, DP charges, GST, capped brokerage) plus a
market-impact slippage term in basis points of turnover.

Replaces the former duplicate Zerodha model from engine/execution.
"""

from __future__ import annotations

from execution.tax import (
    calculate_all_in_friction,
)
from research.backtest.models import TransactionCost


def equity_delivery_cost(
    *,
    entry_price: float,
    exit_price: float,
    quantity: int,
    slippage_bps: float = 5.0,
) -> TransactionCost:
    """
    All-in NSE equity-delivery round-trip cost for one trade,
    including market-impact slippage on both legs.
    """

    breakdown = calculate_all_in_friction(
        buy_price=entry_price,
        sell_price=exit_price,
        quantity=quantity,
        asset_class="EQUITY",
        product_type="DELIVERY",
        exchange="NSE",
    )

    turnover = (
        entry_price + exit_price
    ) * quantity

    slippage = (
        turnover *
        slippage_bps /
        10000
    )

    brokerage = float(
        breakdown["brokerage"]
    )

    statutory = float(
        breakdown["total_friction"]
    ) - brokerage

    total = (
        float(breakdown["total_friction"])
        + slippage
    )

    return TransactionCost(
        brokerage=round(
            brokerage,
            2,
        ),
        slippage=round(
            slippage,
            2,
        ),
        taxes=round(
            statutory,
            2,
        ),
        total=round(
            total,
            2,
        ),
    )
