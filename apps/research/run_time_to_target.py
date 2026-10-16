"""
Script: run_time_to_target.py
Purpose: MEASURED time-to-target per registry strategy (the validated
complement to the live pace-ETA band).

Runs every backtestable registry strategy (S01–S18 minus the data-gated
S15/S17) at default parameters over daily equity history through the
standardized research exits (dynamic 2×ATR stop, 2R target, max-holding-bars
vertical barrier — the same triple-barrier geometry the walk-forward gate
validates under), pools each strategy's TradeResults, and records how long
TARGET exits actually took: median / p25 / p75 holding bars + hit rate.

Outputs (both, every run):
  1. versioned evidence artifact  (storage/research_evidence/time_to_target_*.json)
  2. web snapshot                 (storage/research/time_to_target.json) — the ONLY
     channel the PWA reads (apps/web may not import research code). Absent or
     insufficient rows render as "not measured", never a fabricated median.

A median publishes only with >= --min-target-hits TARGET exits (default 10);
anything thinner reads "insufficient". Daily bars only: 1 bar ≈ 1 trading day.

Usage:
  python apps/research/run_time_to_target.py [--tier NIFTY_50] [--count 5]
      [--start 2018-01-01] [--strategies S01_MomentumRSI,S11_VolumeProfile] [--pit]
"""

from __future__ import annotations

import sys as _boot_sys
from pathlib import Path as _boot_Path
_BOOT_ROOT = _boot_Path(__file__).resolve().parents[2]
if str(_BOOT_ROOT) not in _boot_sys.path:
    _boot_sys.path.insert(0, str(_BOOT_ROOT))

import argparse
import json
from datetime import datetime

try:  # Windows consoles default to cp1252 — force UTF-8 like the other CLIs
    sys_stdout = _boot_sys.stdout
    sys_stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from mjonai.core.enums import Provider
from mjonai.research.data.timeframe import TimeFrame
from mjonai.research.config import ResearchConfig
from mjonai.research.bootstrap import ResearchBootstrap
from mjonai.research.context import ResearchContext
from mjonai.research.universe_loader import load_universe_symbols, UniverseTier
from mjonai.research.pit_universe import PitUniverseLedger, NIFTY50_INDEX_NAME
from mjonai.research.dynamic_exits import dynamic_stop_loss, dynamic_target
from mjonai.research.registry_adapter import (
    available_registry_strategies,
    load_registry_strategy,
)
from mjonai.research.analytics.time_to_target import summarize_time_to_target
from mjonai.research.evidence import record_evidence

SNAPSHOT_PATH = _BOOT_ROOT / "storage" / "research" / "time_to_target.json"

