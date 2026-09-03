"""
Script: run_universe_benchmark.py
Purpose: Master Dynamic Multi-Universe Benchmark across 8 Strategies.
         - ZERO hardcoded symbols (loads Nifty 50 / Nifty 500 dynamically).
         - ZERO hardcoded stop-loss percentages (uses true 14-period ATR volatility).
         - Evaluates full multi-stock portfolio performance and leaderboard.
"""

import sys
import argparse
from time import perf_counter
from datetime import datetime

from core.enums import Provider
from research.data.timeframe import TimeFrame
from research.config import ResearchConfig
from research.bootstrap import ResearchBootstrap
from research.context import ResearchContext
from research.universe_loader import load_universe_symbols, UniverseTier
from research.dynamic_exits import dynamic_stop_loss, dynamic_target
from research.registry_adapter import load_registry_strategy


def main():
    parser = argparse.ArgumentParser(description="MJONAI Dynamic Universe Benchmark")
    parser.add_argument("--tier", type=str, default="NIFTY_50", choices=["NIFTY_50", "NIFTY_500"], help="Universe tier")
    parser.add_argument("--count", type=int, default=20, help="Number of stocks to test")
    parser.add_argument("--years", type=int, default=5, help="Years of historical data")
    args = parser.parse_args()

    started = perf_counter()
    tier_enum = UniverseTier.NIFTY_50 if args.tier == "NIFTY_50" else UniverseTier.NIFTY_500
    symbols = load_universe_symbols(tier=tier_enum, max_count=args.count)

    start_date = datetime(datetime.now().year - args.years, 1, 1)
    end_date = datetime.now()

    config = ResearchConfig(
        provider=Provider.YAHOO,
        timeframe=TimeFrame.DAY_1,
        start=start_date,
        end=end_date,
        max_holding_bars=20,
    )

    all_strategies = [
        "S01_MomentumRSI",
        "S02_MeanReversion",
        "S03_TurtleBreakout",
        "S04_BollingerSqueeze",
        "S05_PriceAction",
        "S06_MomentumShort",
        "S07_MeanReversionShort",
        "S08_IntradayAllDay",
    ]

    print("=" * 110)
    print(f"MJONAI RESEARCH ENGINE — DYNAMIC UNIVERSE BENCHMARK ({args.tier}: {len(symbols)} STOCKS, {args.years} YEARS)")
    print(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} | Volatility Model: Dynamic 14-ATR")
    print(f"Stocks ({len(symbols)}): {', '.join(symbols[:10])}{'...' if len(symbols) > 10 else ''}")
    print("=" * 110)

    context = ResearchContext(config=config, symbols=symbols, strategy_ids=all_strategies)
    pipeline, instruments = ResearchBootstrap.build(context)

    summary_rows = []

    for strat_id in all_strategies:
        try:
            strat = load_registry_strategy(strat_id)
            results = pipeline.run(
                instruments=instruments,
                config=context.config,
                strategy=strat,
                stop_loss_func=dynamic_stop_loss,
                target_func=dynamic_target,
            )

            total_trades = sum(r.trades for r in results)
            total_wins = sum(r.report.trade.winning_trades for r in results)
            total_losses = sum(r.report.trade.losing_trades for r in results)
            win_rate = (total_wins / total_trades * 100.0) if total_trades > 0 else 0.0

            gross_win = sum(r.report.trade.average_win_pct * r.report.trade.winning_trades for r in results)
            gross_loss = sum(abs(r.report.trade.average_loss_pct) * r.report.trade.losing_trades for r in results)
            profit_factor = (gross_win / gross_loss) if gross_loss > 0 else 0.0

            avg_win = (gross_win / total_wins) if total_wins > 0 else 0.0
            avg_loss = (-gross_loss / total_losses) if total_losses > 0 else 0.0
            max_dd = max((r.report.equity.max_drawdown_pct for r in results), default=0.0)

            summary_rows.append({
                "id": strat_id,
                "name": strat.description,
                "direction": strat.direction,
                "trades": total_trades,
                "win_rate": win_rate,
                "profit_factor": profit_factor,
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "max_dd": max_dd,
            })

        except Exception as e:
            print(f"Error testing {strat_id}: {e}")

    # Rank by Profit Factor descending
    summary_rows.sort(key=lambda x: x["profit_factor"], reverse=True)

    print(f"\n{'RANK':<5} | {'STRATEGY':<22} | {'DIRECTION':<9} | {'TRADES':<7} | {'WIN RATE':<9} | {'PROFIT FACTOR':<14} | {'AVG WIN':<8} | {'AVG LOSS':<9} | {'MAX DD':<7}")
    print("-" * 110)

    for rank, row in enumerate(summary_rows, 1):
        print(
            f"#{rank:<4} | {row['id']:<22} | {row['direction']:<9} | {row['trades']:<7} | "
            f"{row['win_rate']:>7.1f}% | {row['profit_factor']:>13.2f} | {row['avg_win']:>7.2f}% | {row['avg_loss']:>8.2f}% | {row['max_dd']:>6.1f}%"
        )

    print("=" * 110)
    elapsed = perf_counter() - started
    print(f"Dynamic Universe Benchmark completed in {elapsed:.2f} seconds.")


if __name__ == "__main__":
    main()
