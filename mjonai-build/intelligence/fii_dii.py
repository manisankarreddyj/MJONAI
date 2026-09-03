"""
Module: intelligence/fii_dii.py
Purpose: SOTA Institutional FII / DII Net Flow Intelligence Engine.
         Analyzes Foreign & Domestic institutional participation in Indian equities,
         FII Index Futures Long/Short Squeeze Ratios, Participant-Wise Derivatives Matrix,
         and 5-Day Cumulative Cash Velocity to determine macro liquidity bias.
"""

from dataclasses import dataclass, field, asdict
import logging
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)


def calculate_fii_long_short_ratio(
    fii_long_contracts: int,
    fii_short_contracts: int,
) -> Dict[str, Any]:
    """
    Calculate FII Index Futures Long-Short Ratio from Participant-Wise Open Interest.
    - Ratio < 0.20 (<20% Longs): Extreme Bearish Positioning -> Imminent Short Squeeze Alert.
    - Ratio > 0.75 (>75% Longs): Extreme Bullish Overheating -> Long Unwinding Correction Alert.
    - Ratio 0.35 - 0.65: Normal balanced institutional stance.
    """
    total = max(1, fii_long_contracts + fii_short_contracts)
    long_pct = round((fii_long_contracts / total) * 100.0, 1)
    short_pct = round((fii_short_contracts / total) * 100.0, 1)
    ratio = round(fii_long_contracts / max(1, fii_short_contracts), 2)

    if long_pct <= 20.0:
        positioning = "EXTREME_OVERSOLD_SQUEEZE_ALERT"
        interpretation = "FIIs heavily short on Index Futures (<=20% Longs). Historically marks explosive short-squeeze bottoms."
    elif long_pct >= 75.0:
        positioning = "OVERBOUGHT_PULLBACK_ALERT"
        interpretation = "FIIs overextended on Index Futures (>=75% Longs). Vulnerable to institutional profit-taking pullbacks."
    elif long_pct >= 55.0:
        positioning = "MODERATELY_BULLISH"
        interpretation = "FIIs holding net long bias on Index Futures."
    elif long_pct <= 40.0:
        positioning = "MODERATELY_BEARISH"
        interpretation = "FIIs holding net short bias on Index Futures."
    else:
        positioning = "BALANCED"
        interpretation = "FIIs neutral on Index Futures positioning."

    return {
        "fii_long_contracts": fii_long_contracts,
        "fii_short_contracts": fii_short_contracts,
        "long_percentage": long_pct,
        "short_percentage": short_pct,
        "long_short_ratio": ratio,
        "positioning": positioning,
        "interpretation": interpretation,
    }


def calculate_cumulative_flow_velocity(
    daily_flows: List[Dict[str, float]],
    window_days: int = 5,
) -> Dict[str, Any]:
    """
    Computes multi-day cumulative FII & DII cash flow momentum in ₹ Crores.
    """
    if not daily_flows:
        return {"fii_5d_net_cr": 0.0, "dii_5d_net_cr": 0.0, "total_5d_net_cr": 0.0, "trend": "NEUTRAL", "window_days": 0}

    recent = daily_flows[-window_days:]
    fii_sum = sum(float(x.get("fii_net_cr", 0.0)) for x in recent)
    dii_sum = sum(float(x.get("dii_net_cr", 0.0)) for x in recent)
    total_sum = round(fii_sum + dii_sum, 2)

    if fii_sum > 5000:
        trend = "STRONG_GLOBAL_ACCUMULATION"
    elif total_sum > 3000:
        trend = "INSTITUTIONAL_ACCUMULATION"
    elif fii_sum < -5000 and dii_sum > 5000:
        trend = "DII_ABSORPTION_OF_FII_OUTFLOW"
    elif total_sum < -3000:
        trend = "INSTITUTIONAL_LIQUIDATION"
    else:
        trend = "BALANCED_CHOP"

    return {
        "fii_5d_net_cr": round(fii_sum, 2),
        "dii_5d_net_cr": round(dii_sum, 2),
        "total_5d_net_cr": total_sum,
        "trend": trend,
        "window_days": len(recent),
    }


