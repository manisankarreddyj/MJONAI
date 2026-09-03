import duckdb

con = duckdb.connect("research/research_data.duckdb")

# Get run ID
run = con.execute("SELECT run_id, COUNT(*) FROM backtest_results GROUP BY run_id").fetchall()
print("RUNS IN DATABASE:")
for r in run:
    print(f"  {r[0]}: {r[1]:,} trades")

# Check data quality
print("\nDATA QUALITY:")
q = con.execute("""
    SELECT
        COUNT(*) as total,
        ROUND(AVG(COALESCE(net_return, 0)), 4) as avg_net_coalesce,
        ROUND(AVG(net_return), 4) as avg_net_raw,
        SUM(CASE WHEN win THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN NOT win THEN 1 ELSE 0 END) as losses
    FROM backtest_results
""").fetchone()

print(f"  Total trades: {q[0]:,}")
print(f"  Avg net (COALESCE): {q[1]}")
print(f"  Avg net (raw): {q[2]}")
print(f"  Wins: {q[3]} | Losses: {q[4]}")
print(f"  Win rate: {q[3]*100/(q[3]+q[4]):.1f}%")

# Sample returns
print("\nSAMPLE RETURNS (10 rows):")
for r in con.execute("SELECT net_return FROM backtest_results LIMIT 10").fetchall():
    print(f"  {r[0]}")

# Check for actual NaN strings
print("\nCHECKING FOR 'nan' STRINGS:")
n = con.execute("SELECT COUNT(*) FROM backtest_results WHERE net_return = 'nan' OR net_return = 'NaN'").fetchone()
print(f"  Rows with 'nan' string: {n[0]}")

# Check return distribution
print("\nRETURN DISTRIBUTION:")
d = con.execute("""
    SELECT
        MIN(net_return) as min_ret,
        MAX(net_return) as max_ret,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY net_return) as p25,
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY net_return) as p50,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY net_return) as p75
    FROM backtest_results
    WHERE net_return IS NOT NULL
""").fetchall()

if d:
    print(f"  Min: {d[0][0]:.4f}%")
    print(f"  P25: {d[0][3]:.4f}%")
    print(f"  Median: {d[0][4]:.4f}%")
    print(f"  P75: {d[0][2]:.4f}%")
    print(f"  Max: {d[0][1]:.4f}%")

con.close()