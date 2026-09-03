"""
Module: base.py

Purpose:
    Shared utilities for the Analytics subsystem.

Responsibilities:
    - Load trade data
    - Common helper functions
    - Safe numeric conversions

Used by:
    performance_metrics.py
    capital_metrics.py
    equity_curve.py
    strategy_metrics.py
    market_metrics.py
    risk_metrics.py
"""

from __future__ import annotations

import logging
from typing import Any

from db.repository import get_all_closed_trades

logger = logging.getLogger(__name__)


def load_closed_trades() -> list[dict]:
    """
    Load all closed trades from the repository.
    """

    logger.info("Loading closed trades...")

    trades = get_all_closed_trades()

    logger.info(
        "Loaded %s closed trades.",
        len(trades),
    )

    return trades


def to_float(value: Any) -> float:
    """
    Safely convert database values to float.
    """

    if value is None:
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def calculate_trade_capital(trade: dict) -> float:
    """
    Calculate capital deployed for one trade.

    Formula:
        Entry Price × Quantity
    """

    entry_price = to_float(
        trade.get("entry_price")
    )

    quantity = to_float(
        trade.get("quantity")
    )

    return round(
        entry_price * quantity,
        2,
    )