"""Run the options forward-sim battery: NIFTY/BANKNIFTY x NEXT_DAY/EXPIRY/HOLD_5D.
Appends to cache/fwd_sim_options.jsonl deterministically."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import forward_sim_options as o

OUT = r"D:\MJONAI\cache\fwd_sim_options.jsonl"


def main() -> None:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    existing = set()
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                    existing.add((d["underlying"], d["exit_mode"]))
                except Exception:
                    pass
    for u in ("NIFTY", "BANKNIFTY"):
        for mode in ("NEXT_DAY", "EXPIRY", "HOLD_5D"):
            if (u, mode) in existing:
                print(f"SKIP {u}/{mode}")
                continue
            print(f"RUN  {u}/{mode}", flush=True)
            res = o.run_options_sim(u, mode)
            with open(OUT, "a", encoding="utf-8") as f:
                f.write(json.dumps(res, default=str) + "\n")
            print(f"DONE {u}/{mode} trades={res['perf']['n_trades']}", flush=True)


if __name__ == "__main__":
    main()