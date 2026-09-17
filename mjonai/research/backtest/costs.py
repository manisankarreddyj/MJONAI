"""Round-trip transaction costs for research backtests.

Single source of truth for statutory rates is build's
`execution/tax.py` (STT both sides on delivery, exchange + SEBI
charges, stamp duty, DP charges, GST, capped brokerage) plus a
market-impact slippage term in basis points of turnover.

Replaces the former duplicate Zerodha model from engine/execution.
"""

from __future__ import annotations

from mjonai.execution.tax import (
    calculate_all_in_friction,
)
from mjonai.research.backtest.models import TransactionCost


def _equity_round_trip_cost(
    *,
    entry_price: float,
    exit_price: float,
    quantity: int,
    product_type: str,
    slippage_bps: float = 5.0,
) -> TransactionCost:
    """
    All-in NSE equity round-trip cost for one trade under the given
    product regime (DELIVERY or INTRADAY), including market-impact
    slippage on both legs. Statutory rates come from `execution/tax.py`.
    """

    breakdown = calculate_all_in_friction(
        buy_price=entry_price,
        sell_price=exit_price,
        quantity=quantity,
        asset_class="EQUITY",
        product_type=product_type,
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


def equity_delivery_cost(
    *,
    entry_price: float,
    exit_price: float,
    quantity: int,
    slippage_bps: float = 5.0,
) -> TransactionCost:
    """
    All-in NSE equity-delivery round-trip cost for one LONG trade
    (0.10% STT both sides, 0.015% buy stamp duty, DP ₹15.34).
    """

    return _equity_round_trip_cost(
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        product_type="DELIVERY",
        slippage_bps=slippage_bps,
    )


def equity_intraday_cost(
    *,
    entry_price: float,
    exit_price: float,
    quantity: int,
    slippage_bps: float = 5.0,
) -> TransactionCost:
    """
    All-in NSE equity-intraday round-trip cost for one SHORT trade
    (0.025% STT sell-only, 0.003% buy stamp duty, no DP charges).
    NSE cash has no overnight shorts — SHORT backtests must clear
    under the intraday regime, not delivery.
    """

    return _equity_round_trip_cost(
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        product_type="INTRADAY",
        slippage_bps=slippage_bps,
    )
