"""
Unit and Institutional Test Suite for Directional Options & Vertical Spreads Engine
(options/directional_options.py)
"""

import pytest

from options.directional_options import (
    generate_directional_option_trade,
    generate_vertical_spread_trade,
    _resolve_lot_size,
    DirectionalOptionTradeResult,
    VerticalSpreadTradeResult,
)


def test_resolve_lot_sizes():
    """Verify dynamic and fallback lot sizes."""
    assert _resolve_lot_size("NIFTY") > 0
    assert _resolve_lot_size("BANKNIFTY") > 0
    assert _resolve_lot_size("UNKNOWN_TEST_SYM") == 25


def test_generate_directional_option_trade_buyer_and_writer():
    """Verify single-leg option buyer and writer setup generation."""
    spot = 24500.0
    strikes = [24300.0, 24400.0, 24500.0, 24600.0, 24700.0]

    # 1. Bullish Option Buyer (ATM CE)
    buyer = generate_directional_option_trade(
        underlying_symbol="NIFTY",
        spot_price=spot,
        signal_direction="LONG",
        available_strikes=strikes,
        trade_style="BUY",
    )
    assert buyer is not None
    assert buyer["option_type"] == "CE"
    assert buyer["action"] == "BUY"
    assert buyer["strike"] == 24500.0
    assert buyer["stop_loss_premium"] < buyer["estimated_premium"]
    assert buyer["target_premium"] > buyer["estimated_premium"]
    assert buyer["fast_profit_target"] is True

    # 2. Bullish Option Writer (OTM PE)
    writer = generate_directional_option_trade(
        underlying_symbol="NIFTY",
        spot_price=spot,
        signal_direction="LONG",
        available_strikes=strikes,
        trade_style="SELL",
    )
    assert writer is not None
    assert writer["option_type"] == "PE"
    assert writer["action"] == "SELL"
    # Writer target is 50% decay (target < estimated premium)
    assert writer["target_premium"] < writer["estimated_premium"]
    assert writer["stop_loss_premium"] > writer["estimated_premium"]


def test_generate_directional_option_trade_bearish():
    """Verify bearish option trade picks PE for buyer and CE for writer."""
    spot = 24500.0
    strikes = [24300.0, 24400.0, 24500.0, 24600.0, 24700.0]

    # Bearish Option Buyer -> Buy PE
    bear_buy = generate_directional_option_trade(
        underlying_symbol="NIFTY",
        spot_price=spot,
        signal_direction="SHORT",
        available_strikes=strikes,
        trade_style="BUY",
    )
    assert bear_buy is not None
    assert bear_buy["option_type"] == "PE"
    assert bear_buy["action"] == "BUY"


def test_generate_vertical_spread_bull_call_debit():
    """Verify Bull Call Debit Spread generation and risk-reward bounds."""
    spot = 24500.0
    strikes = [24300.0, 24400.0, 24500.0, 24600.0, 24700.0]

    spread = generate_vertical_spread_trade(
        underlying_symbol="NIFTY",
        spot_price=spot,
        signal_direction="LONG",
        available_strikes=strikes,
        spread_type="DEBIT",
    )
    assert spread is not None
    assert spread["spread_type"] == "BULL_CALL_DEBIT"
    assert spread["net_cost"] > 0
    assert spread["max_profit"] > 0
    assert spread["max_loss"] == spread["net_cost"]
    assert len(spread["legs"]) == 2
    assert spread["legs"][0]["action"] == "BUY"
    assert spread["legs"][1]["action"] == "SELL"


def test_generate_vertical_spread_bull_put_credit():
    """Verify Bull Put Credit Spread generation and credit profit bounds."""
    spot = 24500.0
    strikes = [24100.0, 24200.0, 24300.0, 24400.0, 24500.0]

    spread = generate_vertical_spread_trade(
        underlying_symbol="NIFTY",
        spot_price=spot,
        signal_direction="LONG",
        available_strikes=strikes,
        spread_type="CREDIT",
    )
    assert spread is not None
    assert spread["spread_type"] == "BULL_PUT_CREDIT"
    assert spread["net_cost"] > 0
    assert spread["max_profit"] == spread["net_cost"]
    assert spread["max_loss"] > 0
    assert len(spread["legs"]) == 2
    assert spread["legs"][0]["action"] == "SELL"
    assert spread["legs"][1]["action"] == "BUY"


def test_generate_vertical_spread_bear_put_debit():
    """Verify Bear Put Debit Spread generation."""
    spot = 24500.0
    strikes = [24300.0, 24400.0, 24500.0, 24600.0, 24700.0]

    spread = generate_vertical_spread_trade(
        underlying_symbol="NIFTY",
        spot_price=spot,
        signal_direction="SHORT",
        available_strikes=strikes,
        spread_type="DEBIT",
    )
    assert spread is not None
    assert spread["spread_type"] == "BEAR_PUT_DEBIT"
    assert spread["net_cost"] > 0
    assert len(spread["legs"]) == 2
