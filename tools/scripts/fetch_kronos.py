"""
Module: tools/scripts/fetch_kronos.py
Purpose: Vendor the Kronos time-series foundation model (shiyu-coder/Kronos, MIT)
         at a pinned revision for MJONAI's research forecasting tier (ADR-0002).

Kronos is natively OHLCV-native and is the ADR-0002 first-choice TSFM;
mjonai/research/forecasting/kronos_adapter.py loads it from this vendored copy.
The CODE tree is vendored (pinned, ~small); the HF model WEIGHTS are a separate
owner opt-in download so nothing heavy enters the core venv / CI silently.
Idempotent and safe to re-run.

Usage:
  python tools/scripts/fetch_kronos.py               # clone/update to pinned ref
  python tools/scripts/fetch_kronos.py --sha <sha>    # override to a specific revision
"""

from __future__ import annotations

import argparse
import datetime as _dt
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR_DIR = REPO_ROOT / "storage" / "vendor" / "kronos"
SNAPSHOT = REPO_ROOT / "storage" / "vendor" / "kronos_snapshot.txt"
UPSTREAM = "https://github.com/shiyu-coder/Kronos.git"
DEFAULT_REF = "master"


def _git(args, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    ).stdout.strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Vendor Kronos (MIT) for the research forecasting tier.")
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
    print(f"Kronos vendored -> {VENDOR_DIR} (sha {sha[:12]})")
    print("Next steps (research-only, owner opt-in):")
    print("  1) python -m pip install -r requirements-research-ml.txt   # torch + HF")
    print("  2) python -c \"from huggingface_hub import snapshot_download; snapshot_download('NeoQuasar/Kronos-mini')\"")
    print("  3) run the forecast benchmark: apps/research/run_forecast_benchmark.py  (adds Kronos to the gate)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
