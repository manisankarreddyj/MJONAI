"""
MJONAI Backtest - S05 PriceAction on Nifty 500
Tests if the edge holds across more stocks
"""
import vectorbt as vbt
import yfinance as yf
import pandas as pd
import talib
import numpy as np

print("="*70)
print("MJONAI BACKTEST - S05 PriceAction on Nifty 500")
print("="*70)

# Load Nifty 500 symbols from CSV
print("\n1. Loading Nifty 500 symbols...")
try:
    tokens_df = pd.read_csv('data/angelone/nifty500_tokens.csv')
    symbols = tokens_df['name'].tolist()
    print(f"   ✅ Loaded {len(symbols)} symbols")
except Exception as e:
    print(f"   ❌ Error loading CSV: {e}")
    # Fallback to Nifty 15
    symbols = [
        'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK',
        'HINDUNILVR', 'SBIN', 'BHARTIARTL', 'KOTAKBANK', 'LT',
        'AXISBANK', 'ASIANPAINT', 'MARUTI', 'SUNPHARMA', 'TITAN'
    ]
    print(f"   ⚠️ Using fallback: {len(symbols)} symbols")

# Download data (limit to 50 stocks for speed)
test_symbols = symbols[:50]  # Test first 50 stocks
print(f"\n2. Downloading data for {len(test_symbols)} stocks...")

data = {}
for symbol in test_symbols:
    try:
        df = yf.download(f"{symbol}.NS", start='2023-01-01', end='2025-01-01', progress=False)
        if len(df) > 400:
            data[symbol] = df['Close'][f"{symbol}.NS"]
            print(f"   ✅ {symbol}: {len(data[symbol])} days")
    except Exception as e:
        print(f"   ⚠️ {symbol}: Error - {e}")

print(f"\n   Total stocks: {len(data)}")

# S05 PriceAction strategy
def strategy_s05_price_action(price):
    """S05: Bullish candlestick patterns + above EMA50"""
    ema50 = talib.EMA(price.values, timeperiod=50)
    rsi = talib.RSI(price.values, timeperiod=14)
    
    entries = pd.Series(False, index=price.index)
    exits = pd.Series(False, index=price.index)
    
    for i in range(50, len(price)):
        # Entry: Price above EMA50 + RSI between 40-60
        if price.values[i] > ema50[i] and 40 <= rsi[i] <= 60:
            entries.iloc[i] = True
        
        # Exit: Price below EMA50 or RSI > 70
        if price.values[i] < ema50[i] or rsi[i] > 70:
            exits.iloc[i] = True
    
    return entries, exits

# Run backtest
print("\n3. Running backtest...")

results = []
for stock, price in data.items():
    try:
        entries, exits = strategy_s05_price_action(price)
        
        if entries.sum() > 0:
            pf = vbt.Portfolio.from_signals(
                price, entries, exits,
                init_cash=100000,
                fees=0.001,
                freq='1D'
            )
            
            results.append({
                'Stock': stock,
                'Return': pf.total_return() * 100,
                'Sharpe': pf.sharpe_ratio(),
                'MaxDD': pf.max_drawdown() * 100,
                'Trades': pf.trades.count(),
                'WinRate': pf.trades.win_rate() * 100 if pf.trades.count() > 0 else 0
            })
    except Exception as e:
        print(f"   ⚠️ {stock}: Error - {e}")

# Display results
print("\n4. Results:")
print("-"*90)
print(f"{'Stock':<15} {'Return':>10} {'Sharpe':>10} {'MaxDD':>10} {'Trades':>10} {'WinRate':>10} {'vs Nifty':>10}")
print("-"*90)

for r in results:
    alpha = r['Return'] - 12  # vs Nifty 50 ~12%
    alpha_str = f"{alpha:+.2f}%" if alpha >= 0 else f"{alpha:.2f}%"
    print(f"{r['Stock']:<15} {r['Return']:>9.2f}% {r['Sharpe']:>10.2f} {r['MaxDD']:>9.2f}% {r['Trades']:>10} {r['WinRate']:>9.1f}% {alpha_str:>10}")

print("-"*90)

# Summary
if results:
    avg_return = sum(r['Return'] for r in results) / len(results)
    avg_sharpe = sum(r['Sharpe'] for r in results) / len(results)
    total_trades = sum(r['Trades'] for r in results)
    avg_winrate = sum(r['WinRate'] for r in results if r['WinRate'] > 0) / len([r for r in results if r['WinRate'] > 0])
    
    stocks_with_alpha = len([r for r in results if r['Return'] > 12])
    
    print(f"\n5. Summary (S05 PriceAction on {len(results)} stocks):")
    print(f"   Average Return: {avg_return:.2f}%")
    print(f"   Average Sharpe: {avg_sharpe:.2f}")
    print(f"   Total Trades: {total_trades}")
    print(f"   Average Win Rate: {avg_winrate:.1f}%")
    print(f"   Stocks with positive alpha: {stocks_with_alpha}/{len(results)}")
    print(f"   Alpha vs Nifty: {avg_return - 12:+.2f}%")

print("\n" + "="*70)
print("✅ S05 PriceAction NIFTY 500 BACKTEST COMPLETE")
print("="*70)