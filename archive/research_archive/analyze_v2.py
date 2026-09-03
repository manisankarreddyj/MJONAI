import duckdb

DB_PATH = "research/research_data.duckdb"

def analyze(run_id=None):
    con = duckdb.connect(DB_PATH)
    if run_id is None:
        row = con.execute("SELECT run_id FROM backtest_results GROUP BY run_id ORDER BY MAX(created_at) DESC LIMIT 1").fetchone()
        if row:
            run_id = row[0]
        else:
            print("No results found.")
            return
    print(f"{'='*70}")
    print(f"📊 V2 ANALYSIS — {run_id}")
    print(f"{'='*70}")
    ov = con.execute(f"""SELECT COUNT(*),COUNT(DISTINCT stock),
        ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END)*100.0/COUNT(*),1),
        ROUND(AVG(net_return),4),ROUND(AVG(gross_return),4),
        ROUND(AVG(actual_rr),2),ROUND(AVG(forward_return_5d)*100,4)
        FROM backtest_results WHERE run_id='{run_id}'""").fetchone()
    print(f"\nTrades:{ov[0]:,} Stocks:{ov[1]} Win:{ov[2]}% Net:{ov[3]:.4f}% Gross:{ov[4]:.4f}% RR:{ov[5]:.2f}")
    print(f"\n{'='*70}\nBY DIRECTION\n{'='*70}")
    for r in con.execute(f"""SELECT direction,COUNT(*),
        ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END)*100.0/COUNT(*),1),
        ROUND(AVG(net_return),4) FROM backtest_results
        WHERE run_id='{run_id}' GROUP BY direction""").fetchall():
        e="🟢" if r[3]>0 else "🔴"
        print(f"  {e} {r[0]:<6} {r[1]:>5} Win:{r[2]:>5.1f}% Net:{r[3]:>7.4f}%")
    print(f"\n{'='*70}\nBY INDICATOR\n{'='*70}")
    for r in con.execute(f"""SELECT indicator,direction,COUNT(*),
        ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END)*100.0/COUNT(*),1),
        ROUND(AVG(net_return),4),ROUND(AVG(actual_rr),2)
        FROM backtest_results WHERE run_id='{run_id}'
        GROUP BY indicator,direction HAVING COUNT(*)>=20
        ORDER BY AVG(net_return) DESC""").fetchall():
        e="🟢" if r[4]>0 else "🔴"
        print(f"  {e} {r[0]:<12} {r[1]:<6} {r[2]:>5} Win:{r[3]:>5.1f}% Net:{r[4]:>7.4f}% RR:{r[5]:.2f}")
    print(f"\n{'='*70}\nRISK METRICS (LONG)\n{'='*70}")
    for r in con.execute(f"""SELECT indicator,COUNT(*),
        ROUND(AVG(net_return),4),ROUND(STDDEV(net_return),4),
        ROUND(MIN(net_return),4),ROUND(MAX(net_return),4),
        ROUND(SUM(CASE WHEN win THEN net_return ELSE 0 END)/NULLIF(ABS(SUM(CASE WHEN NOT win THEN net_return ELSE 0 END)),0),2)
        FROM backtest_results WHERE run_id='{run_id}' AND direction='LONG'
        GROUP BY indicator HAVING COUNT(*)>=30 ORDER BY AVG(net_return) DESC""").fetchall():
        e="🟢" if r[2]>0 else "🔴"
        sh=round(r[2]/r[3],2) if r[3] and r[3]>0 else 0
        print(f"  {e} {r[0]:<12} {r[1]:>5} Net:{r[2]:>7.4f}% Worst:{r[4]:.2f}% Best:{r[5]:.2f}% Sharpe:{sh:.2f} PF:{r[6]:.2f}")
    print(f"\n{'='*70}\nEXIT REASONS\n{'='*70}")
    for r in con.execute(f"""SELECT exit_reason,COUNT(*),
        ROUND(AVG(net_return),4) FROM backtest_results
        WHERE run_id='{run_id}' GROUP BY exit_reason
        ORDER BY COUNT(*) DESC""").fetchall():
        e="🟢" if r[2]>0 else "🔴"
        print(f"  {e} {r[0]:<12} {r[1]:>5} Net:{r[2]:>7.4f}%")
    print(f"\n{'='*70}\nTOP 10 EDGES (30+ trades, net>0)\n{'='*70}")
    for i,r in enumerate(con.execute(f"""SELECT indicator,parameters,direction,COUNT(*),
        ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END)*100.0/COUNT(*),1),
        ROUND(AVG(net_return),4),ROUND(AVG(actual_rr),2)
        FROM backtest_results WHERE run_id='{run_id}'
        GROUP BY indicator,parameters,direction
        HAVING COUNT(*)>=30 AND AVG(net_return)>0
        ORDER BY AVG(net_return) DESC LIMIT 10""").fetchall(),1):
        print(f"  🟢 #{i} {r[0]:<12} {r[1]:<20} {r[2]:<6} {r[3]:>4} Win:{r[4]:>5.1f}% Net:{r[5]:>7.4f}% RR:{r[6]:.2f}")
    con.close()

