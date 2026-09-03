"""
Module: intelligence/sector_rotation.py
Purpose: SOTA NSE Sectoral Relative Strength, Relative Rotation Graphs (RRG),
         Defensive vs Cyclical Breadth, and Strategy Confidence Multiplier Engine.
"""

from dataclasses import dataclass, field, asdict
import logging
from typing import Dict, List, Any, Optional, Tuple, Union

logger = logging.getLogger(__name__)

SECTOR_INDICES: Dict[str, str] = {
    "BANK": "^NSEBANK",
    "IT": "^CNXIT",
    "AUTO": "^CNXAUTO",
    "PHARMA": "^CNXPHARMA",
    "FMCG": "^CNXFMCG",
    "METAL": "^CNXMETAL",
    "ENERGY": "^CNXENERGY",
    "REALTY": "^CNXREALTY",
    "PSU_BANK": "^CNXPSUBANK",
    "FIN_SERVICE": "^CNXFIN",
    "INFRA": "^CNXINFRA",
}

# Defensive vs Cyclical groupings for macro market regime detection
DEFENSIVE_SECTORS = {"IT", "PHARMA", "FMCG"}
CYCLICAL_SECTORS = {"AUTO", "METAL", "REALTY", "BANK", "PSU_BANK", "INFRA"}


def calculate_rrg_quadrant(rs_ratio: float, rs_momentum: float) -> str:
    """
    Classify sector into Julius de Kempenaer's Relative Rotation Graph (RRG) 4-Quadrant phase space:
      - LEADING (RS-Ratio >= 100, RS-Mom >= 100): Outperforming with accelerating momentum.
      - WEAKENING (RS-Ratio >= 100, RS-Mom < 100): Outperforming with decelerating momentum.
      - LAGGING (RS-Ratio < 100, RS-Mom < 100): Underperforming with decelerating momentum.
      - IMPROVING (RS-Ratio < 100, RS-Mom >= 100): Underperforming but momentum turning UP (Early accumulation).
    """
    if rs_ratio >= 100.0:
        return "LEADING" if rs_momentum >= 100.0 else "WEAKENING"
    else:
        return "IMPROVING" if rs_momentum >= 100.0 else "LAGGING"


def get_sector_confidence_multiplier(rrg_quadrant: str) -> float:
    """
    Returns strategy conviction multiplier based on sector RRG quadrant:
      - LEADING: +15% boost (1.15x)
      - IMPROVING: +10% boost (1.10x)
      - WEAKENING: Neutral (1.00x)
      - LAGGING: -20% penalty (0.80x)
    """
    quad = str(rrg_quadrant or "").upper().strip()
    if quad == "LEADING":
        return 1.15
    elif quad == "IMPROVING":
        return 1.10
    elif quad == "WEAKENING":
        return 1.00
    elif quad == "LAGGING":
        return 0.80
    return 1.00


def calculate_defensive_vs_cyclical_breadth(sector_returns: Dict[str, float]) -> Dict[str, Any]:
    """
    Calculates the Defensive vs Cyclical market participation breadth:
      - Cyclical Dominance (Cyclicals > Defensives) -> Strong Risk-On Bull Market.
      - Defensive Dominance (Defensives > Cyclicals) -> Cautious / Distribution / Risk-Off Market.
    """
    if not sector_returns:
        return {"market_breadth": "BALANCED", "cyclical_avg": 0.0, "defensive_avg": 0.0, "spread": 0.0}

    def_rets = [ret for sec, ret in sector_returns.items() if sec in DEFENSIVE_SECTORS]
    cyc_rets = [ret for sec, ret in sector_returns.items() if sec in CYCLICAL_SECTORS]

    avg_def = round(sum(def_rets) / max(1, len(def_rets)), 2)
    avg_cyc = round(sum(cyc_rets) / max(1, len(cyc_rets)), 2)
    spread = round(avg_cyc - avg_def, 2)

    if spread >= 0.75:
        breadth = "AGGRESSIVE_RISK_ON_CYCLICAL_DOMINANCE"
    elif spread <= -0.75:
        breadth = "DEFENSIVE_ROTATION_RISK_OFF"
    else:
        breadth = "BALANCED_BROAD_PARTICIPATION"

    return {
        "market_breadth": breadth,
        "cyclical_avg_return_pct": avg_cyc,
        "defensive_avg_return_pct": avg_def,
        "spread_pct": spread,
    }


