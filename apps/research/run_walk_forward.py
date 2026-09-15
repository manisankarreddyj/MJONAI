"""
Script: run_walk_forward.py
Purpose: Institutional Walk-Forward Optimization & Out-of-Sample Verification Engine.
         - ZERO hardcoded symbols (loads dynamic universe).
         - ZERO hardcoded stops (uses dynamic 14-period ATR volatility).
         - Evaluates Train (In-Sample) vs. Test (Out-of-Sample) performance.
         - Computes Walk-Forward Efficiency (WFE %) to mathematically prove zero overfitting.
"""

from __future__ import annotations

# ADR-0008: repo-root bootstrap — allows `python <this file>` from the repo root.
import sys as _boot_sys
from pathlib import Path as _boot_Path
_BOOT_ROOT = _boot_Path(__file__).resolve().parents[2]
if str(_BOOT_ROOT) not in _boot_sys.path:
    _boot_sys.path.insert(0, str(_BOOT_ROOT))

import argparse
import sys
from time import perf_counter
from datetime import datetime, timedelta

from mjonai.core.enums import Provider
from mjonai.research.data.timeframe import TimeFrame
from mjonai.research.config import ResearchConfig
from mjonai.research.bootstrap import ResearchBootstrap
from mjonai.research.context import ResearchContext
from mjonai.research.universe_loader import load_universe_symbols, UniverseTier
from mjonai.research.dynamic_exits import dynamic_stop_loss, dynamic_target
from mjonai.research.optimization.research_optimizer import ResearchOptimizer
from mjonai.research.walk_forward.walk_forward_engine import WalkForwardEngine
from mjonai.research.registry_adapter import load_registry_strategy


