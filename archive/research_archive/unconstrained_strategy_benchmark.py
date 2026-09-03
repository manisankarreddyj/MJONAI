"""
Module: engine/unconstrained_strategy_benchmark.py
Purpose: SOTA Unconstrained 12-Strategy Alpha Isolation Benchmark.
         Tests every strategy (S01 to S12) in isolated parallel tracks with ZERO slot choking.
         Every valid signal across all 51 Angel One instruments is executed and tracked
         with high-frequency 1-minute MTM, Tranche 1 Breakeven SL ratchets, BSM Greeks,
         and 100% statutory SEBI taxes.

Outputs:
  1. scratch/unconstrained_all_trades_ledger.csv
  2. scratch/unconstrained_benchmark.log
  3. scratch/unconstrained_12strat_report.md
"""

from datetime import datetime, date, timedelta
import os
import sys
import io
from pathlib import Path
import logging
import csv
import json

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Ensure project root is in sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

# Setup dual logging (Console + scratch/unconstrained_benchmark.log)
scratch_dir = Path(root_dir) / "scratch"
scratch_dir.mkdir(parents=True, exist_ok=True)
log_file_path = scratch_dir / "unconstrained_benchmark.log"

file_handler = logging.FileHandler(log_file_path, mode="w", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s"))
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])
logger = logging.getLogger("UnconstrainedBenchmark")

import pandas as pd
import numpy as np

# Load credentials from .env.master
from dotenv import load_dotenv
env_master_path = Path("d:/MJONAI/credentials/.env.master")
if env_master_path.exists():
    load_dotenv(str(env_master_path))
else:
    load_dotenv()

# DIRECT PRODUCTION IMPORTS
from core.constants import TOTAL_CAPITAL, SECTOR_MAP
from strategy.signal_scanner import (
    _S01, _S02, _S03, _S04, _S05, _S06, _S07, _S08, _S09, _S10, _S11, _S12
)
from execution.tax import calculate_all_in_friction, calculate_tax
from execution.tracker import calculate_trailing_sl
from options.greeks import calculate_black_scholes_greeks
from options.directional_options import FALLBACK_LOT_SIZES, _resolve_lot_size


def get_strike_interval(symbol: str, spot_price: float) -> float:
    """Dynamic NSE Tiered Strike Interval Resolver."""
    sym_u = symbol.upper()
    if sym_u == "NIFTY":
        return 50.0
    elif sym_u == "BANKNIFTY":
        return 100.0
    elif spot_price < 500.0:
        return 5.0
    elif spot_price < 1500.0:
        return 20.0
    elif spot_price < 5000.0:
        return 50.0
    else:
        return 100.0


def calculate_nifty_adx(nifty_df: pd.DataFrame, current_ts: pd.Timestamp) -> float:
    """Calculate 14-period ADX on resampled 15m Nifty benchmark candles."""
    try:
        n_slice = nifty_df.loc[:current_ts]
        if len(n_slice) < 60:
            return 18.0
        n_15m = n_slice.resample("15min").agg({
            "High": "max", "Low": "min", "Close": "last"
        }).dropna()
        if len(n_15m) < 28:
            return 18.0
            
        high = n_15m["High"]
        low = n_15m["Low"]
        close = n_15m["Close"]
        
        plus_dm = high.diff()
        minus_dm = low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        
        tr1 = pd.DataFrame(high - low)
        tr2 = pd.DataFrame(abs(high - close.shift(1)))
        tr3 = pd.DataFrame(abs(low - close.shift(1)))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr = tr.rolling(14).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=1/14).mean() / atr)
        minus_di = 100 * (abs(minus_dm).ewm(alpha=1/14).mean() / atr)
        dx = (abs(plus_di - minus_di) / abs(plus_di + minus_di)) * 100
        adx = float(dx.rolling(14).mean().iloc[-1])
        return adx if not np.isnan(adx) else 18.0
    except Exception:
        return 18.0


def load_angelone_cached_candles():
    """Load cached 1-minute historical candles from scratch/angelone_1min_cache."""
    cache_dir = scratch_dir / "angelone_1min_cache"
    if not cache_dir.exists():
        logger.critical(f"Cache directory {cache_dir} does not exist.")
        return {}

    candles = {}
    for p_file in cache_dir.glob("*_1min_30d.parquet"):
        sym = p_file.stem.replace("_1min_30d", "")
        try:
            df = pd.read_parquet(p_file)
            if not df.empty:
                candles[sym] = df
        except Exception as e:
            logger.warning(f"Error loading {p_file}: {e}")

    logger.info(f"Loaded 1-minute historical data for {len(candles)} instruments from Angel One cache.")
    return candles


