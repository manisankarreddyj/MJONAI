import duckdb

con = duckdb.connect("research/research_data.duckdb")

print("=" * 60)
print("TOP 10 EDGES BY IC (5d)")
print("=" * 60)

top = con.execute("""
    SELECT indicator, parameters, direction, holding_days,
           COUNT(*) as signals,
           ROUND(AVG(forward_return_5d) * 100, 4) as ic_5d,
           ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
           ROUND(AVG(net_return), 4) as avg_return,
           ROUND(AVG(actual_rr), 2) as avg_rr
    FROM backtest_results
    GROUP BY indicator, parameters, direction, holding_days
    HAVING COUNT(*) >= 100
    ORDER BY ABS(ic_5d) DESC
    LIMIT 10
""").fetchdf()

for i, row in top.iterrows():
    print(f"\n#{i+1}: {row['indicator']} {row['parameters']} {row['direction']} {row['holding_days']}d")
    print(f"   IC: {row['ic_5d']:.4f} | Win: {row['win_rate']}% | Avg: {row['avg_return']:.4f}% | RR: {row['avg_rr']:.2f} | Signals: {row['signals']}")

print("\n" + "=" * 60)
print("TOP 5 BY WIN RATE (100+ signals)")
print("=" * 60)

win = con.execute("""
    SELECT indicator, parameters, direction, holding_days,
           COUNT(*) as signals,
           ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
           ROUND(AVG(net_return), 4) as avg_return,
           ROUND(AVG(actual_rr), 2) as avg_rr
    FROM backtest_results
    GROUP BY indicator, parameters, direction, holding_days
    HAVING COUNT(*) >= 100
    ORDER BY win_rate DESC
    LIMIT 5
""").fetchdf()

for i, row in win.iterrows():
    print(f"\n#{i+1}: {row['indicator']} {row['parameters']} {row['direction']} {row['holding_days']}d")
    print(f"   Win: {row['win_rate']}% | Avg: {row['avg_return']:.4f}% | RR: {row['avg_rr']:.2f} | Signals: {row['signals']}")

print("\n" + "=" * 60)
print("OVERALL STATS")
print("=" * 60)

stats = con.execute("""
    SELECT COUNT(*) as total,
           ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
           ROUND(AVG(net_return), 4) as avg_return,
           ROUND(AVG(actual_rr), 2) as avg_rr,
           COUNT(DISTINCT stock) as stocks,
           COUNT(DISTINCT indicator) as indicators
    FROM backtest_results
""").fetchone()

print(f"Total trades: {stats[0]:,}")
print(f"Overall win rate: {stats[1]}%")
print(f"Avg net return: {stats[2]:.4f}%")
print(f"Avg RR: {stats[3]:.2f}")
print(f"Stocks tested: {stats[4]}")
print(f"Indicators tested: {stats[5]}")

con.close()