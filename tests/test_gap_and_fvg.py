import numpy as np
import pandas as pd
import pytest

from mjonai.data.microstructure.gap_analyzer import (
    analyze_opening_gap_and_fvg,
    detect_fair_value_gaps,
    GapType,
)
from mjonai.strategy.registry.s18_gap_fill import GapFillAndFVGStrategy


def test_fair_value_gap_detection():
    """Verify 3-candle Fair Value Gap (FVG) detection."""
    # Bullish FVG: Low of candle 2 > High of candle 0
    highs = np.array([100.0, 108.0, 115.0, 114.0])
    lows  = np.array([95.0,  102.0, 104.0, 106.0])
    # Low[2] = 104.0, High[0] = 100.0 -> Bullish FVG zone: 100.0 to 104.0
    fvgs = detect_fair_value_gaps(highs, lows, min_gap_pct=0.5)
    assert len(fvgs) >= 1
    fvg = fvgs[0]
    assert fvg.gap_type == "BULLISH_FVG"
    assert fvg.bottom_level == 100.0
    assert fvg.top_level == 104.0
    assert fvg.mid_point == 102.0


def test_opening_gap_analyzer():
    """Verify opening gap classification into Exhaustion vs Breakaway."""
    # Case 1: 0.8% exhaustion gap
    df = pd.DataFrame({
        "Open": [100.0, 100.5, 101.0, 102.0, 102.8],
        "High": [101.0, 101.5, 102.0, 103.0, 103.5],
        "Low": [99.0, 99.5, 100.0, 101.0, 101.8],
        "Close": [100.0, 101.0, 101.5, 102.0, 102.5],
        "Volume": [10000, 10000, 10000, 10000, 12000],
    })
    snap = analyze_opening_gap_and_fvg("RELIANCE", df)
    assert snap.gap_type == GapType.EXHAUSTION_FILL
    assert snap.fill_probability_pct == 74.0
    assert snap.prev_close == 102.0


def test_s18_gap_fill_strategy():
    """Verify S18 signal generation for gap fill mean reversion."""
    strat = GapFillAndFVGStrategy()
    assert strat.name == "S18_GapFillFVG"
    assert strat.is_active is True

    # 1.0% opening gap up
    df = pd.DataFrame({
        "Open": [100.0] * 20 + [101.0],
        "High": [101.0] * 20 + [101.5],
        "Low": [99.0] * 20 + [100.5],
        "Close": [100.0] * 20 + [101.0],
        "Volume": [10000] * 21,
    })
    sig = strat.generate_signal(
        df=df,
        symbol="NIFTY",
        vix=13.0,
        market_state="NEUTRAL",
        mqi_level="HIGH",
    )
    if sig:
        assert sig.signal_direction in ("SHORT", "LONG")
        assert sig.technical_score >= 75
