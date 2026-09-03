"""
Module: research/stress_testing/monte_carlo.py
Purpose: Institutional 10,000-run Monte Carlo Trade Permutation & VaR Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any
import numpy as np


@dataclass(slots=True)
class MonteCarloReport:
    iterations: int
    initial_capital: float
    median_ending_equity: float
    p05_ending_equity: float
    p95_ending_equity: float
    median_max_drawdown_pct: float
    p95_max_drawdown_pct: float
    p99_max_drawdown_pct: float
    empirical_var_95_inr: float
    empirical_var_99_inr: float
    ruin_probability_pct: float  # P(Equity <= 50% of start)
    profit_probability_pct: float


def run_monte_carlo_simulation(
    trades_pnl: List[float],
    initial_capital: float = 1_000_000.0,
    iterations: int = 5000,
    ruin_threshold_pct: float = 50.0,
) -> MonteCarloReport:
    """
    Execute 5,000 - 10,000 Monte Carlo reshuffling runs on trade PnL sequence.
    """
    if len(trades_pnl) < 5:
        return MonteCarloReport(
            iterations=0,
            initial_capital=initial_capital,
            median_ending_equity=initial_capital,
            p05_ending_equity=initial_capital,
            p95_ending_equity=initial_capital,
            median_max_drawdown_pct=0.0,
            p95_max_drawdown_pct=0.0,
            p99_max_drawdown_pct=0.0,
            empirical_var_95_inr=0.0,
            empirical_var_99_inr=0.0,
            ruin_probability_pct=0.0,
            profit_probability_pct=0.0,
        )

    pnl_array = np.array(trades_pnl, dtype=np.float64)
    n_trades = len(pnl_array)
    ruin_level = initial_capital * (ruin_threshold_pct / 100.0)

    # Randomly resample trade indexes with replacement
    indices = np.random.randint(0, n_trades, size=(iterations, n_trades))
    simulated_pnls = pnl_array[indices]

    # Calculate cumulative equity curves
    cum_pnls = np.cumsum(simulated_pnls, axis=1)
    equity_paths = initial_capital + cum_pnls
    # Prepend starting capital
    starting_column = np.full((iterations, 1), initial_capital)
    equity_paths = np.hstack([starting_column, equity_paths])

    ending_equities = np.maximum(0.0, equity_paths[:, -1])
    peak_equities = np.maximum.accumulate(equity_paths, axis=1)
    drawdowns = np.clip((peak_equities - equity_paths) / np.maximum(peak_equities, 1e-9), 0.0, 1.0)
    max_drawdowns = np.max(drawdowns, axis=1) * 100.0

    # Ruin probability: touched ruin level at any point
    min_equities = np.min(equity_paths, axis=1)
    ruin_count = np.sum(min_equities <= ruin_level)

    # Sort distributions
    ending_equities.sort()
    max_drawdowns.sort()

    p01_idx = int(iterations * 0.01)
    p05_idx = int(iterations * 0.05)
    p50_idx = int(iterations * 0.50)
    p95_idx = int(iterations * 0.95)
    p99_idx = int(iterations * 0.99)

    # VaR is relative to initial capital
    var_95 = max(0.0, initial_capital - ending_equities[p05_idx])
    var_99 = max(0.0, initial_capital - ending_equities[p01_idx])

    return MonteCarloReport(
        iterations=iterations,
        initial_capital=initial_capital,
        median_ending_equity=round(float(ending_equities[p50_idx]), 2),
        p05_ending_equity=round(float(ending_equities[p05_idx]), 2),
        p95_ending_equity=round(float(ending_equities[p95_idx]), 2),
        median_max_drawdown_pct=round(float(max_drawdowns[p50_idx]), 2),
        p95_max_drawdown_pct=round(float(max_drawdowns[p95_idx]), 2),
        p99_max_drawdown_pct=round(float(max_drawdowns[p99_idx]), 2),
        empirical_var_95_inr=round(float(var_95), 2),
        empirical_var_99_inr=round(float(var_99), 2),
        ruin_probability_pct=round(float(ruin_count / iterations * 100.0), 2),
        profit_probability_pct=round(float(np.sum(ending_equities > initial_capital) / iterations * 100.0), 1),
    )