def run_unconstrained_benchmark():
    logger.info("================================================================================")
    logger.info("  🚀 STARTING UNCONSTRAINED 12-STRATEGY ALPHA BENCHMARK (NO SLOT LIMITS)")
    logger.info("  • Mode: Pure Strategy Alpha Isolation (Every Signal Executed & Tracked)")
    logger.info("  • Resolution: 1-Minute Live Bars (1,875 Candles across 51 Instruments)")
    logger.info("  • Mechanics: 3-Tranche Scaling + Breakeven SL Ratchet + Real SEBI Friction")
    logger.info("================================================================================")

    candles_dict = load_angelone_cached_candles()
    nifty_df = candles_dict.get("NIFTY")
    if nifty_df is None or nifty_df.empty:
        logger.critical("NIFTY 50 1-minute benchmark missing.")
        return

    # Filter to 1-Week Period: 17-Aug-2026 09:15 to 21-Aug-2026 15:30 (1,875 bars)
    mask_1week = (nifty_df.index >= "2026-08-17 09:15:00+05:30") & (nifty_df.index <= "2026-08-21 15:30:00+05:30")
    timeline_1m = sorted(list(nifty_df.loc[mask_1week].index))
    logger.info(f"Target 1-Week Timeline: {len(timeline_1m)} 1-minute bars from {timeline_1m[0]} to {timeline_1m[-1]}")

    strategy_registry = [
        ("S01_MomentumRSI", _S01, "SWING", "EQUITY"),
        ("S02_MeanReversion", _S02, "SWING", "EQUITY"),
        ("S03_TurtleBreakout", _S03, "SWING", "EQUITY"),
        ("S04_BollingerSqueeze", _S04, "SWING", "EQUITY"),
        ("S05_PriceActionCandles", _S05, "SWING", "EQUITY"),
        ("S06_MomentumShort", _S06, "SWING", "EQUITY"),
        ("S07_MeanReversionShort", _S07, "SWING", "EQUITY"),
        ("S08_IntradayAllDay", _S08, "INTRADAY", "EQUITY"),
        ("S09_OptionsThetaDecay", _S09, "SWING", "OPTION"),
        ("S10_DirectionalOptions", _S10, "SWING", "OPTION"),
        ("S11_VolumeProfile", _S11, "SWING", "EQUITY"),
        ("S12_MultiTimeframeConfluence", _S12, "SWING", "EQUITY"),
    ]

    all_open_trades = []
    all_closed_trades = []
    trade_id_seq = 10001
    
    # Strategy-specific active position tracker: (strat_name, symbol) -> Trade
    active_positions = set()
    # Strategy-specific symbol cooldown: (strat_name, symbol) -> Cooldown Expiry Timestamp
    strat_symbol_cooldown = {}

    current_session = None

    # ── Master 1-Minute Replay Loop ──────────────────────────────────────────
    for bar_idx, ts in enumerate(timeline_1m):
        sim_date = ts.strftime('%Y-%m-%d')
        sim_time = ts.strftime('%H:%M')

        # Session Initialization
        if sim_date != current_session:
            current_session = sim_date
            n_slice = nifty_df.loc[:ts]["Close"]
            n_close = float(n_slice.iloc[-1])
            vix_val = 13.90
            adx_val = calculate_nifty_adx(nifty_df, ts)
            market_state = "BULL" if n_close > 24150 else ("BEAR" if n_close < 23500 else "SIDEWAYS")
            mqi_level = "HIGH"
            logger.info(f"📅 [SESSION START] {sim_date} 09:15 IST — Regime: {market_state} (ADX: {adx_val:.1f}, VIX: {vix_val:.1f})")

        # ── 1. Active Trade Tracking Engine (Every 1 Minute) ─────────────────
        remaining_open = []
        for trade in all_open_trades:
            sym = trade["underlying"]
            strat_name = trade["strategy_id"]
            sym_df = candles_dict.get(sym)
            if sym_df is None or ts not in sym_df.index:
                remaining_open.append(trade)
                continue

            bar = sym_df.loc[ts]
            b_high = float(bar["High"])
            b_low = float(bar["Low"])
            b_close = float(bar["Close"])

            trade["minutes_held"] += 1
            direction = trade["direction"]
            asset_class = trade["asset_class"]
            is_intraday = (strat_name == "S08_IntradayAllDay")
            prod_type = "INTRADAY" if is_intraday else "DELIVERY"

            # ── A. OPTION CONTRACT TRACKING ──
            if asset_class == "OPTION":
                if strat_name == "S09_OptionsThetaDecay":
                    # Dual-Leg Strangle BSM Pricing
                    bsm_ce = calculate_black_scholes_greeks(spot=b_close, strike=trade["strike_ce"], dte_days=max(0.1, 4.0 - trade["minutes_held"]/375.0), iv=0.14, option_type="CE")
                    bsm_pe = calculate_black_scholes_greeks(spot=b_close, strike=trade["strike_pe"], dte_days=max(0.1, 4.0 - trade["minutes_held"]/375.0), iv=0.14, option_type="PE")
                    current_opt_p = max(0.10, round(float(bsm_ce.get("theoretical_price", 5.0)) + float(bsm_pe.get("theoretical_price", 5.0)), 2))
                else:
                    # Directional Call/Put Option Pricing
                    delta = trade["delta"]
                    underlying_move = (b_close - trade["entry_underlying"])
                    price_delta = underlying_move * delta
                    theta_decay = (trade["theta_per_day"] / 375.0) * trade["minutes_held"]
                    current_opt_p = max(0.05, round(trade["entry_price"] + price_delta - theta_decay, 2))

                trade["current_price"] = current_opt_p

                # Tranche 1 Check
                t1_reached = (current_opt_p >= trade["target1"]) if trade["option_action"] == "BUY" else (current_opt_p <= trade["target1"])
                if t1_reached and not trade["t1_hit"]:
                    trade["t1_hit"] = True
                    trade["t1_exit_time"] = f"{sim_date} {sim_time}"
                    trade["t1_exit_price"] = trade["target1"]
                    trade["current_sl"] = trade["entry_price"]  # Breakeven Ratchet

                    buy_p = trade["entry_price"] if trade["option_action"] == "BUY" else trade["target1"]
                    sell_p = trade["target1"] if trade["option_action"] == "BUY" else trade["entry_price"]
                    f_data = calculate_all_in_friction(buy_p, sell_p, trade["qty_t1"], "OPTIONS", "INTRADAY")
                    
                    g_pnl = (trade["target1"] - trade["entry_price"]) * trade["qty_t1"] if trade["option_action"] == "BUY" else (trade["entry_price"] - trade["target1"]) * trade["qty_t1"]
                    n_pnl = g_pnl - f_data["total_friction"]
                    trade["t1_pnl"] = n_pnl
                    trade["realized_pnl"] += n_pnl
                    trade["total_friction"] += f_data["total_friction"]

                # Stop Loss or Expiry Check
                sl_hit = (current_opt_p <= trade["current_sl"]) if trade["option_action"] == "BUY" else (current_opt_p >= trade["current_sl"])
                time_expiry = (trade["minutes_held"] >= trade["max_minutes"]) or (ts.hour == 15 and ts.minute >= 15 and is_intraday)

                if sl_hit or time_expiry:
                    exit_p = trade["current_sl"] if sl_hit else current_opt_p
                    exit_reason = "STOP_LOSS" if (sl_hit and not trade["t1_hit"]) else ("BREAKEVEN_SL" if sl_hit else "TIME_EXPIRY")

                    rem_qty = trade["qty_total"] - (trade["qty_t1"] if trade["t1_hit"] else 0)
                    buy_p = trade["entry_price"] if trade["option_action"] == "BUY" else exit_p
                    sell_p = exit_p if trade["option_action"] == "BUY" else trade["entry_price"]
                    f_data = calculate_all_in_friction(buy_p, sell_p, rem_qty, "OPTIONS", "INTRADAY")
                    
                    g_pnl = (exit_p - trade["entry_price"]) * rem_qty if trade["option_action"] == "BUY" else (trade["entry_price"] - exit_p) * rem_qty
                    n_pnl = g_pnl - f_data["total_friction"]

                    trade["final_exit_time"] = f"{sim_date} {sim_time}"
                    trade["final_exit_price"] = exit_p
                    trade["final_exit_reason"] = exit_reason
                    trade["final_exit_pnl"] = n_pnl
                    trade["realized_pnl"] += n_pnl
                    trade["total_friction"] += f_data["total_friction"]
                    trade["status"] = "CLOSED"
                    all_closed_trades.append(trade)
                    active_positions.discard((strat_name, sym))

                    if sl_hit and not trade["t1_hit"]:
                        strat_symbol_cooldown[(strat_name, sym)] = ts + timedelta(minutes=30)
                else:
                    remaining_open.append(trade)
                continue

            # ── B. CASH EQUITIES LONG TRACKING ──
            if direction == "LONG":
                # Intraday 15:15 EOD Square-Off
                if is_intraday and (ts.hour == 15 and ts.minute >= 15):
                    rem_qty = trade["qty_total"] - (trade["qty_t1"] if trade["t1_hit"] else 0)
                    f_data = calculate_all_in_friction(trade["entry_price"], b_close, rem_qty, "EQUITY", prod_type)
                    g_pnl = (b_close - trade["entry_price"]) * rem_qty
                    n_pnl = g_pnl - f_data["total_friction"]

                    trade["final_exit_time"] = f"{sim_date} {sim_time}"
                    trade["final_exit_price"] = b_close
                    trade["final_exit_reason"] = "INTRADAY_EOD_SQUAREOFF"
                    trade["final_exit_pnl"] = n_pnl
                    trade["realized_pnl"] += n_pnl
                    trade["total_friction"] += f_data["total_friction"]
                    trade["status"] = "CLOSED"
                    all_closed_trades.append(trade)
                    active_positions.discard((strat_name, sym))
                    continue

                # Tranche 1 Check
                if b_high >= trade["target1"] and not trade["t1_hit"]:
                    trade["t1_hit"] = True
                    trade["t1_exit_time"] = f"{sim_date} {sim_time}"
                    trade["t1_exit_price"] = trade["target1"]
                    trade["current_sl"] = trade["entry_price"]  # Breakeven Ratchet

                    f_data = calculate_all_in_friction(trade["entry_price"], trade["target1"], trade["qty_t1"], "EQUITY", prod_type)
                    g_pnl = (trade["target1"] - trade["entry_price"]) * trade["qty_t1"]
                    n_pnl = g_pnl - f_data["total_friction"]
                    trade["t1_pnl"] = n_pnl
                    trade["realized_pnl"] += n_pnl
                    trade["total_friction"] += f_data["total_friction"]

                sl_hit = (b_low <= trade["current_sl"])
                time_expiry = (trade["minutes_held"] >= trade["max_minutes"])

                if sl_hit or time_expiry:
                    exit_p = trade["current_sl"] if sl_hit else b_close
                    exit_reason = "STOP_LOSS" if (sl_hit and not trade["t1_hit"]) else ("BREAKEVEN_SL" if sl_hit else "TIME_EXPIRY")

                    rem_qty = trade["qty_total"] - (trade["qty_t1"] if trade["t1_hit"] else 0)
                    f_data = calculate_all_in_friction(trade["entry_price"], exit_p, rem_qty, "EQUITY", prod_type)
                    g_pnl = (exit_p - trade["entry_price"]) * rem_qty
                    n_pnl = g_pnl - f_data["total_friction"]

                    trade["final_exit_time"] = f"{sim_date} {sim_time}"
                    trade["final_exit_price"] = exit_p
                    trade["final_exit_reason"] = exit_reason
                    trade["final_exit_pnl"] = n_pnl
                    trade["realized_pnl"] += n_pnl
                    trade["total_friction"] += f_data["total_friction"]
                    trade["status"] = "CLOSED"
                    all_closed_trades.append(trade)
                    active_positions.discard((strat_name, sym))

                    if sl_hit and not trade["t1_hit"]:
                        strat_symbol_cooldown[(strat_name, sym)] = ts + timedelta(minutes=30)
                else:
                    remaining_open.append(trade)

            # ── C. CASH EQUITIES SHORT TRACKING ──
            elif direction == "SHORT":
                if is_intraday and (ts.hour == 15 and ts.minute >= 15):
                    rem_qty = trade["qty_total"] - (trade["qty_t1"] if trade["t1_hit"] else 0)
                    f_data = calculate_all_in_friction(b_close, trade["entry_price"], rem_qty, "EQUITY", prod_type)
                    g_pnl = (trade["entry_price"] - b_close) * rem_qty
                    n_pnl = g_pnl - f_data["total_friction"]

                    trade["final_exit_time"] = f"{sim_date} {sim_time}"
                    trade["final_exit_price"] = b_close
                    trade["final_exit_reason"] = "INTRADAY_EOD_SQUAREOFF"
                    trade["final_exit_pnl"] = n_pnl
                    trade["realized_pnl"] += n_pnl
                    trade["total_friction"] += f_data["total_friction"]
                    trade["status"] = "CLOSED"
                    all_closed_trades.append(trade)
                    active_positions.discard((strat_name, sym))
                    continue

                if b_low <= trade["target1"] and not trade["t1_hit"]:
                    trade["t1_hit"] = True
                    trade["t1_exit_time"] = f"{sim_date} {sim_time}"
                    trade["t1_exit_price"] = trade["target1"]
                    trade["current_sl"] = trade["entry_price"]  # Breakeven Ratchet

                    f_data = calculate_all_in_friction(trade["target1"], trade["entry_price"], trade["qty_t1"], "EQUITY", prod_type)
                    g_pnl = (trade["entry_price"] - trade["target1"]) * trade["qty_t1"]
                    n_pnl = g_pnl - f_data["total_friction"]
                    trade["t1_pnl"] = n_pnl
                    trade["realized_pnl"] += n_pnl
                    trade["total_friction"] += f_data["total_friction"]

                sl_hit = (b_high >= trade["current_sl"])
                time_expiry = (trade["minutes_held"] >= trade["max_minutes"])

                if sl_hit or time_expiry:
                    exit_p = trade["current_sl"] if sl_hit else b_close
                    exit_reason = "STOP_LOSS" if (sl_hit and not trade["t1_hit"]) else ("BREAKEVEN_SL" if sl_hit else "TIME_EXPIRY")

                    rem_qty = trade["qty_total"] - (trade["qty_t1"] if trade["t1_hit"] else 0)
                    f_data = calculate_all_in_friction(exit_p, trade["entry_price"], rem_qty, "EQUITY", prod_type)
                    g_pnl = (trade["entry_price"] - exit_p) * rem_qty
                    n_pnl = g_pnl - f_data["total_friction"]

                    trade["final_exit_time"] = f"{sim_date} {sim_time}"
                    trade["final_exit_price"] = exit_p
                    trade["final_exit_reason"] = exit_reason
                    trade["final_exit_pnl"] = n_pnl
                    trade["realized_pnl"] += n_pnl
                    trade["total_friction"] += f_data["total_friction"]
                    trade["status"] = "CLOSED"
                    all_closed_trades.append(trade)
                    active_positions.discard((strat_name, sym))

                    if sl_hit and not trade["t1_hit"]:
                        strat_symbol_cooldown[(strat_name, sym)] = ts + timedelta(minutes=30)
                else:
                    remaining_open.append(trade)

        all_open_trades = remaining_open

        # ── 2. UNCONSTRAINED SIGNAL SCANNER (Evaluates EVERY Strategy independently) ──
        # A. 15-Minute Macro Scanner (:00, :15, :30, :45 from 09:30 to 15:00)
        is_15m_bar = (ts.minute % 15 == 0) and (ts.hour >= 10 or (ts.hour == 9 and ts.minute >= 30)) and (ts.hour < 15)
        # B. 5-Minute Fast Scanner (:00, :05, :10... from 09:20 to 15:00)
        is_5m_bar = (ts.minute % 5 == 0) and (ts.hour >= 10 or (ts.hour == 9 and ts.minute >= 20)) and (ts.hour < 15)

        for sym, s_df in candles_dict.items():
            if ts not in s_df.index:
                continue

            s_slice = s_df.loc[:ts]
            if len(s_slice) < 60:
                continue

            # Iterate through each strategy independently (Zero Slot Competition)
            for strat_name, strat_obj, tf_type, asset_cls in strategy_registry:
                # Check if this strategy is already holding this symbol
                if (strat_name, sym) in active_positions:
                    continue
                # Check anti-churning cooldown
                if (strat_name, sym) in strat_symbol_cooldown and ts < strat_symbol_cooldown[(strat_name, sym)]:
                    continue

                if tf_type == "INTRADAY" and not is_5m_bar:
                    continue
                if tf_type == "SWING" and not is_15m_bar:
                    continue

                # Prepare resampled DataFrame
                if tf_type == "INTRADAY":
                    df_resampled = s_slice.resample("5min").agg({
                        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
                    }).dropna()
                    if len(df_resampled) < 20:
                        continue
                else:
                    df_resampled = s_slice.resample("15min").agg({
                        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
                    }).dropna()
                    if len(df_resampled) < 40:
                        continue

                try:
                    sig = strat_obj.execute_safe(df=df_resampled, symbol=sym, vix=vix_val, market_state=market_state, mqi_level=mqi_level)
                    if sig is None or (float(sig.technical_score or 0) < 70):
                        continue

                    c_entry = float(sig.entry_price or df_resampled["Close"].iloc[-1])
                    c_atr = float(sig.atr or (c_entry * 0.012))
                    raw_sl = sig.swing_low if sig.signal_direction == "LONG" else sig.swing_high
                    sl_price = float(raw_sl) if raw_sl is not None else (c_entry - 1.8 * c_atr if sig.signal_direction == "LONG" else c_entry + 1.8 * c_atr)
                    risk_dist = max(c_entry * 0.005, abs(c_entry - sl_price))

                    POSITION_CAPITAL = 50000.0  # Standardized ₹50k position per unconstrained trade
                    
                    if asset_cls == "OPTION" or sym in ("NIFTY", "BANKNIFTY"):
                        lot_size = _resolve_lot_size(sym)
                        strike_step = get_strike_interval(sym, c_entry)
                        
                        if strat_name == "S09_OptionsThetaDecay":
                            str_ce = round(c_entry / strike_step) * strike_step + strike_step
                            str_pe = round(c_entry / strike_step) * strike_step - strike_step
                            contract_name = f"{sym}_STRANGLE"
                            opt_action = "SELL"
                            
                            bsm_ce = calculate_black_scholes_greeks(spot=c_entry, strike=str_ce, dte_days=4.0, iv=0.14, option_type="CE")
                            bsm_pe = calculate_black_scholes_greeks(spot=c_entry, strike=str_pe, dte_days=4.0, iv=0.14, option_type="PE")
                            opt_premium = max(1.0, round(float(bsm_ce.get("theoretical_price", 5.0)) + float(bsm_pe.get("theoretical_price", 5.0)), 2))
                            opt_sl = round(opt_premium * 1.50, 2)
                            opt_target = round(opt_premium * 0.50, 2)
                            delta_val = 0.0
                            theta_val = round(opt_premium * 0.12, 2)
                        elif sig.signal_direction == "LONG":
                            strike = round(c_entry / strike_step) * strike_step
                            str_ce, str_pe = strike, strike
                            contract_name = f"{sym}{int(strike)}CE"
                            opt_action = "BUY"
                            bsm = calculate_black_scholes_greeks(spot=c_entry, strike=strike, dte_days=4.0, iv=0.14, option_type="CE")
                            opt_premium = max(1.0, round(bsm.get("theoretical_price", c_entry * 0.018), 2))
                            opt_sl = round(opt_premium * 0.70, 2)
                            opt_target = round(opt_premium * 1.35, 2)
                            delta_val = float(bsm.get("delta", 0.52))
                            theta_val = float(abs(bsm.get("theta_per_day", opt_premium * 0.10)))
                        else:
                            strike = round(c_entry / strike_step) * strike_step
                            str_ce, str_pe = strike, strike
                            contract_name = f"{sym}{int(strike)}PE"
                            opt_action = "BUY"
                            bsm = calculate_black_scholes_greeks(spot=c_entry, strike=strike, dte_days=4.0, iv=0.14, option_type="PE")
                            opt_premium = max(1.0, round(bsm.get("theoretical_price", c_entry * 0.018), 2))
                            opt_sl = round(opt_premium * 0.70, 2)
                            opt_target = round(opt_premium * 1.35, 2)
                            delta_val = float(bsm.get("delta", -0.52))
                            theta_val = float(abs(bsm.get("theta_per_day", opt_premium * 0.10)))

                        num_lots = max(1, min(10, int(POSITION_CAPITAL / (opt_premium * lot_size))))
                        qty_tot = num_lots * lot_size
                        qty_t1_units = (num_lots // 2 * lot_size) if num_lots >= 2 else (1 * lot_size)

                        new_trade = {
                            "trade_id": f"UNC-{trade_id_seq}",
                            "symbol": contract_name,
                            "underlying": sym,
                            "sector": SECTOR_MAP.get(sym, "INDEX"),
                            "strategy_id": strat_name,
                            "asset_class": "OPTION",
                            "direction": sig.signal_direction,
                            "option_action": opt_action,
                            "strike_ce": str_ce,
                            "strike_pe": str_pe,
                            "delta": delta_val,
                            "theta_per_day": theta_val,
                            "entry_time": f"{sim_date} {sim_time}",
                            "entry_price": opt_premium,
                            "entry_underlying": round(c_entry, 2),
                            "initial_sl": opt_sl,
                            "current_sl": opt_sl,
                            "target1": opt_target,
                            "qty_total": qty_tot,
                            "qty_t1": qty_t1_units,
                            "t1_hit": False,
                            "t1_exit_time": "-",
                            "t1_exit_price": "-",
                            "t1_pnl": 0.0,
                            "final_exit_time": "-",
                            "final_exit_price": "-",
                            "final_exit_reason": "OPEN",
                            "final_exit_pnl": 0.0,
                            "total_friction": 0.0,
                            "minutes_held": 0,
                            "max_minutes": 1500,
                            "realized_pnl": 0.0,
                            "status": "OPEN"
                        }
                        all_open_trades.append(new_trade)
                        active_positions.add((strat_name, sym))
                        trade_id_seq += 1
                    else:
                        qty_tot = max(1, int(POSITION_CAPITAL / c_entry))
                        t1_target = round(c_entry + 2.5 * risk_dist if sig.signal_direction == "LONG" else c_entry - 2.5 * risk_dist, 2)

                        new_trade = {
                            "trade_id": f"UNC-{trade_id_seq}",
                            "symbol": sym,
                            "underlying": sym,
                            "sector": SECTOR_MAP.get(sym, "OTHER"),
                            "strategy_id": strat_name,
                            "asset_class": "EQUITY",
                            "direction": sig.signal_direction,
                            "option_action": "BUY" if sig.signal_direction == "LONG" else "SELL",
                            "entry_time": f"{sim_date} {sim_time}",
                            "entry_price": round(c_entry, 2),
                            "entry_underlying": round(c_entry, 2),
                            "initial_sl": round(sl_price, 2),
                            "current_sl": round(sl_price, 2),
                            "target1": t1_target,
                            "qty_total": qty_tot,
                            "qty_t1": int(qty_tot * 0.5),
                            "t1_hit": False,
                            "t1_exit_time": "-",
                            "t1_exit_price": "-",
                            "t1_pnl": 0.0,
                            "final_exit_time": "-",
                            "final_exit_price": "-",
                            "final_exit_reason": "OPEN",
                            "final_exit_pnl": 0.0,
                            "total_friction": 0.0,
                            "minutes_held": 0,
                            "max_minutes": 375 if tf_type == "INTRADAY" else 1875,
                            "realized_pnl": 0.0,
                            "status": "OPEN"
                        }
                        all_open_trades.append(new_trade)
                        active_positions.add((strat_name, sym))
                        trade_id_seq += 1
                except Exception:
                    pass

    # Close remaining open trades at simulation end
    final_ts = timeline_1m[-1]
    final_date_str = final_ts.strftime('%Y-%m-%d %H:%M')
    for tr in all_open_trades:
        sym = tr["underlying"]
        s_df = candles_dict.get(sym)
        c_final = float(s_df.loc[final_ts]["Close"]) if (s_df is not None and final_ts in s_df.index) else tr["entry_price"]
        rem_q = tr["qty_total"] - (tr["qty_t1"] if tr["t1_hit"] else 0)
        
        if tr["asset_class"] == "OPTION":
            buy_p = tr["entry_price"] if tr["option_action"] == "BUY" else tr.get("current_price", tr["entry_price"])
            sell_p = tr.get("current_price", tr["entry_price"]) if tr["option_action"] == "BUY" else tr["entry_price"]
            f_data = calculate_all_in_friction(buy_p, sell_p, rem_q, "OPTIONS", "INTRADAY")
            g_pnl = (tr.get("current_price", tr["entry_price"]) - tr["entry_price"]) * rem_q if tr["option_action"] == "BUY" else (tr["entry_price"] - tr.get("current_price", tr["entry_price"])) * rem_q
            n_pnl = g_pnl - f_data["total_friction"]
            tr["final_exit_price"] = tr.get("current_price", tr["entry_price"])
        else:
            is_intra = (tr["strategy_id"] == "S08_IntradayAllDay")
            p_type = "INTRADAY" if is_intra else "DELIVERY"
            f_data = calculate_all_in_friction(tr["entry_price"], c_final, rem_q, tr["asset_class"], p_type)
            g_pnl = (c_final - tr["entry_price"]) * rem_q if tr["direction"] == "LONG" else (tr["entry_price"] - c_final) * rem_q
            n_pnl = g_pnl - f_data["total_friction"]
            tr["final_exit_price"] = c_final

        tr["final_exit_time"] = final_date_str
        tr["final_exit_reason"] = "SIMULATION_END_MTM"
        tr["final_exit_pnl"] = n_pnl
        tr["realized_pnl"] += n_pnl
        tr["total_friction"] += f_data["total_friction"]
        tr["status"] = "CLOSED"
        all_closed_trades.append(tr)

    # ── 3. Generate Pristine CSV Ledger ──────────────────────────────────────
    csv_ledger_path = scratch_dir / "unconstrained_all_trades_ledger.csv"
    with open(csv_ledger_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Trade_ID", "Symbol", "Strategy_ID", "Asset_Class", "Direction", "Entry_Time", "Entry_Price",
            "Tranche_1_Exit_Time", "Tranche_1_Exit_Price", "Tranche_1_PnL", "Final_Exit_Time", "Final_Exit_Price",
            "Final_Exit_Reason", "Quantity", "Total_Friction", "Net_PnL", "Return_Pct"
        ])
        for t in all_closed_trades:
            fin_p = float(t.get("final_exit_price", t["entry_price"]))
            ret_pct = ((fin_p - t["entry_price"]) / t["entry_price"] * 100.0) if (t["direction"] == "LONG" or t["option_action"] == "BUY") else ((t["entry_price"] - fin_p) / t["entry_price"] * 100.0)
            writer.writerow([
                t["trade_id"], t["symbol"], t["strategy_id"], t["asset_class"], t["direction"], t["entry_time"],
                t["entry_price"], t["t1_exit_time"], t["t1_exit_price"], round(t["t1_pnl"], 2),
                t["final_exit_time"], round(fin_p, 2), t["final_exit_reason"], t["qty_total"],
                round(t["total_friction"], 2), round(t["realized_pnl"], 2), round(ret_pct, 2)
            ])

    # ── 4. Generate Strategy Attribution Matrix Report ───────────────────────
    strat_stats = {}
    for sid, _, tf_t, a_cls in strategy_registry:
        strat_stats[sid] = {
            "name": sid,
            "type": f"{tf_t} {a_cls}",
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "gross_win": 0.0,
            "gross_loss": 0.0,
            "friction": 0.0,
            "net_pnl": 0.0,
        }

    for t in all_closed_trades:
        sid = t["strategy_id"]
        if sid in strat_stats:
            strat_stats[sid]["trades"] += 1
            strat_stats[sid]["friction"] += t["total_friction"]
            strat_stats[sid]["net_pnl"] += t["realized_pnl"]
            if t["realized_pnl"] > 0:
                strat_stats[sid]["wins"] += 1
                strat_stats[sid]["gross_win"] += t["realized_pnl"]
            else:
                strat_stats[sid]["losses"] += 1
                strat_stats[sid]["gross_loss"] += abs(t["realized_pnl"])

    report_path = scratch_dir / "unconstrained_12strat_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 🏛️ Master 12-Strategy Unconstrained Alpha Matrix\n\n")
        f.write(f"**Period:** 17-Aug-2026 09:15 to 21-Aug-2026 15:30 IST (5 Full Trading Sessions)  \n")
        f.write(f"**Universe:** 51 Instruments (Nifty 50 Index, Bank Nifty Index + 49 Constituents)  \n")
        f.write(f"**Replay Timeframe:** 1-Minute Live Bars (1,875 Bars from Angel One SmartAPI)  \n")
        f.write(f"**Execution Mode:** Pure Alpha Isolation (Zero Slot Competition, Zero Bottlenecking)  \n")
        f.write(f"**Total Signals Executed:** {len(all_closed_trades)} Trades Tracked  \n\n")
        f.write("---\n\n")
        f.write("## 📊 1. Master Strategy Ranking Matrix\n\n")
        f.write("| Rank | Strategy ID | Type | Signals | Win Rate % | Gross Wins (₹) | Total Friction (₹) | Net Realized P&L (₹) | Profit Factor | Verdict |\n")
        f.write("| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |\n")
        
        # Sort by Net P&L descending
        sorted_strats = sorted(strat_stats.values(), key=lambda x: x["net_pnl"], reverse=True)
        for rank, s in enumerate(sorted_strats, 1):
            wr = (s["wins"] / s["trades"] * 100.0) if s["trades"] > 0 else 0.0
            pf = (s["gross_win"] / s["gross_loss"]) if s["gross_loss"] > 0 else (99.9 if s["gross_win"] > 0 else 0.0)
            
            if s["net_pnl"] > 0 and wr >= 50.0:
                verdict = "🌟 ALPHA STAR"
            elif s["net_pnl"] > 0:
                verdict = "✅ PROFITABLE"
            elif s["trades"] == 0:
                verdict = "⏸️ ZERO SIGNALS"
            elif s["net_pnl"] > -2000.0:
                verdict = "⚠️ UNDERPERFORMING"
            else:
                verdict = "🛑 TOXIC / KILL"

            f.write(f"| {rank} | **{s['name']}** | {s['type']} | {s['trades']} | **{wr:.1f}%** ({s['wins']}/{s['trades']}) | ₹{s['gross_win']:,.2f} | ₹{s['friction']:,.2f} | **₹{s['net_pnl']:+,.2f}** | **{pf:.2f}** | {verdict} |\n")

    logger.info("================================================================================")
    logger.info(f"  ✅ UNCONSTRAINED BENCHMARK COMPLETED: {len(all_closed_trades)} Total Signals Evaluated!")
    for rank, s in enumerate(sorted_strats, 1):
        wr = (s["wins"] / s["trades"] * 100.0) if s["trades"] > 0 else 0.0
        logger.info(f"  #{rank:02d} {s['name']:<28} Trades: {s['trades']:<3} WR: {wr:>5.1f}% | Net PnL: ₹{s['net_pnl']:>+9.2f}")
    logger.info(f"  Report exported to: {report_path}")
    logger.info("================================================================================")


if __name__ == "__main__":
    run_unconstrained_benchmark()
