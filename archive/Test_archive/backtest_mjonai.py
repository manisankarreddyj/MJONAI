"""
MJONAI Strategy Backtest
Tests S01 MomentumRSI strategy on multiple stocks
"""
import vectorbt as vbt
import yfinance as yf
import pandas as pd
import talib
import numpy as np

print("="*60)
print("MJONAI STRATEGY BACKTEST - S01 MomentumRSI")
print("="*60)

# Test stocks (Nifty 15)
stocks = ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS']

# Download data
print("\n1. Downloading data...")
data = {}
for stock in stocks:
    df = yf.download(stock, start='2024-01-01', end='2025-01-01', progress=False)
    if len(df) > 200:
        data[stock] = df['Close'][stock]
        print(f"   ✅ {stock}: {len(data[stock])} days")
    else:
        print(f"   ⚠️ {stock}: Insufficient data ({len(df)} rows)")

print(f"\n   Total stocks: {len(data)}")

# Generate S01 signals for each stock
print("\n2. Generating S01 MomentumRSI signals...")

all_entries = {}
all_exits = {}

for stock, price in data.items():
    # Calculate RSI
    rsi = talib.RSI(price.values, timeperiod=14)
    
    # Calculate MACD
    macd, signal, hist = talib.MACD(price.values)
    
    # Calculate EMAs
    ema20 = talib.EMA(price.values, timeperiod=20)
    ema50 = talib.EMA(price.values, timeperiod=50)
    ema200 = talib.EMA(price.values, timeperiod=200)
    
    # Generate signals (simplified S01 logic)
    entries = pd.Series(False, index=price.index)
    exits = pd.Series(False, index=price.index)
    
    for i in range(200, len(price)):
        # Entry conditions (simplified):
        # - RSI between 55-70
        # - MACD bullish (hist > 0)
        # - EMA20 > EMA50
        if (55 <= rsi[i] <= 70 and 
            hist[i] > 0 and 
            ema20[i] > ema50[i]):
            entries.iloc[i] = True
        
        # Exit conditions:
        # - RSI > 70 (overbought) or RSI < 45 (momentum lost)
        # - MACD bearish (hist < 0)
        if rsi[i] > 70 or rsi[i] < 45 or hist[i] < 0:
            exits.iloc[i] = True
    
    all_entries[stock] = entries
    all_exits[stock] = exits
    
    entry_count = entries.sum()
    exit_count = exits.sum()
    print(f"   {stock}: {entry_count} entries, {exit_count} exits")

# Run backtest for each stock
print("\n3. Running backtest...")

results = []
for stock in data:
    price = data[stock]
    entries = all_entries[stock]
    exits = all_exits[stock]
    
    # Run portfolio
    pf = vbt.Portfolio.from_signals(
        price,
        entries,
        exits,
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

# Display results
print("\n4. Results:")
print("-"*80)
print(f"{'Stock':<12} {'Return':>10} {'Sharpe':>10} {'MaxDD':>10} {'Trades':>10} {'WinRate':>10}")
print("-"*80)

for r in results:
    print(f"{r['Stock']:<12} {r['Return']:>9.2f}% {r['Sharpe']:>10.2f} {r['MaxDD']:>9.2f}% {r['Trades']:>10} {r['WinRate']:>9.1f}%")

print("-"*80)

# Summary
avg_return = sum(r['Return'] for r in results) / len(results)
avg_sharpe = sum(r['Sharpe'] for r in results) / len(results)
print(f"\n5. Summary:")
print(f"   Average Return: {avg_return:.2f}%")
print(f"   Average Sharpe: {avg_sharpe:.2f}")
print(f"   Stocks tested: {len(results)}")

print("\n" + "="*60)
print("✅ MJONAI BACKTEST COMPLETE")
print("="*60)