@dataclass(frozen=True)
class SectorRotationResult:
    """Immutable contract representing comprehensive sector rotation intelligence."""
    leading_sectors: List[str]
    improving_sectors: List[str]
    weakening_sectors: List[str]
    lagging_sectors: List[str]
    rotating_into: List[str]
    top_sector_pick: str
    market_breadth: str
    sector_rankings: List[Dict[str, Any]]
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def analyze_sector_rotation(
    sector_performance_dict: Optional[Dict[str, float]] = None,
    benchmark_return_pct: float = 0.0,
    sector_momentum_dict: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Rank sectors by relative strength, calculate RRG 4-quadrant positioning,
    and compute defensive vs cyclical breadth.

    Args:
        sector_performance_dict: dict mapping sector name to recent return % (e.g. {'IT': 2.5, 'BANK': 1.1})
        benchmark_return_pct: Nifty 50 return % over the same period
        sector_momentum_dict: dict mapping sector name to momentum ROC %

    Returns:
        Dictionary contract containing RRG quadrants, rankings, and multipliers.
    """
    if not sector_performance_dict:
        sector_performance_dict = {
            "BANK": 0.5,
            "IT": 1.2,
            "AUTO": 0.8,
            "PHARMA": 0.2,
            "FMCG": -0.3,
            "METAL": 1.5,
            "ENERGY": 0.1,
            "REALTY": 2.0,
            "PSU_BANK": 0.9,
        }

    if not sector_momentum_dict:
        # Default momentum proxy centered around 100
        sector_momentum_dict = {sec: round(100.0 + (ret - benchmark_return_pct) * 2.0, 2) for sec, ret in sector_performance_dict.items()}

    ranked = []
    leading = []
    improving = []
    weakening = []
    lagging = []

    for sector, ret in sector_performance_dict.items():
        excess = round(ret - benchmark_return_pct, 2)
        # RS-Ratio normalized around 100
        rs_ratio = round(100.0 + excess * 5.0, 2)
        rs_mom = sector_momentum_dict.get(sector, 100.0)

        quadrant = calculate_rrg_quadrant(rs_ratio, rs_mom)
        multiplier = get_sector_confidence_multiplier(quadrant)

        item = {
            "sector": sector,
            "return_pct": ret,
            "relative_strength": excess,
            "rs_ratio": rs_ratio,
            "rs_momentum": rs_mom,
            "rrg_quadrant": quadrant,
            "confidence_multiplier": multiplier,
            "status": "OUTPERFORMING" if excess > 0 else "UNDERPERFORMING",
        }
        ranked.append(item)

        if quadrant == "LEADING":
            leading.append(sector)
        elif quadrant == "IMPROVING":
            improving.append(sector)
        elif quadrant == "WEAKENING":
            weakening.append(sector)
        else:
            lagging.append(sector)

    # Sort descending by relative strength
    ranked.sort(key=lambda x: (x["relative_strength"], x["rs_momentum"]), reverse=True)

    top_pick = ranked[0]["sector"] if ranked else "NIFTY"
    rotating_into = (leading + improving)[:3]

    # Breadth analytics
    breadth = calculate_defensive_vs_cyclical_breadth(sector_performance_dict)

    reasons = [
        f"Top Leading Sector: {top_pick} ({ranked[0]['relative_strength']:+.2f}% vs Nifty | Quadrant: {ranked[0]['rrg_quadrant']})" if ranked else "Neutral",
        f"Capital Accumulation Focus: {', '.join(rotating_into) if rotating_into else 'Broad Market'}",
        f"Macro Sector Breadth: {breadth['market_breadth']} (Cyclical vs Defensive Spread: {breadth['spread_pct']:+.2f}%)",
    ]

    result = SectorRotationResult(
        leading_sectors=leading,
        improving_sectors=improving,
        weakening_sectors=weakening,
        lagging_sectors=lagging,
        rotating_into=rotating_into,
        top_sector_pick=top_pick,
        market_breadth=breadth["market_breadth"],
        sector_rankings=ranked,
        reasons=reasons,
    )
    return result.to_dict()
