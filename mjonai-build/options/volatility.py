"""
Module: options/volatility.py
Purpose: SOTA Institutional Volatility Surface, IV Rank (IVR), IV Percentile (IVP),
         Term Structure (Contango/Backwardation), and Event IV Crush Engine.
"""

from dataclasses import dataclass, field, asdict
import logging
from typing import Dict, List, Any, Optional, Tuple, Union

logger = logging.getLogger(__name__)


def calculate_iv_rank(current_iv: float, min_iv: float, max_iv: float) -> float:
    """
    Calculate Implied Volatility Rank (IVR).
    Measures where current IV lies relative to its 52-week high and low.
    Formula: IVR = (Current IV - Min IV) / (Max IV - Min IV) * 100
    """
    if max_iv <= min_iv or current_iv <= 0:
        return 50.0

    clipped_iv = max(min_iv, min(max_iv, current_iv))
    ivr = ((clipped_iv - min_iv) / (max_iv - min_iv)) * 100.0
    return round(ivr, 2)


def calculate_iv_percentile(current_iv: float, historical_iv_series: List[float]) -> float:
    """
    Calculate Implied Volatility Percentile (IVP).
    Measures the percentage of trading days in the past year where IV was lower than current IV.
    """
    if not historical_iv_series or current_iv <= 0:
        return 50.0

    valid_series = [x for x in historical_iv_series if x is not None and x > 0]
    if not valid_series:
        return 50.0

    count_lower = sum(1 for iv in valid_series if iv < current_iv)
    ivp = (count_lower / len(valid_series)) * 100.0
    return round(ivp, 2)


def classify_volatility_regime(
    iv_percentile: float,
    vix: float = 15.0,
) -> Dict[str, Any]:
    """
    Classify volatility regime to guide options strategy selection.
      - LOW_VOL (<30% IVP): Premium is cheap -> Favor Option Buying & Long Gamma.
      - MEDIUM_VOL (30-70% IVP): Balanced -> Favor Vertical Spreads.
      - HIGH_VOL (>70% IVP): Premium is rich -> Favor Option Writing, S09 Theta Selling, Iron Condors.
      - EXTREME_VOL (VIX > 24): High tail risk -> Favor wide-winged defined risk spreads only.
    """
    if vix >= 24.0:
        regime = "EXTREME_VOLATILITY"
        recommended_action = "DEFINED_RISK_SPREADS_ONLY"
        bias = "SHORT_VEGA"
    elif iv_percentile >= 70.0:
        regime = "HIGH_VOLATILITY"
        recommended_action = "OPTION_WRITING_THETA_DECAY"
        bias = "SHORT_VEGA"
    elif iv_percentile <= 30.0:
        regime = "LOW_VOLATILITY"
        recommended_action = "OPTION_BUYING_MOMENTUM"
        bias = "LONG_VEGA"
    else:
        regime = "MEDIUM_VOLATILITY"
        recommended_action = "BALANCED_VERTICAL_SPREADS"
        bias = "NEUTRAL_VEGA"

    return {
        "regime": regime,
        "recommended_action": recommended_action,
        "vega_bias": bias,
        "iv_percentile": iv_percentile,
        "vix": vix,
    }


def calculate_iv_crush(
    pre_event_iv: float,
    expected_crush_pct: float = 0.35,
) -> Dict[str, float]:
    """
    Quantifies expected Implied Volatility collapse post-binary event (Earnings, Budget, RBI Policy).
    E.g. 35% IV crush drops IV from 40% -> 26%.
    """
    if pre_event_iv <= 0:
        return {"post_event_iv": 0.15, "iv_drop": 0.0}

    post_iv = round(pre_event_iv * (1.0 - expected_crush_pct), 4)
    iv_drop = round(pre_event_iv - post_iv, 4)

    return {
        "pre_event_iv": pre_event_iv,
        "post_event_iv": max(0.08, post_iv),
        "iv_drop_absolute": iv_drop,
        "crush_pct": round(expected_crush_pct * 100.0, 1),
    }


def analyze_volatility_term_structure(
    near_term_iv: float,
    next_term_iv: float,
) -> Dict[str, Any]:
    """
    Analyze Volatility Term Structure (Near-term weekly vs Next-term monthly).
      - Contango (Next > Near): Normal market state (low panic).
      - Backwardation / Inversion (Near > Next): Immediate market distress / event risk priced in.
    """
    if near_term_iv <= 0 or next_term_iv <= 0:
        return {"structure": "NORMAL_CONTANGO", "spread_bps": 0.0}

    diff = near_term_iv - next_term_iv
    spread_bps = round(diff * 10_000, 1)

    if diff > 0.02:  # Weekly IV > Monthly by > 2%
        structure = "BACKWARDATION_INVERTED"
        description = "High near-term event risk / panic pricing"
    elif diff < -0.01:
        structure = "CONTANGO_NORMAL"
        description = "Normal upward-sloping volatility term structure"
    else:
        structure = "FLAT"
        description = "Flat volatility term structure across expiries"

    return {
        "structure": structure,
        "near_term_iv": near_term_iv,
        "next_term_iv": next_term_iv,
        "spread_bps": spread_bps,
        "description": description,
    }


