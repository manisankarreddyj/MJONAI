"""
Module: capital_metrics.py

Purpose:
    Calculate capital deployment and trading cost metrics for the portfolio.

Public API:
    - get_capital_metrics(trades)
    - load_capital_metrics()
"""

from __future__ import annotations

import logging
from collections import defaultdict
from statistics import median

from analytics.base import load_closed_trades, calculate_trade_capital, to_float

logger = logging.getLogger(__name__)


def get_capital_metrics(trades: list[dict]) -> dict:
    if not trades:	
        return {}

    capitals = []
    daily_capital = defaultdict(float)

    brokerage = 0.0
    stt = 0.0
    gst = 0.0
    exchange = 0.0
    sebi = 0.0
    stamp = 0.0
    slippage = 0.0

    total_profit = 0.0

    for trade in trades:
        capital = calculate_trade_capital(trade)
        capitals.append(capital)

        total_profit += to_float(trade.get("net_pnl"))

        trade_date = (
            str(trade.get("entry_time") or trade.get("created_at"))
        )[:10]

        daily_capital[trade_date] += capital

        brokerage += to_float(trade.get("brokerage"))
        stt += to_float(trade.get("stt"))
        gst += to_float(trade.get("gst"))
        exchange += to_float(trade.get("exchange_charge"))
        sebi += to_float(trade.get("sebi_charge"))
        stamp += to_float(trade.get("stamp_duty"))
        slippage += to_float(trade.get("slippage"))

    total_turnover = round(sum(capitals), 2)

    avg_capital = round(sum(capitals) / len(capitals), 2)
    median_capital = round(median(capitals), 2)

    max_capital = round(max(capitals), 2)
    min_capital = round(min(capitals), 2)

    daily_values = list(daily_capital.values())

    avg_daily = round(sum(daily_values) / len(daily_values), 2)
    max_daily = round(max(daily_values), 2)
    min_daily = round(min(daily_values), 2)

    total_cost = round(
        brokerage
        + stt
        + gst
        + exchange
        + sebi
        + stamp
        + slippage,
        2,
    )

    avg_cost = round(total_cost / len(trades), 2)

    return {
        "capital_summary": {
            "total_capital_turnover": total_turnover,
            "average_capital_per_trade": avg_capital,
            "median_capital_per_trade": median_capital,
            "maximum_capital_per_trade": max_capital,
            "minimum_capital_per_trade": min_capital,
        },
        "daily_capital": {
            "trading_days": len(daily_values),
            "average_daily_capital": avg_daily,
            "maximum_daily_capital": max_daily,
            "minimum_daily_capital": min_daily,
        },
        "capital_efficiency": {
            "return_on_maximum_capital_pct":
                round((total_profit / max_daily) * 100, 2)
                if max_daily else 0.0,
            "return_on_average_daily_capital_pct":
                round((total_profit / avg_daily) * 100, 2)
                if avg_daily else 0.0,
        },
        "cost_summary": {
            "brokerage": round(brokerage, 2),
            "stt": round(stt, 2),
            "gst": round(gst, 2),
            "exchange_charge": round(exchange, 2),
            "sebi_charge": round(sebi, 2),
            "stamp_duty": round(stamp, 2),
            "slippage": round(slippage, 2),
            "total_cost": total_cost,
            "average_cost_per_trade": avg_cost,
            "cost_as_pct_of_turnover":
                round((total_cost / total_turnover) * 100, 4)
                if total_turnover else 0.0,
        },
    }


def load_capital_metrics() -> dict:
    logger.info("Loading capital metrics...")
    trades = load_closed_trades()
    return get_capital_metrics(trades)


if __name__ == "__main__":
    from pprint import pprint
    pprint(load_capital_metrics())