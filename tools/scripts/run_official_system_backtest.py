"""
Script: scripts/run_official_system_backtest.py
Purpose: Execute the 100% OFFICIAL MJONAI Research & Strategy System:
         - Live Strategy Suite (strategy.registry: S01, S02, S04)
         - Official Registry Adapter (research.registry_adapter.load_registry_strategy)
         - Official Strategy Runner (research.runner.StrategyRunner)
         - Official Backtest Engine (research.backtest.engine.BacktestEngine)
         - Official Analytics Engine (analytics.performance.PerformanceAnalyzer)
         over Real Parquet Historical Data (14-21 Aug 2026) with ₹1,00,000 (1 Lakh) Capital.
"""

# ADR-0008: repo-root bootstrap — allows `python <this file>` from the repo root.
import sys as _boot_sys
from pathlib import Path as _boot_Path
_BOOT_ROOT = _boot_Path(__file__).resolve().parents[2]
if str(_BOOT_ROOT) not in _boot_sys.path:
    _boot_sys.path.insert(0, str(_BOOT_ROOT))

import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.ERROR)
logging.getLogger("strategy").setLevel(logging.ERROR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import numpy as np
import pandas as pd

from mjonai.core.constants import TOTAL_CAPITAL
from mjonai.research.registry_adapter import load_registry_strategy
from mjonai.research.runner import StrategyRunner
from mjonai.research.backtest.engine import BacktestEngine
from mjonai.analytics.performance import PerformanceAnalyzer

CACHE_DIR = Path("d:/MJONAI/archive/scratch/angelone_1min_cache")  # scratch/ moved to repo-root archive/ 2026-09-03

START_DATE = "2026-08-14 09:15:00"
END_DATE = "2026-08-21 15:30:00"
INITIAL_CAPITAL = 100000.0  # ₹1,00,000 (1 Lakh)


def stop_loss_func(df, signal_index, entry_price, direction):
    # 1.8% Stop Loss
    return round(entry_price * 0.982 if direction == "LONG" else entry_price * 1.018, 2)


def target_func(entry_price, stop_loss, direction):
    # 1:2.5 Reward-to-Risk Target
    risk = abs(entry_price - stop_loss)
    return round(entry_price + (risk * 2.5) if direction == "LONG" else entry_price - (risk * 2.5), 2)


def load_parquet_universe() -> dict[str, pd.DataFrame]:
    data = {}
    parquet_files = sorted(list(CACHE_DIR.glob("*_1min_30d.parquet")))

    for f in parquet_files:
        sym = f.stem.split("_1min_")[0]
        if sym in ["NIFTY", "BANKNIFTY"]:
            continue
        try:
            df = pd.read_parquet(f)
            idx = df.index if isinstance(df.index, pd.DatetimeIndex) else pd.to_datetime(df["timestamp"])
            if idx.tz is not None:
                df.index = idx.tz_convert("Asia/Kolkata").tz_localize(None)
            else:
                df.index = pd.to_datetime(idx)

            # Warm-up from July 20 to Aug 21
            mask = (df.index >= "2026-07-20") & (df.index <= "2026-08-21 15:30:00")
            df_sub = df[mask]
            if len(df_sub) >= 2000:
                df_15m = df_sub.resample("15min").agg({
                    "Open": "first",
                    "High": "max",
                    "Low": "min",
                    "Close": "last",
                    "Volume": "sum"
                }).dropna()

                if len(df_15m) >= 250:
                    data[sym] = df_15m
        except Exception:
            pass

    return data


def run_official_system():
    print("=" * 95, flush=True)
    print("🏛️ MJONAI OFFICIAL SYSTEM BACKTEST (REGISTRY STRATEGIES + BACKTEST ENGINE + ANALYTICS)", flush=True)
    print(f"   Starting Capital: ₹{INITIAL_CAPITAL:,.2f} (1 Lakh) | Testing Period: {START_DATE} to {END_DATE}", flush=True)
    print("=" * 95, flush=True)

    universe = load_parquet_universe()
    print(f"📊 Loaded {len(universe)} Liquid Equities with complete 15-Minute history (250+ bars).", flush=True)

    strategy_ids = [
        "S01_MomentumRSI",
        "S02_MeanReversion",
        "S04_BollingerSqueeze",
    ]

    backtest_engine = BacktestEngine(initial_capital=INITIAL_CAPITAL)
    analytics = PerformanceAnalyzer()

    all_trades = []
    strategy_trade_counts = {}

    for strat_id in strategy_ids:
        strategy_trade_counts[strat_id] = 0
        print(f"\n⏳ Running Strategy Engine: {strat_id} across {len(universe)} equities...", flush=True)
        try:
            adapter = load_registry_strategy(strat_id)
            runner = StrategyRunner(adapter)

            strat_trades = []
            for sym, df in universe.items():
                adapter.symbol = sym

                # Generate signals through official StrategyRunner
                signals = runner.run(sym, df)

                # Filter signals strictly inside the 14-21 August testing window
                test_signals = [s for s in signals if df.index[s.index] >= pd.to_datetime(START_DATE)]

                if not test_signals:
                    continue

                # Execute via official BacktestEngine
                trades = backtest_engine.run(
                    strategy=adapter,
                    symbol=sym,
                    df=df,
                    signals=test_signals,
                    stop_loss_func=stop_loss_func,
                    target_func=target_func,
                    max_holding_bars=24,  # 24 15-min bars = 1.5 trading days
                )

                if trades:
                    strat_trades.extend(trades)

            strategy_trade_counts[strat_id] = len(strat_trades)
            all_trades.extend(strat_trades)
            print(f"  ✅ {strat_id}: Generated {len(strat_trades)} executed trades.", flush=True)
        except Exception as e:
            print(f"  ❌ Error testing {strat_id}: {e}", flush=True)

    # Analyze via official PerformanceAnalyzer
    report = analytics.analyze(all_trades, initial_capital=INITIAL_CAPITAL)

    print("\n" + "═" * 95, flush=True)
    print("🏆 OFFICIAL MJONAI PERFORMANCE AUDIT (₹1 LAKH CAPITAL)", flush=True)
    print("═" * 95, flush=True)

    print("\n📈 Strategy Contribution Breakdown:", flush=True)
    for s_name, count in strategy_trade_counts.items():
        print(f"  • {s_name:<25}: {count:>3} trades executed", flush=True)

    t_stats = report.trade
    e_stats = report.equity
    p_stats = report.performance

    net_profit = e_stats.final_capital - e_stats.initial_capital
    print(f"""
📊 <b>OFFICIAL PRODUCTION SYSTEM AUDIT (₹1 LAKH CAPITAL)</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>Starting Capital:</b>            ₹{e_stats.initial_capital:,.2f} (1 Lakh)
💰 <b>Ending Capital:</b>              ₹{e_stats.final_capital:,.2f}
📈 <b>Total Net Realized PnL:</b>      {('🟢 +' if net_profit >= 0 else '🔴 -')}₹{abs(net_profit):,.2f} ({e_stats.total_return_pct:+.2f}%)
🎯 <b>Total System Trades Taken:</b>   {t_stats.total_trades}
🏆 <b>Win Rate:</b>                     {t_stats.win_rate_pct:.1f}% ({t_stats.winning_trades} Wins / {t_stats.losing_trades} Losses)
⚖️ <b>Profit Factor:</b>                {t_stats.profit_factor:.2f}
🛡️ <b>Max Drawdown:</b>                 {e_stats.max_drawdown_pct:.2f}%
📊 <b>Expectancy per Trade:</b>         {t_stats.expectancy:+.2f}%
⚡ <b>Payoff Ratio (Win/Loss):</b>      {t_stats.payoff_ratio:.2f}x

📋 <b>Official System Trade Journal (First 25 Trades):</b>
""", flush=True)
    for i, t in enumerate(all_trades[:25], 1):
        status_icon = "🟢" if t.net_pnl > 0 else "🔴"
        pnl_pct = (t.net_pnl / (t.entry_price * t.quantity)) * 100 if (t.entry_price * t.quantity) > 0 else 0.0
        print(f"{i:2d}. {status_icon} {t.symbol:<12} ({t.strategy:<18}) | Entry: {str(t.entry_date)[:16]} @ ₹{t.entry_price:<8.2f} | Exit: {str(t.exit_date)[:16]} @ ₹{t.exit_price:<8.2f} | Net: ₹{t.net_pnl:+7.2f} ({pnl_pct:+5.2f}%) | Reason: {t.exit_reason}", flush=True)
    print("═" * 95, flush=True)


if __name__ == "__main__":
    run_official_system()