@dataclass(frozen=True)
class FIIDIIFlowResult:
    """Immutable contract representing comprehensive FII/DII institutional intelligence."""
    fii_net_cr: float
    dii_net_cr: float
    total_institutional_net_cr: float
    flow_regime: str  # MEGA_BULLISH, GLOBAL_BULLISH, DOMESTIC_ABSORPTION, SEVERE_DRAIN, NEUTRAL
    confidence: int
    recommendation: str
    fii_long_short_ratio: float = 1.0
    fii_long_pct: float = 50.0
    fii_positioning_regime: str = "BALANCED"
    fii_5d_cumulative_cr: float = 0.0
    dii_5d_cumulative_cr: float = 0.0
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def analyze_fii_dii_flow(
    fii_cash_net_cr: float = 0.0,
    dii_cash_net_cr: float = 0.0,
    fii_index_futures_longs: int = 0,
    fii_index_futures_shorts: int = 0,
    historical_daily_flows: Optional[List[Dict[str, float]]] = None,
) -> Dict[str, Any]:
    """
    Evaluate institutional net flows, futures long/short ratios, and multi-day velocity.

    Args:
        fii_cash_net_cr: FII net cash purchase (+) or sale (-) in ₹ Crores
        dii_cash_net_cr: DII net cash purchase (+) or sale (-) in ₹ Crores
        fii_index_futures_longs: Number of FII Long contracts on Index Futures
        fii_index_futures_shorts: Number of FII Short contracts on Index Futures
        historical_daily_flows: Past daily net flows for trend calculation

    Returns:
        Dictionary contract containing flow regime, confidence, squeeze alert, and recommendations.
    """
    total_net = round(fii_cash_net_cr + dii_cash_net_cr, 2)
    reasons = []

    # 1. Evaluate FII Futures Long-Short Squeeze Ratio
    futures_intel = calculate_fii_long_short_ratio(fii_index_futures_longs, fii_index_futures_shorts)
    if fii_index_futures_longs > 0 or fii_index_futures_shorts > 0:
        reasons.append(f"FII Index Futures: {futures_intel['long_percentage']:.1f}% Long ({futures_intel['long_short_ratio']:.2f} L/S Ratio) -> {futures_intel['positioning']}")

    # 2. Multi-Day Velocity
    velocity = calculate_cumulative_flow_velocity(historical_daily_flows or [])
    if velocity["window_days"] > 1:
        reasons.append(f"5-Day Trend: {velocity['trend']} (FII 5D: ₹{velocity['fii_5d_net_cr']:+,.0f} Cr | DII 5D: ₹{velocity['dii_5d_net_cr']:+,.0f} Cr)")

    # 3. Cash Flow Regime Classification
    # Regime 1: Both Institutional groups buying heavily
    if fii_cash_net_cr > 500 and dii_cash_net_cr > 500:
        regime = "MEGA_BULLISH"
        confidence = 90
        recommendation = f"Both FII & DII deploying heavy capital (+₹{total_net:,.0f} Cr). Aggressive Long bias."
        reasons.append(f"FII Net: +₹{fii_cash_net_cr:,.0f} Cr | DII Net: +₹{dii_cash_net_cr:,.0f} Cr")

    # Regime 2: Global money leading
    elif fii_cash_net_cr > 1000:
        regime = "GLOBAL_BULLISH"
        confidence = 80
        recommendation = f"Heavy FII institutional accumulation (+₹{fii_cash_net_cr:,.0f} Cr). Favour high-beta & large-cap momentum."
        reasons.append(f"FII inflows dominant (+₹{fii_cash_net_cr:,.0f} Cr)")

    # Regime 3: DII absorbing FII selling (Classic Indian market pattern)
    elif fii_cash_net_cr < -1000 and dii_cash_net_cr > 1000:
        regime = "DOMESTIC_ABSORPTION"
        confidence = 70
        recommendation = "DIIs providing strong floor against FII selling. Market likely rangebound/defensive; trade stock-specific."
        reasons.append(f"FII Outflow: -₹{abs(fii_cash_net_cr):,.0f} Cr absorbed by DII Inflow: +₹{dii_cash_net_cr:,.0f} Cr")

    # Regime 4: Both institutional groups dumping shares
    elif fii_cash_net_cr < -500 and dii_cash_net_cr < -500:
        regime = "SEVERE_DRAIN"
        confidence = 85
        recommendation = f"Both FII & DII exiting cash (-₹{abs(total_net):,.0f} Cr). High liquidity risk — tighten stops or stay in cash."
        reasons.append(f"Institutional liquidity drain (-₹{abs(total_net):,.0f} Cr total)")

    else:
        regime = "NEUTRAL"
        confidence = 55
        recommendation = "Moderate institutional flows. Let technical chart signals govern position entries."
        reasons.append(f"FII: ₹{fii_cash_net_cr:+,.0f} Cr | DII: ₹{dii_cash_net_cr:+,.0f} Cr")

    # Squeeze Alert Confidence Booster
    if futures_intel["positioning"] == "EXTREME_OVERSOLD_SQUEEZE_ALERT" and regime in ("DOMESTIC_ABSORPTION", "NEUTRAL"):
        confidence = min(95, confidence + 15)
        recommendation += " ⚡ HIGH SHORT-SQUEEZE PROBABILITY (FII <=20% Longs)."

    result = FIIDIIFlowResult(
        fii_net_cr=fii_cash_net_cr,
        dii_net_cr=dii_cash_net_cr,
        total_institutional_net_cr=total_net,
        flow_regime=regime,
        confidence=confidence,
        recommendation=recommendation,
        fii_long_short_ratio=futures_intel["long_short_ratio"],
        fii_long_pct=futures_intel["long_percentage"],
        fii_positioning_regime=futures_intel["positioning"],
        fii_5d_cumulative_cr=velocity["fii_5d_net_cr"],
        dii_5d_cumulative_cr=velocity["dii_5d_net_cr"],
        reasons=reasons,
    )
    return result.to_dict()
