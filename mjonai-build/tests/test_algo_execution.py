import pytest
from execution.algo_execution import (
    SEBIRateLimiter,
    calculate_implementation_shortfall,
    generate_twap_slices,
    generate_vwap_slices,
    select_optimal_broker,
)


def test_sebi_rate_limiter_token_bucket():
    """Verify SEBI 10-OPS token bucket rate limiter."""
    limiter = SEBIRateLimiter(max_ops=10, burst_limit=5)
    # Immediate acquire within burst limit
    assert limiter.acquire(tokens_needed=3, timeout=0.1) is True
    assert limiter.acquire(tokens_needed=2, timeout=0.1) is True


def test_implementation_shortfall_calculation():
    """Verify Perot / Almgren-Chriss implementation shortfall tracking."""
    # Buy order: Arrival price = 1000.0, Fill price = 1002.0 (20 bps slippage)
    res_buy = calculate_implementation_shortfall(
        symbol="RELIANCE",
        arrival_price=1000.0,
        execution_price=1002.0,
        quantity=100,
        direction="LONG",
    )
    assert res_buy.shortfall_bps == 20.0
    assert res_buy.shortfall_rupees == 200.0
    assert res_buy.is_favorable is False

    # Favorable fill (price improved): Arrival = 1000.0, Fill = 998.0 (-20 bps)
    res_fav = calculate_implementation_shortfall(
        symbol="RELIANCE",
        arrival_price=1000.0,
        execution_price=998.0,
        quantity=100,
        direction="LONG",
    )
    assert res_fav.shortfall_bps == -20.0
    assert res_fav.is_favorable is True


def test_twap_and_vwap_order_slicing():
    """Verify TWAP and VWAP child order distribution."""
    total_q = 5000
    twap_slices = generate_twap_slices(total_quantity=total_q, duration_minutes=10, num_slices=5)
    assert len(twap_slices) == 5
    assert sum(s.quantity for s in twap_slices) == total_q
    assert all(s.quantity == 1000 for s in twap_slices)

    vwap_slices = generate_vwap_slices(total_quantity=total_q, num_slices=5)
    assert len(vwap_slices) == 5
    assert sum(s.quantity for s in vwap_slices) == total_q
    # U-curve should allocate more to slices 1 and 5 (open and close)
    assert vwap_slices[0].quantity > vwap_slices[2].quantity


def test_smart_order_routing_broker_selection():
    """Verify smart routing selection based on asset class."""
    b_opt, reason_opt = select_optimal_broker("OPTIONS", "S09_OptionsThetaDecay", num_legs=2)
    assert b_opt == "SHOONYA"
    assert "Zero-Brokerage" in reason_opt

    b_eq, reason_eq = select_optimal_broker("EQUITY", "S01_MomentumRSI", num_legs=1)
    assert b_eq == "ANGELONE"
