from __future__ import annotations

from research.optimization.models import (
    OptimizationResult,
    OptimizationSummary,
)


class GridSearchOptimizer:

    def __init__(
        self,
        min_trades: int = 10,
    ):

        # Below this, a parameter set's statistics are noise and
        # must not be selected. Kept low enough for single-symbol
        # daily strategies inside 3-year training windows.
        self._min_trades = min_trades

    def rank(
        self,
        results: list[OptimizationResult],
    ) -> OptimizationSummary:

        if not results:

            return OptimizationSummary(
                strategy="",
                symbol="",
                total_runs=0,
                best_result=None,
                results=[],
            )

        # Risk-adjusted objective: raw total return
        # rewards the luckiest grid cell, not the best one.
        ranked = sorted(
            results,
            key=lambda result: (
                result.report.performance.sharpe_ratio,
                result.report.trade.profit_factor,
                result.report.equity.total_return_pct,
            ),
            reverse=True,
        )

        # Under-traded runs stay visible in the ranking
        # but cannot be selected as best.
        eligible = [
            result
            for result in ranked
            if result.report.trade.total_trades
            >= self._min_trades
        ]

        best = eligible[0] if eligible else None

        return OptimizationSummary(
            strategy=(
                best.strategy
                if best
                else ranked[0].strategy
            ),
            symbol=(
                best.symbol
                if best
                else ranked[0].symbol
            ),
            total_runs=len(ranked),
            best_result=best,
            results=ranked,
        )