"""
Unit and Institutional Test Suite for risk/trade_risk.py
Tests Position Sizing, 3-Tranche Scaling Quantities, Fractal Stops,
Derivative Lot Size Enforcers, and TradeRiskLevels Contracts.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from risk.trade_risk import (
    TradeRiskLevels,
    find_swing_low,
    find_swing_high,
    get_market_weight,
    get_confidence_weight,
    calculate_costs,
    split_tranche_quantities,
    calculate_position_size,
    validate_trade,
    calculate_trade_levels,
    evaluate_trade_risk_levels,
)


# ── 1. CONTRACT TESTS ────────────────────────────────────────────────────────

def test_trade_risk_levels_contract():
    """Verify TradeRiskLevels dataclass serializes cleanly to dict."""
    levels = TradeRiskLevels(
        entry=1000.0,
        stop_loss=980.0,
        target=1050.0,
        target_1=1030.0,
        target_2=1050.0,
        quantity=100,
        t1_quantity=50,
        t2_quantity=30,
        runner_quantity=20,
        atr=15.0,
        real_rr=2.4,
        total_cost=85.0,
        costs={"brokerage": 40.0, "total": 85.0},
        trade_type="SWING",
        sl_method="STRUCTURE",
        signal_direction="LONG",
        is_approved=True,
    )
    d = levels.to_dict()
    assert d["entry"] == 1000.0
    assert d["t1_quantity"] == 50
    assert d["runner_quantity"] == 20


# ── 2. 3-TRANCHE SPLITTING TESTS (INTEGER INDIVISIBILITY) ─────────────────────

def test_split_tranche_quantities_all_cases():
    """Verify 3-tranche splitting math across 0, 1, 2, 3, and 100 shares."""
    # 0 shares
    assert split_tranche_quantities(0) == (0, 0, 0)

    # 1 share -> 100% in Tranche 1
    assert split_tranche_quantities(1) == (1, 0, 0)

    # 2 shares -> 1 in T1, 1 in T2, 0 in Runners
    assert split_tranche_quantities(2) == (1, 1, 0)

    # 3 shares -> 1 in T1, 1 in T2, 1 in Runners
    assert split_tranche_quantities(3) == (1, 1, 1)

    # 100 shares -> 50 in T1, 30 in T2, 20 in Runners
    assert split_tranche_quantities(100) == (50, 30, 20)


# ── 3. FRACTAL PIVOT TESTS ───────────────────────────────────────────────────

def test_find_swing_low_and_high():
    """Verify fractal swing low and high discovery."""
    # Lows with a dip at index 5
    data_low = [
        {"Low": 100}, {"Low": 98}, {"Low": 95}, {"Low": 92}, {"Low": 90},
        {"Low": 85},  # Swing low (lower than 2 before and 2 after)
        {"Low": 88}, {"Low": 92}, {"Low": 94}, {"Low": 96}
    ]
    sw_low = find_swing_low(data_low, lookback=10)
    assert sw_low == 85.0

    # Highs with a peak at index 5
    data_high = [
        {"High": 100}, {"High": 102}, {"High": 105}, {"High": 108}, {"High": 110},
        {"High": 120},  # Swing high
        {"High": 115}, {"High": 112}, {"High": 108}, {"High": 105}
    ]
    sw_high = find_swing_high(data_high, lookback=10)
    assert sw_high == 120.0


# ── 4. DERIVATIVE LOT SIZING & FREEZE LIMITS ─────────────────────────────────

def test_derivative_lot_sizing_and_freeze():
    """Verify lot sizing (multiples of 25) and freeze quantity caps."""
    # Calculate position size for NIFTY with lot_size = 25
    qty = calculate_position_size(
        entry=24000.0,
        stop_loss=23900.0,
        confidence=90.0,
        vix=14.0,
        trade_type="SWING",
        system_mode="LIVE",
        lot_size=25,
    )
    # Must be a multiple of 25
    assert qty % 25 == 0

    # Freeze quantity cap at 50
    qty_frozen = calculate_position_size(
        entry=24000.0,
        stop_loss=23900.0,
        confidence=90.0,
        vix=14.0,
        trade_type="SWING",
        system_mode="LIVE",
        lot_size=25,
        freeze_qty=50,
    )
    assert qty_frozen <= 50


# ── 5. STATUTORY REGULATORY FRICTION TESTS ───────────────────────────────────

def test_regulatory_cost_matrix():
    """N2/H8: costs flow from the CANONICAL execution/tax.py engine plus the
    standard 5 bps/side research slippage — the old private model (flat ₹20
    brokerage, always-delivery exit STT) is gone."""
    entry, qty = 1000.0, 10
    from execution.tax import calculate_all_in_friction

    canon = calculate_all_in_friction(buy_price=entry, sell_price=entry, quantity=qty)
    expected_slip = round(entry * qty * 0.0005 * 2, 2)

    costs = calculate_costs(entry=entry, quantity=qty, direction="BUY")
    assert costs["total"] == round(canon["total_friction"] + expected_slip, 2)
    assert costs["stt"] > 0             # delivery sell STT present
    assert costs["gst"] > 0             # 18% GST
    assert costs["total"] > costs["slippage"] > 0


# ── 6. BIDIRECTIONAL TRADE LEVEL ENGINEERING TESTS ───────────────────────────

def test_calculate_trade_levels_long_and_short():
    """Verify calculate_trade_levels generates complete geometry for LONG and SHORT.
    target_rr=3.5 keeps the fixture's net R:R above the 2.0 gate under the
    CANONICAL cost engine (N2/H8): with honest all-in friction (buy-side STT,
    DP charges) the previous default-RR geometry is correctly rejected."""
    # LONG Trade
    res_long = evaluate_trade_risk_levels(
        entry=1000.0,
        atr=15.0,
        confidence=85.0,
        vix=14.0,
        trade_type="SWING",
        target_rr=3.5,
        signal_direction="LONG",
        system_mode="LIVE",
    )
    assert res_long.is_approved is True
    assert res_long.stop_loss < res_long.entry
    assert res_long.target > res_long.entry
    assert res_long.target_1 < res_long.target_2
    assert res_long.t1_quantity + res_long.t2_quantity + res_long.runner_quantity == res_long.quantity

    # SHORT Trade
    res_short = evaluate_trade_risk_levels(
        entry=1000.0,
        atr=15.0,
        confidence=85.0,
        vix=14.0,
        trade_type="SWING",
        target_rr=3.5,
        signal_direction="SHORT",
        system_mode="LIVE",
    )
    assert res_short.is_approved is True
    assert res_short.stop_loss > res_short.entry
    assert res_short.target < res_short.entry
    assert res_short.target_1 > res_short.target_2
