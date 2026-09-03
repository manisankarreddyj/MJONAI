"""
Unit and Institutional Test Suite for Options Chain Engine & Analytics
(options/chain_engine.py)
"""

import pytest

from options.chain_engine import (
    get_atm_strike,
    calculate_pcr,
    calculate_max_pain,
    calculate_expected_move,
    select_optimal_strike,
    build_option_chain_ladder,
    OptionChainLadderResult,
)


def test_get_atm_strike_indices_and_equities():
    """Verify ATM strike rounding for Indian indices and stock options."""
    # NIFTY step = 50
    assert get_atm_strike(24523.5, "NIFTY") == 24500.0
    assert get_atm_strike(24526.0, "NIFTY") == 24550.0

    # BANKNIFTY step = 100
    assert get_atm_strike(51849.0, "BANKNIFTY") == 51800.0
    assert get_atm_strike(51851.0, "BANKNIFTY") == 51900.0

    # MIDCPNIFTY step = 25
    assert get_atm_strike(12411.0, "MIDCPNIFTY") == 12400.0
    assert get_atm_strike(12413.0, "MIDCPNIFTY") == 12425.0

    # Equities: RELIANCE @ 2880 (step 50) -> 2900
    assert get_atm_strike(2880.0, "RELIANCE") == 2900.0


def test_calculate_pcr_oi_and_volume():
    """Verify Put-Call Ratio calculations for Open Interest and Volume."""
    chain = [
        {"strike": 24400.0, "ce_oi": 10000.0, "pe_oi": 30000.0, "ce_volume": 5000.0, "pe_volume": 15000.0},
        {"strike": 24500.0, "ce_oi": 50000.0, "pe_oi": 50000.0, "ce_volume": 20000.0, "pe_volume": 20000.0},
        {"strike": 24600.0, "ce_oi": 40000.0, "pe_oi": 20000.0, "ce_volume": 15000.0, "pe_volume": 5000.0},
    ]
    # Total CE OI = 100k, Total PE OI = 100k -> PCR = 1.0
    res = calculate_pcr(chain)
    assert res["pcr_oi"] == 1.0
    assert res["pcr_volume"] == 1.0
    assert res["total_ce_oi"] == 100000.0
    assert res["total_pe_oi"] == 100000.0


def test_calculate_max_pain():
    """Verify Max Pain strike identifies strike of minimum buyer payout."""
    # Symmetrical chain centered around 24500
    chain = [
        {"strike": 24400.0, "ce_oi": 10000.0, "pe_oi": 80000.0},
        {"strike": 24500.0, "ce_oi": 90000.0, "pe_oi": 90000.0},
        {"strike": 24600.0, "ce_oi": 80000.0, "pe_oi": 10000.0},
    ]
    max_pain = calculate_max_pain(chain)
    assert max_pain == 24500.0


def test_calculate_expected_move_1sigma_and_2sigma():
    """Verify 1-SD and 2-SD expected move calculation."""
    spot = 24000.0
    atm_iv = 0.15
    dte = 7.0  # 1 week

    res = calculate_expected_move(spot, atm_iv, dte_days=dte)
    assert res["expected_move_rs"] > 0
    assert res["upper_range"] > spot
    assert res["lower_range"] < spot
    assert res["upper_2sigma"] > res["upper_range"]
    assert res["lower_2sigma"] < res["lower_range"]


def test_select_optimal_strike_by_delta():
    """Verify optimal strike selector matches target delta."""
    spot = 24500.0
    strikes = [24300.0, 24400.0, 24500.0, 24600.0, 24700.0]

    # ATM Call target Delta = 0.50 -> Should pick 24500
    res_ce = select_optimal_strike(spot, strikes, option_type="CE", target_delta=0.50, dte_days=5.0, atm_iv=0.15)
    assert res_ce["strike"] == 24500.0
    assert res_ce["is_atm"] is True


def test_build_option_chain_ladder_contract():
    """Verify full option chain ladder construction and contract serialization."""
    result = build_option_chain_ladder(symbol="NIFTY", spot=24520.0, dte_days=4.0, atm_iv=0.14, num_strikes=5)
    assert isinstance(result, OptionChainLadderResult)
    assert result.symbol == "NIFTY"
    assert result.atm_strike == 24500.0
    assert len(result.ladder) == 11  # 5 below + ATM + 5 above
    assert result.max_pain > 0
    assert result.expected_move_1sigma > 0

    d = result.to_dict()
    assert d["atm_strike"] == 24500.0
    assert "ladder" in d
