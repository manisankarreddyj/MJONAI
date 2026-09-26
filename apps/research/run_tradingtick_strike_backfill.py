"""CLI: backfill the per-strike daily OHLC warehouse for index options from
TradingTick.in (NIFTY monthly expiries 2019-02 -> present, BANKNIFTY monthly
expiries 2016-06 -> present).

Writes one storage identity per underlying under --out:
  {UNDERLYING}/{YYYY-MM}.parquet      (natural key trade_date, expiry,
                                      option_type, strike)

The tradingtick_strike_ohlc endpoint serves monthly expiries only (weekly
expiries never appear), one chart request per (expiry, option, strike).
Run from the repo root:
  python apps/research/run_tradingtick_strike_backfill.py --start 2019-02-01 --end 2026-09-01
"""

# ADR-0008: repo-root bootstrap.
import sys as _boot_sys
from pathlib import Path as _boot_Path
_BOOT_ROOT = _boot_Path(__file__).resolve().parents[2]
if str(_BOOT_ROOT) not in _boot_sys.path:
    _boot_sys.path.insert(0, str(_BOOT_ROOT))
import argparse
from datetime import date

from mjonai.research.data.tradingtick_strike_ohlc import ingest_range

DEFAULT_OUT = r"D:\MJONAI\storage\parquet\tradingtick_strike"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2019-02-01", help="YYYY-MM-DD (inclusive)")
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
    print("\n=== TRADINGTICK STRIKE-OHLC BACKFILL SUMMARY ===")
    for k, v in summary.items():
        if k == "skipped":
            print(f"(empty contracts: {len(v)})")
        elif k == "errors":
            print(f"errors: {v}")
        elif k == "contracts_total":
            print(f"contracts_total: {v}")
        elif k == "contracts_empty":
            print(f"contracts_empty: {v}")
        elif k == "rows_total":
            print(f"rows_total: {v}")
        elif k in ("NIFTY", "BANKNIFTY"):
            print(f"rows_{k}: {v}")
        else:
            print(f"{k}: {v}")


if __name__ == "__main__":
    main()