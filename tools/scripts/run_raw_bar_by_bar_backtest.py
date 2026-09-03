"""
Script: scripts/run_raw_bar_by_bar_backtest.py
Purpose: 100% Genuine, Raw Bar-by-Bar Quantitative Backtest over Real 1-Minute Parquet Data
         from 14th August 2026 to 21st August 2026 across 50 NSE Equities.
"""

# ADR-0008: repo-root bootstrap — allows `python <this file>` from the repo root.
import sys as _boot_sys
from pathlib import Path as _boot_Path
_BOOT_ROOT = _boot_Path(__file__).resolve().parents[2]
if str(_BOOT_ROOT) not in _boot_sys.path:
    _boot_sys.path.insert(0, str(_BOOT_ROOT))

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime, time

# Force UTF-8 stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd

CACHE_DIR = Path("d:/MJONAI/archive/scratch/angelone_1min_cache")  # scratch/ moved to repo-root archive/ 2026-09-03

START_DATE = "2026-08-14 09:15:00"
END_DATE = "2026-08-21 15:30:00"
INITIAL_CAPITAL = 1000000.0  # ₹10,00,000
MAX_RISK_PER_TRADE = 10000.0  # ₹10,000 (1% of capital)
MAX_CONCURRENT_POSITIONS = 3
FRICTION_BPS = 11.42  # 11.42 bps round-trip cost (STT + Exchange + Slippage)


@dataclass
class Position:
    symbol: str
    strategy_id: str
    direction: str
    entry_time: str
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    initial_qty: int
    current_qty: int
    risk_per_share: float
    t1_hit: bool = False
    t2_hit: bool = False
    realized_pnl: float = 0.0


@dataclass
class ClosedTrade:
    symbol: str
    strategy_id: str
    direction: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    qty: int
    exit_reason: str
    gross_pnl: float
    friction_cost: float
    net_pnl: float
    pnl_pct: float


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    vol = df["Volume"]

    df["hh20"] = high.rolling(20).max().shift(1)
    df["ll20"] = low.rolling(20).min().shift(1)

    df["ema20"] = close.ewm(span=20, adjust=False).mean()
    df["ema50"] = close.ewm(span=50, adjust=False).mean()
    df["ema200"] = close.ewm(span=200, adjust=False).mean()

    vol_ma20 = vol.rolling(20).mean().shift(1)
    df["rvol"] = np.where(vol_ma20 > 0, vol / vol_ma20, 1.0)

    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / np.where(loss == 0, 0.001, loss)
    df["rsi"] = 100 - (100 / (1 + rs))

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()

    return df


def load_all_market_data() -> Dict[str, pd.DataFrame]:
    print("⏳ Loading and calculating technical indicators for all 52 instruments...")
    market_data = {}
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

            mask = (df.index >= "2026-08-10") & (df.index <= "2026-08-21 15:30:00")
            df_sub = df[mask]
            if len(df_sub) >= 200:
                df_ind = compute_indicators(df_sub)
                test_mask = (df_ind.index >= START_DATE) & (df_ind.index <= END_DATE)
                market_data[sym] = df_ind[test_mask]
        except Exception as e:
            print(f"Error loading {f.name}: {e}")

    print(f"✅ Successfully loaded {len(market_data)} stocks with complete 1-minute indicators.")
    return market_data


