#!/usr/bin/env python
"""
Module: tools/scripts/convert_qlib_to_parquet.py
Purpose: Convert qlib-format .bin data to MJONAI's parquet cache with adjustment_mode tagging.

Adapted from Qbot's qbot/data/dump_bin.py (qlib's FileFeatureStorage) — clean-room reimplementation.

Usage:
    python tools/scripts/convert_qlib_to_parquet.py \
        --qlib-dir ~/.qlib/qlib_data/cn_data \
        --out-dir storage/parquet/qlib_converted \
        --adjustment-mode raw \
        --freq day

The qlib .bin format: little-endian float32 with 4-byte index header (int32 start_index).
Each feature file: [start_index][float32 values...]
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from tqdm import tqdm


QLIB_DUMP_SUFFIX = ".bin"
QLIB_FREQ_MAP = {"day": "1d", "1min": "1m", "15min": "15m", "30min": "30m", "60min": "1h"}


def read_qlib_bin(bin_path: Path) -> tuple[Optional[int], np.ndarray]:
    """
    Read a qlib .bin file.

    Returns:
        (start_index, values_array) or (None, empty_array) if file invalid/empty.
    """
    if not bin_path.exists() or bin_path.stat().st_size < 4:
        return None, np.array([], dtype=np.float32)

    with bin_path.open("rb") as f:
        header = f.read(4)
        if len(header) < 4:
            return None, np.array([], dtype=np.float32)
        start_index = struct.unpack("<i", header)[0]  # little-endian int32
        data = np.fromfile(f, dtype="<f")  # little-endian float32
    return start_index, data


def build_calendar(qlib_dir: Path, freq: str) -> list[pd.Timestamp]:
    """Read qlib calendar txt file."""
    cal_file = qlib_dir / "calendars" / f"{freq}.txt"
    if not cal_file.exists():
        raise FileNotFoundError(f"Calendar not found: {cal_file}")
    with cal_file.open("r") as f:
        dates = [line.strip() for line in f if line.strip()]
    return [pd.Timestamp(d) for d in dates]


def read_instruments(qlib_dir: Path) -> pd.DataFrame:
    """Read qlib instruments file (all.txt)."""
    inst_file = qlib_dir / "instruments" / "all.txt"
    if not inst_file.exists():
        raise FileNotFoundError(f"Instruments file not found: {inst_file}")
    df = pd.read_csv(
        inst_file,
        sep="\t",
        names=["symbol", "start_datetime", "end_datetime"],
        dtype={"symbol": str},
    )
    df["start_datetime"] = pd.to_datetime(df["start_datetime"])
    df["end_datetime"] = pd.to_datetime(df["end_datetime"])
    return df


def convert_symbol(
    symbol: str,
    qlib_dir: Path,
    freq: str,
    calendar: list[pd.Timestamp],
    adjustment_mode: str,
    out_root: Path,
) -> tuple[int, int]:
    """
    Convert all features for one symbol from .bin to parquet.

    Returns:
        (features_converted, rows_written)
    """
    feat_dir = qlib_dir / "features" / symbol.lower()
    if not feat_dir.exists():
        return 0, 0

    bin_files = sorted(feat_dir.glob(f"*{QLIB_DUMP_SUFFIX}"))
    if not bin_files:
        return 0, 0

    # Read all features into a dict of Series aligned to calendar
    feature_series = {}
    for bin_file in bin_files:
        field = bin_file.stem.replace(f".{freq}", "").replace(QLIB_DUMP_SUFFIX, "")
        start_idx, values = read_qlib_bin(bin_file)
        if start_idx is None or len(values) == 0:
            continue
        # Align to calendar
        end_idx = start_idx + len(values)
        if end_idx > len(calendar):
            # Truncate if exceeds calendar (shouldn't happen with valid data)
            values = values[: len(calendar) - start_idx]
            end_idx = len(calendar)
        series = pd.Series(values, index=calendar[start_idx:end_idx], dtype=np.float32)
        feature_series[field] = series

    if not feature_series:
        return 0, 0

    # Combine into DataFrame
    df = pd.DataFrame(feature_series)
    df.index.name = "timestamp"

    # Standard column ordering
    preferred_order = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "vwap",
        "amount",
        "turnover",
        "factor",
        "open_interest",
    ]
    cols = [c for c in preferred_order if c in df.columns] + [
        c for c in df.columns if c not in preferred_order
    ]
    df = df[cols]

    # Add metadata columns
    df.insert(0, "symbol", symbol)
    df.insert(1, "adjustment_mode", adjustment_mode)

    # Write parquet
    out_dir = out_root / freq / symbol
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{freq}_{adjustment_mode}.parquet"
    df.to_parquet(out_file, compression="snappy", index=True)

    return len(df.columns), len(df)


def main():
    parser = argparse.ArgumentParser(
        description="Convert qlib .bin data to MJONAI parquet cache"
    )
    parser.add_argument(
        "--qlib-dir",
        required=True,
        type=Path,
        help="Root qlib data directory (containing calendars/, instruments/, features/)",
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        type=Path,
        help="Output root directory for parquet cache",
    )
    parser.add_argument(
        "--adjustment-mode",
        default="raw",
        choices=["raw", "adjusted"],
        help="Adjustment mode tag for output parquet (default: raw)",
    )
    parser.add_argument(
        "--freq",
        default="day",
        choices=["day", "1min", "15min", "30min", "60min"],
        help="Qlib frequency (default: day)",
    )
    parser.add_argument(
        "--symbols",
        nargs="*",
        help="Specific symbols to convert (default: all in instruments/all.txt)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of symbols (for testing)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List symbols without converting",
    )
    args = parser.parse_args()

    qlib_dir = args.qlib_dir.expanduser().resolve()
    if not qlib_dir.exists():
        print(f"ERROR: qlib-dir not found: {qlib_dir}", file=sys.stderr)
        sys.exit(1)

    # Load calendar
    try:
        calendar = build_calendar(qlib_dir, args.freq)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Load instruments
    try:
        instruments = read_instruments(qlib_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    symbols = args.symbols or instruments["symbol"].tolist()
    if args.limit:
        symbols = symbols[: args.limit]

    print(f"QLib dir: {qlib_dir}")
    print(f"Output dir: {args.out_dir}")
    print(f"Freq: {args.freq} ({QLIB_FREQ_MAP.get(args.freq, args.freq)})")
    print(f"Adjustment mode: {args.adjustment_mode}")
    print(f"Calendar: {len(calendar)} bars ({calendar[0].date()} -> {calendar[-1].date()})")
    print(f"Symbols to convert: {len(symbols)}")

    if args.dry_run:
        for s in symbols:
            print(f"  {s}")
        return

    out_root = args.out_dir.expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    total_features = 0
    total_rows = 0
    failed = []

    for symbol in tqdm(symbols, desc="Converting symbols"):
        try:
            feats, rows = convert_symbol(
                symbol=symbol,
                qlib_dir=qlib_dir,
                freq=args.freq,
                calendar=calendar,
                adjustment_mode=args.adjustment_mode,
                out_root=out_root,
            )
            total_features += feats
            total_rows += rows
        except Exception as e:
            failed.append((symbol, str(e)))

    print(f"\n=== Conversion Complete ===")
    print(f"Symbols processed: {len(symbols) - len(failed)}")
    print(f"Features written: {total_features}")
    print(f"Total rows: {total_rows}")
    if failed:
        print(f"Failed ({len(failed)}):")
        for sym, err in failed:
            print(f"  {sym}: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()