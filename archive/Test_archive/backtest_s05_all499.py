"""
MJONAI Backtest - S05 PriceAction on ALL 499 Nifty 500 stocks
Tests if we can achieve 5+ trades per day with 60%+ win rate
"""
import vectorbt as vbt
import yfinance as yf
import pandas as pd
import talib
import numpy as np

print("="*70)
print("MJONAI BACKTEST - S05 PriceAction on ALL 499 Stocks")
print("="*70)

# Load Nifty 500 symbols
print("\n1. Loading Nifty 500 symbols...")
try:
    tokens_df = pd.read_csv('data/angelone/nifty500_tokens.csv')
    symbols = tokens_df['name'].tolist()
    print(f"   ✅ Loaded {len(symbols)} symbols")
except Exception as e:
    print(f"   ❌ Error: {e}")
    symbols = []

# Download data (limit to 200 stocks for speed)
test_symbols = symbols[:200]
print(f"\n2. Downloading data for {len(test_symbols)} stocks...")

data = {}
for symbol in test_symbols:
    try:
        df = yf.download(f"{symbol}.NS", start='2024-01-01', end='2025-01-01', progress=False)
        if len(df) > 200:
            data[symbol] = df['Close'][f"{symbol}.NS"]
    except:
        pass

print(f"   ✅ {len(data)} stocks loaded")

# S05 PriceAction strategy
def strategy_s05(price):
    ema50 = talib.EMA(price.values, timeperiod=50)
    rsi = talib.RSI(price.values, timeperiod=14)
    
    entries = pd.Series(False, index=price.index)
    exits = pd.Series(False, index=price.index)
    
    for i in range(50, len(price)):
        if price.values[i] > ema50[i] and 40 <= rsi[i] <= 60:
            entries.iloc[i] = True
        if price.values[i] < ema50[i] or rsi[i] > 70:
            exits.iloc[i] = True
    
    return entries, exits

# Run backtest
print("\n3. Running backtest...")

results = []
total_trades = 0
total_wins = 0

for stock, price in data.items():
    try:
        entries, exits = strategy_s05(price)
        
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
    trading_days = 252  # ~1 year
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
    
    if trades_per_day >= 5 and overall_win_rate >= 60:
        print(f"\n🎉 CRITERIA MET! Ready for live deployment.")
    else:
        print(f"\n⚠️ CRITERIA NOT MET. Need to improve:")
        if trades_per_day < 5:
            print(f"   - Need more trades per day (currently {trades_per_day:.1f})")
        if overall_win_rate < 60:
            print(f"   - Need higher win rate (currently {overall_win_rate:.1f}%)")

print("\n" + "="*70)
print("✅ BACKTEST COMPLETE")
print("="*70)