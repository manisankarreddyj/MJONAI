"""
Module: intelligence/gift_nifty.py
Purpose: SOTA Pre-Market Gift Nifty Gap, Opening Sentiment,
         Breakaway vs Exhaustion Gap Classifier, and Global Macro Confluence Engine.
"""

from dataclasses import dataclass, field, asdict
import logging
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)


def classify_gap_type(
    gap_pct: float,
    prev_close: float,
    prev_high: float = 0.0,
    prev_low: float = 0.0,
    is_multi_day_breakout: bool = False,
) -> Dict[str, Any]:
    """
    Classify opening gap behavior and probability of gap fill in the first 60 minutes:
      - BREAKAWAY_GAP: Opening outside multi-day range with momentum (Low fill prob: ~25%, High Trend Day prob: ~75%).
      - EXHAUSTION_GAP: Massive opening gap (>1.2%) after extended trend (High fill prob: ~70%, Trap risk).
      - COMMON_GAP: Minor gap within previous day's trading range (Random walk / Chop).
    """
    abs_gap = abs(gap_pct)

    if abs_gap >= 1.20:
        gap_type = "EXHAUSTION_GAP"
        fill_probability = 70.0
        tactical_rule = "FADE_OR_WAIT: Extended gap prone to opening profit-taking & mean-reversion trap."
    elif is_multi_day_breakout or abs_gap >= 0.40:
        gap_type = "BREAKAWAY_GAP"
        fill_probability = 25.0
        tactical_rule = "TREND_CONTINUATION: High probability of one-way trend day; look for opening range breakout continuation."
    elif abs_gap <= 0.20:
        gap_type = "COMMON_GAP"
        fill_probability = 50.0
        tactical_rule = "RANGEBOUND_CHOP: Trade pure stock-specific technical levels."
    else:
        gap_type = "MILD_PROBING_GAP"
        fill_probability = 45.0
        tactical_rule = "NORMAL_OPEN: Check opening 15-minute high/low before initiating directional momentum."

    return {
        "gap_type": gap_type,
        "gap_magnitude_pct": round(gap_pct, 2),
        "fill_probability_pct": fill_probability,
        "tactical_rule": tactical_rule,
    }


def calculate_global_confluence_score(
    us_futures_pct: float = 0.0,
    crude_oil_change_pct: float = 0.0,
    dxy_dollar_change_pct: float = 0.0,
    asian_indices_pct: float = 0.0,
) -> Dict[str, Any]:
    """
    Compute Global Macro Sentiment Score (0 to 100):
      - US Tech / S&P Futures (+) -> Bullish (+weight)
      - Asian Markets (+) -> Bullish (+weight)
      - Brent Crude Oil (+) -> Bearish for India (-weight)
      - US Dollar Index (+) -> Bearish for Emerging Markets (-weight)
    """
    # Base score = 50 (Neutral)
    score = 50.0

    # 1. US Futures contribution (weight 35%)
    score += (us_futures_pct * 15.0)

    # 2. Asian Indices contribution (weight 25%)
    score += (asian_indices_pct * 10.0)

    # 3. Crude Oil contribution (Inverse for India: -weight 20%)
    score -= (crude_oil_change_pct * 4.0)

    # 4. Dollar Index DXY contribution (Inverse: -weight 20%)
    score -= (dxy_dollar_change_pct * 10.0)

    score_clamped = round(max(5.0, min(95.0, score)), 1)

    if score_clamped >= 65.0:
        climate = "GLOBAL_RISK_ON"
    elif score_clamped <= 35.0:
        climate = "GLOBAL_RISK_OFF"
    else:
        climate = "GLOBAL_NEUTRAL"

    return {
        "global_macro_score": score_clamped,
        "global_climate": climate,
        "us_futures_pct": us_futures_pct,
        "crude_oil_change_pct": crude_oil_change_pct,
        "dxy_dollar_change_pct": dxy_dollar_change_pct,
        "asian_indices_pct": asian_indices_pct,
    }


