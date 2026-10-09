import pytest
from mjonai.core.market_state import calculate_market_state, MarketRegimePolicy


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
