"""
Unit and Institutional Test Suite for Non-Directional Multi-Leg Options & Delta Hedging
(options/multi_leg.py)
"""

import pytest

from mjonai.options.multi_leg import (
    construct_short_strangle_trade,
    construct_iron_condor_trade,
    calculate_strangle_rebalance_adjustment,
    calculate_atm_straddle_expected_range,
    ShortStrangleTradeResult,
    IronCondorTradeResult,
)


def test_calculate_atm_straddle_expected_range():
    """Verify 85% rule on ATM Straddle premium."""
    # NIFTY ATM CE = 100, ATM PE = 100 -> Total = 200 -> Expected Range = 170 pts
    res = calculate_atm_straddle_expected_range(atm_call_premium=100.0, atm_put_premium=100.0, multiplier=0.85)
    assert res["combined_straddle_premium"] == 200.0
    assert res["expected_range_points"] == 170.0


def test_construct_short_strangle_trade():
    """Verify 2-leg delta-neutral Short Strangle construction."""
    spot = 24500.0
    strikes = [24000.0, 24200.0, 24400.0, 24500.0, 24600.0, 24800.0, 25000.0]

    strangle = construct_short_strangle_trade(
        underlying_symbol="NIFTY",
        spot_price=spot,
        available_strikes=strikes,
        dte_days=4.0,
        atm_iv=0.15,
    )
    assert strangle is not None
    assert strangle["direction"] == "NON_DIRECTIONAL"
    assert strangle["call_strike"] > spot
    assert strangle["put_strike"] < spot
    assert strangle["combined_premium"] > 0
    assert strangle["upper_breakeven"] > strangle["call_strike"]
    assert strangle["lower_breakeven"] < strangle["put_strike"]
    assert len(strangle["legs"]) == 2
    assert strangle["legs"][0]["action"] == "SELL"
    assert strangle["legs"][1]["action"] == "SELL"


def test_construct_iron_condor_trade():
    """Verify 4-leg defined-risk Iron Condor construction."""
    spot = 24500.0
    strikes = [23800.0, 24000.0, 24200.0, 24500.0, 24800.0, 25000.0, 25200.0]

    condor = construct_iron_condor_trade(
        underlying_symbol="NIFTY",
        spot_price=spot,
        available_strikes=strikes,
        dte_days=4.0,
        atm_iv=0.15,
    )
    assert condor is not None
    assert condor["net_credit"] > 0
    assert condor["max_loss"] > 0
    assert len(condor["legs"]) == 4
    # 2 shorts (inner) + 2 longs (wings)
    actions = [leg["action"] for leg in condor["legs"]]
    assert actions.count("SELL") == 2
    assert actions.count("BUY") == 2


def test_calculate_strangle_rebalance_adjustment():
    """Verify dynamic delta rebalancing and threatened leg roll logic."""
    # 1. Delta Balanced -> HOLD
    balanced = calculate_strangle_rebalance_adjustment(
        spot=24500.0,
        call_strike=24800.0,
        put_strike=24200.0,
        call_premium=40.0,
        put_premium=40.0,
        entry_call_premium=40.0,
        entry_put_premium=40.0,
        net_delta=0.05,
    )
    assert balanced["adjustment_required"] is False
    assert balanced["recommended_action"] == "HOLD"

    # 2. Bullish Delta Drift (> 0.25) -> ROLL_UP_PUT_WING
    bull_drift = calculate_strangle_rebalance_adjustment(
        spot=24750.0,
        call_strike=24800.0,
        put_strike=24200.0,
        call_premium=90.0,
        put_premium=10.0,
        entry_call_premium=40.0,
        entry_put_premium=40.0,
        net_delta=0.30,
    )
    assert bull_drift["adjustment_required"] is True
    assert bull_drift["recommended_action"] == "ROLL_UP_PUT_WING"

    # 3. Threatened Put Leg (2.5x premium) -> ROLL_DOWN_CALL_WING
    threatened_put = calculate_strangle_rebalance_adjustment(
        spot=24200.0,
        call_strike=24800.0,
        put_strike=24300.0,
        call_premium=10.0,
        put_premium=110.0,
        entry_call_premium=40.0,
        entry_put_premium=40.0,
        net_delta=-0.15,
    )
    assert threatened_put["adjustment_required"] is True
    assert threatened_put["recommended_action"] == "ROLL_DOWN_CALL_WING"
