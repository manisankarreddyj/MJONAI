"""
Module: strategy_metrics.py

Purpose:
    Calculate performance metrics grouped by strategy.

Public API:
    - get_strategy_metrics(trades)
    - load_strategy_metrics()
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from mjonai.db.repository import get_all_closed_trades

logger = logging.getLogger(__name__)


def _to_float(value: Any) -> float:
    """Safely convert values to float."""
    if value is None:
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def get_strategy_metrics(trades: list[dict]) -> dict:
    """
    Calculate performance metrics grouped by strategy.
    """

    grouped = defaultdict(list)

    for trade in trades:
        strategy = trade.get("strategy_id", "UNKNOWN")
        grouped[strategy].append(trade)

    summary = {}

    for strategy, rows in grouped.items():

        winners = []
        losers = []

        gross_profit = 0.0
        gross_loss = 0.0

        for trade in rows:

            pnl = _to_float(trade.get("net_pnl"))

            if pnl > 0:
                winners.append(pnl)
                gross_profit += pnl

            elif pnl < 0:
                losers.append(pnl)
                gross_loss += abs(pnl)

        total = len(rows)
        wins = len(winners)
        losses = len(losers)

        net_profit = gross_profit - gross_loss

        summary[strategy] = {

            "total_trades": total,

            "wins": wins,

            "losses": losses,

            "win_rate": round(
                (wins / total) * 100,
                2
            ) if total else 0.0,

            "gross_profit": round(
                gross_profit,
                2
            ),

            "gross_loss": round(
                gross_loss,
                2
            ),

            "net_profit": round(
                net_profit,
                2
            ),

            "profit_factor": round(
                gross_profit / gross_loss,
                2
            ) if gross_loss else 0.0,

            "average_trade": round(
                net_profit / total,
                2
            ) if total else 0.0,
        }

    return dict(
        sorted(
            summary.items(),
            key=lambda x: x[1]["net_profit"],
            reverse=True,
        )
    )


def load_strategy_metrics() -> dict:
    """
    Load all closed trades from repository
    and calculate per-strategy metrics.
    """

    logger.info("Loading strategy metrics...")

    trades = get_all_closed_trades()

    metrics = get_strategy_metrics(trades)

    logger.info(
        "Calculated metrics for %d strategies.",
        len(metrics)
    )

    return metrics


if __name__ == "__main__":

    metrics = load_strategy_metrics()

    print("\n" + "=" * 50)
    print("MJONAI STRATEGY PERFORMANCE")
    print("=" * 50)

    if not metrics:
        print("\nNo closed trades found.\n")

    for strategy, data in metrics.items():

        print(f"\nStrategy      : {strategy}")
        print("-" * 50)

        print(f"Total Trades  : {data['total_trades']}")
        print(f"Wins          : {data['wins']}")
        print(f"Losses        : {data['losses']}")
        print(f"Win Rate      : {data['win_rate']:.2f}%")

        print()

        print(f"Gross Profit  : ₹{data['gross_profit']:.2f}")
        print(f"Gross Loss    : ₹{data['gross_loss']:.2f}")
        print(f"Net Profit    : ₹{data['net_profit']:.2f}")

        print()

        print(f"Profit Factor : {data['profit_factor']:.2f}")
        print(f"Average Trade : ₹{data['average_trade']:.2f}")

    print("\n" + "=" * 50)