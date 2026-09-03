"""
Module: run_v2.py
Purpose: Runner for v2 grid tester. Run from project root with: python -m research.run_v2
"""

import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

args = sys.argv[1:]

if "--stocks" in args:
    idx = args.index("--stocks")
    count = int(args[idx + 1])
elif "--quick" in args:
    count = 5
else:
    count = 50

from research.grid_tester_v2 import run_test

stats = run_test(max_stocks=count)

print(f"\n{'='*60}")
print(f"V2 TEST COMPLETE")
print(f"  Stocks: {stats['ok']} ok, {stats['failed']} failed")
print(f"  Trades: {stats['signals']:,}")
print(f"  Time: {stats['elapsed']}s")
print(f"{'='*60}")
print(f"\nRun analysis: python -m research.analyze_v2")