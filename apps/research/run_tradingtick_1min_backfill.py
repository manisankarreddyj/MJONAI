"""CLI: backfill the NIFTY / BANKNIFTY 1-minute index-bar warehouse from
TradingTick.in historical intraday charts (2015 -> present, ~375 bars/day).

Spot index bars, OHLC only (no volume — never fabricated). One monthly
parquet per underlying:
    storage/parquet/tradingtick_1min/{NIFTY,BANKNIFTY}/{YYYY-MM}.parquet

Run from the repo root:
  python apps/research/run_tradingtick_1min_backfill.py --start 2015-01-01 --end 2026-09-24
"""

# ADR-0008: repo-root bootstrap — allows `python <this file>` from the repo root.
import sys as _boot_sys
from pathlib import Path as _boot_Path
_BOOT_ROOT = _boot_Path(__file__).resolve().parents[2]
if str(_BOOT_ROOT) not in _boot_sys.path:
    _boot_sys.path.insert(0, str(_BOOT_ROOT))
import argparse
from datetime import date

from mjonai.research.data.tradingtick_1min import ingest_range

DEFAULT_OUT = r"D:\MJONAI\storage\parquet\tradingtick_1min"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2015-01-01", help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--underlying", action="append",
                    help="NIFTY or BANKNIFTY (repeatable); default: both")
    ap.add_argument("--tf", type=int, default=1, choices=[1, 3, 5, 15, 30, 60],
                    help="candle period (minutes); default 1 (higher TFs resample locally)")
    args = ap.parse_args()

    summary = ingest_range(
        start=date.fromisoformat(args.start),
        end=date.fromisoformat(args.end),
        out_dir=args.out,
        underlyings=args.underlying or ("NIFTY", "BANKNIFTY"),
        tf=args.tf,
    )
    print("\n=== TRADINGTICK 1-MIN BACKFILL SUMMARY ===")
    for k, v in summary.items():
        if k != "skipped_days":
            print(f"{k}: {v}")
    print(f"(empty/missing days: {len(summary['skipped_days'])})")


if __name__ == "__main__":
    main()