"""
Module: intelligence/market_breadth.py
Purpose: SOTA Market Breadth, Advance-Decline Thrust, McClellan Oscillator,
         and Institutional Distribution Divergence Engine for Indian Equities (NSE 500).
"""

from dataclasses import dataclass, field, asdict
import logging
from typing import Dict, List, Any, Optional, Tuple, Union

logger = logging.getLogger(__name__)


def calculate_advance_decline_ratio(
    advances: int,
    declines: int,
    unchanged: int = 0,
) -> Dict[str, Any]:
    """
    Calculate Advance-Decline Ratio (ADR) and market participation health.
    - ADR > 2.0: Broad-based aggressive buying (Bullish thrust).
    - ADR < 0.5: Broad-based liquidations (Bearish wash).
    """
    total = max(1, advances + declines + unchanged)
    ad_ratio = round(advances / max(1, declines), 2)
    adv_pct = round((advances / total) * 100.0, 1)
    dec_pct = round((declines / total) * 100.0, 1)

    if ad_ratio >= 2.0:
        health = "STRONG_BULLISH_BREADTH"
    elif ad_ratio >= 1.2:
        health = "MILD_BULLISH_BREADTH"
    elif ad_ratio <= 0.5:
        health = "STRONG_BEARISH_BREADTH"
    elif ad_ratio <= 0.8:
        health = "MILD_BEARISH_BREADTH"
    else:
        health = "NEUTRAL_BALANCED_BREADTH"

    return {
        "advances": advances,
        "declines": declines,
        "unchanged": unchanged,
        "ad_ratio": ad_ratio,
        "advances_pct": adv_pct,
        "declines_pct": dec_pct,
        "breadth_health": health,
    }


def calculate_mcclellan_oscillator(
    net_advances_series: List[float],
    fast_period: int = 19,
    slow_period: int = 39,
) -> Dict[str, Any]:
    """
    Calculate McClellan Oscillator = EMA(19, Net Advances) - EMA(39, Net Advances).
    Measures short-to-medium term liquidity thrust.
      - Oscillator > +100: Overbought Breadth Thrust.
      - Oscillator < -100: Oversold Breadth Washout.
    """
    if not net_advances_series or len(net_advances_series) < slow_period:
        # Fallback approximation for shorter series
        latest = net_advances_series[-1] if net_advances_series else 0.0
        return {
            "mcclellan_oscillator": round(latest * 0.1, 2),
            "oscillator_regime": "NEUTRAL",
        }

    # Calculate EMA fast & slow
    alpha_fast = 2.0 / (fast_period + 1.0)
    alpha_slow = 2.0 / (slow_period + 1.0)

    ema_fast = net_advances_series[0]
    ema_slow = net_advances_series[0]

    for val in net_advances_series[1:]:
        ema_fast = (val * alpha_fast) + (ema_fast * (1.0 - alpha_fast))
        ema_slow = (val * alpha_slow) + (ema_slow * (1.0 - alpha_slow))

    mcclellan = round(ema_fast - ema_slow, 2)

    if mcclellan >= 100.0:
        regime = "OVERBOUGHT_BREADTH_THRUST"
    elif mcclellan <= -100.0:
        regime = "OVERSOLD_BREADTH_WASHOUT"
    elif mcclellan >= 30.0:
        regime = "POSITIVE_MOMENTUM"
    elif mcclellan <= -30.0:
        regime = "NEGATIVE_MOMENTUM"
    else:
        regime = "NEUTRAL"

    return {
        "mcclellan_oscillator": mcclellan,
        "oscillator_regime": regime,
    }


