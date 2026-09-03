from __future__ import annotations

from mjonai.research.optimization.engine import OptimizationEngine
from mjonai.research.optimization.models import OptimizationSummary
from mjonai.research.optimization.parameters import ParameterGrid
from mjonai.research.pipeline import ResearchPipeline


class ResearchOptimizer:

    def __init__(
        self,
        pipeline: ResearchPipeline,
        min_trades: int = 10,
    ) -> None:

        self._pipeline = pipeline
        self._engine = OptimizationEngine(
            min_trades=min_trades,
        )

    def optimize(
        self,
        *,
        strategy,
        instrument,
        config,
        stop_loss_func,
        target_func,
    ) -> OptimizationSummary:

        runs = []

        grid = ParameterGrid(
            strategy.parameters,
        )

        for parameter_set in grid.generate():

            strategy.configure(
                parameter_set,
            )

            results = self._pipeline.run(
                instruments=[instrument],
                config=config,
                strategy=strategy,
                stop_loss_func=stop_loss_func,
                target_func=target_func,
            )

            if not results:
                continue

            runs.append(
                (
                    parameter_set,
                    results[0].report,
                )
            )

        return self._engine.summarize(
            strategy=strategy.name,
            symbol=instrument.symbol,
            runs=runs,
        )