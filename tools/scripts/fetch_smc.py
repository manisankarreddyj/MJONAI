"""
Module: tools/scripts/fetch_smc.py
Purpose: Vendor the Smart Money Concepts indicator library (joshyattridge/smart-money-concepts)
         pinned, for MJONAI's research-only SMC features (mjonai/research/discovery/smc_features.py).

Pure pandas/numpy; no torch. Vendored + SHA-pinned so the leakage-safe wrapper is reproducible
and adds NO runtime dependency. IMPORTANT: the library's swing/FVG/BOS functions look *forward*
(ahead of the decision bar) — the wrapper de-biases them (see smc_features.py); never use the raw
library output in a live signal. Idempotent and safe to re-run.

Usage:
  python tools/scripts/fetch_smc.py               # clone/update to pinned ref
  python tools/scripts/fetch_smc.py --sha <sha>    # override to a specific revision
"""

from __future__ import annotations

import argparse
import datetime as _dt
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR_DIR = REPO_ROOT / "storage" / "vendor" / "smc"
SNAPSHOT = REPO_ROOT / "storage" / "vendor" / "smc_snapshot.txt"
UPSTREAM = "https://github.com/joshyattridge/smart-money-concepts.git"
DEFAULT_REF = "master"


def _git(args, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    ).stdout.strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Vendor smart-money-concepts (MIT) for research SMC features.")
    ap.add_argument("--sha", default=None, help="specific commit SHA to pin (default: upstream HEAD of master)")
    args = ap.parse_args(argv)

    VENDOR_DIR.parent.mkdir(parents=True, exist_ok=True)

    if (VENDOR_DIR / ".git").exists():
        _git(["fetch", "--quiet", "origin"], VENDOR_DIR)
        target = args.sha or _git(["rev-parse", f"origin/{DEFAULT_REF}"], VENDOR_DIR)
        _git(["checkout", "--quiet", target], VENDOR_DIR)
    else:
        print(f"$ git clone {UPSTREAM} -> {VENDOR_DIR}")
        subprocess.run(["git", "clone", "--quiet", UPSTREAM, str(VENDOR_DIR)], check=True)
        if args.sha:
            _git(["checkout", "--quiet", args.sha], VENDOR_DIR)

    sha = _git(["rev-parse", "HEAD"], VENDOR_DIR)
    SNAPSHOT.write_text(
        f"repo={UPSTREAM}\nref={args.sha or 'origin/master'}\nsha={sha}\n"
        f"fetched_at={_dt.datetime.now(_dt.timezone.utc).isoformat()}\n",
        encoding="utf-8",
    )
    print(f"smart-money-concepts vendored -> {VENDOR_DIR} (sha {sha[:12]})")
    print("Wrapped + de-biased (leakage-safe) in mjonai/research/discovery/smc_features.py — research only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
