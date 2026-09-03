"""
Module: options/oi_scanner.py
Purpose: SOTA Institutional Open Interest (OI) & Smart Money Flow Engine.
         Detects 4-Quadrant Derivative Positioning (Long/Short Buildup & Covering),
         Dealer Gamma Exposure (GEX), Gamma Flip Volatility Thresholds,
         and Major Strike Support/Resistance Walls for Indian Indices and Equities.
"""

from dataclasses import dataclass, field, asdict
import logging
from typing import Dict, List, Any, Optional, Tuple, Union

logger = logging.getLogger(__name__)


def classify_oi_buildup(price_change_pct: float, oi_change_pct: float) -> str:
    """
    Classify market positioning into standard institutional 4-Quadrant matrix:
      - Long Buildup: Price UP + OI UP (Aggressive long creation)
      - Short Buildup: Price DOWN + OI UP (Aggressive short creation)
      - Short Covering: Price UP + OI DOWN (Bear capitulation / short squeeze)
      - Long Unwinding: Price DOWN + OI DOWN (Bull profit-taking / stop-outs)
    """
    if abs(price_change_pct) < 0.10 and abs(oi_change_pct) < 1.0:
        return "NEUTRAL"

    if price_change_pct > 0:
        return "LONG_BUILDUP" if oi_change_pct >= 0 else "SHORT_COVERING"
    else:
        return "SHORT_BUILDUP" if oi_change_pct >= 0 else "LONG_UNWINDING"


