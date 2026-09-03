import pytest
from mjonai.core.market_state import calculate_market_state, MarketRegimePolicy
from mjonai.risk.devil_checks import check_circuit_band_proximity
from mjonai.risk.trade_risk import calculate_volatility_risk_parity_quantity


def test_regime_hysteresis_schmitt_trigger():
    """Verify that regime does not oscillate on boundary noise."""
    policy = MarketRegimePolicy(bull_score_threshold=2, bear_score_threshold=-2)
    # 1. Strong Bull (+3) -> State is BULL
    snap1 = calculate_market_state(
        custom_nifty_price=23000.0,
        custom_ema200=22000.0,
        custom_vix=12.0,
        custom_breadth_pct=0.70,
        policy=policy,
    )
    assert snap1.market_state == "BULL"

    # 2. Score drops slightly to +1 (within hysteresis buffer) -> Remains BULL (no whipsaw)
    snap2 = calculate_market_state(
        custom_nifty_price=22500.0,
        custom_ema200=22000.0,
        custom_vix=16.0,  # Neutral vix (0)
        custom_breadth_pct=0.50,  # Neutral breadth (0) -> total score = +1
        policy=policy,
    )
    assert snap2.market_state == "BULL"


def test_circuit_band_proximity_sentry():
    """Verify NSE Upper/Lower circuit limit pre-trade elimination."""
    # Case 1: Stock is at 100, Upper Circuit is 101 (1.0% away < 2.0% safe buffer) -> VETO LONG
    passed, reason = check_circuit_band_proximity(
        current_price=100.0,
        upper_circuit=101.0,
        direction="LONG",
        min_safe_buffer_pct=2.0,
    )
    assert passed is False
    assert "Near Upper Circuit" in reason

    # Case 2: Stock is at 100, Upper Circuit is 110 (10.0% away >= 2.0%) -> PASS
    passed_ok, _ = check_circuit_band_proximity(
        current_price=100.0,
        upper_circuit=110.0,
        direction="LONG",
    )
    assert passed_ok is True


def test_volatility_risk_parity_quantity():
    """Verify constant dollar risk across low-beta vs high-beta stocks."""
    total_cap = 100000.0  # 1 Lakh Capital
    risk_pct = 1.0        # Risk 1% = ₹1,000 per trade

    # High-beta volatile stock (Entry: 1000, SL: 950 -> ₹50 risk/share)
    # Expected qty = 1000 / 50 = 20 shares
    qty_high_vol = calculate_volatility_risk_parity_quantity(
        total_capital=total_cap,
        risk_per_trade_pct=risk_pct,
        entry_price=1000.0,
        stop_loss_price=950.0,
    )
    assert qty_high_vol == 20
    assert qty_high_vol * 50 == 1000.0  # Exact ₹1,000 risk

    # Low-beta stable stock (Entry: 500, SL: 480 -> ₹20 risk/share)
    # Expected qty = 1000 / 20 = 50 shares
    qty_low_vol = calculate_volatility_risk_parity_quantity(
        total_capital=total_cap,
        risk_per_trade_pct=risk_pct,
        entry_price=500.0,
        stop_loss_price=480.0,
    )
    assert qty_low_vol == 50
    assert qty_low_vol * 20 == 1000.0  # Exact ₹1,000 risk