@dataclass(frozen=True)
class VolatilitySkewResult:
    """Immutable contract representing the Volatility Smile & Skew analysis."""
    put_call_skew_ratio: float
    smile_curvature_pct: float
    skew_regime: str  # "STEEP_PUT_SKEW", "NORMAL_INDEX_SKEW", "FLAT_BALANCED_SKEW", "CALL_EUPHORIA_INVERTED_SKEW"
    call_25d_iv: float
    put_25d_iv: float
    atm_iv: float
    recommended_strike_bias: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calculate_volatility_skew(
    call_25d_iv: float,
    put_25d_iv: float,
    atm_iv: float,
) -> VolatilitySkewResult:
    """
    Quantifies Options Volatility Skew (25-Delta Put IV vs 25-Delta Call IV)
    and Smile Curvature relative to At-The-Money (ATM) IV.

    Formulas:
      - Skew Ratio = Put_25D_IV / Call_25D_IV
      - Smile Curvature = [(Put_25D_IV + Call_25D_IV) / 2] - ATM_IV
    """
    if call_25d_iv <= 0 or put_25d_iv <= 0 or atm_iv <= 0:
        return VolatilitySkewResult(
            put_call_skew_ratio=1.15,
            smile_curvature_pct=0.0,
            skew_regime="NORMAL_INDEX_SKEW",
            call_25d_iv=max(0.10, call_25d_iv),
            put_25d_iv=max(0.10, put_25d_iv),
            atm_iv=max(0.10, atm_iv),
            recommended_strike_bias="SYMMETRIC_STRANGLE",
        )

    skew_ratio = round(put_25d_iv / call_25d_iv, 3)
    curvature = round(((put_25d_iv + call_25d_iv) / 2.0 - atm_iv) * 100.0, 2)

    if skew_ratio > 1.35:
        skew_regime = "STEEP_PUT_SKEW"
        bias = "ASYMMETRIC_OTM_PUT_WIDER_OR_IRON_CONDOR"
    elif skew_ratio >= 1.10:
        skew_regime = "NORMAL_INDEX_SKEW"
        bias = "SYMMETRIC_STRANGLE"
    elif skew_ratio >= 0.95:
        skew_regime = "FLAT_BALANCED_SKEW"
        bias = "BALANCED_STRANGLE_OR_VERTICAL_SPREAD"
    else:
        skew_regime = "CALL_EUPHORIA_INVERTED_SKEW"
        bias = "ASYMMETRIC_OTM_CALL_WIDER_OR_BULL_CALL_SPREAD"

    return VolatilitySkewResult(
        put_call_skew_ratio=skew_ratio,
        smile_curvature_pct=curvature,
        skew_regime=skew_regime,
        call_25d_iv=round(call_25d_iv, 4),
        put_25d_iv=round(put_25d_iv, 4),
        atm_iv=round(atm_iv, 4),
        recommended_strike_bias=bias,
    )


def get_strike_delta_adjustment(
    skew_ratio: float,
    base_delta: float = 0.20,
) -> Tuple[float, float]:
    """
    Dynamically offsets short option strike deltas (Call Delta, Put Delta) based on Volatility Skew.
    
    Returns:
        (target_call_delta, target_put_delta)
    """
    if skew_ratio > 1.35:
        # Steep downside fear: push Put further OTM (e.g. 0.12 delta) and pull Call closer (e.g. 0.24 delta)
        return (round(min(0.30, base_delta + 0.04), 2), round(max(0.10, base_delta - 0.08), 2))
    elif skew_ratio < 0.95:
        # Call frenzy: push Call further OTM and pull Put closer
        return (round(max(0.10, base_delta - 0.08), 2), round(min(0.30, base_delta + 0.04), 2))
    else:
        # Normal symmetric market
        return (round(base_delta, 2), round(base_delta, 2))


@dataclass(frozen=True)
class VolatilityRegimeResult:
    """Immutable contract representing the complete volatility environment analysis."""
    symbol: str
    current_iv: float
    iv_rank: float
    iv_percentile: float
    regime: str
    recommended_action: str
    vega_bias: str
    term_structure: str
    vix: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

