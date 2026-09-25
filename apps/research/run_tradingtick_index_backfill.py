"""CLI: backfill the historical index SPOT and FUTURES daily warehouse from
TradingTick.in (deep history 2000+ spot / 2003+ futures for NIFTY, parallel
BANKNIFTY surfaces — real rows verified at 2014-01 and 2003-01).

Writes two storage identities under --out:
  spot/{UNDERLYING}/{YYYY-MM}.parquet      (natural key trade_date)
  futures/{UNDERLYING}/{YYYY-MM}.parquet   (natural key trade_date, expiry)

Run from the repo root:
  python apps/research/run_tradingtick_index_backfill.py --start 2014-01-01 --end 2026-08-01
"""

# ADR-0008: repo-root bootstrap.
import sys as _boot_sys
from pathlib import Path as _boot_Path
_BOOT_ROOT = _boot_Path(__file__).resolve().parents[2]
if str(_BOOT_ROOT) not in _boot_sys.path:
    _boot_sys.path.insert(0, str(_BOOT_ROOT))
import argparse
from datetime import date

from mjonai.research.data.tradingtick_index import ingest_range

DEFAULT_OUT = r"D:\MJONAI\storage\parquet\tradingtick_index"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2014-01-01", help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--surface", action="append", choices=["spot", "futures"],
                    help="spot or futures (repeatable); default: both")
    ap.add_argument("--underlying", action="append",
                    help="NIFTY or BANKNIFTY (repeatable); default: both")
    args = ap.parse_args()

    summary = ingest_range(
        start=date.fromisoformat(args.start),
        end=date.fromisoformat(args.end),
        out_dir=args.out,
        surfaces=args.surface or ("spot", "futures"),
        underlyings=args.underlying or ("NIFTY", "BANKNIFTY"),
    )
    print("\n=== TRADINGTICK INDEX BACKFILL SUMMARY ===")
    for k, v in summary.items():
        if k == "skipped":
            print(f"(empty months: {len(v)})")
        elif k == "errors":
            print(f"errors: {v}")
        elif k == "months_total":
            print(f"months_total: {v}")
        elif k == "months_empty":
            print(f"months_empty: {v}")
        elif k == "rows_total":
            print(f"rows_total: {v}")
        else:
            print(f"{k}: {v}")


if __name__ == "__main__":
    main()