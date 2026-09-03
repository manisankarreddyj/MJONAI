"""
Module: exit_simulator.py
Purpose: Simulate trades with SL, T1, T2, trailing SL.
         Works with both daily and 5-minute data.
"""

import numpy as np


def simulate_trade(
    entry_price: float,
    atr: float,
    direction: str,
    highs: list,
    lows: list,
    closes: list,
    max_hold: int = 20,
    sl_multiplier: float = 1.5,
    t1_multiplier: float = 1.0,
    t2_multiplier: float = 2.0,
    trailing_atr_mult: float = 1.5,
) -> dict:
    """
    Simulate a trade with SL, T1, T2, trailing SL.
    
    Args:
        entry_price: Entry price
        atr: ATR at entry
        direction: LONG or SHORT
        highs: list of high prices after entry
        lows: list of low prices after entry
        closes: list of close prices after entry
        max_hold: maximum holding periods
        sl_multiplier: SL distance = sl_multiplier × ATR
        t1_multiplier: T1 distance = t1_multiplier × risk
        t2_multiplier: T2 distance = t2_multiplier × risk
        trailing_atr_mult: trailing SL distance = trailing_atr_mult × ATR
    
    Returns:
        dict with exit details
    """
    risk = sl_multiplier * atr
    shares_total = 1.0
    shares_remaining = 1.0
    realized_pnl = 0.0
    
    if direction == "LONG":
        sl = entry_price - risk
        t1 = entry_price + (t1_multiplier * risk)
        t2 = entry_price + (t2_multiplier * risk)
    else:
        sl = entry_price + risk
        t1 = entry_price - (t1_multiplier * risk)
        t2 = entry_price - (t2_multiplier * risk)
    
    current_sl = sl
    t1_hit = False
    t2_hit = False
    
    for day in range(min(max_hold, len(highs))):
        high = highs[day]
        low = lows[day]
        close = closes[day]
        
        if direction == "LONG":
            # Check SL first
            if low <= current_sl:
                exit_price = current_sl
                pnl = (exit_price - entry_price) * shares_remaining
                realized_pnl += pnl
                return {
                    "exit_price": round(exit_price, 2),
                    "exit_reason": "SL",
                    "gross_pnl_pct": round(realized_pnl / entry_price * 100, 4),
                    "hold_days": day + 1,
                    "t1_hit": t1_hit,
                    "t2_hit": t2_hit,
                    "shares_sold_at_t1": 0.5 if t1_hit else 0,
                    "shares_sold_at_t2": 0.3 if t2_hit else 0,
                }
            
            # Check T1
            if not t1_hit and high >= t1:
                t1_hit = True
                pnl_t1 = (t1 - entry_price) * 0.5
                realized_pnl += pnl_t1
                shares_remaining -= 0.5
                current_sl = entry_price  # Move to breakeven
            
            # Check T2
            if t1_hit and not t2_hit and high >= t2:
                t2_hit = True
                pnl_t2 = (t2 - entry_price) * 0.3
                realized_pnl += pnl_t2
                shares_remaining -= 0.3
            
            # Trailing SL for remaining shares
            if t2_hit and shares_remaining > 0:
                new_trail = close - (trailing_atr_mult * atr)
                if new_trail > current_sl:
                    current_sl = new_trail
        
        else:  # SHORT
            if high >= current_sl:
                exit_price = current_sl
                pnl = (entry_price - exit_price) * shares_remaining
                realized_pnl += pnl
                return {
                    "exit_price": round(exit_price, 2),
                    "exit_reason": "SL",
                    "gross_pnl_pct": round(realized_pnl / entry_price * 100, 4),
                    "hold_days": day + 1,
                    "t1_hit": t1_hit,
                    "t2_hit": t2_hit,
                    "shares_sold_at_t1": 0.5 if t1_hit else 0,
                    "shares_sold_at_t2": 0.3 if t2_hit else 0,
                }
            
            if not t1_hit and low <= t1:
                t1_hit = True
                pnl_t1 = (entry_price - t1) * 0.5
                realized_pnl += pnl_t1
                shares_remaining -= 0.5
                current_sl = entry_price
            
            if t1_hit and not t2_hit and low <= t2:
                t2_hit = True
                pnl_t2 = (entry_price - t2) * 0.3
                realized_pnl += pnl_t2
                shares_remaining -= 0.3
            
            if t2_hit and shares_remaining > 0:
                new_trail = close + (trailing_atr_mult * atr)
                if new_trail < current_sl:
                    current_sl = new_trail
    
    # Max hold reached — exit at last close
    last_close = closes[min(max_hold - 1, len(closes) - 1)]
    if direction == "LONG":
        pnl_final = (last_close - entry_price) * shares_remaining
    else:
        pnl_final = (entry_price - last_close) * shares_remaining
    realized_pnl += pnl_final
    
    return {
        "exit_price": round(last_close, 2),
        "exit_reason": "TIME",
        "gross_pnl_pct": round(realized_pnl / entry_price * 100, 4),
        "hold_days": min(max_hold, len(closes)),
        "t1_hit": t1_hit,
        "t2_hit": t2_hit,
        "shares_sold_at_t1": 0.5 if t1_hit else 0,
        "shares_sold_at_t2": 0.3 if t2_hit else 0,
    }


if __name__ == "__main__":
    # Test LONG trade
    entry = 1000.0
    atr = 20.0
    
    # Simulated price path: goes up, hits T1, hits T2, then trails
    highs = [1010, 1020, 1035, 1050, 1045, 1060, 1070, 1065, 1080, 1075]
    lows  = [995, 1005, 1015, 1030, 1035, 1045, 1055, 1050, 1065, 1060]
    closes = [1008, 1018, 1030, 1048, 1042, 1058, 1068, 1060, 1078, 1072]
    
    result = simulate_trade(entry, atr, "LONG", highs, lows, closes)
    
    print("=== LONG TRADE TEST ===")
    print(f"Entry: ₹{entry}")
    print(f"ATR: {atr}")
    print(f"SL: ₹{entry - 1.5*atr}")
    print(f"T1: ₹{entry + 1.5*atr}")
    print(f"T2: ₹{entry + 3*atr}")
    print(f"\nResult: {result}")
    
    # Test SHORT trade
    print("\n=== SHORT TRADE TEST ===")
    highs_short = [1005, 995, 980, 970, 975, 960, 950, 955, 940, 945]
    lows_short = [990, 980, 965, 955, 960, 945, 935, 940, 925, 930]
    closes_short = [992, 982, 968, 958, 962, 948, 938, 942, 928, 935]
    
    result_short = simulate_trade(entry, atr, "SHORT", highs_short, lows_short, closes_short)
    print(f"Result: {result_short}")