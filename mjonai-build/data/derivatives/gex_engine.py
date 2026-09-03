"""
Module: data/derivatives/gex_engine.py
Purpose: SOTA Dealer Gamma Exposure (GEX), Delta Exposure (DEX) & Zero-Gamma Level Engine.
         Calculates aggregate dealer market-making positioning across the entire option chain:
         - Total Market GEX ($ / ₹ Notional per 1% move in underlying)
         - Zero-Gamma Level (The "Gamma Flip" price where market shifts from mean-reversion to trend acceleration)
         - Major Gamma Call/Put Walls (Pinning strikes and mechanical dealer magnets)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

from core.time_utils import now_ist

logger = logging.getLogger(__name__)


def _std_norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * (x ** 2))


def calculate_black_scholes_gamma(
    spot: float,
    strike: float,
    dte_days: float,
    iv: float,
    r: float = 0.07,
) -> float:
    """
    Compute Black-Scholes Gamma (dDelta / dSpot) for a single option contract.
    """
    if spot <= 0.0 or strike <= 0.0:
        return 0.0
    t = max(dte_days, 0.001) / 365.0
    iv_clean = max(iv, 0.001)

    d1 = (math.log(spot / strike) + (r + 0.5 * (iv_clean ** 2)) * t) / (iv_clean * math.sqrt(t))
    gamma = _std_norm_pdf(d1) / (spot * iv_clean * math.sqrt(t))
    return float(gamma)


class GammaRegime(str, Enum):
    POSITIVE_GAMMA = "POSITIVE_GAMMA"  # Dealers Long Gamma: Market is pinned, mean-reverting, low volatility
    NEGATIVE_GAMMA = "NEGATIVE_GAMMA"  # Dealers Short Gamma: Market has explosive volatility and trend acceleration
    NEUTRAL_GAMMA  = "NEUTRAL_GAMMA"   # Near Zero-Gamma boundary line


@dataclass(frozen=True)
class GammaExposureSnapshot:
    """
    Immutable Institutional Gamma Exposure Assessment Contract.
    """
    underlying: str
    spot_price: float
    zero_gamma_level: Optional[float]
    total_gex_crores: float
    call_gex_crores: float
    put_gex_crores: float
    gamma_regime: GammaRegime
    major_call_wall: Optional[float]
    major_put_wall: Optional[float]
    is_in_positive_gamma: bool
    timestamp: datetime
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "underlying": self.underlying,
            "spot_price": self.spot_price,
            "zero_gamma_level": self.zero_gamma_level,
            "total_gex_crores": round(self.total_gex_crores, 2),
            "call_gex_crores": round(self.call_gex_crores, 2),
            "put_gex_crores": round(self.put_gex_crores, 2),
            "gamma_regime": self.gamma_regime.value,
            "major_call_wall": self.major_call_wall,
            "major_put_wall": self.major_put_wall,
            "is_in_positive_gamma": self.is_in_positive_gamma,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
        }


def calculate_gamma_exposure(
    underlying: str,
    spot_price: float,
    strikes: Sequence[float],
    call_oi: Sequence[float],
    put_oi: Sequence[float],
    dte_days: float = 4.0,
    call_iv: Optional[Sequence[float]] = None,
    put_iv: Optional[Sequence[float]] = None,
    default_iv: float = 0.14,
    lot_size: int = 65,
) -> GammaExposureSnapshot:
    """
    Calculate full Dealer Gamma Exposure (GEX) and solve for the Zero-Gamma Level.

    Formula:
        GEX_strike = Spot^2 * Gamma * OI * LotSize * 0.01
        Total GEX = Sum(Call GEX) - Sum(Put GEX)  (Dealers Long Calls / Short Puts)

    Returns:
        GammaExposureSnapshot: Complete dealer positioning assessment.
    """
    now = now_ist()
    strikes_arr = np.array(strikes, dtype=float)
    c_oi_arr = np.array(call_oi, dtype=float)
    p_oi_arr = np.array(put_oi, dtype=float)
    n = len(strikes_arr)

    c_iv_arr = np.array(call_iv, dtype=float) if call_iv is not None else np.full(n, default_iv, dtype=float)
    p_iv_arr = np.array(put_iv, dtype=float) if put_iv is not None else np.full(n, default_iv, dtype=float)

    if n == 0 or spot_price <= 0.0:
        return GammaExposureSnapshot(
            underlying=underlying,
            spot_price=spot_price,
            zero_gamma_level=None,
            total_gex_crores=0.0,
            call_gex_crores=0.0,
            put_gex_crores=0.0,
            gamma_regime=GammaRegime.NEUTRAL_GAMMA,
            major_call_wall=None,
            major_put_wall=None,
            is_in_positive_gamma=True,
            timestamp=now,
            message="No option chain strikes provided for GEX calculation",
        )

    # 1. Compute Strike-by-Strike GEX at current Spot Price
    call_gex_list = []
    put_gex_list = []

    for i in range(n):
        k = strikes_arr[i]
        c_gamma = calculate_black_scholes_gamma(spot_price, k, dte_days, c_iv_arr[i])
        p_gamma = calculate_black_scholes_gamma(spot_price, k, dte_days, p_iv_arr[i])

        # GEX in INR Crores (Spot^2 * Gamma * OI * LotSize * 0.01 / 1e7)
        c_gex = (spot_price ** 2) * c_gamma * c_oi_arr[i] * lot_size * 0.01 / 1e7
        p_gex = (spot_price ** 2) * p_gamma * p_oi_arr[i] * lot_size * 0.01 / 1e7

        call_gex_list.append(c_gex)
        put_gex_list.append(p_gex)

    call_gex_arr = np.array(call_gex_list, dtype=float)
    put_gex_arr = np.array(put_gex_list, dtype=float)

    total_call_gex = float(np.sum(call_gex_arr))
    total_put_gex = float(np.sum(put_gex_arr))
    net_gex = total_call_gex - total_put_gex

    # Find Major Walls
    max_c_idx = int(np.argmax(call_gex_arr)) if len(call_gex_arr) > 0 else 0
    max_p_idx = int(np.argmax(put_gex_arr)) if len(put_gex_arr) > 0 else 0
    call_wall = float(strikes_arr[max_c_idx]) if len(strikes_arr) > 0 else None
    put_wall = float(strikes_arr[max_p_idx]) if len(strikes_arr) > 0 else None

    # 2. Solve for Zero-Gamma Level across price sweep (+/- 8% from Spot)
    def _evaluate_net_gex_at_price(test_p: float) -> float:
        tot_c = 0.0
        tot_p = 0.0
        for i in range(n):
            k = strikes_arr[i]
            cg = calculate_black_scholes_gamma(test_p, k, dte_days, c_iv_arr[i])
            pg = calculate_black_scholes_gamma(test_p, k, dte_days, p_iv_arr[i])
            tot_c += (test_p ** 2) * cg * c_oi_arr[i] * lot_size * 0.01
            tot_p += (test_p ** 2) * pg * p_oi_arr[i] * lot_size * 0.01
        return tot_c - tot_p

    zero_gamma: Optional[float] = None
    price_grid = np.linspace(spot_price * 0.90, spot_price * 1.10, 41)
    gex_curve = [_evaluate_net_gex_at_price(p) for p in price_grid]

    for i in range(len(gex_curve) - 1):
        if (gex_curve[i] <= 0 and gex_curve[i + 1] >= 0) or (gex_curve[i] >= 0 and gex_curve[i + 1] <= 0):
            # Linear interpolation for zero root
            p0, p1 = price_grid[i], price_grid[i + 1]
            g0, g1 = gex_curve[i], gex_curve[i + 1]
            if g1 != g0:
                zero_gamma = round(float(p0 - g0 * (p1 - p0) / (g1 - g0)), 1)
                break

    if zero_gamma is None:
        zero_gamma = round(spot_price, 1)

    # 3. Classify Gamma Regime
    is_pos = net_gex >= 0.0
    if net_gex > 25.0:
        regime = GammaRegime.POSITIVE_GAMMA
        msg = f"Positive Gamma Regime (Net GEX: +₹{net_gex:.1f} Cr | Spot > Zero-Gamma {zero_gamma:.0f} | Low Volatility Mean-Reversion Mode)"
    elif net_gex < -25.0:
        regime = GammaRegime.NEGATIVE_GAMMA
        msg = f"Negative Gamma Regime (Net GEX: -₹{abs(net_gex):.1f} Cr | Spot < Zero-Gamma {zero_gamma:.0f} | High Volatility Trend Acceleration Mode)"
    else:
        regime = GammaRegime.NEUTRAL_GAMMA
        msg = f"Neutral Gamma Zone (Net GEX: ₹{net_gex:+.1f} Cr | Zero-Gamma {zero_gamma:.0f})"

    return GammaExposureSnapshot(
        underlying=underlying.upper(),
        spot_price=spot_price,
        zero_gamma_level=zero_gamma,
        total_gex_crores=net_gex,
        call_gex_crores=total_call_gex,
        put_gex_crores=total_put_gex,
        gamma_regime=regime,
        major_call_wall=call_wall,
        major_put_wall=put_wall,
        is_in_positive_gamma=is_pos,
        timestamp=now,
        message=msg,
    )
