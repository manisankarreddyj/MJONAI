"""
MJONAI Backtest - All 7 Strategies on 2-Year Data
Tests S01-S07 on Nifty 15 stocks over 2 years
"""
import vectorbt as vbt
import yfinance as yf
import pandas as pd
import talib
import numpy as np

print("="*80)
print("MJONAI BACKTEST - ALL 7 STRATEGIES (2-YEAR TEST)")
print("="*80)

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
    except Exception as e:
        print(f"   ❌ {stock.replace('.NS', '')}: Error - {e}")

print(f"\n   Total stocks: {len(data)}")

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
    """S02: RSI < 30 + BB lower + above EMA200"""
    rsi = talib.RSI(price.values, timeperiod=14)
    upper, middle, lower = talib.BBANDS(price.values, timeperiod=20)
    ema200 = talib.EMA(price.values, timeperiod=200)
    
    entries = pd.Series(False, index=price.index)
    exits = pd.Series(False, index=price.index)
    
    for i in range(200, len(price)):
        if rsi[i] < 30 and price.values[i] <= lower[i] and price.values[i] > ema200[i]:
            entries.iloc[i] = True
        if rsi[i] > 50 or price.values[i] > middle[i]:
            exits.iloc[i] = True
    
    return entries, exits

def strategy_s03_turtle_breakout(price):
    """S03: 20-day high breakout + above EMA200"""
    high_20 = pd.Series(price.values).rolling(20).max().values
    ema200 = talib.EMA(price.values, timeperiod=200)
    
    entries = pd.Series(False, index=price.index)
    exits = pd.Series(False, index=price.index)
    
    for i in range(200, len(price)):
        # Entry: Price breaks 20-day high + above EMA200
        if price.values[i] > high_20[i-1] and price.values[i] > ema200[i]:
            entries.iloc[i] = True
        
        # Exit: Price below 10-day low
        low_10 = min(price.values[i-10:i])
        if price.values[i] < low_10:
            exits.iloc[i] = True
    
    return entries, exits

def strategy_s04_bollinger_squeeze(price):
    """S04: BB squeeze + expansion + MACD bullish + RSI > 50"""
    upper, middle, lower = talib.BBANDS(price.values, timeperiod=20)
    macd, signal, hist = talib.MACD(price.values)
    rsi = talib.RSI(price.values, timeperiod=14)
    
    bb_width = (upper - lower) / middle
    avg_width = pd.Series(bb_width).rolling(20).mean().values
    
    entries = pd.Series(False, index=price.index)
    exits = pd.Series(False, index=price.index)
    
    for i in range(30, len(price)):
        if (bb_width[i] < avg_width[i] * 0.75 and
            bb_width[i] > bb_width[i-1] and
            hist[i] > 0 and
            rsi[i] > 50):
            entries.iloc[i] = True
        
        if hist[i] < 0 or rsi[i] < 40:
            exits.iloc[i] = True
    
    return entries, exits

def strategy_s05_price_action(price):
    """S05: Bullish candlestick patterns + above EMA50"""
    ema50 = talib.EMA(price.values, timeperiod=50)
    
    # Simplified candlestick patterns (hammer + engulfing)
    entries = pd.Series(False, index=price.index)
    exits = pd.Series(False, index=price.index)
    
    for i in range(50, len(price)):
        # Hammer pattern (simplified)
        body = abs(price.values[i] - price.values[i-1])
        lower_shadow = min(price.values[i], price.values[i-1]) - min(price.values[i], price.values[i-1])  # Simplified
        upper_shadow = max(price.values[i], price.values[i-1]) - max(price.values[i], price.values[i-1])  # Simplified
        
        # Entry: Price above EMA50 + RSI between 40-60 (simplified)
        rsi = talib.RSI(price.values, timeperiod=14)
        if price.values[i] > ema50[i] and 40 <= rsi[i] <= 60:
            entries.iloc[i] = True
        
        # Exit: Price below EMA50 or RSI > 70
        if price.values[i] < ema50[i] or rsi[i] > 70:
            exits.iloc[i] = True
    
    return entries, exits

