"""
Module: deep_analysis.py
Purpose: Complete deep dive analysis of backtest results.
"""

import duckdb

DB_PATH = "research/research_data.duckdb"


def run_deep_analysis():
    con = duckdb.connect(DB_PATH)

    # ── 1. PER-STOCK PERFORMANCE ──────────────────────────────────────
    print("=" * 70)
    print("📊 PER-STOCK PERFORMANCE")
    print("=" * 70)

    stocks = con.execute("""
        SELECT stock, COUNT(*) as trades,
           ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
           ROUND(AVG(net_return), 4) as avg_return,
           ROUND(SUM(net_return), 2) as total_return,
           ROUND(AVG(actual_rr), 2) as avg_rr
        FROM backtest_results GROUP BY stock ORDER BY total_return DESC
    """).fetchdf()

    for _, row in stocks.iterrows():
        e = "🟢" if row['total_return'] > 0 else "🔴"
        print(f"  {e} {row['stock']:<15} | {row['trades']:>5} trades | Win: {row['win_rate']:>5.1f}% | Total: {row['total_return']:>8.2f}%")

    print(f"\n  Winning stocks: {len(stocks[stocks['total_return'] > 0])}/{len(stocks)}")

    # ── 2. PER-INDICATOR PERFORMANCE ─────────────────────────────────
    print("\n" + "=" * 70)
    print("📈 PER-INDICATOR PERFORMANCE")
    print("=" * 70)

    indicators = con.execute("""
        SELECT indicator, COUNT(*) as trades,
           ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
           ROUND(AVG(net_return), 4) as avg_return,
           ROUND(SUM(net_return), 2) as total_return,
           ROUND(AVG(actual_rr), 2) as avg_rr
        FROM backtest_results GROUP BY indicator ORDER BY total_return DESC
    """).fetchdf()

    for _, row in indicators.iterrows():
        e = "🟢" if row['total_return'] > 0 else "🔴"
        print(f"  {e} {row['indicator']:<12} | {row['trades']:>6} trades | Win: {row['win_rate']:>5.1f}% | Total: {row['total_return']:>8.2f}% | RR: {row['avg_rr']:.2f}")

    # ── 3. PER-HOLDING-PERIOD ─────────────────────────────────────────
    print("\n" + "=" * 70)
    print("⏱️ PER-HOLDING-PERIOD")
    print("=" * 70)

    holds = con.execute("""
        SELECT holding_days, COUNT(*) as trades,
           ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
           ROUND(AVG(net_return), 4) as avg_return,
           ROUND(SUM(net_return), 2) as total_return
        FROM backtest_results GROUP BY holding_days ORDER BY holding_days
    """).fetchdf()

    for _, row in holds.iterrows():
        e = "🟢" if row['total_return'] > 0 else "🔴"
        print(f"  {e} {row['holding_days']:>2}d | {row['trades']:>6} trades | Win: {row['win_rate']:>5.1f}% | Avg: {row['avg_return']:>7.4f}% | Total: {row['total_return']:>8.2f}%")

    # ── 4. LONG vs SHORT ──────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("🔄 LONG vs SHORT")
    print("=" * 70)

    dirs = con.execute("""
        SELECT direction, COUNT(*) as trades,
           ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
           ROUND(AVG(net_return), 4) as avg_return,
           ROUND(SUM(net_return), 2) as total_return
        FROM backtest_results GROUP BY direction
    """).fetchdf()

    for _, row in dirs.iterrows():
        e = "🟢" if row['total_return'] > 0 else "🔴"
        print(f"  {e} {row['direction']:<6} | {row['trades']:>6} trades | Win: {row['win_rate']:>5.1f}% | Avg: {row['avg_return']:>7.4f}% | Total: {row['total_return']:>8.2f}%")

    # ── 5. BEST COMBO PER INDICATOR ───────────────────────────────────
    print("\n" + "=" * 70)
    print("🏆 BEST COMBO PER INDICATOR (highest avg return, 30+ signals)")
    print("=" * 70)

    best = con.execute("""
        SELECT indicator, direction, holding_days, parameters,
               COUNT(*) as trades,
           ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
           ROUND(AVG(net_return), 4) as avg_return,
           ROUND(AVG(actual_rr), 2) as avg_rr
        FROM backtest_results
        GROUP BY indicator, direction, holding_days, parameters
        HAVING COUNT(*) >= 30
        ORDER BY indicator, avg_return DESC
    """).fetchdf()

    seen = set()
    for _, row in best.iterrows():
        key = row['indicator']
        if key in seen:
            continue
        seen.add(key)
        e = "🟢" if row['avg_return'] > 0 else "🔴"
        print(f"  {e} {row['indicator']:<12} {row['direction']:<6} {row['holding_days']:>2}d {row['parameters']:<25} | Win: {row['win_rate']:>5.1f}% | Avg: {row['avg_return']:>7.4f}% | RR: {row['avg_rr']:.2f} | N: {row['trades']}")

    # ── 6. DAY-OF-WEEK ANALYSIS ───────────────────────────────────────
    print("\n" + "=" * 70)
    print("📅 DAY-OF-WEEK ANALYSIS")
    print("=" * 70)

    dow = con.execute("""
        SELECT CASE CAST(strftime('%w', signal_date) AS INTEGER)
               WHEN 0 THEN 'Sunday' WHEN 1 THEN 'Monday'
               WHEN 2 THEN 'Tuesday' WHEN 3 THEN 'Wednesday'
               WHEN 4 THEN 'Thursday' WHEN 5 THEN 'Friday'
               END as day_of_week,
               COUNT(*) as trades,
           ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
           ROUND(AVG(net_return), 4) as avg_return
        FROM backtest_results
        GROUP BY CAST(strftime('%w', signal_date) AS INTEGER)
        ORDER BY CAST(strftime('%w', signal_date) AS INTEGER)
    """).fetchdf()

    for _, row in dow.iterrows():
        e = "🟢" if row['avg_return'] > 0 else "🔴"
        print(f"  {e} {row['day_of_week']:<10} | {row['trades']:>5} trades | Win: {row['win_rate']:>5.1f}% | Avg: {row['avg_return']:>7.4f}%")

    # ── 7. MONTH ANALYSIS ─────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("📅 MONTH ANALYSIS")
    print("=" * 70)

    month = con.execute("""
        SELECT CAST(strftime('%m', signal_date) AS INTEGER) as month,
               COUNT(*) as trades,
           ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
           ROUND(AVG(net_return), 4) as avg_return
        FROM backtest_results
        GROUP BY CAST(strftime('%m', signal_date) AS INTEGER)
        ORDER BY month
    """).fetchdf()

    month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    for _, row in month.iterrows():
        e = "🟢" if row['avg_return'] > 0 else "🔴"
        m = month_names[int(row['month'])]
        print(f"  {e} {m:<4} | {row['trades']:>5} trades | Win: {row['win_rate']:>5.1f}% | Avg: {row['avg_return']:>7.4f}%")

    # ── 8. COST IMPACT ANALYSIS ───────────────────────────────────────
    print("\n" + "=" * 70)
    print("💰 COST IMPACT ANALYSIS")
    print("=" * 70)

    costs = con.execute("""
        SELECT COUNT(*) as trades,
           ROUND(AVG(total_cost), 4) as avg_cost_per_trade,
           ROUND(SUM(total_cost), 2) as total_costs,
           ROUND(AVG(gross_return), 4) as avg_gross_return,
           ROUND(AVG(net_return), 4) as avg_net_return,
           ROUND((AVG(gross_return) - AVG(net_return)) * 100.0 / NULLIF(ABS(AVG(gross_return)), 0), 1) as cost_pct
        FROM backtest_results
    """).fetchone()

    print(f"  Trades:           {costs[0]:,}")
    print(f"  Avg cost/trade:   {costs[1]:.4f}%")
    print(f"  Total costs:      {costs[2]:.2f}%")
    print(f"  Avg gross return: {costs[3]:.4f}%")
    print(f"  Avg net return:   {costs[4]:.4f}%")
    print(f"  Cost drag:        {costs[5]:.1f}% of gross return")

    # ── 9. DRAWDOWN ANALYSIS (per stock) ──────────────────────────────
    print("\n" + "=" * 70)
    print("📉 WORST LOSING STREAKS (per stock)")
    print("=" * 70)

    streaks = con.execute("""
        WITH ranked AS (
            SELECT stock, signal_date, net_return, win,
                   ROW_NUMBER() OVER (PARTITION BY stock ORDER BY signal_date) as rn
            FROM backtest_results
            WHERE holding_days = 5
        ),
        streaks AS (
            SELECT stock, signal_date, net_return, win, rn,
                   rn - ROW_NUMBER() OVER (PARTITION BY stock, win ORDER BY signal_date) as grp
            FROM ranked
        ),
        loss_streaks AS (
            SELECT stock, grp, COUNT(*) as streak_length,
                   SUM(net_return) as streak_loss,
                   MIN(signal_date) as start_date,
                   MAX(signal_date) as end_date
            FROM streaks
            WHERE NOT win
            GROUP BY stock, grp
            HAVING COUNT(*) >= 3
        )
        SELECT stock, streak_length, ROUND(streak_loss, 2) as loss,
               start_date, end_date
        FROM loss_streaks
        ORDER BY streak_length DESC, loss ASC
        LIMIT 15
    """).fetchdf()

    if not streaks.empty:
        for _, row in streaks.iterrows():
            print(f"  🔴 {row['stock']:<15} | {row['streak_length']} consecutive losses | "
                  f"Total loss: {row['loss']:.2f}% | {row['start_date']} to {row['end_date']}")
    else:
        print("  No 3+ consecutive losing streaks found (good!)")

    # ── 10. PARAMETER SENSITIVITY ─────────────────────────────────────
    print("\n" + "=" * 70)
    print("🔬 PARAMETER SENSITIVITY (RSI threshold sweep)")
    print("=" * 70)

    sensitivity = con.execute("""
        SELECT parameters, COUNT(*) as trades,
           ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
           ROUND(AVG(net_return), 4) as avg_return
        FROM backtest_results
        WHERE indicator = 'RSI' AND direction = 'LONG' AND holding_days = 5
        GROUP BY parameters
        ORDER BY parameters
    """).fetchdf()

    for _, row in sensitivity.iterrows():
        e = "🟢" if row['avg_return'] > 0 else "🔴"
        print(f"  {e} {row['parameters']:<20} | {row['trades']:>5} trades | Win: {row['win_rate']:>5.1f}% | Avg: {row['avg_return']:>7.4f}%")

    # ── 11. MULTI-SIGNAL CONVERGENCE ──────────────────────────────────
    print("\n" + "=" * 70)
    print("🔗 MULTI-SIGNAL CONVERGENCE")
    print("=" * 70)

    convergence = con.execute("""
        WITH daily AS (
            SELECT stock, signal_date, direction,
                   COUNT(DISTINCT indicator) as n_signals,
                   AVG(net_return) as avg_ret,
                   SUM(CASE WHEN win THEN 1 ELSE 0 END) as wins,
                   COUNT(*) as total
            FROM backtest_results
            GROUP BY stock, signal_date, direction
        )
        SELECT n_signals, COUNT(*) as days,
           ROUND(SUM(wins) * 100.0 / SUM(total), 1) as win_rate,
           ROUND(AVG(avg_ret), 4) as avg_return
        FROM daily
        GROUP BY n_signals
        ORDER BY n_signals
    """).fetchdf()

    for _, row in convergence.iterrows():
        e = "🟢" if row['avg_return'] > 0 else "🔴"
        print(f"  {e} {row['n_signals']} indicators agree | {row['days']:>4} days | Win: {row['win_rate']:>5.1f}% | Avg: {row['avg_return']:>7.4f}%")

    # ── SUMMARY ───────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("📋 SUMMARY")
    print("=" * 70)

    s = con.execute("""
        SELECT COUNT(*) as total, COUNT(DISTINCT stock) as stocks,
           COUNT(DISTINCT indicator) as indicators,
           ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
           ROUND(AVG(net_return), 4) as avg_return,
           ROUND(SUM(net_return), 2) as total_return,
           ROUND(AVG(actual_rr), 2) as avg_rr
        FROM backtest_results
    """).fetchone()

    print(f"  Total: {s[0]:,} trades | Stocks: {s[1]} | Indicators: {s[2]}")
    print(f"  Win rate: {s[3]}% | Avg return: {s[4]:.4f}% | Total: {s[5]:.2f}% | RR: {s[6]:.2f}")

    con.close()


if __name__ == "__main__":
    run_deep_analysis()