def calculate_breadth_divergence(
    index_change_pct: float,
    ad_ratio: float,
) -> Dict[str, Any]:
    """
    Detects critical smart money institutional distribution or accumulation divergences:
      - Bearish Divergence: Index UP (+0.5%+) but ADR < 0.8 (Heavyweights hiding broader selloff).
      - Bullish Divergence: Index DOWN (-0.5%-) but ADR > 1.2 (Broader market accumulating despite index drag).
    """
    if index_change_pct >= 0.50 and ad_ratio < 0.80:
        divergence = "BEARISH_DISTRIBUTION_DIVERGENCE"
        warning = "WARNING: Nifty rising on narrow heavyweight buying while broader market declines. High reversal risk."
    elif index_change_pct <= -0.50 and ad_ratio > 1.20:
        divergence = "BULLISH_ACCUMULATION_DIVERGENCE"
        warning = "OPPORTUNITY: Nifty dragged down by heavyweights while broader market advances. High rebound probability."
    else:
        divergence = "NO_DIVERGENCE_CONFIRMED"
        warning = "Index momentum aligned with broader market breadth."

    return {
        "divergence_type": divergence,
        "divergence_warning": warning,
        "is_divergent": divergence != "NO_DIVERGENCE_CONFIRMED",
    }


@dataclass(frozen=True)
class MarketBreadthResult:
    """Immutable contract representing comprehensive market breadth intelligence."""
    advances: int
    declines: int
    ad_ratio: float
    breadth_health: str
    volume_ratio: float
    mcclellan_oscillator: float
    oscillator_regime: str
    divergence_type: str
    is_divergent: bool
    stocks_above_20ema_pct: float
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def analyze_market_breadth(
    advances: int = 250,
    declines: int = 250,
    advancing_volume: float = 1.0,
    declining_volume: float = 1.0,
    index_change_pct: float = 0.0,
    stocks_above_20ema_pct: float = 50.0,
    historical_net_advances: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    Synthesize complete market breadth, volume ratio, McClellan oscillator, and divergence alerts.

    Args:
        advances: Number of advancing stocks in NSE 500
        declines: Number of declining stocks in NSE 500
        advancing_volume: Total volume traded on advancing stocks
        declining_volume: Total volume traded on declining stocks
        index_change_pct: Benchmark NIFTY 50 change %
        stocks_above_20ema_pct: Percentage of stocks trading above their 20-day EMA
        historical_net_advances: Historical series of (advances - declines) for McClellan calculation

    Returns:
        Dictionary contract containing breadth health, volume ratio, and divergence warnings.
    """
    ad_data = calculate_advance_decline_ratio(advances, declines)
    ad_ratio = ad_data["ad_ratio"]

    # Volume ratio
    vol_ratio = round(advancing_volume / max(0.01, declining_volume), 2)

    # McClellan Oscillator
    net_adv_history = historical_net_advances or [float(advances - declines)]
    mcclellan_data = calculate_mcclellan_oscillator(net_adv_history)

    # Divergence Check
    div_data = calculate_breadth_divergence(index_change_pct, ad_ratio)

    reasons = [
        f"A/D Ratio: {ad_ratio:.2f} ({advances} Advances / {declines} Declines -> {ad_data['breadth_health']})",
        f"Volume Ratio: {vol_ratio:.2f}x buy/sell volume",
        f"McClellan Oscillator: {mcclellan_data['mcclellan_oscillator']:+.1f} ({mcclellan_data['oscillator_regime']})",
        f"Breadth Participation: {stocks_above_20ema_pct:.1f}% stocks > 20 EMA",
    ]

    if div_data["is_divergent"]:
        reasons.append(f"⚡ {div_data['divergence_type']}: {div_data['divergence_warning']}")

    result = MarketBreadthResult(
        advances=advances,
        declines=declines,
        ad_ratio=ad_ratio,
        breadth_health=ad_data["breadth_health"],
        volume_ratio=vol_ratio,
        mcclellan_oscillator=mcclellan_data["mcclellan_oscillator"],
        oscillator_regime=mcclellan_data["oscillator_regime"],
        divergence_type=div_data["divergence_type"],
        is_divergent=div_data["is_divergent"],
        stocks_above_20ema_pct=stocks_above_20ema_pct,
        reasons=reasons,
    )
    return result.to_dict()
