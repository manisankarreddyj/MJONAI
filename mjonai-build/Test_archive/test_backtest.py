"""
Simple VectorBT Backtest Test
Tests a basic moving average crossover strategy on HDFCBANK
"""
import vectorbt as vbt
import yfinance as yf
import pandas as pd

print("="*50)
print("MJONAI BACKTEST TEST")
print("="*50)

# Download data
print("\n1. Downloading HDFCBANK data...")
data = yf.download('HDFCBANK.NS', start='2024-01-01', end='2025-01-01', progress=False)
price = data['Close']['HDFCBANK.NS']
print(f"   ✅ Downloaded {len(price)} days of data")

# Calculate moving averages
print("\n2. Calculating moving averages...")
fast_ma = vbt.MA.run(price, window=10)
slow_ma = vbt.MA.run(price, window=50)
print(f"   ✅ Fast MA (10) and Slow MA (50) calculated")

# Generate signals
print("\n3. Generating signals...")
entries = fast_ma.ma_crossed_above(slow_ma)
exits = fast_ma.ma_crossed_below(slow_ma)
print(f"   ✅ Generated {entries.sum()} entry signals and {exits.sum()} exit signals")

# Run backtest
print("\n4. Running backtest...")
pf = vbt.Portfolio.from_signals(
    price, 
    entries, 
    exits,
    init_cash=100000,  # ₹1,00,000
    fees=0.001,        # 0.1% fees
    freq='1D'
)

# Get results
print("\n5. Results:")
print(f"   Total Return: {pf.total_return()*100:.2f}%")
print(f"   Sharpe Ratio: {pf.sharpe_ratio():.2f}")
print(f"   Max Drawdown: {pf.max_drawdown()*100:.2f}%")
print(f"   Total Trades: {pf.trades.count()}")
print(f"   Win Rate: {pf.trades.win_rate()*100:.1f}%")

print("\n" + "="*50)
print("✅ BACKTEST COMPLETE")
print("="*50)