DISCLOSURE = (
    "MEASURED time-to-target — median/p25/p75 holding days among TARGET exits of "
    "each registry strategy run at default parameters over DAILY equity bars "
    "through the standardized research exits (dynamic 2×ATR stop, 2R target, "
    "max-holding-bars vertical barrier). Descriptive only: past travel times, "
    "not a promise of when (or whether) a live target prints, and not an edge "
    "claim. Rows below the target-hit floor read insufficient, never a median. "
    "INTRADAY-design strategies (S08/S13/S18) are WITHHELD even when daily-bar "
    "hits exist — daily-bar travel times do not apply to their 5m/15m live "
    "frame, and showing them would repeat the retired daily-for-intraday fiction."
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tier", default="NIFTY_50", choices=["NIFTY_50", "NIFTY_500"])
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--start", default="2018-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--strategies", default="",
                    help="comma-separated registry ids (default: all backtestable)")
    ap.add_argument("--max-holding-bars", type=int, default=20)
    ap.add_argument("--min-target-hits", type=int, default=10)
    ap.add_argument("--pit", action="store_true",
                    help="PIT membership masking (NIFTY_50 only, Decision 6 Phase 3)")
    a = ap.parse_args()

    tier_enum = UniverseTier.NIFTY_50 if a.tier == "NIFTY_50" else UniverseTier.NIFTY_500
    start_date = datetime.fromisoformat(a.start)
    end_date = datetime.fromisoformat(a.end) if a.end else datetime.now()

    if a.pit and a.tier != "NIFTY_50":
        print("FATAL: --pit only supports NIFTY_50.", file=_boot_sys.stderr)
        return 2

    backtestable = available_registry_strategies()
    wanted = [s.strip() for s in a.strategies.split(",") if s.strip()] or list(backtestable)
    unknown = [s for s in wanted if s not in backtestable]
    if unknown:
        print(f"FATAL: not backtestable: {unknown} (available: {backtestable})", file=_boot_sys.stderr)
        return 2

    pit_ledger = PitUniverseLedger() if a.pit else None
    symbols = load_universe_symbols(tier=tier_enum, max_count=a.count,
                                    asof=start_date if a.pit else None)

    config = ResearchConfig(
        provider=Provider.YAHOO,
        timeframe=TimeFrame("1d"),
        start=start_date,
        end=end_date,
        max_holding_bars=a.max_holding_bars,
    )
    context = ResearchContext(config=config, symbols=symbols, strategy_ids=list(wanted))
    pipeline, instruments = ResearchBootstrap.build(context)

    legs_by_symbol: dict = {}
    if pit_ledger is not None:
        for inst in instruments:
            legs_by_symbol[inst.symbol] = pit_ledger.membership_intervals(
                inst.symbol, index_name=NIFTY50_INDEX_NAME)

    print("=" * 100)
    print(f"TIME-TO-TARGET: {len(wanted)} strategies × {len(instruments)} symbols "
          f"({start_date.date()} → {end_date.date()}, daily, exits=ATR2x/2R/{a.max_holding_bars}b)")
    print("=" * 100)

    strat_rows: dict = {}
    for sid in wanted:
        strategy = load_registry_strategy(sid)
        try:
            results = pipeline.run(
                instruments=instruments,
                config=config,
                strategy=strategy,
                stop_loss_func=dynamic_stop_loss,
                target_func=dynamic_target,
                membership_intervals_by_symbol=legs_by_symbol or None,
            )
        except Exception as exc:  # one strategy must never kill the sweep
            print(f"{sid:<26} ERROR: {exc}")
            strat_rows[sid.split('_')[0]] = {
                "error": str(exc), "median_days_to_target": None,
                "insufficient_reason": f"run failed: {exc}",
            }
            continue
        trades = [t for r in results for t in (getattr(r, "trades_list", None) or [])]
        summary = summarize_time_to_target(trades, min_target_hits=a.min_target_hits)
        short = sid.split("_")[0]
        # Intraday designs trade the 5m/15m live frame — a daily-bar median
        # would mislead exactly like the retired daily-for-intraday scanner
        # fiction, so it is withheld (counts stay visible for transparency).
        design_tf = str(getattr(getattr(strategy, "_s", strategy), "timeframe", "SWING")).upper()
        if design_tf == "INTRADAY":
            summary["median_days_to_target"] = None
            summary["p25_days_to_target"] = None
            summary["p75_days_to_target"] = None
            summary["insufficient_reason"] = (
                f"withheld: {short} is INTRADAY-design — daily-bar travel times "
                "do not apply to its 5m/15m live frame"
            )
        strat_rows[short] = summary
        med = summary["median_days_to_target"]
        if med is None:
            print(f"{sid:<26} n={summary['n_trades']:<4} INSUFFICIENT "
                  f"({summary['insufficient_reason']})")
        else:
            print(f"{sid:<26} n={summary['n_trades']:<4} hit={summary['target_hit_rate']:.1%} "
                  f"med={med}d p25={summary['p25_days_to_target']}d "
                  f"p75={summary['p75_days_to_target']}d (n_target={summary['n_target']})")

    payload = {
        "universe": {"tier": a.tier, "count": a.count,
                     "symbols": [i.symbol for i in instruments], "pit": bool(a.pit)},
        "window": {"start": start_date.date().isoformat(),
                   "end": end_date.date().isoformat(), "timeframe": "1d"},
        "exits": {"stop": "dynamic ATR(14)x2", "target": "2R",
                  "max_holding_bars": a.max_holding_bars},
        "min_target_hits": a.min_target_hits,
        "strategies": strat_rows,
        "disclosure": DISCLOSURE,
    }
    record_evidence("time_to_target", payload)

    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(
        {"asof": datetime.now().isoformat(timespec="seconds"), **payload},
        indent=2), encoding="utf-8")
    print(f"[time-to-target] snapshot -> {SNAPSHOT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
