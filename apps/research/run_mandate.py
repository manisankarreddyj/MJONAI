#!/usr/bin/env python
"""
CLI: Load and validate a YAML fund mandate, instantiate strategies, and run a backtest.

Usage:
    python apps/research/run_mandate.py path/to/mandate.yaml --universe RELIANCE,TCS,INFY
    python apps/research/run_mandate.py path/to/mandate.yaml --universe RELIANCE,TCS,INFY --blind
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mjonai.configs.strategy_config import load_spec, build_strategies_from_spec
from mjonai.research.backtest.engine import BacktestEngine
from mjonai.research.data.market_data import MarketDataService


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="run_mandate",
        description="Load a YAML mandate and run a backtest",
    )
    parser.add_argument("mandate", help="Path to mandate YAML file")
    parser.add_argument("--universe", required=True, help="Tickers comma-separated, e.g. RELIANCE,TCS,INFY")
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--blind", action="store_true", help="Run LLM agents in blind mode (withholds ticker/industry/date)")
    parser.add_argument("--timeframe", default="daily", choices=["daily", "15m", "5m"], help="Data timeframe")
    parser.add_argument("--out", help="Write results JSON to file")
    parser.add_argument("--capital", type=float, help="Override mandate capital")
    args = parser.parse_args()

    # Load and validate mandate
    try:
        spec = load_spec(args.mandate)
        print(f"[Mandate] {spec.name} | Capital: {spec.capital:,.0f} | Rebalance: {spec.rebalance} | Benchmark: {spec.benchmark}")
        print(f"[Strategies] {len(spec.strategies)}: {', '.join(s.title for s in spec.strategies)}")
    except ValueError as e:
        print(f"[Error] Invalid mandate: {e}", file=sys.stderr)
        sys.exit(1)

    # Override capital if provided
    if args.capital:
        spec.capital = args.capital

    # Parse universe
    universe = [u.strip().upper() for u in args.universe.split(",") if u.strip()]
    if not universe:
        print("[Error] No valid tickers in universe", file=sys.stderr)
        sys.exit(1)
    print(f"[Universe] {len(universe)} tickers: {', '.join(universe)}")

    # Build strategies
    strategies = build_strategies_from_spec(spec, blind=args.blind)
    print(f"[Built] {len(strategies)} strategy instances")
    for inst in strategies:
        print(f"  - {inst.spec.name} ({inst.spec.title}) weight={inst.spec.weight} blend={inst.blend_policy.method}")

    # Run backtest
    print("[Backtest] Starting...")
    data_service = MarketDataService()
    engine = BacktestEngine(
        start_date=args.start,
        end_date=args.end,
        universe=universe,
        timeframe=args.timeframe,
        capital=spec.capital,
    )

    try:
        result = engine.run(spec, strategies, data_service, blind=args.blind)
        print(f"[Result] {result}")

        if args.out:
            import json
            Path(args.out).write_text(json.dumps(result, indent=2))
            print(f"[Output] Written to {args.out}")
    except Exception as e:
        print(f"[Error] Backtest failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()