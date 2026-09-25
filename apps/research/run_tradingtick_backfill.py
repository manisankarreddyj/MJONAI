"""CLI: backfill the F&O EOD chain warehouse from TradingTick.in historical
option-chain snapshots (deep history 2016+ NIFTY/BANKNIFTY, close-only).

Complements run_fno_backfill.py (NSE official bhavcopy, full-OHLC, ~2024
onwards for rich GEX/IV work). Both write the SAME warehouse; the overlap
merges by natural key with NSE-winning preference enforced by running the
NSE backfill AFTER this one (merge is keep=last).

Run from the repo root:
  python apps/research/run_tradingtick_backfill.py --start 2021-01-01 --end 2026-09-24
"""

# ADR-0008: repo-root bootstrap — allows `python <this file>` from the repo root.
import sys as _boot_sys
from pathlib import Path as _boot_Path
_BOOT_ROOT = _boot_Path(__file__).resolve().parents[2]
if str(_BOOT_ROOT) not in _boot_sys.path:
    _boot_sys.path.insert(0, str(_BOOT_ROOT))
import argparse
from datetime import date

from mjonai.research.data.fno_tradingtick import ingest_range

DEFAULT_OUT = r"D:\MJONAI\storage\parquet\fno_chain"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2021-01-01", help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--underlying", action="append",
                    help="NIFTY or BANKNIFTY (repeatable); default: both")
    args = ap.parse_args()

    summary = ingest_range(
        start=date.fromisoformat(args.start),
        end=date.fromisoformat(args.end),
        out_dir=args.out,
        underlyings=args.underlying or ("NIFTY", "BANKNIFTY"),
    )
    print("\n=== TRADINGTICK BACKFILL SUMMARY ===")
    for k, v in summary.items():
        if k != "skipped_dates":
            print(f"{k}: {v}")
    print(f"(empty/missing chains: {len(summary['skipped_dates'])})")


if __name__ == "__main__":
    main()