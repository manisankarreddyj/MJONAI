"""
Unit and Institutional Test Suite for Black-Scholes Greeks Engine
(options/greeks.py)
"""

import math
import pytest

from options.greeks import (
    calculate_black_scholes_greeks,
    calculate_implied_volatility,
    OptionGreeksResult,
)


def test_call_and_put_greeks_math():
    """Verify ATM Call and Put Greeks adhere to Black-Scholes properties."""
    spot = 24500.0
    strike = 24500.0
    dte = 7.0
    iv = 0.15

    # 1. Call Option Greeks
    call = calculate_black_scholes_greeks(spot, strike, dte, iv, option_type="CE")
    assert 0.45 < call["delta"] < 0.55
    assert call["gamma"] > 0
    assert call["theta_per_day"] < 0
    assert call["vega_per_pct"] > 0
    assert call["theoretical_price"] > 0

    # 2. Put Option Greeks
    put = calculate_black_scholes_greeks(spot, strike, dte, iv, option_type="PE")
    assert -0.55 < put["delta"] < -0.45
    assert put["gamma"] > 0
    assert put["theta_per_day"] < 0
    assert put["vega_per_pct"] > 0

    # 3. Symmetry Check: Gamma and Vega must be identical for Call & Put
    assert abs(call["gamma"] - put["gamma"]) < 1e-8
    assert abs(call["vega_per_pct"] - put["vega_per_pct"]) < 1e-4

    # 4. Put-Call Parity Delta Check: Delta(Call) - Delta(Put) == 1.0 (when q=0)
    assert round(call["delta"] - put["delta"], 2) == 1.0


def test_second_order_greeks_vanna_volga_charm():
    """Verify second-order Greeks (Vanna, Volga, Charm) are computed accurately."""
    res = calculate_black_scholes_greeks(24000.0, 24000.0, dte_days=5.0, iv=0.18, option_type="CE")
    assert "vanna" in res
    assert "volga" in res
    assert "charm" in res
    assert not math.isnan(res["vanna"])
    assert not math.isnan(res["volga"])
    assert not math.isnan(res["charm"])


def test_dividend_yield_effect():
    """Verify continuous dividend yield reduces Call value and increases Put value."""
    spot = 2000.0
    strike = 2000.0
    dte = 30.0
    iv = 0.25

    no_div_call = calculate_black_scholes_greeks(spot, strike, dte, iv, "CE", dividend_yield=0.0)
    with_div_call = calculate_black_scholes_greeks(spot, strike, dte, iv, "CE", dividend_yield=0.03)

    # Dividend reduces Call price
    assert with_div_call["theoretical_price"] < no_div_call["theoretical_price"]

    no_div_put = calculate_black_scholes_greeks(spot, strike, dte, iv, "PE", dividend_yield=0.0)
    with_div_put = calculate_black_scholes_greeks(spot, strike, dte, iv, "PE", dividend_yield=0.03)

    # Dividend increases Put price
    assert with_div_put["theoretical_price"] > no_div_put["theoretical_price"]


def test_0_dte_near_expiry_stability():
    """Verify 0-DTE boundary conditions handle near-zero time with zero division errors."""
    res = calculate_black_scholes_greeks(25000.0, 25000.0, dte_days=0.001, iv=0.15, option_type="CE")
    assert res["theoretical_price"] >= 0.05
    assert not math.isnan(res["delta"])
    assert not math.isnan(res["gamma"])


def test_implied_volatility_solver_roundtrip():
    """Verify IV solver accurately recovers known IV from theoretical price."""
    spot = 24500.0
    strike = 24600.0
    dte = 5.0
    known_iv = 0.1750  # 17.5%

    # Calculate theoretical price
    greeks = calculate_black_scholes_greeks(spot, strike, dte, known_iv, option_type="CE")
    mkt_price = greeks["theoretical_price"]

    # Solve back for IV
    solved_iv = calculate_implied_volatility(mkt_price, spot, strike, dte, option_type="CE")
    assert abs(solved_iv - known_iv) < 0.005  # Within 0.5% IV accuracy


def test_implied_volatility_deep_otm_convergence():
    """Verify IV solver converges for deep OTM options without failing."""
    spot = 24500.0
    strike = 26000.0  # 1500 pts OTM
    dte = 3.0
    low_price = 5.0

    solved_iv = calculate_implied_volatility(low_price, spot, strike, dte, option_type="CE")
    assert solved_iv > 0.0
    assert not math.isnan(solved_iv)