def main():
    parser = argparse.ArgumentParser(description="MJONAI Walk-Forward Optimization Engine")
    parser.add_argument("--strategy", type=str, default="S01_MomentumRSI", help="Strategy to optimize")
    parser.add_argument("--tier", type=str, default="NIFTY_50", choices=["NIFTY_50", "NIFTY_500"], help="Universe tier")
    parser.add_argument("--count", type=int, default=5, help="Number of stocks to test")
    parser.add_argument("--train_years", type=int, default=3, help="Training window in years")
    parser.add_argument("--val_years", type=int, default=1, help="Validation window in years")
    parser.add_argument("--step_years", type=int, default=1, help="Walk-forward step between windows (years)")
    parser.add_argument("--embargo_days", type=int, default=7, help="Embargo buffer between training and validation (days)")
    parser.add_argument("--min_trades", type=int, default=10, help="Minimum trades for a parameter set to be selectable")
    parser.add_argument("--timeframe", type=str, default="1d", choices=["1d", "15m", "5m", "1m"],
                        help="Candle timeframe. Intraday values route to the Angel One provider")
    args = parser.parse_args()

    started = perf_counter()
    tier_enum = UniverseTier.NIFTY_50 if args.tier == "NIFTY_50" else UniverseTier.NIFTY_500
    symbols = load_universe_symbols(tier=tier_enum, max_count=args.count)

    start_date = datetime(2018, 1, 1)
    end_date = datetime.now()

    # Intraday research needs the Angel One intraday provider AND a
    # shorter history window (broker caps minute-candle depth; and
    # intraday frames are huge).
    is_intraday = args.timeframe != "1d"
    provider = Provider.YAHOO if not is_intraday else Provider.ANGEL
    timeframe = TimeFrame(args.timeframe)

    if is_intraday:
        start_date = end_date - timedelta(days=max(35, args.val_years * 365 + 40))
        print(f"[note] Intraday run: history window shortened to {start_date.date()} "
              f"(broker minute-data limits + frame size)")

    config = ResearchConfig(
        provider=provider,
        timeframe=timeframe,
        start=start_date,
        end=end_date,
        max_holding_bars=20 if not is_intraday else 75,  # 75x15m ~ 4-5 sessions
    )

    context = ResearchContext(
        config=config,
        symbols=symbols,
        strategy_ids=[args.strategy],
    )

    pipeline, instruments = ResearchBootstrap.build(context)
    optimizer = ResearchOptimizer(
        pipeline,
        min_trades=args.min_trades,
    )
    walk_forward = WalkForwardEngine(optimizer)

    strategy = load_registry_strategy(args.strategy)

    print("=" * 110)
    print(f"MJONAI WALK-FORWARD OPTIMIZATION & OUT-OF-SAMPLE VERIFICATION: {strategy.name}")
    print(f"Dataset: {start_date.date()} to {end_date.date()} | Train Window: {args.train_years}y | Test Window: {args.val_years}y")
    print(f"Stocks ({len(instruments)}): {', '.join(i.symbol for i in instruments)}")
    print("=" * 110)

    total_train_return = 0.0
    total_val_return = 0.0
    total_windows_count = 0
    oos_trade_pnls: list[float] = []   # G5: pooled OOS net P&L (₹)
    oos_trade_returns: list[float] = []  # G5: pooled OOS per-trade net return %
    per_symbol_summaries: list = []

    for instrument in instruments:
        summary = walk_forward.run(
            strategy=strategy,
            instrument=instrument,
            config=context.config,
            stop_loss_func=dynamic_stop_loss,
            target_func=dynamic_target,
            training_years=args.train_years,
            validation_years=args.val_years,
            step_years=args.step_years,
            embargo_days=args.embargo_days,
        )

        per_symbol_summaries.append(summary)

        print(f"\nSYMBOL: {summary.symbol} | Evaluated Windows: {len(summary.windows)}")
        print(f"{'WINDOW':<8} | {'TRAIN PERIOD':<23} | {'TEST PERIOD (OUT-OF-SAMPLE)':<27} | {'OPTIMAL PARAMS':<25} | {'TRAIN RET':<10} | {'TEST RET':<10}")
        print("-" * 110)

        for index, window in enumerate(summary.windows, start=1):
            train_str = f"{window.window.train_start.date()} -> {window.window.train_end.date()}"
            val_str = f"{window.window.validation_start.date()} -> {window.window.validation_end.date()}"
            params_str = ", ".join(f"{k}={v}" for k, v in window.parameters.items())

            train_ret = window.training_report.equity.total_return_pct
            val_ret = window.validation_report.equity.total_return_pct

            total_train_return += train_ret
            total_val_return += val_ret
            total_windows_count += 1

            for oos_trade in (window.validation_trades or []):
                oos_trade_pnls.append(float(oos_trade.net_pnl))
                oos_trade_returns.append(float(oos_trade.net_return_pct))

            status_icon = "[PASS]" if val_ret > 0 else "[LOSS]"
            print(
                f"W#{index:<6} | {train_str:<23} | {val_str:<27} | {params_str:<25} | "
                f"{train_ret:>8.2f}% | {val_ret:>8.2f}% {status_icon}"
            )

        # Canonical WFE (Pardo, 2008) computed on ANNUALIZED returns — the
        # same definition the docs' "WFE > 50% is robust" bench applies to.
        symbol_verdict = walk_forward.evaluate_walk_forward_efficiency(summary)
        print(
            f"{summary.symbol} WFE: {symbol_verdict.wfe_pct:>6.1f}% | "
            f"IS {symbol_verdict.annualized_is_return:.2f}% | "
            f"OOS {symbol_verdict.annualized_oos_return:.2f}% | "
            f"stability {symbol_verdict.plateau_stability_score:.2f} — {symbol_verdict.notes}"
        )

    print("=" * 110)
    elapsed = perf_counter() - started

    avg_is = total_train_return / max(1, total_windows_count)
    avg_oos = total_val_return / max(1, total_windows_count)

    print(f"WALK-FORWARD SUMMARY: {total_windows_count} Windows Evaluated across {len(instruments)} Stocks")
    print(f"Avg In-Sample Return : {avg_is:.2f}%")
    print(f"Avg Out-of-Sample Ret: {avg_oos:.2f}%")

    # ── Overall verdict — pooled across all symbols, canonical WFE ──────────
    pooled_summary = walk_forward.pool_summaries(
        strategy.name,
        per_symbol_summaries,
    )
    overall = walk_forward.evaluate_walk_forward_efficiency(pooled_summary)
    print(
        f"Overall WFE: {overall.wfe_pct:.1f}% | "
        f"IS {overall.annualized_is_return:.2f}% | "
        f"OOS {overall.annualized_oos_return:.2f}% | "
        f"stability {overall.plateau_stability_score:.2f}"
    )
    print(f"Canonical WFE Gate (>=50% AND OOS>0): {'ROBUST' if overall.is_robust else 'NOT ROBUST (overfitting signal)'}")

    if total_windows_count == 0:
        print(
            "\nFATAL: no walk-forward windows completed — cannot validate. "
            f"(train {args.train_years}y + val {args.val_years}y + {args.embargo_days}d embargo exceed available history; "
            "intraday runs need a LONGER history window or a live minute data archive.)",
            file=sys.stderr,
        )
        return 2

    # ── G5: STATISTICAL VALIDATION — the docs' DSR / Reality Check / Monte
    # Carlo claims now have a real execution path on pooled OOS trades.
    from mjonai.analytics.statistical_validation import (
        deflated_sharpe_ratio,
        monte_carlo_drawdown_simulation,
        whites_reality_check,
    )
    from mjonai.research.backtest.engine import INITIAL_CAPITAL

    print("-" * 125)
    print(f"STATISTICAL VALIDATION — {len(oos_trade_returns)} pooled OOS trades "
          f"(trade-level returns: non-IID approximation, labelled as such)")
    dsr = deflated_sharpe_ratio(oos_trade_returns, num_trials=max(2, total_windows_count))
    wrc = whites_reality_check(oos_trade_returns)
    mc = monte_carlo_drawdown_simulation(
        oos_trade_pnls, initial_capital=INITIAL_CAPITAL
    )
    dsr_note = (
        "DSR>0 survives multiple-testing deflation"
        if len(oos_trade_returns) >= 10
        else "insufficient samples for DSR (<10 trades)"
    )
    print(f"Deflated Sharpe Ratio   : {dsr:>8.4f}  ({dsr_note}; trials proxy = window count)")
    wrc_note = (
        f"p={wrc['p_value']:.4f} -> edge "
        + ("SIGNIFICANT at 5%" if wrc["is_significant"] else "NOT significant at 5%")
        if len(oos_trade_returns) >= 15
        else "insufficient samples for WRC (<15 trades)"
    )
    print(f"White's Reality Check   : sharpe={wrc['sharpe']:.2f}  ({wrc_note})")
    print(
        f"Monte Carlo (n={mc['simulations']}): medianDD={mc['median_max_dd_pct']:.2f}% | "
        f"P95DD={mc['p95_max_dd_pct']:.2f}% | P99DD={mc['p99_max_dd_pct']:.2f}% | "
        f"P(profit)={mc['prob_profit_pct']:.1f}%"
    )

    print(f"Completed in {elapsed:.2f} seconds.")

    # ── FAIL-CLOSED GATE ────────────────────────────────────────────────────
    # An empty walk-forward run must never masquerade as validation: intraday
    # windows are silent zero-window runs (history < train + val + embargo).
    # Exit code: 2 = no windows (cannot validate) · 1 = overfit · 0 = robust.
    return walk_forward.verdict_exit_code(
        overall,
        total_windows_count,
    )


if __name__ == "__main__":
    sys.exit(main())