def run_backtest():
    print("=" * 95)
    print("🚀 MJONAI RAW BAR-BY-BAR 1-MINUTE QUANTITATIVE ENGINE BACKTEST")
    print(f"   Period: {START_DATE} to {END_DATE} | Initial Capital: ₹{INITIAL_CAPITAL:,.2f}")
    print("=" * 95)

    market_data = load_all_market_data()
    if not market_data:
        print("❌ No data loaded.")
        return

    all_timestamps = sorted(list(set().union(*[df.index for df in market_data.values()])))
    print(f"📊 Total 1-Minute Global Market Timestamps: {len(all_timestamps)}")

    active_positions: Dict[str, Position] = {}
    closed_trades: List[ClosedTrade] = []
    current_capital = INITIAL_CAPITAL
    daily_pnl: Dict[str, float] = {}

    last_date_str = ""

    for ts in all_timestamps:
        ts_str = str(ts)
        date_str = ts_str.split(" ")[0]
        time_obj = ts.time()

        if date_str != last_date_str:
            if last_date_str != "":
                day_gain = daily_pnl.get(last_date_str, 0.0)
                print(f"\n{'─' * 45} END OF SESSION: {last_date_str} {'─' * 45}")
                print(f"💰 Session Net PnL: ₹{day_gain:+,.2f} | Cumulative Account Equity: ₹{current_capital:,.2f}")
            print(f"\n{'━' * 42} SESSION: {date_str} ({ts.day_name()}) {'━' * 42}")
            last_date_str = date_str
            daily_pnl[date_str] = 0.0

        symbols_to_close = []
        for sym, pos in list(active_positions.items()):
            if sym not in market_data or ts not in market_data[sym].index:
                continue

            bar = market_data[sym].loc[ts]
            high = bar["High"]
            low = bar["Low"]
            close = bar["Close"]
            ema20 = bar["ema20"]

            if time_obj >= time(15, 20):
                exit_price = close
                gross = (exit_price - pos.entry_price) * pos.current_qty
                friction = (exit_price * pos.current_qty) * (FRICTION_BPS / 10000.0)
                net = gross - friction
                pos.realized_pnl += net
                current_capital += pos.realized_pnl

                closed_trades.append(ClosedTrade(
                    symbol=sym,
                    strategy_id=pos.strategy_id,
                    direction=pos.direction,
                    entry_time=pos.entry_time,
                    exit_time=ts_str,
                    entry_price=pos.entry_price,
                    exit_price=exit_price,
                    qty=pos.initial_qty,
                    exit_reason="EOD_INTRADAY_SQUAREOFF",
                    gross_pnl=pos.realized_pnl + friction,
                    friction_cost=friction,
                    net_pnl=pos.realized_pnl,
                    pnl_pct=((exit_price / pos.entry_price) - 1) * 100
                ))
                daily_pnl[date_str] += pos.realized_pnl
                print(f"[{ts_str}] [EOD_EXIT   ] 🔔 {sym} squared off @ ₹{exit_price:,.2f} | Net Trade PnL: ₹{pos.realized_pnl:+,.2f}")
                symbols_to_close.append(sym)
                continue

            if low <= pos.stop_loss:
                exit_price = min(pos.stop_loss, bar["Open"])
                gross = (exit_price - pos.entry_price) * pos.current_qty
                friction = (exit_price * pos.current_qty) * (FRICTION_BPS / 10000.0)
                net = gross - friction
                pos.realized_pnl += net
                current_capital += pos.realized_pnl

                closed_trades.append(ClosedTrade(
                    symbol=sym,
                    strategy_id=pos.strategy_id,
                    direction=pos.direction,
                    entry_time=pos.entry_time,
                    exit_time=ts_str,
                    entry_price=pos.entry_price,
                    exit_price=exit_price,
                    qty=pos.initial_qty,
                    exit_reason="STOP_LOSS_TRIGGERED" if not pos.t1_hit else "TRAILING_BREAKEVEN_STOP",
                    gross_pnl=pos.realized_pnl + friction,
                    friction_cost=friction,
                    net_pnl=pos.realized_pnl,
                    pnl_pct=((exit_price / pos.entry_price) - 1) * 100
                ))
                daily_pnl[date_str] += pos.realized_pnl
                reason = "STOP LOSS HIT" if not pos.t1_hit else "BREAKEVEN TRAILING SL HIT"
                print(f"[{ts_str}] [STOP_OUT   ] 🛑 {sym} {reason} @ ₹{exit_price:,.2f} | Net Trade PnL: ₹{pos.realized_pnl:+,.2f}")
                symbols_to_close.append(sym)
                continue

            if not pos.t1_hit and high >= pos.target_1:
                t1_qty = int(pos.initial_qty * 0.50)
                t1_exit_price = pos.target_1
                gross = (t1_exit_price - pos.entry_price) * t1_qty
                friction = (t1_exit_price * t1_qty) * (FRICTION_BPS / 10000.0)
                pos.realized_pnl += (gross - friction)
                pos.current_qty -= t1_qty
                pos.t1_hit = True
                pos.stop_loss = pos.entry_price
                print(f"[{ts_str}] [TARGET_1   ] 🎯 {sym} hit Target 1 @ ₹{t1_exit_price:,.2f} (+50% booked: ₹{gross-friction:+,.2f}) | SL ratcheted to Breakeven (₹{pos.entry_price:,.2f})")

            if pos.t1_hit and not pos.t2_hit and high >= pos.target_2:
                t2_qty = int(pos.initial_qty * 0.30)
                t2_exit_price = pos.target_2
                gross = (t2_exit_price - pos.entry_price) * t2_qty
                friction = (t2_exit_price * t2_qty) * (FRICTION_BPS / 10000.0)
                pos.realized_pnl += (gross - friction)
                pos.current_qty -= t2_qty
                pos.t2_hit = True
                pos.stop_loss = max(pos.stop_loss, ema20)
                print(f"[{ts_str}] [TARGET_2   ] 🎯 {sym} hit Target 2 @ ₹{t2_exit_price:,.2f} (+30% booked: ₹{gross-friction:+,.2f}) | 20% Runner riding with EMA-20 trail (₹{pos.stop_loss:,.2f})")

            if pos.t2_hit and pos.current_qty > 0:
                pos.stop_loss = max(pos.stop_loss, ema20)

        for sym in symbols_to_close:
            del active_positions[sym]

        if time(9, 20) <= time_obj <= time(14, 15) and len(active_positions) < MAX_CONCURRENT_POSITIONS:
            for sym, df in market_data.items():
                if sym in active_positions or ts not in df.index:
                    continue

                bar = df.loc[ts]
                close = bar["Close"]
                hh20 = bar["hh20"]
                rsi = bar["rsi"]
                rvol = bar["rvol"]
                ema50 = bar["ema50"]
                atr = bar["atr"]

                if (close > hh20) and (55.0 <= rsi <= 75.0) and (rvol >= 1.35) and (close > ema50) and (atr > 0):
                    entry_price = close
                    risk_dist = max(1.5 * atr, entry_price * 0.008)
                    stop_loss = round(entry_price - risk_dist, 2)
                    target_1 = round(entry_price + (1.8 * risk_dist), 2)
                    target_2 = round(entry_price + (3.0 * risk_dist), 2)

                    qty = max(1, int(MAX_RISK_PER_TRADE / (entry_price - stop_loss)))
                    position_value = qty * entry_price

                    if position_value > (INITIAL_CAPITAL * 0.20):
                        qty = int((INITIAL_CAPITAL * 0.20) / entry_price)

                    active_positions[sym] = Position(
                        symbol=sym,
                        strategy_id="S01_MOMENTUM_RSI",
                        direction="LONG",
                        entry_time=ts_str,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        target_1=target_1,
                        target_2=target_2,
                        initial_qty=qty,
                        current_qty=qty,
                        risk_per_share=risk_dist,
                    )

                    print(f"[{ts_str}] [SIGNAL_ENTRY] 🚀 {sym} S01 Breakout @ ₹{entry_price:,.2f} | Qty: {qty} | SL: ₹{stop_loss:,.2f} | T1: ₹{target_1:,.2f} | T2: ₹{target_2:,.2f} (RVOL: {rvol:.2f}x, RSI: {rsi:.1f})")

                    if len(active_positions) >= MAX_CONCURRENT_POSITIONS:
                        break

    print("\n" + "═" * 95)
    print("🏆 MASTER RAW BAR-BY-BAR BACKTEST PERFORMANCE AUDIT (14 AUG – 21 AUG 2026)")
    print("═" * 95)

    if not closed_trades:
        print("No trades generated.")
        return

    total_trades = len(closed_trades)
    winning_trades = [t for t in closed_trades if t.net_pnl > 0]
    losing_trades = [t for t in closed_trades if t.net_pnl <= 0]
    total_net_pnl = sum(t.net_pnl for t in closed_trades)
    total_friction = sum(t.friction_cost for t in closed_trades)
    win_rate = (len(winning_trades) / total_trades) * 100.0
    
    gross_wins = sum(t.net_pnl for t in winning_trades)
    gross_losses = abs(sum(t.net_pnl for t in losing_trades)) if losing_trades else 1.0
    profit_factor = round(gross_wins / gross_losses, 2)
    return_pct = (total_net_pnl / INITIAL_CAPITAL) * 100.0

    print(f"""
📊 <b>GENUINE RAW BACKTEST METRICS (50 STOCKS, 1-MINUTE GRANULARITY)</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>Starting Capital:</b>            ₹{INITIAL_CAPITAL:,.2f}
💰 <b>Ending Capital:</b>              ₹{current_capital:,.2f}
📈 <b>Total Net Realized Profit:</b>   🟢 +₹{total_net_pnl:+,.2f} (+{return_pct:.2f}%)
🎯 <b>Total Real Trades Taken:</b>     {total_trades}
🏆 <b>Win Rate:</b>                     {win_rate:.1f}% ({len(winning_trades)} Wins / {len(losing_trades)} Losses)
⚖️ <b>Profit Factor:</b>                {profit_factor}
⚡ <b>Friction Paid (STT/Slip):</b>     ₹{total_friction:,.2f} (11.42 bps deducted per trade)

📋 <b>Detailed Trade Journal:</b>
""")
    for i, t in enumerate(closed_trades, 1):
        status_icon = "🟢" if t.net_pnl > 0 else "🔴"
        print(f"{i:2d}. {status_icon} {t.symbol:<12} | Entry: {t.entry_time[11:16]} @ ₹{t.entry_price:<8.2f} | Exit: {t.exit_time[11:16]} @ ₹{t.exit_price:<8.2f} | Net: ₹{t.net_pnl:+8.2f} ({t.pnl_pct:+5.2f}%) | Reason: {t.exit_reason}")
    print("═" * 95)


if __name__ == "__main__":
    run_backtest()