def calculate_gamma_exposure(
    spot: float,
    chain_data: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Calculate Dealer Gamma Exposure (GEX) across option strikes.
    - Positive GEX: Market makers are long gamma (Volatility dampening / mean-reverting pin)
    - Negative GEX: Market makers are short gamma (Volatility explosion / trend acceleration)
    - Gamma Flip: The strike where aggregate dealer gamma transitions from positive to negative.
    """
    if not chain_data or spot <= 0:
        return {"total_gex": 0.0, "gamma_regime": "NEUTRAL", "gamma_flip_strike": spot}

    total_call_gamma = 0.0
    total_put_gamma = 0.0
    strikes_gex = []

    for item in chain_data:
        strike = float(item.get("strike", 0))
        ce_oi = float(item.get("ce_oi", 0))
        pe_oi = float(item.get("pe_oi", 0))
        ce_gamma = float(item.get("ce_gamma", 0.0001))
        pe_gamma = float(item.get("pe_gamma", 0.0001))

        call_gex = ce_oi * ce_gamma * spot * 0.01
        put_gex = pe_oi * pe_gamma * spot * 0.01

        net_strike_gex = call_gex - put_gex
        strikes_gex.append((strike, net_strike_gex))

        total_call_gamma += call_gex
        total_put_gamma += put_gex

    total_net_gex = round(total_call_gamma - total_put_gamma, 2)
    gamma_regime = "POSITIVE_GAMMA" if total_net_gex > 0 else "NEGATIVE_GAMMA"

    # Find Gamma Flip strike (where cumulative GEX crosses zero)
    gamma_flip_strike = spot
    for strike, gex in sorted(strikes_gex, key=lambda x: x[0]):
        if gex >= 0:
            gamma_flip_strike = strike
            break

    return {
        "total_gex": total_net_gex,
        "gamma_regime": gamma_regime,
        "gamma_flip_strike": gamma_flip_strike,
    }


@dataclass(frozen=True)
class OIScanResult:
    """Immutable contract representing the complete Open Interest anomaly scan."""
    symbol: str
    sentiment: str
    confidence: int
    call_resistance_wall: float
    put_support_wall: float
    net_ce_oi_change: int
    net_pe_oi_change: int
    buildup_type: str
    gamma_regime: str
    total_gex: float
    gamma_flip_strike: float
    ce_unwinding_strikes: List[float] = field(default_factory=list)
    pe_unwinding_strikes: List[float] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def scan_oi_anomalies(
    symbol: str,
    chain_data: List[Dict[str, Any]],
    spot_price: float,
    price_change_pct: float = 0.0,
) -> Dict[str, Any]:
    """
    Analyze Open Interest (OI) distribution, net changes, and dealer gamma positioning.

    Args:
        symbol: Underlying symbol (e.g. "NIFTY", "BANKNIFTY", "RELIANCE")
        chain_data: List of strike dicts with:
                    'strike', 'ce_oi', 'pe_oi', 'ce_change_oi', 'pe_change_oi', 'ce_volume', 'pe_volume'
        spot_price: Current underlying spot price
        price_change_pct: Day's underlying spot percentage change

    Returns:
        Dictionary contract containing institutional sentiment, buildup type, GEX, and walls.
    """
    if not chain_data or spot_price <= 0:
        return OIScanResult(
            symbol=symbol,
            sentiment="NEUTRAL",
            confidence=50,
            call_resistance_wall=0.0,
            put_support_wall=0.0,
            net_ce_oi_change=0,
            net_pe_oi_change=0,
            buildup_type="NEUTRAL",
            gamma_regime="NEUTRAL",
            total_gex=0.0,
            gamma_flip_strike=0.0,
            reasons=["No option chain data available"],
        ).to_dict()

    # 1. Total OI changes
    net_ce_oi_change = sum(float(item.get("ce_change_oi", 0)) for item in chain_data)
    net_pe_oi_change = sum(float(item.get("pe_change_oi", 0)) for item in chain_data)
    total_oi_change = net_ce_oi_change + net_pe_oi_change

    # 2. 4-Quadrant Buildup
    buildup_type = classify_oi_buildup(price_change_pct, total_oi_change)

    # 3. Find Major Support and Resistance Strike Walls (Highest Cumulative OI)
    max_ce_strike = max(chain_data, key=lambda x: float(x.get("ce_oi", 0)))["strike"]
    max_pe_strike = max(chain_data, key=lambda x: float(x.get("pe_oi", 0)))["strike"]

    # 4. Detect Unwinding (Negative Change in OI)
    ce_unwinding_strikes = [
        float(item["strike"]) for item in chain_data if float(item.get("ce_change_oi", 0)) < -1000
    ]
    pe_unwinding_strikes = [
        float(item["strike"]) for item in chain_data if float(item.get("pe_change_oi", 0)) < -1000
    ]

    # 5. Gamma Exposure Analytics
    gex_data = calculate_gamma_exposure(spot_price, chain_data)

    reasons = []
    sentiment = "NEUTRAL"
    confidence = 50

    # Rule 1: Aggressive Bullish Flow (Put Writing + Call Unwinding)
    if net_pe_oi_change > 0 and net_ce_oi_change < 0:
        sentiment = "STRONG_BULLISH"
        confidence = 85
        reasons.append(
            f"Institutional Call Unwinding ({abs(net_ce_oi_change):,.0f} contracts) "
            f"+ Put Writing (+{net_pe_oi_change:,.0f} contracts)"
        )
    elif net_pe_oi_change > (net_ce_oi_change * 1.5):
        sentiment = "BULLISH"
        confidence = 75
        reasons.append(f"Heavy Put Writing dominance (+{net_pe_oi_change:,.0f} PE vs +{net_ce_oi_change:,.0f} CE)")

    # Rule 2: Aggressive Bearish Flow (Call Writing + Put Unwinding)
    elif net_ce_oi_change > 0 and net_pe_oi_change < 0:
        sentiment = "STRONG_BEARISH"
        confidence = 85
        reasons.append(
            f"Institutional Put Unwinding ({abs(net_pe_oi_change):,.0f} contracts) "
            f"+ Call Writing (+{net_ce_oi_change:,.0f} contracts)"
        )
    elif net_ce_oi_change > (net_pe_oi_change * 1.5):
        sentiment = "BEARISH"
        confidence = 75
        reasons.append(f"Heavy Call Writing dominance (+{net_ce_oi_change:,.0f} CE vs +{net_pe_oi_change:,.0f} PE)")
    else:
        reasons.append("Balanced Call/Put OI additions — rangebound expectations")

    reasons.append(f"Major Resistance Wall: ₹{max_ce_strike} CE | Major Support Wall: ₹{max_pe_strike} PE")
    reasons.append(f"Positioning: {buildup_type} | Dealer Gamma: {gex_data['gamma_regime']}")

    result = OIScanResult(
        symbol=symbol,
        sentiment=sentiment,
        confidence=confidence,
        call_resistance_wall=float(max_ce_strike),
        put_support_wall=float(max_pe_strike),
        net_ce_oi_change=int(net_ce_oi_change),
        net_pe_oi_change=int(net_pe_oi_change),
        buildup_type=buildup_type,
        gamma_regime=gex_data["gamma_regime"],
        total_gex=gex_data["total_gex"],
        gamma_flip_strike=gex_data["gamma_flip_strike"],
        ce_unwinding_strikes=ce_unwinding_strikes,
        pe_unwinding_strikes=pe_unwinding_strikes,
        reasons=reasons,
    )
    return result.to_dict()
