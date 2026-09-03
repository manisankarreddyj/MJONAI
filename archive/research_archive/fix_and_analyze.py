import duckdb

con = duckdb.connect("research/research_data.duckdb")

# Delete bad rows
print("Cleaning data...")
con.execute("DELETE FROM backtest_results WHERE net_return = 'nan' OR net_return = 'NaN'")
print("  Bad rows deleted")

# Analysis
print("\n" + "=" * 70)
print("📊 CLEAN DATA ANALYSIS")
print("=" * 70)

ov = con.execute("""
    SELECT COUNT(*), COUNT(DISTINCT stock),
       ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END)*100.0/COUNT(*), 1),
       ROUND(AVG(net_return), 4),
       ROUND(AVG(gross_return), 4),
       ROUND(MIN(net_return), 4),
       ROUND(MAX(net_return), 4),
       ROUND(SUM(CASE WHEN win THEN net_return ELSE 0 END)/NULLIF(ABS(SUM(CASE WHEN NOT win THEN net_return ELSE 0 END)),0), 2)
    FROM backtest_results
""").fetchone()

print(f"\n📋 OVERVIEW")
print(f"  Trades: {ov[0]:,} | Stocks: {ov[1]}")
print(f"  Win rate: {ov[2]}%")
print(f"  Avg net: {ov[3]:.4f}% | Avg gross: {ov[4]:.4f}% | Cost drag: {round(ov[4]-ov[3],4):.4f}%")
print(f"  Worst: {ov[5]:.2f}% | Best: {ov[6]:.2f}% | Profit factor: {ov[7]:.2f}")
print(f"  Nifty buy-hold benchmark: 9.08% (2yr)")

print(f"\n{'='*70}\n🔄 LONG vs SHORT\n{'='*70}")
for r in con.execute("SELECT direction,COUNT(*),ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END)*100.0/COUNT(*),1),ROUND(AVG(net_return),4),ROUND(AVG(gross_return),4) FROM backtest_results GROUP BY direction").fetchall():
    e="🟢" if r[3]>0 else "🔴"
    print(f"  {e} {r[0]:<6} {r[1]:>5} Win:{r[2]:>5.1f}% Net:{r[3]:>7.4f}% Gross:{r[4]:>7.4f}%")

print(f"\n{'='*70}\n📈 BY INDICATOR\n{'='*70}")
for r in con.execute("SELECT indicator,direction,COUNT(*),ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END)*100.0/COUNT(*),1),ROUND(AVG(net_return),4) FROM backtest_results GROUP BY indicator,direction HAVING COUNT(*)>=20 ORDER BY AVG(net_return) DESC").fetchall():
    e="🟢" if r[4]>0 else "🔴"
    print(f"  {e} {r[0]:<12} {r[1]:<6} {r[2]:>5} Win:{r[3]:>5.1f}% Net:{r[4]:>7.4f}%")

print(f"\n{'='*70}\n🚪 EXIT REASONS\n{'='*70}")
for r in con.execute("SELECT exit_reason,COUNT(*),ROUND(AVG(net_return),4) FROM backtest_results GROUP BY exit_reason ORDER BY COUNT(*) DESC").fetchall():
    e="🟢" if r[2]>0 else "🔴"
    print(f"  {e} {r[0]:<12} {r[1]:>5} Net:{r[2]:>7.4f}%")

print(f"\n{'='*70}\n🏆 TOP 10 EDGES (30+ trades, net>0)\n{'='*70}")
top = con.execute("SELECT indicator,parameters,direction,COUNT(*),ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END)*100.0/COUNT(*),1),ROUND(AVG(net_return),4) FROM backtest_results GROUP BY indicator,parameters,direction HAVING COUNT(*)>=30 AND AVG(net_return)>0 ORDER BY AVG(net_return) DESC LIMIT 10").fetchall()
for i,r in enumerate(top,1):
    print(f"  🟢 #{i} {r[0]:<12} {r[1]:<20} {r[2]:<6} {r[3]:>4} Win:{r[4]:>5.1f}% Net:{r[5]:>7.4f}%")
if not top:
    print("  No positive edges found.")

print(f"\n{'='*70}\n🔴 WORST 5 (avoid these)\n{'='*70}")
for i,r in enumerate(con.execute("SELECT indicator,parameters,direction,COUNT(*),ROUND(SUM(CASE WHEN win THEN 1 ELSE 0 END)*100.0/COUNT(*),1),ROUND(AVG(net_return),4) FROM backtest_results GROUP BY indicator,parameters,direction HAVING COUNT(*)>=30 ORDER BY AVG(net_return) ASC LIMIT 5").fetchall(),1):
    print(f"  🔴 #{i} {r[0]:<12} {r[1]:<20} {r[2]:<6} {r[3]:>4} Win:{r[4]:>5.1f}% Net:{r[5]:>7.4f}%")

con.close()
print(f"\n{'='*70}\nDONE\n{'='*70}")