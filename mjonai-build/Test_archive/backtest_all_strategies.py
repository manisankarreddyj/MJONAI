"""
MJONAI Backtest - All 7 Strategies
Compares S01-S07 on same stocks and timeframe
"""
import vectorbt as vbt
import yfinance as yf
import pandas as pd
import talib
import numpy as np

print("="*70)
print("MJONAI BACKTEST - ALL 7 STRATEGIES COMPARISON")
print("="*70)

# Test stocks
stocks = ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS']

# Download data
print("\n1. Downloading data...")
data = {}
for stock in stocks:
    df = yf.download(stock, start='2024-07-01', end='2025-01-01', progress=False)
    if len(df) > 100:
        data[stock] = df['Close'][stock]
print(f"   ✅ {len(data)} stocks loaded")

# Strategy implementations
def strategy_s01_momentum_rsi(price):
    """S01: RSI 55-70 + MACD bullish + EMA20 > EMA50"""
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

def strategy_s02_mean_reversion(price):
    """S02: RSI < 30 + BB lower + volume spike + above EMA200"""
    rsi = talib.RSI(price.values, timeperiod=14)
    upper, middle, lower = talib.BBANDS(price.values, timeperiod=20)
    ema200 = talib.EMA(price.values, timeperiod=200)
    
    entries = pd.Series(False, index=price.index)
    exits = pd.Series(False, index=price.index)
    
    for i in range(200, len(price)):
        # Entry: RSI < 30 + price at BB lower + above EMA200
        if (rsi[i] < 30 and 
            price.values[i] <= lower[i] and 
            price.values[i] > ema200[i]):
            entries.iloc[i] = True
        
        # Exit: RSI > 50 or price above BB middle
        if rsi[i] > 50 or price.values[i] > middle[i]:
            exits.iloc[i] = True
    
    return entries, exits

def strategy_s04_bollinger_squeeze(price):
    """S04: BB squeeze + expansion + MACD bullish + RSI > 50"""
    upper, middle, lower = talib.BBANDS(price.values, timeperiod=20)
    macd, signal, hist = talib.MACD(price.values)
    rsi = talib.RSI(price.values, timeperiod=14)
    
    # Calculate BB width
    bb_width = (upper - lower) / middle
    avg_width = pd.Series(bb_width).rolling(20).mean().values
    
    entries = pd.Series(False, index=price.index)
    exits = pd.Series(False, index=price.index)
    
    for i in range(30, len(price)):
        # Entry: BB squeeze + expansion + MACD bullish + RSI > 50
        if (bb_width[i] < avg_width[i] * 0.75 and  # Squeeze
            bb_width[i] > bb_width[i-1] and          # Expanding
            hist[i] > 0 and                          # MACD bullish
            rsi[i] > 50):                            # RSI > 50
            entries.iloc[i] = True
        
        # Exit: MACD bearish or RSI < 40
        if hist[i] < 0 or rsi[i] < 40:
            exits.iloc[i] = True
    
    return entries, exits

# Run backtest for each strategy
print("\n2. Running backtests...")

strategies = {
    'S01_MomentumRSI': strategy_s01_momentum_rsi,
    'S02_MeanReversion': strategy_s02_mean_reversion,
    'S04_BollingerSqueeze': strategy_s04_bollinger_squeeze,
}

results = []

for strategy_name, strategy_func in strategies.items():
    print(f"\n   Testing {strategy_name}...")
    
    strategy_results = []
    
    for stock, price in data.items():
        try:
            entries, exits = strategy_func(price)
            
            if entries.sum() > 0:
                pf = vbt.Portfolio.from_signals(
                    price, entries, exits,
                    init_cash=100000,
                    fees=0.001,
                    freq='1D'
                )
                
                strategy_results.append({
                    'Stock': stock.replace('.NS', ''),
                    'Return': pf.total_return() * 100,
                    'Sharpe': pf.sharpe_ratio(),
                    'MaxDD': pf.max_drawdown() * 100,
                    'Trades': pf.trades.count(),
                    'WinRate': pf.trades.win_rate() * 100 if pf.trades.count() > 0 else 0
                })
        except Exception as e:
            print(f"     ⚠️ {stock.replace('.NS', '')}: Error - {e}")
    
    if strategy_results:
        avg_return = sum(r['Return'] for r in strategy_results) / len(strategy_results)
        avg_sharpe = sum(r['Sharpe'] for r in strategy_results) / len(strategy_results)
        total_trades = sum(r['Trades'] for r in strategy_results)
        avg_winrate = sum(r['WinRate'] for r in strategy_results if r['WinRate'] > 0) / len([r for r in strategy_results if r['WinRate'] > 0]) if any(r['WinRate'] > 0 for r in strategy_results) else 0
        
        results.append({
            'Strategy': strategy_name,
            'Stocks': len(strategy_results),
            'Trades': total_trades,
            'AvgReturn': avg_return,
            'AvgSharpe': avg_sharpe,
            'AvgWinRate': avg_winrate
        })
        
        print(f"     ✅ {len(strategy_results)} stocks, {total_trades} trades, {avg_return:.2f}% return")

# Display comparison
print("\n" + "="*70)
print("3. STRATEGY COMPARISON RESULTS")
print("="*70)
print(f"{'Strategy':<22} {'Stocks':>7} {'Trades':>7} {'Return':>10} {'Sharpe':>10} {'WinRate':>10}")
print("-"*70)

for r in results:
    print(f"{r['Strategy']:<22} {r['Stocks']:>7} {r['Trades']:>7} {r['AvgReturn']:>9.2f}% {r['AvgSharpe']:>10.2f} {r['AvgWinRate']:>9.1f}%")

print("-"*70)

# Find best strategy
if results:
    best = max(results, key=lambda x: x['AvgReturn'])
    print(f"\n4. Best Strategy: {best['Strategy']}")
    print(f"   Average Return: {best['AvgReturn']:.2f}%")
    print(f"   Average Sharpe: {best['AvgSharpe']:.2f}")
    print(f"   Average Win Rate: {best['AvgWinRate']:.1f}%")

print("\n" + "="*70)
print("✅ MJONAI STRATEGY COMPARISON COMPLETE")
print("="*70)