if __name__ == "__main__":
    analyze()
"""
Module: analyze_v2.py
Purpose: Analysis for v2 grid tester with NaN handling.
"""

import duckdb

DB_PATH = "research/research_data.duckdb"


def analyze(run_id=None):
    con = duckdb.connect(DB_PATH)

    if run_id is None:
        row = con.execute("SELECT run_id FROM backtest_results GROUP BY run_id ORDER BY MAX(created_at) DESC LIMIT 1").fetchone()
        if row:
            run_id = row[0]
        else:
            print("No results found.")
            return

    print("=" * 70)
    print(f"📊 MJONAI V2 ANALYSIS — Run: {run_id}")
    print("=" * 70)

    # OVERVIEW
    ov = con.execute(f"""
        SELECT COUNT(*) as total,
               COUNT(DISTINCT stock) as stocks,
               ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
               ROUND(AVG(COALESCE(net_return, 0)), 4) as avg_net,
               ROUND(AVG(COALESCE(gross_return, 0)), 4) as avg_gross,
               ROUND(AVG(COALESCE(actual_rr, 0)), 2) as avg_rr,
               ROUND(AVG(COALESCE(forward_return_5d, 0)) * 100, 4) as ic_5d,
               SUM(CASE WHEN net_return IS NULL THEN 1 ELSE 0 END) as null_count
        FROM backtest_results WHERE run_id = '{run_id}'
    """).fetchone()

    print(f"\n📋 OVERVIEW")
    print(f"  Trades: {ov[0]:,} | Stocks: {ov[1]}")
    print(f"  Win rate: {ov[2]}% | Avg net: {ov[3]:.4f}%")
    print(f"  Avg gross: {ov[4]:.4f}% | Cost drag: {round(ov[4]-ov[3], 4):.4f}%")
    print(f"  Avg RR: {ov[5]:.2f} | Null returns: {ov[7]}")

    # BY DIRECTION
    print(f"\n{'='*70}")
    print("🔄 LONG vs SHORT")
    print("=" * 70)

    dirs = con.execute(f"""
        SELECT direction, COUNT(*) as trades,
           ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
           ROUND(AVG(COALESCE(net_return, 0)), 4) as avg_net,
           ROUND(AVG(COALESCE(gross_return, 0)), 4) as avg_gross
        FROM backtest_results WHERE run_id = '{run_id}'
        GROUP BY direction
    """).fetchall()

    for r in dirs:
        e = "🟢" if r[3] > 0 else "🔴"
        print(f"  {e} {r[0]:<6} | {r[1]:>5} trades | Win: {r[2]:>5.1f}% | Net: {r[3]:>7.4f}% | Gross: {r[4]:>7.4f}%")

    # BY INDICATOR
    print(f"\n{'='*70}")
    print("📈 BY INDICATOR (sorted by net return)")
    print("=" * 70)

    indicators = con.execute(f"""
        SELECT indicator, direction, COUNT(*) as trades,
           ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
           ROUND(AVG(COALESCE(net_return, 0)), 4) as avg_net,
           ROUND(AVG(COALESCE(actual_rr, 0)), 2) as avg_rr
        FROM backtest_results WHERE run_id = '{run_id}'
        GROUP BY indicator, direction
        HAVING COUNT(*) >= 20
        ORDER BY avg_net DESC
    """).fetchall()

    for r in indicators:
        e = "🟢" if r[4] > 0 else "🔴"
        print(f"  {e} {r[0]:<12} {r[1]:<6} | {r[2]:>5} trades | Win: {r[3]:>5.1f}% | Net: {r[4]:>7.4f}% | RR: {r[5]:.2f}")

    # BEST COMBO PER INDICATOR
    print(f"\n{'='*70}")
    print("🏆 BEST COMBO PER INDICATOR (highest net return)")
    print("=" * 70)

    best = con.execute(f"""
        SELECT indicator, parameters, direction, COUNT(*) as trades,
           ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
           ROUND(AVG(COALESCE(net_return, 0)), 4) as avg_net,
           ROUND(AVG(COALESCE(actual_rr, 0)), 2) as avg_rr
        FROM backtest_results WHERE run_id = '{run_id}'
        GROUP BY indicator, parameters, direction
        HAVING COUNT(*) >= 30
        ORDER BY indicator, avg_net DESC
    """).fetchall()

    seen = set()
    for r in best:
        key = r[0]
        if key in seen:
            continue
        seen.add(key)
        e = "🟢" if r[5] > 0 else "🔴"
        print(f"  {e} {r[0]:<12} {r[1]:<20} {r[2]:<6} | {r[3]:>4} | Win: {r[4]:>5.1f}% | Net: {r[5]:>7.4f}% | RR: {r[6]:.2f}")

    # RISK METRICS (only non-null net_return)
    print(f"\n{'='*70}")
    print("📉 RISK METRICS (LONG, non-null returns only)")
    print("=" * 70)

    risk = con.execute(f"""
        SELECT indicator, COUNT(*) as trades,
           ROUND(AVG(net_return), 4) as avg_net,
           ROUND(MIN(net_return), 4) as worst,
           ROUND(MAX(net_return), 4) as best,
           ROUND(SUM(CASE WHEN win THEN net_return ELSE 0 END) / NULLIF(ABS(SUM(CASE WHEN NOT win THEN net_return ELSE 0 END)), 0), 2) as profit_factor
        FROM backtest_results
        WHERE run_id = '{run_id}' AND direction = 'LONG' AND net_return IS NOT NULL
        GROUP BY indicator
        HAVING COUNT(*) >= 30
        ORDER BY avg_net DESC
    """).fetchall()

    for r in risk:
        e = "🟢" if r[2] > 0 else "🔴"
        print(f"  {e} {r[0]:<12} | {r[1]:>5} | Net: {r[2]:>7.4f}% | Worst: {r[3]:.2f}% | Best: {r[4]:.2f}% | PF: {r[5]:.2f}")

    # EXIT REASONS
    print(f"\n{'='*70}")
    print("🚪 EXIT REASONS")
    print("=" * 70)

    exits = con.execute(f"""
        SELECT exit_reason, COUNT(*) as count,
           ROUND(AVG(COALESCE(net_return, 0)), 4) as avg_net
        FROM backtest_results WHERE run_id = '{run_id}'
        GROUP BY exit_reason ORDER BY count DESC
    """).fetchall()

    for r in exits:
        e = "🟢" if r[2] > 0 else "🔴"
        print(f"  {e} {r[0]:<12} | {r[1]:>5} | Net: {r[2]:>7.4f}%")

    # TOP 10
    print(f"\n{'='*70}")
    print("🏆 TOP 10 EDGES (30+ trades, net > 0)")
    print("=" * 70)

    top = con.execute(f"""
        SELECT indicator, parameters, direction, COUNT(*) as trades,
           ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
           ROUND(AVG(COALESCE(net_return, 0)), 4) as avg_net,
           ROUND(AVG(COALESCE(actual_rr, 0)), 2) as avg_rr
        FROM backtest_results
        WHERE run_id = '{run_id}'
        GROUP BY indicator, parameters, direction
        HAVING COUNT(*) >= 30 AND AVG(COALESCE(net_return, 0)) > 0
        ORDER BY avg_net DESC
        LIMIT 10
    """).fetchall()

    for i, r in enumerate(top, 1):
        print(f"  🟢 #{i} {r[0]:<12} {r[1]:<20} {r[2]:<6} | {r[3]:>4} | Win: {r[4]:>5.1f}% | Net: {r[5]:>7.4f}% | RR: {r[6]:.2f}")

    if not top:
        print("  No positive edges found yet.")

    con.close()


if __name__ == "__main__":
    analyze()