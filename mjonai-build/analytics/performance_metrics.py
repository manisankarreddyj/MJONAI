"""
Module: performance_metrics.py

Purpose:
    Calculate overall trading performance metrics.

Public API:
    - get_performance_metrics(trades)
    - load_performance_metrics()

This module is intentionally database-agnostic except for the
load_performance_metrics() convenience function.
"""

from __future__ import annotations

import logging
from typing import Any

from db.repository import get_all_closed_trades

logger = logging.getLogger(__name__)


def _to_float(value: Any) -> float:
    """Safely convert database values to float."""

    if value is None:
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _calculate_streaks(trades: list[dict]) -> tuple[int, int]:
    """
    Returns:
        (max_win_streak, max_loss_streak)
    """

    max_win = 0
    max_loss = 0

    current_win = 0
    current_loss = 0

    for trade in trades:

        pnl = _to_float(trade.get("net_pnl"))

        if pnl > 0:

            current_win += 1
            current_loss = 0

        elif pnl < 0:

            current_loss += 1
            current_win = 0

        else:

            current_win = 0
            current_loss = 0

        max_win = max(max_win, current_win)
        max_loss = max(max_loss, current_loss)

    return max_win, max_loss


def get_performance_metrics(
    trades: list[dict],
) -> dict:
    """
    Calculate portfolio performance metrics.
    """

    if not trades:

        return {
            "trade_counts": {},
            "profit_metrics": {},
            "performance_metrics": {},
        }

    winners = []
    losers = []
    breakeven = []

    gross_profit = 0.0
    gross_loss = 0.0

    for trade in trades:

        pnl = _to_float(
            trade.get("net_pnl")
        )

        if pnl > 0:

            winners.append(pnl)
            gross_profit += pnl

        elif pnl < 0:

            losers.append(pnl)
            gross_loss += abs(pnl)

        else:

            breakeven.append(pnl)

    total = len(trades)

    win_count = len(winners)
    loss_count = len(losers)
    breakeven_count = len(breakeven)

    net_profit = gross_profit - gross_loss

    profit_factor = (
        round(gross_profit / gross_loss, 2)
        if gross_loss > 0
        else 0.0
    )

    expectancy = (
        round(net_profit / total, 2)
        if total > 0
        else 0.0
    )

    max_win_streak, max_loss_streak = (
        _calculate_streaks(trades)
    )

    return {

        "trade_counts": {

            "total_trades": total,
            "winning_trades": win_count,
            "losing_trades": loss_count,
            "breakeven_trades": breakeven_count,
        },

        "performance_metrics": {

            "win_rate": round(
                (win_count / total) * 100,
                2,
            ),

            "loss_rate": round(
                (loss_count / total) * 100,
                2,
            ),

            "breakeven_rate": round(
                (breakeven_count / total) * 100,
                2,
            ),

            "profit_factor": profit_factor,

            "expectancy": expectancy,

            "largest_winner": (
                max(winners)
                if winners
                else 0.0
            ),

            "largest_loser": (
                min(losers)
                if losers
                else 0.0
            ),

            "average_winner": round(
                sum(winners) / len(winners),
                2,
            ) if winners else 0.0,

            "average_loser": round(
                sum(losers) / len(losers),
                2,
            ) if losers else 0.0,

            "average_trade": round(
                net_profit / total,
                2,
            ),

            "max_win_streak": max_win_streak,
            "max_loss_streak": max_loss_streak,
        },

        "profit_metrics": {

            "gross_profit": round(
                gross_profit,
                2,
            ),

            "gross_loss": round(
                gross_loss,
                2,
            ),

            "net_profit": round(
                net_profit,
                2,
            ),
        },
    }


def load_performance_metrics() -> dict:
    """
    Load trades from repository and
    calculate performance metrics.
    """

    logger.info(
        "Loading performance metrics..."
    )

    trades = get_all_closed_trades()

    metrics = get_performance_metrics(
        trades
    )

    logger.info(
        "Performance metrics calculated."
    )

    return metrics


if __name__ == "__main__":

    from pprint import pprint

    pprint(
        load_performance_metrics()
    )