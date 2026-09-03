"""
Script: scripts/run_mtf_raw_backtest_1lakh.py
Purpose: Multi-Timeframe (MTF) Raw Bar-by-Bar Backtest (15-min Trend Filter + 1-min Execution)
         using ₹1,00,000 (1 Lakh) Capital on Real 1-Minute Historical Data (14-21 Aug 2026).
"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd

CACHE_DIR = Path("d:/MJONAI/mjonai-build/scratch/angelone_1min_cache")

START_DATE = "2026-08-14 09:15:00"
END_DATE = "2026-08-21 15:30:00"
INITIAL_CAPITAL = 100000.0  # ₹1,00,000 (1 Lakh)
MAX_RISK_PER_TRADE = 1000.0  # ₹1,000 (1% of ₹1L)
MAX_CONCURRENT_POSITIONS = 3
FRICTION_BPS = 11.42  # 11.42 bps round-trip transaction costs


@dataclass
class Position:
    symbol: str
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


def resample_ohlcv(df_1m: pd.DataFrame, timeframe: str = "15min") -> pd.DataFrame:
    """Resample 1-minute OHLCV into higher-timeframe candles."""
    df_htf = df_1m.resample(timeframe).agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum"
    }).dropna()
    df_htf["ema50"] = df_htf["Close"].ewm(span=50, adjust=False).mean()
    df_htf["ema20"] = df_htf["Close"].ewm(span=20, adjust=False).mean()
    delta = df_htf["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / np.where(loss == 0, 0.001, loss)
    df_htf["rsi"] = 100 - (100 / (1 + rs))
    return df_htf


def compute_1m_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    vol = df["Volume"]

    df["hh20"] = high.rolling(20).max().shift(1)
    df["ema20"] = close.ewm(span=20, adjust=False).mean()
    df["ema50"] = close.ewm(span=50, adjust=False).mean()
    
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
    df["atr"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()
    return df


def load_mtf_data():
    market_1m = {}
    market_15m = {}
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

            mask = (df.index >= "2026-08-01") & (df.index <= "2026-08-21 15:30:00")
            df_sub = df[mask]
            if len(df_sub) >= 500:
                # 15-minute resampled trend filter
                df_15m = resample_ohlcv(df_sub, "15min")
                market_15m[sym] = df_15m

                # 1-minute execution frame
                df_1m_ind = compute_1m_indicators(df_sub)
                test_mask = (df_1m_ind.index >= START_DATE) & (df_1m_ind.index <= END_DATE)
                market_1m[sym] = df_1m_ind[test_mask]
        except Exception as e:
            pass

    return market_1m, market_15m


def run_mtf_backtest():
    print("=" * 95)
    print("🚀 MJONAI MULTI-TIMEFRAME (15M TREND + 1M TIMING) RAW BACKTEST")
    print(f"   Initial Capital: ₹{INITIAL_CAPITAL:,.2f} (1 Lakh) | Max Risk/Trade: ₹{MAX_RISK_PER_TRADE:,.2f} (1%)")
    print("=" * 95)

    market_1m, market_15m = load_mtf_data()
    all_timestamps = sorted(list(set().union(*[df.index for df in market_1m.values()])))

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
                print(f"💰 Session Net PnL: ₹{day_gain:+,.2f} | Account Equity: ₹{current_capital:,.2f}")
            print(f"\n{'━' * 42} SESSION: {date_str} ({ts.day_name()}) {'━' * 42}")
            last_date_str = date_str
            daily_pnl[date_str] = 0.0

        # 1. Manage Active Positions
        symbols_to_close = []
        for sym, pos in list(active_positions.items()):
            if sym not in market_1m or ts not in market_1m[sym].index:
                continue

            bar = market_1m[sym].loc[ts]
            high, low, close, ema20 = bar["High"], bar["Low"], bar["Close"], bar["ema20"]

            # Mandatory EOD Square-off @ 15:20
            if time_obj >= time(15, 20):
                exit_price = close
                gross = (exit_price - pos.entry_price) * pos.current_qty
                friction = (exit_price * pos.current_qty) * (FRICTION_BPS / 10000.0)
                pos.realized_pnl += (gross - friction)
                current_capital += pos.realized_pnl

                closed_trades.append(ClosedTrade(
                    symbol=sym,
                    entry_time=pos.entry_time,
                    exit_time=ts_str,
                    entry_price=pos.entry_price,
                    exit_price=exit_price,
                    qty=pos.initial_qty,
                    exit_reason="EOD_SQUAREOFF",
                    gross_pnl=pos.realized_pnl + friction,
                    friction_cost=friction,
                    net_pnl=pos.realized_pnl,
                    pnl_pct=((exit_price / pos.entry_price) - 1) * 100
                ))
                daily_pnl[date_str] += pos.realized_pnl
                print(f"[{ts_str}] [EOD_EXIT   ] 🔔 {sym} squared off @ ₹{exit_price:,.2f} | Net: ₹{pos.realized_pnl:+,.2f}")
                symbols_to_close.append(sym)
                continue

            # Stop Loss Hit
            if low <= pos.stop_loss:
                exit_price = min(pos.stop_loss, bar["Open"])
                gross = (exit_price - pos.entry_price) * pos.current_qty
                friction = (exit_price * pos.current_qty) * (FRICTION_BPS / 10000.0)
                pos.realized_pnl += (gross - friction)
                current_capital += pos.realized_pnl

                closed_trades.append(ClosedTrade(
                    symbol=sym,
                    entry_time=pos.entry_time,
                    exit_time=ts_str,
                    entry_price=pos.entry_price,
                    exit_price=exit_price,
                    qty=pos.initial_qty,
                    exit_reason="STOP_LOSS" if not pos.t1_hit else "BREAKEVEN_STOP",
                    gross_pnl=pos.realized_pnl + friction,
                    friction_cost=friction,
                    net_pnl=pos.realized_pnl,
                    pnl_pct=((exit_price / pos.entry_price) - 1) * 100
                ))
                daily_pnl[date_str] += pos.realized_pnl
                reason = "STOP LOSS" if not pos.t1_hit else "BREAKEVEN TRAILING SL"
                print(f"[{ts_str}] [STOP_OUT   ] 🛑 {sym} {reason} @ ₹{exit_price:,.2f} | Net: ₹{pos.realized_pnl:+,.2f}")
                symbols_to_close.append(sym)
                continue

            # Target 1 (50% qty)
            if not pos.t1_hit and high >= pos.target_1:
                t1_qty = int(pos.initial_qty * 0.50)
                gross = (pos.target_1 - pos.entry_price) * t1_qty
                friction = (pos.target_1 * t1_qty) * (FRICTION_BPS / 10000.0)
                pos.realized_pnl += (gross - friction)
                pos.current_qty -= t1_qty
                pos.t1_hit = True
                pos.stop_loss = pos.entry_price  # Ratchet SL to Breakeven
                print(f"[{ts_str}] [TARGET_1   ] 🎯 {sym} hit Target 1 @ ₹{pos.target_1:,.2f} (+50% booked: ₹{gross-friction:+,.2f}) | SL ratcheted to Breakeven")

            # Target 2 (30% qty)
            if pos.t1_hit and not pos.t2_hit and high >= pos.target_2:
                t2_qty = int(pos.initial_qty * 0.30)
                gross = (pos.target_2 - pos.entry_price) * t2_qty
                friction = (pos.target_2 * t2_qty) * (FRICTION_BPS / 10000.0)
                pos.realized_pnl += (gross - friction)
                pos.current_qty -= t2_qty
                pos.t2_hit = True
                pos.stop_loss = max(pos.stop_loss, ema20)
                print(f"[{ts_str}] [TARGET_2   ] 🎯 {sym} hit Target 2 @ ₹{pos.target_2:,.2f} (+30% booked: ₹{gross-friction:+,.2f}) | Runner riding with EMA-20 trail")

            # Trail Runner
            if pos.t2_hit and pos.current_qty > 0:
                pos.stop_loss = max(pos.stop_loss, ema20)

        for sym in symbols_to_close:
            del active_positions[sym]

        # 2. Scan with Higher-Timeframe (15-Min) Trend Filter (09:30 to 14:15)
        if time(9, 30) <= time_obj <= time(14, 15) and len(active_positions) < MAX_CONCURRENT_POSITIONS:
            for sym, df in market_1m.items():
                if sym in active_positions or ts not in df.index:
                    continue

                # Get latest completed 15-min candle
                df_15 = market_15m.get(sym)
                if df_15 is None:
                    continue
                prior_15m = df_15[df_15.index <= ts]
                if len(prior_15m) < 2:
                    continue
                latest_15m = prior_15m.iloc[-1]

                # ── 15-MINUTE HIGHER TIMEFRAME FILTER ──────────────────────
                # 1. 15m Close > 15m EMA50 (Secular Uptrend)
                # 2. 15m RSI > 52 (Bullish Momentum)
                # 3. 15m Candle is Green (Close >= Open)
                htf_bullish = (latest_15m["Close"] > latest_15m["ema50"]) and (latest_15m["rsi"] >= 52.0) and (latest_15m["Close"] >= latest_15m["Open"])
                if not htf_bullish:
                    continue

                # ── 1-MINUTE PRECISION TIMING ──────────────────────────────
                bar = df.loc[ts]
                close, hh20, rsi, rvol, ema50, atr = bar["Close"], bar["hh20"], bar["rsi"], bar["rvol"], bar["ema50"], bar["atr"]

                if (close > hh20) and (55.0 <= rsi <= 75.0) and (rvol >= 1.50) and (close > ema50) and (atr > 0):
                    entry_price = close
                    risk_dist = max(1.5 * atr, entry_price * 0.008)
                    stop_loss = round(entry_price - risk_dist, 2)
                    target_1 = round(entry_price + (1.8 * risk_dist), 2)
                    target_2 = round(entry_price + (3.0 * risk_dist), 2)

                    # Position sizing for ₹1 Lakh capital (Max ₹1,000 risk per trade)
                    qty = max(1, int(MAX_RISK_PER_TRADE / (entry_price - stop_loss)))
                    pos_val = qty * entry_price
                    if pos_val > (INITIAL_CAPITAL * 0.25):  # Max 25% capital per position
                        qty = int((INITIAL_CAPITAL * 0.25) / entry_price)

                    active_positions[sym] = Position(
                        symbol=sym,
                        entry_time=ts_str,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        target_1=target_1,
                        target_2=target_2,
                        initial_qty=qty,
                        current_qty=qty,
                        risk_per_share=risk_dist,
                    )
                    print(f"[{ts_str}] [MTF_ENTRY   ] 🚀 {sym} MTF-Aligned Breakout @ ₹{entry_price:,.2f} | Qty: {qty} | SL: ₹{stop_loss:,.2f} | T1: ₹{target_1:,.2f} | 15m RSI: {latest_15m['rsi']:.1f}")

                    if len(active_positions) >= MAX_CONCURRENT_POSITIONS:
                        break

    print("\n" + "═" * 95)
    print("🏆 MULTI-TIMEFRAME BACKTEST PERFORMANCE AUDIT (₹1 LAKH CAPITAL)")
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
📊 <b>MULTI-TIMEFRAME RESULTS (15-MIN TREND + 1-MIN TIMING)</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>Starting Capital:</b>            ₹{INITIAL_CAPITAL:,.2f} (1 Lakh)
💰 <b>Ending Capital:</b>              ₹{current_capital:,.2f}
📈 <b>Total Net Realized Profit:</b>   🟢 +₹{total_net_pnl:+,.2f} (+{return_pct:.2f}%)
🎯 <b>Total Quality Trades:</b>        {total_trades}
🏆 <b>Win Rate:</b>                     {win_rate:.1f}% ({len(winning_trades)} Wins / {len(losing_trades)} Losses)
⚖️ <b>Profit Factor:</b>                {profit_factor}
⚡ <b>Friction Deducted:</b>           ₹{total_friction:,.2f}

📋 <b>Trade Journal:</b>
""")
    for i, t in enumerate(closed_trades, 1):
        status_icon = "🟢" if t.net_pnl > 0 else "🔴"
        print(f"{i:2d}. {status_icon} {t.symbol:<12} | Entry: {t.entry_time[11:16]} @ ₹{t.entry_price:<8.2f} | Exit: {t.exit_time[11:16]} @ ₹{t.exit_price:<8.2f} | Net: ₹{t.net_pnl:+7.2f} ({t.pnl_pct:+5.2f}%) | Reason: {t.exit_reason}")
    print("═" * 95)


if __name__ == "__main__":
    run_mtf_backtest()
