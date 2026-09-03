"""CLI: backfill the F&O EOD chain warehouse from NSE bhavcopy archives."""
import argparse
from datetime import date

from research.data.fno_eod import ingest_range

DEFAULT_OUT = r"D:\MJONAI\mjonai-build\storage\parquet\fno_chain"


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
