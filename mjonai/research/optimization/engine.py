from __future__ import annotations

from mjonai.analytics.models import PerformanceReport
from mjonai.research.optimization.grid_search import (
    GridSearchOptimizer,
)
from mjonai.research.optimization.models import (
    OptimizationResult,
    OptimizationSummary,
    ParameterSet,
)


class OptimizationEngine:

    def __init__(
        self,
        min_trades: int = 10,
    ) -> None:

        self._grid_search = GridSearchOptimizer(
            min_trades=min_trades,
        )

    def summarize(
        self,
        strategy: str,
        symbol: str,
        runs: list[
            tuple[
                ParameterSet,
                PerformanceReport,
            ]
        ],
    ) -> OptimizationSummary:

        results: list[
            OptimizationResult
        ] = []

        for (
            parameters,
            report,
        ) in runs:

            results.append(
                OptimizationResult(
                    strategy=strategy,
                    symbol=symbol,
                    parameters=parameters,
                    report=report,
                )
            )

        return self._grid_search.rank(
            results,
        )