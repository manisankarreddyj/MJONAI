"""
apps/research/run_pit_audit.py

The cross-sectional finding is only valid if the PIT universe is COMPLETE. A
ledger that silently drops to 40 names on some dates would quietly change the
opportunity set. This audits: per-date member count, leg continuity per symbol,
any date with a non-50 count, and total distinct symbols vs the priced panel.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from collections import Counter
import pandas as pd

from mjonai.research.pit_universe import PitUniverseLedger
from mjonai.research.discovery.cross_sectional import load_panel

def main():
    led = PitUniverseLedger()
    print("coverage_start:", led.coverage_start)
    panel = load_panel()
    dates = panel.index

    counts = {}
    for d in dates:
        try:
            counts[d] = len(led.members(d.date()))
        except Exception as e:
            counts[d] = None
    c = Counter(counts.values())
    print("member-count distribution across", len(counts), "dates:", dict(sorted(c.items(), key=lambda x: (x[0] is None, x[0]))))
    bad = [(d.date(), n) for d, n in counts.items() if n != 50]
    if bad:
        print(f"dates with != 50 members: {len(bad)}")
        # group consecutive
        print("  first 15:", bad[:15])
    else:
        print("OK: every priced date has exactly 50 members (full Nifty 50)")

    # distinct symbols ever a member
    allsyms = set()
    for d in dates[::5]:
        try:
            allsyms.update(led.members(d.date()))
        except Exception:
            pass
    priced = set(panel.columns)
    print(f"distinct PIT symbols (sampled): {len(allsyms)}  priced in panel: {len(priced)}")
    missing = sorted(allsyms - priced)
    print(f"PIT members NOT priced in panel: {len(missing)} {missing[:20]}")
    # per-symbol leg continuity
    ivs = 0
    for s in sorted(allsyms):
        try:
            legs = led.membership_intervals(s)
            ivs += len(legs)
        except Exception:
            pass
    print(f"total membership legs across symbols: {ivs} (avg {ivs/max(len(allsyms),1):.1f} legs/symbol)")

if __name__ == "__main__":
    main()
