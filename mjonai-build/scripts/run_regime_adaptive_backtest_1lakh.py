"""
Script: scripts/run_regime_adaptive_backtest_1lakh.py
Purpose: Regime-Adaptive Multi-Strategy Backtest (S01 Momentum + S02 Mean Reversion + S04 Squeeze)
         on Real 1-Minute Parquet Data (14-21 Aug 2026) with ₹1,00,000 (1 Lakh) Capital.
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
INITIAL_CAPITAL = 100000.0  # ₹1,00,000
MAX_RISK_PER_TRADE = 1000.0  # ₹1,000 (1% of ₹1L)
MAX_CONCURRENT_POSITIONS = 3
FRICTION_BPS = 11.42


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
    close, high, low, vol = df["Close"], df["High"], df["Low"], df["Volume"]

    # 20-bar rolling highs/lows
    df["hh20"] = high.rolling(20).max().shift(1)
    df["ll20"] = low.rolling(20).min().shift(1)

    # EMAs
    df["ema20"] = close.ewm(span=20, adjust=False).mean()
    df["ema50"] = close.ewm(span=50, adjust=False).mean()
    df["ema200"] = close.ewm(span=200, adjust=False).mean()

    # Bollinger Bands (20, 2.0)
    std20 = close.rolling(20).std()
    df["bb_upper"] = df["ema20"] + (2.0 * std20)
    df["bb_lower"] = df["ema20"] - (2.0 * std20)
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["ema20"]

    # Relative Volume
    vol_ma20 = vol.rolling(20).mean().shift(1)
    df["rvol"] = np.where(vol_ma20 > 0, vol / vol_ma20, 1.0)

    # 14-period RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / np.where(loss == 0, 0.001, loss)
    df["rsi"] = 100 - (100 / (1 + rs))

    # 2-period Connors RSI for Mean Reversion
    delta2 = close.diff()
    gain2 = (delta2.where(delta2 > 0, 0)).rolling(2).mean()
    loss2 = (-delta2.where(delta2 < 0, 0)).rolling(2).mean()
    rs2 = gain2 / np.where(loss2 == 0, 0.001, loss2)
    df["rsi2"] = 100 - (100 / (1 + rs2))

    # ATR
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    df["atr"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()

    return df


def load_all_data():
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

            mask = (df.index >= "2026-08-01") & (df.index <= "2026-08-21 15:30:00")
            df_sub = df[mask]
            if len(df_sub) >= 500:
                df_ind = compute_indicators(df_sub)
                test_mask = (df_ind.index >= START_DATE) & (df_ind.index <= END_DATE)
                market_data[sym] = df_ind[test_mask]
        except Exception:
            pass

    return market_data


def run_regime_backtest():
    print("=" * 95)
    print("🚀 MJONAI REGIME-ADAPTIVE BACKTEST (S01 MOMENTUM + S02 DIP BUYING + S04 SQUEEZE)")
    print(f"   Initial Capital: ₹{INITIAL_CAPITAL:,.2f} (1 Lakh) | Max Risk/Trade: ₹{MAX_RISK_PER_TRADE:,.2f} (1%)")
    print("=" * 95)

    market_data = load_all_data()
    all_timestamps = sorted(list(set().union(*[df.index for df in market_data.values()])))

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
            if sym not in market_data or ts not in market_data[sym].index:
                continue

            bar = market_data[sym].loc[ts]
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
                    strategy_id=pos.strategy_id,
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
                    strategy_id=pos.strategy_id,
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
                print(f"[{ts_str}] [STOP_OUT   ] 🛑 {sym} ({pos.strategy_id}) {reason} @ ₹{exit_price:,.2f} | Net: ₹{pos.realized_pnl:+,.2f}")
                symbols_to_close.append(sym)
                continue

            # Target 1 (50% Qty)
            if not pos.t1_hit and high >= pos.target_1:
                t1_qty = int(pos.initial_qty * 0.50)
                gross = (pos.target_1 - pos.entry_price) * t1_qty
                friction = (pos.target_1 * t1_qty) * (FRICTION_BPS / 10000.0)
                pos.realized_pnl += (gross - friction)
                pos.current_qty -= t1_qty
                pos.t1_hit = True
                pos.stop_loss = pos.entry_price  # Ratchet SL to Breakeven
                print(f"[{ts_str}] [TARGET_1   ] 🎯 {sym} ({pos.strategy_id}) hit Target 1 @ ₹{pos.target_1:,.2f} (+50% booked: ₹{gross-friction:+,.2f}) | SL ratcheted to Breakeven")

            # Target 2 (30% Qty)
            if pos.t1_hit and not pos.t2_hit and high >= pos.target_2:
                t2_qty = int(pos.initial_qty * 0.30)
                gross = (pos.target_2 - pos.entry_price) * t2_qty
                friction = (pos.target_2 * t2_qty) * (FRICTION_BPS / 10000.0)
                pos.realized_pnl += (gross - friction)
                pos.current_qty -= t2_qty
                pos.t2_hit = True
                pos.stop_loss = max(pos.stop_loss, ema20)
                print(f"[{ts_str}] [TARGET_2   ] 🎯 {sym} ({pos.strategy_id}) hit Target 2 @ ₹{pos.target_2:,.2f} (+30% booked: ₹{gross-friction:+,.2f})")

            # Manage Runner
            if pos.t2_hit and pos.current_qty > 0:
                pos.stop_loss = max(pos.stop_loss, ema20)

        for sym in symbols_to_close:
            del active_positions[sym]

        # 2. Multi-Strategy Scanner (09:30 to 14:15)
        if time(9, 30) <= time_obj <= time(14, 15) and len(active_positions) < MAX_CONCURRENT_POSITIONS:
            for sym, df in market_data.items():
                if sym in active_positions or ts not in df.index:
                    continue

                bar = df.loc[ts]
                close, high, low = bar["Close"], bar["High"], bar["Low"]
                hh20, ll20 = bar["hh20"], bar["ll20"]
                ema20, ema50, ema200 = bar["ema20"], bar["ema50"], bar["ema200"]
                rsi, rsi2, rvol, atr = bar["rsi"], bar["rsi2"], bar["rvol"], bar["atr"]
                bb_lower, bb_upper = bar["bb_lower"], bar["bb_upper"]

                if atr <= 0:
                    continue

                strat_triggered = None

                # ── STRATEGY 1: S02 MEAN REVERSION LONG (Dip Buying in Bull Trend) ──
                # Stock is above EMA200 (uptrend), but short-term oversold (RSI(2) < 15 or Close < Lower BB)
                if (close > ema200) and (rsi2 <= 15.0 or low <= bb_lower) and (close > low):
                    strat_triggered = "S02_MEAN_REVERSION"
                    risk_dist = max(1.2 * atr, close * 0.007)
                    target_dist = 1.6 * risk_dist

                # ── STRATEGY 2: S04 BOLLINGER SQUEEZE (Volatility Expansion) ────────
                elif (bar["bb_width"] < 0.015) and (close > bb_upper) and (rvol >= 1.80):
                    strat_triggered = "S04_BOLLINGER_SQUEEZE"
                    risk_dist = max(1.4 * atr, close * 0.008)
                    target_dist = 2.2 * risk_dist

                # ── STRATEGY 3: S01 MOMENTUM RSI (Strong High-Volume Trend Breakout) ─
                elif (close > hh20) and (58.0 <= rsi <= 72.0) and (rvol >= 2.00) and (close > ema50):
                    strat_triggered = "S01_MOMENTUM_RSI"
                    risk_dist = max(1.5 * atr, close * 0.008)
                    target_dist = 2.0 * risk_dist

                if strat_triggered:
                    entry_price = close
                    stop_loss = round(entry_price - risk_dist, 2)
                    target_1 = round(entry_price + target_dist, 2)
                    target_2 = round(entry_price + (1.6 * target_dist), 2)

                    qty = max(1, int(MAX_RISK_PER_TRADE / (entry_price - stop_loss)))
                    pos_val = qty * entry_price
                    if pos_val > (INITIAL_CAPITAL * 0.25):
                        qty = int((INITIAL_CAPITAL * 0.25) / entry_price)

                    active_positions[sym] = Position(
                        symbol=sym,
                        strategy_id=strat_triggered,
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
                    print(f"[{ts_str}] [ENTRY_{strat_triggered[:3]}] 🚀 {sym} @ ₹{entry_price:,.2f} | Qty: {qty} | SL: ₹{stop_loss:,.2f} | T1: ₹{target_1:,.2f} | RVOL: {rvol:.2f}x | RSI(2): {rsi2:.1f}")

                    if len(active_positions) >= MAX_CONCURRENT_POSITIONS:
                        break

    print("\n" + "═" * 95)
    print("🏆 REGIME-ADAPTIVE BACKTEST AUDIT (₹1 LAKH CAPITAL)")
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
📊 <b>REGIME-ADAPTIVE RESULTS (S01 + S02 + S04 ON ₹1 LAKH CAPITAL)</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>Starting Capital:</b>            ₹{INITIAL_CAPITAL:,.2f} (1 Lakh)
💰 <b>Ending Capital:</b>              ₹{current_capital:,.2f}
📈 <b>Total Net Realized Profit:</b>   🟢 +₹{total_net_pnl:+,.2f} (+{return_pct:.2f}%)
🎯 <b>Total Real Trades Taken:</b>     {total_trades}
🏆 <b>Win Rate:</b>                     {win_rate:.1f}% ({len(winning_trades)} Wins / {len(losing_trades)} Losses)
⚖️ <b>Profit Factor:</b>                {profit_factor}
⚡ <b>Friction Deducted:</b>           ₹{total_friction:,.2f}

📋 <b>Trade Journal:</b>
""")
    for i, t in enumerate(closed_trades, 1):
        status_icon = "🟢" if t.net_pnl > 0 else "🔴"
        print(f"{i:2d}. {status_icon} {t.symbol:<12} ({t.strategy_id:<21}) | Entry: {t.entry_time[11:16]} @ ₹{t.entry_price:<8.2f} | Exit: {t.exit_time[11:16]} @ ₹{t.exit_price:<8.2f} | Net: ₹{t.net_pnl:+7.2f} ({t.pnl_pct:+5.2f}%) | Reason: {t.exit_reason}")
    print("═" * 95)


if __name__ == "__main__":
    run_regime_backtest()
