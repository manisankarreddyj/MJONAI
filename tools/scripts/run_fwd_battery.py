"""Run the full forward walk-forward battery and append one JSONL line per
(symbol, strategy, cadence) config. Deterministic; idempotent append to
cache/fwd_sim_out.jsonl. Detached-run friendly.

Usage:
    python tools/scripts/run_fwd_battery.py [--out cache/fwd_sim_out.jsonl]
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import forward_sim_deep as f

TRAIN = 180
TEST = 45
EMBARGO = 5

GRIDS = {
    "donchian": {"n": [20, 40, 80], "stop_atr_n": [2, 3]},
    "rsi_reversion": {"n": [7, 14], "lower": [25, 30], "upper": [70, 75], "stop_atr_n": [2, 3]},
    "orb": {"window_minutes": [15, 30], "stop_atr_n": [2, 3]},
}


def main() -> None:
    ap = __import__("argparse").ArgumentParser()
    ap.add_argument("--out", default=r"D:\MJONAI\cache\fwd_sim_out.jsonl")
    ap.add_argument("--symbols", default="NIFTY,BANKNIFTY")
    ap.add_argument("--timeout-per-config", type=float, default=0.0)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    existing = set()
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8") as fh:
            for line in fh:
                try:
                    existing.add((json.loads(line)["symbol"], json.loads(line)["strategy"], json.loads(line)["cadence"]))
                except Exception:
                    pass

    configs = [(s, st, c) for s in args.symbols.split(",") for st in GRIDS for c in ("5m", "15m")]
    for symbol, strategy, cadence in configs:
        if (symbol, strategy, cadence) in existing:
            print(f"SKIP {symbol}/{strategy}/{cadence} (already in {args.out})", flush=True)
            continue
        t0 = time.time()
        print(f"RUN  {symbol}/{strategy}/{cadence}", flush=True)
        result = f.run_symbol(
            symbol, strategy, cadence, TRAIN, TEST, EMBARGO, GRIDS[strategy]
        )
        with open(args.out, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(result, default=str) + "\n")
        print(f"DONE {symbol}/{strategy}/{cadence} in {time.time()-t0:.0f}s "
              f"windows={result['windows']} pooled={result['wfe']['pooled_oos_trades']}",
              flush=True)


if __name__ == "__main__":
    main()