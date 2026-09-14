"""
Module: analytics/reporting.py

Purpose:
    Consolidated portfolio reporting entry point — merges the former
    DB-view tiers (performance_metrics / strategy_metrics / capital_metrics)
    into ONE reporting namespace (P1 analytics 4-tier collapse, 2026-09-14).

Public API:
    - get_performance_metrics(trades) / load_performance_metrics()
    - get_strategy_metrics(trades) / load_strategy_metrics()
    - get_capital_metrics(trades) / load_capital_metrics()

Design notes:
    - Database-agnostic for the get_*() families; load_*() conveniences only
      touch the repository.
    - Single numeric helper: base.to_float (no per-module _to_float copies).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from statistics import median

from mjonai.analytics.base import (
    calculate_trade_capital,
    load_closed_trades,
    to_float,
)

logger = logging.getLogger(__name__)


def _calculate_streaks(trades: list[dict]) -> tuple[int, int]:
    """Returns (max_win_streak, max_loss_streak)."""

    max_win = 0
    max_loss = 0

    current_win = 0
    current_loss = 0

    for trade in trades:
        pnl = to_float(trade.get("net_pnl"))

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


# ── 1. PORTFOLIO PERFORMANCE METRICS ─────────────────────────────────────────


def get_performance_metrics(trades: list[dict]) -> dict:
    """Calculate portfolio performance metrics."""

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
        pnl = to_float(trade.get("net_pnl"))

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
        round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0.0
    )

    expectancy = round(net_profit / total, 2) if total > 0 else 0.0

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
            "win_rate": round((win_count / total) * 100, 2),
            "loss_rate": round((loss_count / total) * 100, 2),
            "breakeven_rate": round((breakeven_count / total) * 100, 2),
            "profit_factor": profit_factor,
            "expectancy": expectancy,
            "largest_winner": max(winners) if winners else 0.0,
            "largest_loser": min(losers) if losers else 0.0,
            "average_winner": (
                round(sum(winners) / len(winners), 2) if winners else 0.0
            ),
            "average_loser": (
                round(sum(losers) / len(losers), 2) if losers else 0.0
            ),
            "average_trade": round(net_profit / total, 2),
            "max_win_streak": max_win_streak,
            "max_loss_streak": max_loss_streak,
        },
        "profit_metrics": {
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "net_profit": round(net_profit, 2),
        },
    }


def load_performance_metrics() -> dict:
    """Load trades from repository and calculate performance metrics."""
    logger.info("Loading performance metrics...")
    trades = load_closed_trades()
    metrics = get_performance_metrics(trades)
    logger.info("Performance metrics calculated.")
    return metrics


# ── 2. STRATEGY-BREAKDOWN METRICS ────────────────────────────────────────────


def get_strategy_metrics(trades: list[dict]) -> dict:
    """Calculate performance metrics grouped by strategy."""

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
            pnl = to_float(trade.get("net_pnl"))

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
            "win_rate": round((wins / total) * 100, 2) if total else 0.0,
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "net_profit": round(net_profit, 2),
            "profit_factor": (
                round(gross_profit / gross_loss, 2) if gross_loss else 0.0
            ),
            "average_trade": (
                round(net_profit / total, 2) if total else 0.0
            ),
        }

    return dict(
        sorted(
            summary.items(),
            key=lambda x: x[1]["net_profit"],
            reverse=True,
        )
    )


def load_strategy_metrics() -> dict:
    """Load all closed trades from repository and calculate per-strategy metrics."""
    logger.info("Loading strategy metrics...")
    trades = load_closed_trades()
    metrics = get_strategy_metrics(trades)
    logger.info("Calculated metrics for %d strategies.", len(metrics))
    return metrics


# ── 3. CAPITAL DEPLOYMENT & COST METRICS ─────────────────────────────────────


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

        trade_date = str(trade.get("entry_time") or trade.get("created_at"))[:10]
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
        brokerage + stt + gst + exchange + sebi + stamp + slippage,
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
            "return_on_maximum_capital_pct": (
                round((total_profit / max_daily) * 100, 2) if max_daily else 0.0
            ),
            "return_on_average_daily_capital_pct": (
                round((total_profit / avg_daily) * 100, 2) if avg_daily else 0.0
            ),
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
            "cost_as_pct_of_turnover": (
                round((total_cost / total_turnover) * 100, 4)
                if total_turnover
                else 0.0
            ),
        },
    }


def load_capital_metrics() -> dict:
    logger.info("Loading capital metrics...")
    trades = load_closed_trades()
    return get_capital_metrics(trades)