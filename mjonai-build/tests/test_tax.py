"""
Unit and Institutional Test Suite for Indian Statutory Tax & Friction Engine
(execution/tax.py)
"""

import pytest

from execution.tax import (
    calculate_brokerage,
    calculate_tax,
    calculate_stt,
    calculate_ctt,
    calculate_stamp_duty,
    calculate_turnover_charges,
    calculate_all_in_friction,
    DP_CHARGES_DELIVERY_SELL,
)


def test_calculate_brokerage_cap_rule():
    """Verify brokerage rule: ₹20 or 0.03% of turnover, whichever is lower."""
    # Small trade: ₹10,000 * 0.03% = ₹3.00
    brok_small = calculate_brokerage(10000.0)
    assert brok_small == 3.00

    # Large trade: ₹1,000,000 * 0.03% = ₹300 -> capped at ₹20.00
    brok_large = calculate_brokerage(1000000.0)
    assert brok_large == 20.00

    # Zero turnover
    assert calculate_brokerage(0.0) == 0.0


def test_calculate_tax_stcg_ltcg_crypto_with_cess():
    """Verify STCG (20.8%), LTCG (13.0%), and Crypto VDA (31.2%) rates with 4% cess."""
    profit = 10000.0

    # STCG @ 20.80% (< 365 days)
    stcg = calculate_tax(profit, holding_days=5, asset_class="EQUITY")
    assert stcg == 2080.00

    # LTCG @ 13.00% (>= 365 days)
    ltcg = calculate_tax(profit, holding_days=400, asset_class="EQUITY")
    assert ltcg == 1300.00

    # Crypto VDA @ 31.20% (Sec 115BBH)
    crypto_tax = calculate_tax(profit, holding_days=5, asset_class="CRYPTO")
    assert crypto_tax == 3120.00

    # Loss trades incur 0 tax
    loss_tax = calculate_tax(-5000.0, holding_days=10)
    assert loss_tax == 0.0


def test_calculate_stt_across_asset_classes():
    """Verify STT rules across Equity Delivery, Intraday, Futures, and Options."""
    turnover = 100000.0

    # Equity Delivery (0.10% on both Buy and Sell)
    assert calculate_stt(turnover, side="BUY", asset_class="EQUITY", product_type="DELIVERY") == 100.00
    assert calculate_stt(turnover, side="SELL", asset_class="EQUITY", product_type="DELIVERY") == 100.00

    # Equity Intraday (0.025% on Sell only)
    assert calculate_stt(turnover, side="BUY", asset_class="EQUITY", product_type="INTRADAY") == 0.00
    assert calculate_stt(turnover, side="SELL", asset_class="EQUITY", product_type="INTRADAY") == 25.00

    # Futures (0.02% on Sell turnover)
    assert calculate_stt(turnover, side="SELL", asset_class="FUTURES") == 20.00

    # Options Premium (0.10% on Sell premium)
    assert calculate_stt(turnover, side="SELL", asset_class="OPTIONS") == 100.00


def test_calculate_ctt_mcx_commodities():
    """Verify MCX Commodity Transaction Tax (CTT) on Sell side."""
    turnover = 100000.0

    # Commodity Futures (0.01% on Sell)
    assert calculate_ctt(turnover, side="SELL", is_option=False) == 10.00

    # Commodity Options (0.05% on Sell)
    assert calculate_ctt(turnover, side="SELL", is_option=True) == 50.00

    # Buy side is exempt from CTT
    assert calculate_ctt(turnover, side="BUY") == 0.00


def test_calculate_stamp_duty_buy_side_only():
    """Verify Stamp Duty is strictly levied on Buy side only."""
    turnover = 100000.0

    # Delivery Buy (0.015%)
    assert calculate_stamp_duty(turnover, side="BUY", asset_class="EQUITY", product_type="DELIVERY") == 15.00

    # Sell side is 0
    assert calculate_stamp_duty(turnover, side="SELL", asset_class="EQUITY") == 0.00


def test_calculate_all_in_friction_single_and_multi_leg():
    """Verify full all-in friction with DP charges and multi-leg option multipliers."""
    # Equity Delivery Trade: Buy 100 @ 1000, Sell 100 @ 1050
    res_eq = calculate_all_in_friction(
        buy_price=1000.0,
        sell_price=1050.0,
        quantity=100,
        asset_class="EQUITY",
        product_type="DELIVERY",
    )

    assert res_eq["brokerage"] == 40.00  # ₹20 buy + ₹20 sell
    assert res_eq["stt_ctt"] == (100.00 + 105.00)  # 0.1% buy + 0.1% sell
    assert res_eq["dp_charges"] == DP_CHARGES_DELIVERY_SELL  # ₹15.34
    assert res_eq["total_friction"] > 0
    assert res_eq["breakeven_pts"] > 0

    # Multi-Leg Iron Condor (4 legs)
    res_condor = calculate_all_in_friction(
        buy_price=50.0,
        sell_price=60.0,
        quantity=100,
        asset_class="OPTIONS",
        num_legs=4,
    )

    # 4 legs * (₹20 buy + ₹20 sell) = ₹160 max brokerage
    assert res_condor["brokerage"] > 0
    assert res_condor["total_friction"] > 0
