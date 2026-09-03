"""
Script: scripts/run_sept1_live_replay.py
Purpose: 100% Genuine, Raw Bar-by-Bar 1-Minute Simulation for TODAY (September 1st, 2026)
         using Calibrated Event-Based Strategies and ₹1,00,000 (1 Lakh) Capital.
"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import yfinance as yf
import numpy as np
import pandas as pd

INITIAL_CAPITAL = 100000.0  # ₹1,00,000 (1 Lakh)
MAX_RISK_PER_TRADE = 1000.0  # ₹1,000 (1% of ₹1L)
MAX_CONCURRENT_POSITIONS = 3
FRICTION_BPS = 11.42  # 11.42 bps statutory transaction costs

SYMBOLS = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LT.NS", "AXISBANK.NS",
    "TITAN.NS", "M&M.NS", "TATASTEEL.NS", "JSWSTEEL.NS", "BEL.NS",
    "NESTLEIND.NS", "COALINDIA.NS", "ONGC.NS", "BAJFINANCE.NS", "ASIANPAINT.NS",
    "HINDALCO.NS", "DIVISLAB.NS", "CIPLA.NS", "APOLLOHOSP.NS", "BPCL.NS"
]


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

    # Rolling 20-bar High/Low for breakouts
    df["hh20"] = high.rolling(20).max().shift(1)
    df["ll20"] = low.rolling(20).min().shift(1)

    # EMAs
    df["ema20"] = close.ewm(span=20, adjust=False).mean()
    df["ema50"] = close.ewm(span=50, adjust=False).mean()
    df["ema200"] = close.ewm(span=200, adjust=False).mean()

    # Bollinger Bands
    std20 = close.rolling(20).std()
    df["bb_upper"] = df["ema20"] + (2.0 * std20)
    df["bb_lower"] = df["ema20"] - (2.0 * std20)
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / (df["ema20"] + 1e-10)

    # Relative Volume (RVOL)
    vol_ma20 = vol.rolling(20).mean().shift(1)
    df["rvol"] = np.where(vol_ma20 > 0, vol / vol_ma20, 1.0)

    # RSI 14
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / np.where(loss == 0, 0.001, loss)
    df["rsi"] = 100 - (100 / (1 + rs))

    # RSI 2 (Connors)
    delta2 = close.diff()
    gain2 = (delta2.where(delta2 > 0, 0)).rolling(2).mean()
    loss2 = (-delta2.where(delta2 < 0, 0)).rolling(2).mean()
    rs2 = gain2 / np.where(loss2 == 0, 0.001, loss2)
    df["rsi2"] = 100 - (100 / (1 + rs2))

    # ATR 14
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    df["atr"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()

    return df


def load_sept1_data() -> Dict[str, pd.DataFrame]:
    print("⏳ Downloading and computing real 1-minute indicators for Sept 1st, 2026...", flush=True)
    market_data = {}
    for s in SYMBOLS:
        clean = s.replace(".NS", "")
        try:
            t = yf.Ticker(s)
            df = t.history(period="5d", interval="1m")
            if not df.empty:
                idx = df.index.tz_convert("Asia/Kolkata").tz_localize(None)
                df.index = idx
                df_ind = compute_indicators(df)
                # Filter specifically Sept 1st
                sept1_bars = df_ind[df_ind.index.strftime("%Y-%m-%d") == "2026-09-01"]
                if len(sept1_bars) >= 300:
                    market_data[clean] = sept1_bars
        except Exception:
            pass

    print(f"✅ Loaded {len(market_data)} stocks with complete 1-minute data for Sept 1st.", flush=True)
    return market_data


def run_sept1_simulation():
    print("=" * 95, flush=True)
    print("🚀 REAL 1-MINUTE BAR-BY-BAR REPLAY — SEPTEMBER 1ST, 2026")
    print(f"   Initial Capital: ₹{INITIAL_CAPITAL:,.2f} (1 Lakh) | Max Risk/Trade: ₹{MAX_RISK_PER_TRADE:,.2f} (1%)")
    print("=" * 95, flush=True)

    market_data = load_sept1_data()
    if not market_data:
        print("❌ No market data available for Sept 1st.")
        return

    all_timestamps = sorted(list(set().union(*[df.index for df in market_data.values()])))
    print(f"📊 Replaying {len(all_timestamps)} real 1-minute bars from {all_timestamps[0].strftime('%H:%M')} to {all_timestamps[-1].strftime('%H:%M')} IST...\n", flush=True)

    active_positions: Dict[str, Position] = {}
    closed_trades: List[ClosedTrade] = []
    current_capital = INITIAL_CAPITAL

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ LIVE SESSION: 2026-09-01 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", flush=True)

    for ts in all_timestamps:
        ts_str = str(ts)
        time_str = ts.strftime("%H:%M")
        time_obj = ts.time()

        # ── 1. MANAGE ACTIVE POSITIONS ──────────────────────────────────────────
        symbols_to_close = []
        for sym, pos in list(active_positions.items()):
            if sym not in market_data or ts not in market_data[sym].index:
                continue

            bar = market_data[sym].loc[ts]
            high, low, close, ema20 = bar["High"], bar["Low"], bar["Close"], bar["ema20"]

            # Mandatory EOD Square-off @ 15:15 IST
            if time_obj >= time(15, 15):
                exit_price = close
                gross = (exit_price - pos.entry_price) * pos.current_qty
                friction = (exit_price * pos.current_qty) * (FRICTION_BPS / 10000.0)
                pos.realized_pnl += (gross - friction)
                current_capital += pos.realized_pnl

                closed_trades.append(ClosedTrade(
                    symbol=sym,
                    strategy_id=pos.strategy_id,
                    direction=pos.direction,
                    entry_time=pos.entry_time,
                    exit_time=time_str,
                    entry_price=pos.entry_price,
                    exit_price=exit_price,
                    qty=pos.initial_qty,
                    exit_reason="EOD_SQUAREOFF",
                    gross_pnl=pos.realized_pnl + friction,
                    friction_cost=friction,
                    net_pnl=pos.realized_pnl,
                    pnl_pct=((exit_price / pos.entry_price) - 1) * 100
                ))
                print(f"[{time_str}] [EOD_EXIT   ] 🔔 {sym} squared off @ ₹{exit_price:,.2f} | Net Trade PnL: ₹{pos.realized_pnl:+,.2f}", flush=True)
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
                    direction=pos.direction,
                    entry_time=pos.entry_time,
                    exit_time=time_str,
                    entry_price=pos.entry_price,
                    exit_price=exit_price,
                    qty=pos.initial_qty,
                    exit_reason="STOP_LOSS" if not pos.t1_hit else "BREAKEVEN_STOP",
                    gross_pnl=pos.realized_pnl + friction,
                    friction_cost=friction,
                    net_pnl=pos.realized_pnl,
                    pnl_pct=((exit_price / pos.entry_price) - 1) * 100
                ))
                reason = "STOP LOSS HIT" if not pos.t1_hit else "BREAKEVEN TRAILING SL"
                print(f"[{time_str}] [STOP_OUT   ] 🛑 {sym} ({pos.strategy_id}) {reason} @ ₹{exit_price:,.2f} | Net Trade PnL: ₹{pos.realized_pnl:+,.2f}", flush=True)
                symbols_to_close.append(sym)
                continue

            # Tranche 1 Target (50% Qty)
            if not pos.t1_hit and high >= pos.target_1:
                t1_qty = int(pos.initial_qty * 0.50)
                gross = (pos.target_1 - pos.entry_price) * t1_qty
                friction = (pos.target_1 * t1_qty) * (FRICTION_BPS / 10000.0)
                pos.realized_pnl += (gross - friction)
                pos.current_qty -= t1_qty
                pos.t1_hit = True
                pos.stop_loss = pos.entry_price  # Move Stop Loss to Breakeven
                print(f"[{time_str}] [TARGET_1   ] 🎯 {sym} hit Target 1 @ ₹{pos.target_1:,.2f} (+50% booked: ₹{gross-friction:+,.2f}) | SL ratcheted to Breakeven (₹{pos.entry_price:,.2f})", flush=True)

            # Tranche 2 Target (30% Qty)
            if pos.t1_hit and not pos.t2_hit and high >= pos.target_2:
                t2_qty = int(pos.initial_qty * 0.30)
                gross = (pos.target_2 - pos.entry_price) * t2_qty
                friction = (pos.target_2 * t2_qty) * (FRICTION_BPS / 10000.0)
                pos.realized_pnl += (gross - friction)
                pos.current_qty -= t2_qty
                pos.t2_hit = True
                pos.stop_loss = max(pos.stop_loss, ema20)
                print(f"[{time_str}] [TARGET_2   ] 🎯 {sym} hit Target 2 @ ₹{pos.target_2:,.2f} (+30% booked: ₹{gross-friction:+,.2f}) | 20% Runner riding with EMA-20 trail (₹{pos.stop_loss:,.2f})", flush=True)

            # Manage 20% Runner
            if pos.t2_hit and pos.current_qty > 0:
                pos.stop_loss = max(pos.stop_loss, ema20)

        for sym in symbols_to_close:
            del active_positions[sym]

        # ── 2. SCAN FOR FRESH EVENT SIGNALS (09:30 to 14:15 IST) ────────────────────
        if time(9, 30) <= time_obj <= time(14, 15) and len(active_positions) < MAX_CONCURRENT_POSITIONS:
            for sym, df in market_data.items():
                if sym in active_positions or ts not in df.index:
                    continue

                idx_loc = df.index.get_loc(ts)
                if idx_loc < 20:
                    continue

                curr = df.iloc[idx_loc]
                prev = df.iloc[idx_loc - 1]

                close, high, low = curr["Close"], curr["High"], curr["Low"]
                hh20, ema20, ema50, ema200 = curr["hh20"], curr["ema20"], curr["ema50"], curr["ema200"]
                rsi, rsi2, rvol, atr = curr["rsi"], curr["rsi2"], curr["rvol"], curr["atr"]
                bb_up, bb_dn, bb_width = curr["bb_upper"], curr["bb_lower"], curr["bb_width"]

                if atr <= 0:
                    continue

                strat_triggered = None

                # ── STRATEGY 1: S01 FRESH 20-BAR RESISTANCE BREAKOUT ────────────────
                # Event Trigger: Prev bar below 20-bar high -> Current bar breaks above with volume
                if (prev["Close"] <= prev["hh20"]) and (close > hh20) and (55.0 <= rsi <= 75.0) and (rvol >= 1.50) and (close > ema50):
                    strat_triggered = "S01_MOMENTUM_RSI"
                    risk_dist = max(1.5 * atr, close * 0.008)
                    target_dist = 2.2 * risk_dist

                # ── STRATEGY 2: S02 MEAN REVERSION DIPS IN UPTREND ───────────────────
                elif (close > ema200) and (prev["rsi2"] <= 12.0) and (rsi2 > prev["rsi2"]) and (close > low):
                    strat_triggered = "S02_MEAN_REVERSION"
                    risk_dist = max(1.2 * atr, close * 0.007)
                    target_dist = 1.8 * risk_dist

                # ── STRATEGY 3: S04 FRESH BOLLINGER EXPANSION ────────────────────────
                elif (prev["Close"] <= prev["bb_upper"]) and (close > bb_up) and (bb_width > prev["bb_width"] * 1.05) and (rvol >= 1.60):
                    strat_triggered = "S04_BOLLINGER_SQUEEZE"
                    risk_dist = max(1.4 * atr, close * 0.008)
                    target_dist = 2.4 * risk_dist

                if strat_triggered:
                    entry_price = close
                    stop_loss = round(entry_price - risk_dist, 2)
                    target_1 = round(entry_price + target_dist, 2)
                    target_2 = round(entry_price + (1.6 * target_dist), 2)

                    # Position Sizing for ₹1 Lakh Capital (Max ₹1,000 Risk)
                    qty = max(1, int(MAX_RISK_PER_TRADE / (entry_price - stop_loss)))
                    pos_val = qty * entry_price
                    if pos_val > (INITIAL_CAPITAL * 0.25):  # Max 25% allocation
                        qty = int((INITIAL_CAPITAL * 0.25) / entry_price)

                    active_positions[sym] = Position(
                        symbol=sym,
                        strategy_id=strat_triggered,
                        direction="LONG",
                        entry_time=time_str,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        target_1=target_1,
                        target_2=target_2,
                        initial_qty=qty,
                        current_qty=qty,
                        risk_per_share=risk_dist,
                    )

                    print(f"[{time_str}] [SIGNAL_ENTRY] 🚀 {sym} ({strat_triggered}) @ ₹{entry_price:,.2f} | Qty: {qty} | SL: ₹{stop_loss:,.2f} | T1: ₹{target_1:,.2f} | RVOL: {rvol:.2f}x | RSI: {rsi:.1f}", flush=True)

                    if len(active_positions) >= MAX_CONCURRENT_POSITIONS:
                        break

    # ─────────────────────────────────────────────────────────────
    # MASTER DAY PERFORMANCE AUDIT
    # ─────────────────────────────────────────────────────────────
    print("\n" + "═" * 95, flush=True)
    print("🏆 MASTER SEPTEMBER 1ST, 2026 QUANTITATIVE PERFORMANCE AUDIT (₹1 LAKH CAPITAL)")
    print("═" * 95, flush=True)

    if not closed_trades:
        print("No trades generated today.")
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
📊 <b>GENUINE SEPTEMBER 1ST LIVE METRICS (₹1 LAKH CAPITAL)</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>Starting Capital:</b>            ₹{INITIAL_CAPITAL:,.2f} (1 Lakh)
💰 <b>Ending Capital:</b>              ₹{current_capital:,.2f}
📈 <b>Total Net Realized Profit:</b>   {('🟢 +' if total_net_pnl >= 0 else '🔴 -')}₹{abs(total_net_pnl):,.2f} ({return_pct:+.2f}%)
🎯 <b>Total Real Trades Taken:</b>     {total_trades}
🏆 <b>Win Rate:</b>                     {win_rate:.1f}% ({len(winning_trades)} Wins / {len(losing_trades)} Losses)
⚖️ <b>Profit Factor:</b>                {profit_factor}
⚡ <b>Friction Paid (STT/Slip):</b>     ₹{total_friction:,.2f} (11.42 bps deducted per trade)

📋 <b>September 1st Complete Trade Journal:</b>
""", flush=True)
    for i, t in enumerate(closed_trades, 1):
        status_icon = "🟢" if t.net_pnl > 0 else "🔴"
        print(f"{i:2d}. {status_icon} {t.symbol:<12} ({t.strategy_id:<21}) | Entry: {t.entry_time} @ ₹{t.entry_price:<8.2f} | Exit: {t.exit_time} @ ₹{t.exit_price:<8.2f} | Net: ₹{t.net_pnl:+7.2f} ({t.pnl_pct:+5.2f}%) | Reason: {t.exit_reason}", flush=True)
    print("═" * 95, flush=True)


if __name__ == "__main__":
    run_sept1_simulation()