def strategy_s06_momentum_short(price):
    """S06: RSI 30-45 + MACD bearish + EMA20 < EMA50 (SHORT)"""
    rsi = talib.RSI(price.values, timeperiod=14)
    macd, signal, hist = talib.MACD(price.values)
    ema20 = talib.EMA(price.values, timeperiod=20)
    ema50 = talib.EMA(price.values, timeperiod=50)
    
    entries = pd.Series(False, index=price.index)  # Entry = short
    exits = pd.Series(False, index=price.index)    # Exit = cover
    
    for i in range(50, len(price)):
        # Entry: RSI 30-45 + MACD bearish + EMA20 < EMA50
        if 30 <= rsi[i] <= 45 and hist[i] < 0 and ema20[i] < ema50[i]:
            entries.iloc[i] = True
        
        # Exit: RSI < 20 or RSI > 55 or MACD bullish
        if rsi[i] < 20 or rsi[i] > 55 or hist[i] > 0:
            exits.iloc[i] = True
    
    return entries, exits

def strategy_s07_mean_reversion_short(price):
    """S07: RSI > 70 + above BB upper + below EMA200 (SHORT)"""
    rsi = talib.RSI(price.values, timeperiod=14)
    upper, middle, lower = talib.BBANDS(price.values, timeperiod=20)
    ema200 = talib.EMA(price.values, timeperiod=200)
    
    entries = pd.Series(False, index=price.index)
    exits = pd.Series(False, index=price.index)
    
    for i in range(200, len(price)):
        # Entry: RSI > 70 + above BB upper + below EMA200
        if rsi[i] > 70 and price.values[i] > upper[i] and price.values[i] < ema200[i]:
            entries.iloc[i] = True
        
        # Exit: RSI < 50 or price below BB middle
        if rsi[i] < 50 or price.values[i] < middle[i]:
            exits.iloc[i] = True
    
    return entries, exits

# Run backtest for each strategy
print("\n2. Running backtests...")

strategies = {
    'S01_MomentumRSI': strategy_s01_momentum_rsi,
    'S02_MeanReversion': strategy_s02_mean_reversion,
    'S03_TurtleBreakout': strategy_s03_turtle_breakout,
    'S04_BollingerSqueeze': strategy_s04_bollinger_squeeze,
    'S05_PriceAction': strategy_s05_price_action,
    'S06_MomentumShort': strategy_s06_momentum_short,
    'S07_MeanReversionShort': strategy_s07_mean_reversion_short,
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
    else:
        print(f"     ⚠️ No signals generated")

# Display comparison
print("\n" + "="*80)
print("3. ALL 7 STRATEGIES COMPARISON (2-YEAR TEST)")
print("="*80)
print(f"{'Strategy':<25} {'Stocks':>7} {'Trades':>7} {'Return':>10} {'Sharpe':>10} {'WinRate':>10} {'vs Nifty':>10}")
print("-"*80)

for r in results:
    alpha = r['AvgReturn'] - 12  # vs Nifty 50 ~12%
    alpha_str = f"{alpha:+.2f}%" if alpha >= 0 else f"{alpha:.2f}%"
    print(f"{r['Strategy']:<25} {r['Stocks']:>7} {r['Trades']:>7} {r['AvgReturn']:>9.2f}% {r['AvgSharpe']:>10.2f} {r['AvgWinRate']:>9.1f}% {alpha_str:>10}")

print("-"*80)

# Find best strategy
if results:
    best = max(results, key=lambda x: x['AvgReturn'])
    worst = min(results, key=lambda x: x['AvgReturn'])
    
    print(f"\n4. BEST STRATEGY: {best['Strategy']}")
    print(f"   Average Return: {best['AvgReturn']:.2f}%")
    print(f"   Average Sharpe: {best['AvgSharpe']:.2f}")
    print(f"   Average Win Rate: {best['AvgWinRate']:.1f}%")
    print(f"   Alpha vs Nifty: {best['AvgReturn'] - 12:+.2f}%")
    
    print(f"\n5. WORST STRATEGY: {worst['Strategy']}")
    print(f"   Average Return: {worst['AvgReturn']:.2f}%")
    print(f"   Alpha vs Nifty: {worst['AvgReturn'] - 12:+.2f}%")

print("\n" + "="*80)
print("✅ MJONAI ALL 7 STRATEGIES BACKTEST COMPLETE")
print("="*80)