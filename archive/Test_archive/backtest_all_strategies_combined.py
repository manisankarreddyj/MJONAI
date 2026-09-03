"""
MJONAI Backtest - S02 MeanReversion on ALL stocks
Test if mean reversion has higher win rate
"""
import vectorbt as vbt
import yfinance as yf
import pandas as pd
import talib
import numpy as np

print("="*70)
print("MJONAI BACKTEST - S02 MeanReversion (Higher Win Rate)")
print("="*70)

# Load symbols
print("\n1. Loading symbols...")
tokens_df = pd.read_csv('data/angelone/nifty500_tokens.csv')
symbols = tokens_df['name'].tolist()[:200]
print(f"   ✅ {len(symbols)} symbols")

# Download data
print("\n2. Downloading data...")
data = {}
for symbol in symbols:
    try:
        df = yf.download(f"{symbol}.NS", start='2024-01-01', end='2025-01-01', progress=False)
        if len(df) > 200:
            data[symbol] = df['Close'][f"{symbol}.NS"]
    except:
        pass

print(f"   ✅ {len(data)} stocks loaded")

# S02 MeanReversion strategy
def strategy_s02(price):
    """S02: RSI < 30 + BB lower + above EMA200 (mean reversion)"""
    rsi = talib.RSI(price.values, timeperiod=14)
    upper, middle, lower = talib.BBANDS(price.values, timeperiod=20)
    ema200 = talib.EMA(price.values, timeperiod=200)
    
    entries = pd.Series(False, index=price.index)
    exits = pd.Series(False, index=price.index)
    
    for i in range(200, len(price)):
        # Entry: RSI < 30 + at BB lower + above EMA200
        if (rsi[i] < 30 and 
            price.values[i] <= lower[i] and 
            price.values[i] > ema200[i]):
            entries.iloc[i] = True
        
        # Exit: RSI > 50 or price above BB middle
        if rsi[i] > 50 or price.values[i] > middle[i]:
            exits.iloc[i] = True
    
    return entries, exits

# Run backtest
print("\n3. Running backtest...")

results = []
total_trades = 0
total_wins = 0

for stock, price in data.items():
    try:
        entries, exits = strategy_s02(price)
        
        if entries.sum() > 0:
            pf = vbt.Portfolio.from_signals(
                price, entries, exits,
                init_cash=100000,
                fees=0.001,
                freq='1D'
            )
            
            trades = pf.trades.count()
            wins = int(pf.trades.win_rate() * trades) if trades > 0 else 0
            
            total_trades += trades
            total_wins += wins
            
            results.append({
                'Stock': stock,
                'Return': pf.total_return() * 100,
                'Trades': trades,
                'WinRate': pf.trades.win_rate() * 100 if trades > 0 else 0
            })
    except:
        pass

# Calculate metrics
if results:
    trading_days = 252
    trades_per_day = total_trades / trading_days
    overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
    
    print(f"\n4. Results:")
    print(f"   Stocks tested: {len(results)}")
    print(f"   Total trades: {total_trades}")
    print(f"   Trading days: {trading_days}")
    print(f"   Trades per day: {trades_per_day:.1f}")
    print(f"   Total wins: {total_wins}")
    print(f"   Overall win rate: {overall_win_rate:.1f}%")
    
    print(f"\n5. vs Your Criteria:")
    print(f"   Trades per day: {trades_per_day:.1f} (target: ≥5) {'✅' if trades_per_day >= 5 else '❌'}")
    print(f"   Win rate: {overall_win_rate:.1f}% (target: ≥60%) {'✅' if overall_win_rate >= 60 else '❌'}")

print("\n" + "="*70)
print("✅ BACKTEST COMPLETE")
print("="*70)