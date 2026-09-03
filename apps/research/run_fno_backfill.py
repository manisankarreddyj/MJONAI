"""CLI: backfill the F&O EOD chain warehouse from NSE bhavcopy archives."""

# ADR-0008: repo-root bootstrap — allows `python <this file>` from the repo root.
import sys as _boot_sys
from pathlib import Path as _boot_Path
_BOOT_ROOT = _boot_Path(__file__).resolve().parents[2]
if str(_BOOT_ROOT) not in _boot_sys.path:
    _boot_sys.path.insert(0, str(_BOOT_ROOT))
import argparse
from datetime import date

from mjonai.research.data.fno_eod import ingest_range

DEFAULT_OUT = r"D:\MJONAI\storage\parquet\fno_chain"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", required=True, help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--underlying", action="append",
                    help="filter to underlying (repeatable); default: ALL")
    args = ap.parse_args()

    summary = ingest_range(
        start=date.fromisoformat(args.start),
        end=date.fromisoformat(args.end),
        out_dir=args.out,
        underlyings=args.underlying or None,
    )
    print("\n=== BACKFILL SUMMARY ===")
    for k, v in summary.items():
        if k != "skipped_days":
            print(f"{k}: {v}")
    print(f"(non-trading/unpublished days skipped: {len(summary['skipped_days'])})")


if __name__ == "__main__":
    main()