@dataclass(frozen=True)
class GiftNiftyGapResult:
    """Immutable contract representing the complete pre-market opening intelligence."""
    predicted_gap_pct: float
    predicted_gap_points: float
    opening_bias: str  # STRONG_BULLISH, BULLISH, FLAT, BEARISH, STRONG_BEARISH
    gift_nifty_price: float
    nifty_prev_close: float
    gap_type: str
    fill_probability_pct: float
    global_macro_score: float
    global_climate: str
    recommendation: str
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def analyze_pre_market_gap(
    gift_nifty_price: Optional[float] = None,
    nifty_prev_close: Optional[float] = None,
    prev_high: float = 0.0,
    prev_low: float = 0.0,
    is_multi_day_breakout: bool = False,
    us_futures_pct: float = 0.0,
    crude_oil_change_pct: float = 0.0,
    dxy_dollar_change_pct: float = 0.0,
    asian_indices_pct: float = 0.0,
) -> Dict[str, Any]:
    """
    Analyze pre-market opening gap expectations, gap classification, and global macro confluence.

    Args:
        gift_nifty_price: Current Gift Nifty trading price
        nifty_prev_close: Previous NSE Nifty 50 close
        prev_high: Previous day's high
        prev_low: Previous day's low
        is_multi_day_breakout: Whether gap is breaking out of multi-day consolidation
        us_futures_pct: Overnight US Futures change %
        crude_oil_change_pct: Overnight Brent Crude change %
        dxy_dollar_change_pct: Dollar Index change %
        asian_indices_pct: Asian Markets (Nikkei/Hang Seng) average change %

    Returns:
        Dictionary contract containing opening bias, gap classification, and tactical rules.
    """
    # Safe defaults
    if nifty_prev_close is None or nifty_prev_close <= 0:
        nifty_prev_close = 24500.0

    if gift_nifty_price is None or gift_nifty_price <= 0:
        gift_nifty_price = nifty_prev_close

    gap_points = round(gift_nifty_price - nifty_prev_close, 2)
    gap_pct = round((gap_points / nifty_prev_close) * 100.0, 2)

    # 1. Classify Gap Dynamics
    gap_meta = classify_gap_type(
        gap_pct=gap_pct,
        prev_close=nifty_prev_close,
        prev_high=prev_high,
        prev_low=prev_low,
        is_multi_day_breakout=is_multi_day_breakout,
    )

    # 2. Global Macro Confluence
    global_macro = calculate_global_confluence_score(
        us_futures_pct=us_futures_pct,
        crude_oil_change_pct=crude_oil_change_pct,
        dxy_dollar_change_pct=dxy_dollar_change_pct,
        asian_indices_pct=asian_indices_pct,
    )

    reasons = []

    if gap_pct >= 0.75:
        bias = "STRONG_BULLISH"
        recommendation = f"Strong Gap-Up expected (>+0.75%). {gap_meta['tactical_rule']}"
        reasons.append(f"Gift Nifty trading +{gap_points:.1f} pts (+{gap_pct:.2f}%) above previous close")
    elif gap_pct >= 0.25:
        bias = "BULLISH"
        recommendation = f"Mild Gap-Up (+0.25% to +0.75%). {gap_meta['tactical_rule']}"
        reasons.append(f"Positive pre-market momentum (+{gap_points:.1f} pts)")
    elif gap_pct <= -0.75:
        bias = "STRONG_BEARISH"
        recommendation = f"Strong Gap-Down expected (<-0.75%). {gap_meta['tactical_rule']}"
        reasons.append(f"Gift Nifty trading {gap_points:.1f} pts ({gap_pct:.2f}%) below previous close")
    elif gap_pct <= -0.25:
        bias = "BEARISH"
        recommendation = f"Mild Gap-Down (-0.25% to -0.75%). {gap_meta['tactical_rule']}"
        reasons.append(f"Negative pre-market drift ({gap_points:.1f} pts)")
    else:
        bias = "FLAT"
        recommendation = f"Flat open expected. {gap_meta['tactical_rule']}"
        reasons.append(f"Neutral pre-market drift ({gap_points:+.1f} pts / {gap_pct:+.2f}%)")

    reasons.append(f"Gap Structure: {gap_meta['gap_type']} (Fill Probability: {gap_meta['fill_probability_pct']}%)")
    reasons.append(f"Global Macro Score: {global_macro['global_macro_score']}/100 ({global_macro['global_climate']})")

    result = GiftNiftyGapResult(
        predicted_gap_pct=gap_pct,
        predicted_gap_points=gap_points,
        opening_bias=bias,
        gift_nifty_price=gift_nifty_price,
        nifty_prev_close=nifty_prev_close,
        gap_type=gap_meta["gap_type"],
        fill_probability_pct=gap_meta["fill_probability_pct"],
        global_macro_score=global_macro["global_macro_score"],
        global_climate=global_macro["global_climate"],
        recommendation=recommendation,
        reasons=reasons,
    )
    return result.to_dict()
