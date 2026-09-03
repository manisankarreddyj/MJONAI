"""
MJONAI Backtest - 2 Year Test
Tests S01 MomentumRSI on 15 stocks over 2 years
"""
import vectorbt as vbt
import yfinance as yf
import pandas as pd
import talib
import numpy as np

print("="*70)
print("MJONAI BACKTEST - 2 YEAR TEST (S01 MomentumRSI)")
print("="*70)

# Nifty 15 stocks
stocks = [
    'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
    'HINDUNILVR.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS', 'LT.NS',
    'AXISBANK.NS', 'ASIANPAINT.NS', 'MARUTI.NS', 'SUNPHARMA.NS', 'TITAN.NS'
]

# Download 2 years of data
print("\n1. Downloading 2 years of data...")
data = {}
for stock in stocks:
    try:
        df = yf.download(stock, start='2023-01-01', end='2025-01-01', progress=False)
        if len(df) > 400:
            data[stock] = df['Close'][stock]
            print(f"   ✅ {stock.replace('.NS', '')}: {len(data[stock])} days")
        else:
            print(f"   ⚠️ {stock.replace('.NS', '')}: Insufficient data")
    except Exception as e:
        print(f"   ❌ {stock.replace('.NS', '')}: Error - {e}")

print(f"\n   Total stocks: {len(data)}")

# S01 MomentumRSI strategy
def strategy_s01(price):
    rsi = talib.RSI(price.values, timeperiod=14)
    macd, signal, hist = talib.MACD(price.values)
    ema20 = talib.EMA(price.values, timeperiod=20)
    ema50 = talib.EMA(price.values, timeperiod=50)
    
    entries = pd.Series(False, index=price.index)
    exits = pd.Series(False, index=price.index)
    
    for i in range(50, len(price)):
        if 55 <= rsi[i] <= 70 and hist[i] > 0 and ema20[i] > ema50[i]:
            entries.iloc[i] = True
        if rsi[i] > 70 or rsi[i] < 45 or hist[i] < 0:
            exits.iloc[i] = True
    
    return entries, exits

# Run backtest
print("\n2. Running backtest...")

results = []
for stock, price in data.items():
    try:
        entries, exits = strategy_s01(price)
        
        if entries.sum() > 0:
            pf = vbt.Portfolio.from_signals(
                price, entries, exits,
                init_cash=100000,
                fees=0.001,
                freq='1D'
            )
            
            results.append({
                'Stock': stock.replace('.NS', ''),
                'Return': pf.total_return() * 100,
                'Sharpe': pf.sharpe_ratio(),
                'MaxDD': pf.max_drawdown() * 100,
                'Trades': pf.trades.count(),
                'WinRate': pf.trades.win_rate() * 100 if pf.trades.count() > 0 else 0
            })
    except Exception as e:
        print(f"   ⚠️ {stock.replace('.NS', '')}: Error - {e}")

# Display results
print("\n3. Results:")
print("-"*80)
print(f"{'Stock':<12} {'Return':>10} {'Sharpe':>10} {'MaxDD':>10} {'Trades':>10} {'WinRate':>10}")
print("-"*80)

for r in results:
    print(f"{r['Stock']:<12} {r['Return']:>9.2f}% {r['Sharpe']:>10.2f} {r['MaxDD']:>9.2f}% {r['Trades']:>10} {r['WinRate']:>9.1f}%")

print("-"*80)

# Summary
if results:
    avg_return = sum(r['Return'] for r in results) / len(results)
    avg_sharpe = sum(r['Sharpe'] for r in results) / len(results)
    total_trades = sum(r['Trades'] for r in results)
    avg_winrate = sum(r['WinRate'] for r in results if r['WinRate'] > 0) / len([r for r in results if r['WinRate'] > 0])
    
    print(f"\n4. Summary (2 Year Test):")
    print(f"   Stocks with signals: {len(results)}/{len(data)}")
    print(f"   Average Return: {avg_return:.2f}%")
    print(f"   Average Sharpe: {avg_sharpe:.2f}")
    print(f"   Total Trades: {total_trades}")
    print(f"   Average Win Rate: {avg_winrate:.1f}%")
    
    # Compare with Nifty 50
    print(f"\n5. Benchmark Comparison:")
    print(f"   S01 MomentumRSI: {avg_return:.2f}%")
    print(f"   Nifty 50 (2023-2024): ~12-15% (typical)")
    print(f"   Alpha: {avg_return - 12:.2f}% (vs Nifty)")

print("\n" + "="*70)
print("✅ MJONAI 2-YEAR BACKTEST COMPLETE")
print("="*70)