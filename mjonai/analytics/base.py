"""
Module: base.py

Purpose:
    Shared utilities for the Analytics subsystem.

Responsibilities:
    - Load trade data
    - Common helper functions
    - Safe numeric conversions

Used by:
    reporting.py
    risk_metrics.py
"""

from __future__ import annotations

import logging

from mjonai.core.numeric import safe_float as to_float
from mjonai.db.repository import get_all_closed_trades

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