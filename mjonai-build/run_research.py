from __future__ import annotations

from time import perf_counter

from configs.research_config import (
    CONFIG,
    STRATEGIES,
    SYMBOLS,
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

    print("=" * 80)
    print("MJONAI RESEARCH ENGINE")
    print("=" * 80)

    context = ResearchContext(
        config=CONFIG,
        symbols=SYMBOLS,
        strategy_ids=STRATEGIES,
    )

    pipeline, instruments = ResearchBootstrap.build(
        context,
    )


    strategy = load_registry_strategy(
        context.strategy_ids[0],
    )

    print(
        f"Research Universe : {len(instruments)}"
    )

    results = pipeline.run(
        instruments=instruments,
        config=context.config,
        strategy=strategy,
        stop_loss_func=stop_loss,
        target_func=target,
    )

    print("\n" + "=" * 105)
    print(f"PERFORMANCE REPORT: {strategy.name} ({context.config.start.strftime('%Y-%m-%d')} to {context.config.end.strftime('%Y-%m-%d')})")
    print("=" * 105)
    print(f"{'SYMBOL':<12} | {'SIGNALS':<8} | {'TRADES':<7} | {'WIN RATE':<10} | {'PROFIT FACTOR':<14} | {'SHARPE':<8} | {'AVG WIN':<9} | {'AVG LOSS':<9} | {'MAX DD':<8}")
    print("-" * 105)

    total_trades_all = 0
    total_wins_all = 0
    total_net_pnl_all = 0.0

    for res in results:
        sym = res.instrument.symbol
        sig_count = res.signals
        trade_count = res.trades
        stats = res.report.trade
        equity = res.report.equity
        perf = res.report.performance

        total_trades_all += trade_count
        total_wins_all += stats.winning_trades

        print(
            f"{sym:<12} | {sig_count:<8} | {trade_count:<7} | {stats.win_rate_pct:>8.1f}% | "
            f"{stats.profit_factor:>13.2f} | {perf.sharpe_ratio:>7.2f} | {stats.average_win_pct:>8.2f}% | {stats.average_loss_pct:>8.2f}% | {equity.max_drawdown_pct:>7.1f}%"
        )

    print("-" * 105)
    overall_win_rate = (total_wins_all / total_trades_all * 100.0) if total_trades_all > 0 else 0.0
    print(f"PORTFOLIO TOTALS: {total_trades_all} Trades across {len(results)} symbols | Overall Win Rate: {overall_win_rate:.1f}%")
    print("=" * 90)

    elapsed = perf_counter() - started

    print()
    print(
        f"Research run completed in {elapsed:.2f} sec"
    )


if __name__ == "__main__":
    main()