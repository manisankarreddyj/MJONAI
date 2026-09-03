"""
Module: analyze_results.py

Purpose: Query DuckDB backtest results and find genuine edges.
         Run after grid_tester.py completes.

Usage:
    python research/analyze_results.py                    # Latest run
    python research/analyze_results.py --run_id grid_20260705_120000  # Specific run

Last modified: 2026-07-05
"""

import os
import sys
import duckdb
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(__file__), "research_data.duckdb")


def get_db():
    return duckdb.connect(DB_PATH)


def get_latest_run_id():
    """Get the most recent run_id."""
    con = get_db()
    result = con.execute("SELECT run_id FROM backtest_results GROUP BY run_id ORDER BY MAX(created_at) DESC LIMIT 1").fetchone()
    con.close()
    return result[0] if result else None


def analyze(run_id=None):
    """Complete analysis of a grid test run."""
    if run_id is None:
        run_id = get_latest_run_id()

    if run_id is None:
        print("No backtest results found. Run grid_tester.py first.")
        return

    con = get_db()

    print("=" * 70)
    print(f"MJONAI Research Analysis — Run: {run_id}")
    print("=" * 70)

    # ── Overview ─────────────────────────────────────────────────────────
    overview = con.execute(f"""
        SELECT
            COUNT(*) as total_trades,
            COUNT(DISTINCT stock) as unique_stocks,
            COUNT(DISTINCT indicator) as unique_indicators,
            SUM(CASE WHEN win THEN 1 ELSE 0 END) as total_wins,
            SUM(CASE WHEN NOT win THEN 1 ELSE 0 END) as total_losses,
            ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as overall_win_rate,
            ROUND(AVG(net_return), 4) as avg_net_return,
            ROUND(AVG(actual_rr), 2) as avg_rr
        FROM backtest_results
        WHERE run_id = '{run_id}'
    """).fetchdf()

    print(f"\n📊 OVERVIEW")
    print(f"  Total trades:     {overview['total_trades'].iloc[0]:,}")
    print(f"  Unique stocks:    {overview['unique_stocks'].iloc[0]}")
    print(f"  Unique indicators:{overview['unique_indicators'].iloc[0]}")
    print(f"  Overall win rate: {overview['overall_win_rate'].iloc[0]}%")
    print(f"  Avg net return:   {overview['avg_net_return'].iloc[0]:.4f}%")
    print(f"  Avg RR:           {overview['avg_rr'].iloc[0]:.2f}")

    # ── Top Indicators by IC ────────────────────────────────────────────
    print(f"\n📈 TOP INDICATORS BY IC (Information Coefficient)")
    print(f"  IC > 0.05 = genuine edge")
    print(f"  IC > 0.10 = strong edge (rare)")
    print(f"  IC < 0.02 = noise (retire)")

    ic_results = con.execute(f"""
        SELECT
            indicator,
            parameters,
            direction,
            COUNT(*) as signals,
            ROUND(AVG(forward_return_5d) * 100, 4) as ic_5d,
            ROUND(AVG(forward_return_20d) * 100, 4) as ic_20d,
            ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
            ROUND(AVG(net_return), 4) as avg_return,
            ROUND(AVG(actual_rr), 2) as avg_rr
        FROM backtest_results
        WHERE run_id = '{run_id}'
        GROUP BY indicator, parameters, direction
        HAVING COUNT(*) >= 30
        ORDER BY ABS(ic_5d) DESC
        LIMIT 30
    """).fetchdf()

    print(f"\n{'Indicator':<20} {'Params':<30} {'Dir':<6} {'#':<6} {'IC_5d':<8} {'IC_20d':<8} {'Win%':<6} {'AvgRet':<8} {'RR':<6}")
    print("-" * 105)
    for _, row in ic_results.iterrows():
        edge_marker = "🟢" if abs(row['ic_5d']) > 0.05 else "🟡" if abs(row['ic_5d']) > 0.02 else "⚪"
        print(f"{edge_marker} {row['indicator']:<18} {str(row['parameters']):<28} {row['direction']:<6} {row['signals']:<6} {row['ic_5d']:<8.4f} {row['ic_20d']:<8.4f} {row['win_rate']:<6.1f} {row['avg_return']:<8.4f} {row['avg_rr']:<6.2f}")

    # ── Best Holding Period per Indicator ────────────────────────────────
    print(f"\n⏱️ BEST HOLDING PERIOD PER INDICATOR")

    hold_results = con.execute(f"""
        SELECT
            indicator,
            direction,
            holding_days,
            COUNT(*) as signals,
            ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
            ROUND(AVG(net_return), 4) as avg_return,
            ROUND(SUM(net_return), 2) as total_return
        FROM backtest_results
        WHERE run_id = '{run_id}'
        GROUP BY indicator, direction, holding_days
        HAVING COUNT(*) >= 20
        ORDER BY indicator, direction, avg_return DESC
    """).fetchdf()

    current_indicator = None
    for _, row in hold_results.iterrows():
        if row['indicator'] != current_indicator:
            current_indicator = row['indicator']
            print(f"\n  {row['indicator']} ({row['direction']}):")

        marker = "✅" if row['avg_return'] > 0 else "❌"
        print(f"    {marker} {row['holding_days']}d: {row['signals']} signals, {row['win_rate']}% win, {row['avg_return']:.4f}% avg, {row['total_return']:.2f}% total")

    # ── Regime Performance ───────────────────────────────────────────────
    print(f"\n🐂🐻 REGIME PERFORMANCE (where available)")

    regime_results = con.execute(f"""
        SELECT
            indicator,
            direction,
            market_state,
            COUNT(*) as signals,
            ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
            ROUND(AVG(net_return), 4) as avg_return
        FROM backtest_results
        WHERE run_id = '{run_id}' AND market_state IS NOT NULL
        GROUP BY indicator, direction, market_state
        HAVING COUNT(*) >= 20
        ORDER BY indicator, direction, avg_return DESC
    """).fetchdf()

    if not regime_results.empty:
        for _, row in regime_results.iterrows():
            print(f"  {row['indicator']} {row['direction']} in {row['market_state']}: {row['win_rate']}% win, {row['avg_return']:.4f}% avg ({row['signals']} signals)")
    else:
        print("  (No regime data yet — populate regime_history table)")

    # ── TOP 10 EDGE COMBINATIONS ─────────────────────────────────────────
    print(f"\n🏆 TOP 10 EDGE COMBINATIONS (IC > 0.03, win rate > 45%, 50+ signals)")

    top_edges = con.execute(f"""
        SELECT
            indicator,
            parameters,
            direction,
            holding_days,
            COUNT(*) as signals,
            ROUND(AVG(forward_return_5d) * 100, 4) as ic_5d,
            ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
            ROUND(AVG(net_return), 4) as avg_net_return,
            ROUND(AVG(actual_rr), 2) as avg_rr,
            ROUND(SUM(net_return), 2) as total_net_return
        FROM backtest_results
        WHERE run_id = '{run_id}'
        GROUP BY indicator, parameters, direction, holding_days
        HAVING COUNT(*) >= 50
            AND ABS(AVG(forward_return_5d)) > 0.0003
            AND SUM(CASE WHEN win THEN 1 ELSE 0 END) * 1.0 / COUNT(*) > 0.45
        ORDER BY (ABS(AVG(forward_return_5d)) * SUM(CASE WHEN win THEN 1 ELSE 0 END) * 1.0 / COUNT(*)) DESC
        LIMIT 10
    """).fetchdf()

    if not top_edges.empty:
        print(f"\n{'#':<3} {'Indicator':<18} {'Params':<25} {'Dir':<6} {'Hold':<5} {'#Sig':<6} {'IC5d':<8} {'Win%':<6} {'NetRet':<8} {'RR':<5}")
        print("-" * 95)
        for i, row in top_edges.iterrows():
            print(f"{i+1:<3} {row['indicator']:<18} {str(row['parameters']):<23} {row['direction']:<6} {row['holding_days']}d{'':<3} {row['signals']:<6} {row['ic_5d']:<8.4f} {row['win_rate']:<6.1f} {row['avg_net_return']:<8.4f} {row['avg_rr']:<5.2f}")
    else:
        print("  No edges found yet (need more data or lower thresholds)")

    # ── GENUINE EDGES SUMMARY ────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("🎯 GENUINE EDGES (IC > 0.05, win rate > 48%, 100+ signals)")
    print(f"{'='*70}")

    genuine_edges = con.execute(f"""
        SELECT
            indicator,
            parameters,
            direction,
            holding_days,
            COUNT(*) as signals,
            ROUND(AVG(forward_return_5d) * 100, 4) as ic_5d,
            ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
            ROUND(AVG(net_return), 4) as avg_net_return,
            ROUND(AVG(actual_rr), 2) as avg_rr
        FROM backtest_results
        WHERE run_id = '{run_id}'
        GROUP BY indicator, parameters, direction, holding_days
        HAVING COUNT(*) >= 100
            AND ABS(AVG(forward_return_5d)) > 0.0005
            AND SUM(CASE WHEN win THEN 1 ELSE 0 END) * 1.0 / COUNT(*) > 0.48
        ORDER BY ABS(AVG(forward_return_5d)) DESC
    """).fetchdf()

    if not genuine_edges.empty:
        for i, row in genuine_edges.iterrows():
            print(f"\n  ✅ EDGE #{i+1}:")
            print(f"     Indicator: {row['indicator']}")
            print(f"     Parameters: {row['parameters']}")
            print(f"     Direction: {row['direction']}")
            print(f"     Hold: {row['holding_days']} days")
            print(f"     Signals: {row['signals']}")
            print(f"     IC (5d): {row['ic_5d']:.4f}")
            print(f"     Win rate: {row['win_rate']}%")
            print(f"     Avg return: {row['avg_net_return']:.4f}%")
            print(f"     Avg RR: {row['avg_rr']:.2f}")

        print(f"\n  Total genuine edges found: {len(genuine_edges)}")
        print(f"  These are your FOUNDATION. Build the ranking engine around these.")
    else:
        print("  No genuine edges yet. Need more data or different indicators.")

    con.close()


if __name__ == "__main__":
    run_id = None
    if len(sys.argv) > 2 and sys.argv[1] == "--run_id":
        run_id = sys.argv[2]

    analyze(run_id)