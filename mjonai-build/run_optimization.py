from __future__ import annotations

from time import perf_counter

from configs.research_config import (
    CONFIG,
    STRATEGIES,
    SYMBOLS,
)

from research.optimization.research_optimizer import (
    ResearchOptimizer,
)
from research.bootstrap import ResearchBootstrap
from research.context import ResearchContext
from research.registry_adapter import load_registry_strategy


def stop_loss(
    df,
    signal_index,
    entry_price,
    direction,
):

    if direction == "LONG":
        return entry_price * 0.97

    return entry_price * 1.03


def target(
    entry_price,
    stop_loss_price,
    direction,
):

    risk = abs(
        entry_price -
        stop_loss_price
    )

    if direction == "LONG":
        return entry_price + risk * 2

    return entry_price - risk * 2


def main():

    started = perf_counter()

    context = ResearchContext(
        config=CONFIG,
        symbols=SYMBOLS,
        strategy_ids=STRATEGIES,
    )

    pipeline, instruments = ResearchBootstrap.build(
        context,
    )

    optimizer = ResearchOptimizer(
        pipeline,
    )

    strategy = load_registry_strategy(
        context.strategy_ids[0],
    )

    for instrument in instruments:

        summary = optimizer.optimize(
            strategy=strategy,
            instrument=instrument,
            config=context.config,
            stop_loss_func=stop_loss,
            target_func=target,
        )

        print(
            f"{summary.symbol} : "
            f"{summary.total_runs} runs"
        )

        if summary.best_result:

            print(
                summary.best_result.parameters.values
            )

            print(
                summary.best_result.report.equity.total_return_pct
            )

            print("-" * 80)

    elapsed = perf_counter() - started

    print(
        f"\nCompleted in {elapsed:.2f} sec"
    )


if __name__ == "__main__":
    main()