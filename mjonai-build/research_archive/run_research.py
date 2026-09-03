"""
Module: run_research.py

Purpose: One-command research runner.
         Runs grid test on all stocks, then analyzes results.

Usage:
    python research/run_research.py                    # Full test (all 500 stocks)
    python research/run_research.py --quick            # Quick test (5 stocks)
    python research/run_research.py --stocks 50        # Test 50 stocks
    python research/run_research.py --analyze          # Analyze latest results only

Last modified: 2026-07-05
"""

import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')


def main():
    args = sys.argv[1:]

    # Quick test
    if "--quick" in args:
        from research.grid_tester import run_grid_test
        print("Running QUICK test (5 stocks)...")
        stats = run_grid_test(max_stocks=5)
        from research.analyze_results import analyze
        analyze(stats['run_id'])
        return

    # Custom stock count
    if "--stocks" in args:
        idx = args.index("--stocks")
        count = int(args[idx + 1])
        from research.grid_tester import run_grid_test
        print(f"Running test on {count} stocks...")
        stats = run_grid_test(max_stocks=count)
        from research.analyze_results import analyze
        analyze(stats['run_id'])
        return

    # Analyze only
    if "--analyze" in args:
        from research.analyze_results import analyze
        analyze()
        return

    # Full test
    from research.grid_tester import run_grid_test
    print("Running FULL test (all stocks)...")
    print("This will take 1-3 hours depending on your machine.")
    print("Results are stored in DuckDB — you can analyze anytime.\n")

    stats = run_grid_test()

    print(f"\n{'='*60}")
    print("Grid test complete. Running analysis...")
    print(f"{'='*60}\n")

    from research.analyze_results import analyze
    analyze(stats['run_id'])

    print(f"\n{'='*60}")
    print("Research complete.")
    print("To re-analyze later: python research/analyze_results.py")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()