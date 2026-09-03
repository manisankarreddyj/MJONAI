import duckdb
con = duckdb.connect("research/research_data.duckdb")

# Check sample data
print("SAMPLE DATA (first 10 rows):")
rows = con.execute("""
    SELECT stock, indicator, direction, entry_price, exit_price,
           gross_return, net_return, win, actual_rr
    FROM backtest_results
    WHERE run_id = (SELECT run_id FROM backtest_results LIMIT 1)
    LIMIT 10
""").fetchall()

for r in rows:
    print(f"  {r[0]:<12} {r[1]:<10} {r[2]:<6} Entry:{r[3]} Exit:{r[4]} Gross:{r[5]} Net:{r[6]} Win:{r[7]} RR:{r[8]}")

# Count NaN vs non-NaN
print("\nNULL/NAN COUNTS:")
counts = con.execute("""
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN net_return IS NULL THEN 1 ELSE 0 END) as null_net,
        SUM(CASE WHEN gross_return IS NULL THEN 1 ELSE 0 END) as null_gross,
        SUM(CASE WHEN entry_price IS NULL THEN 1 ELSE 0 END) as null_entry,
        SUM(CASE WHEN exit_price IS NULL THEN 1 ELSE 0 END) as null_exit,
        SUM(CASE WHEN net_return IS NOT NULL THEN 1 ELSE 0 END) as valid_net,
        ROUND(AVG(CASE WHEN net_return IS NOT NULL THEN net_return END), 4) as avg_valid_net
    FROM backtest_results
""").fetchone()

print(f"  Total: {counts[0]}")
print(f"  Null net_return: {counts[1]}")
print(f"  Null gross_return: {counts[2]}")
print(f"  Null entry_price: {counts[3]}")
print(f"  Null exit_price: {counts[4]}")
print(f"  Valid net_return: {counts[5]}")
print(f"  Avg valid net: {counts[6]}")

con.close()