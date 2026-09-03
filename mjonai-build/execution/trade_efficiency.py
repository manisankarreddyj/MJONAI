"""
Module: execution/trade_efficiency.py
Purpose: SOTA Institutional Trade Efficiency, MAE/MFE Diagnostic & Alpha Retention Analytics.
         Implements quantitative metrics used by top prop desks to evaluate trade lifecycle capture:
           1. Profit Capture Efficiency (PCE) = Realized PnL / MFE (Max Favorable Excursion)
           2. Adverse Risk Ratio (ARR) = MAE / Initial Risk Distance
           3. Trailing Stop Efficiency (TSE) = Realized Exit Price / Peak Price
           4. Execution Quality Classification (PERFECT_RUN, PREMATURE_EXIT, SUBOPTIMAL_HOLD, CONTROLLED_LOSS)
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import logging
import math
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TradeEfficiencyMetrics:
    """Immutable contract containing institutional post-trade execution diagnostics."""
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    initial_sl: float
    mfe_price: float
    mae_price: float
    realized_pnl_pts: float
    mfe_potential_pts: float
    mae_risk_pts: float
    profit_capture_efficiency_pct: float   # Realized / MFE * 100
    adverse_risk_ratio: float              # MAE / Initial SL distance
    trailing_exit_efficiency_pct: float    # Exit / MFE price * 100
    classification: str                    # PERFECT_RUN, PREMATURE_EXIT, SUBOPTIMAL_HOLD, CONTROLLED_LOSS
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calculate_trade_efficiency(
    symbol: str,
    entry_price: float,
    exit_price: float,
    initial_sl: float,
    mfe_price: Optional[float] = None,
    mae_price: Optional[float] = None,
    direction: str = "LONG",
) -> TradeEfficiencyMetrics:
    """
    Compute comprehensive institutional trade efficiency and MAE/MFE analytics.
    """
    e = max(0.01, float(entry_price))
    x = max(0.01, float(exit_price))
    sl = max(0.01, float(initial_sl))
    dir_u = str(direction).strip().upper()
    is_long = dir_u in ("LONG", "BUY")

    # If peak/trough not provided, bound with entry and exit
    if is_long:
        mfe_p = max(e, float(mfe_price if mfe_price is not None else max(e, x)))
        mae_p = min(e, float(mae_price if mae_price is not None else min(e, x)))
        realized_pts = x - e
        mfe_pts = max(1e-6, mfe_p - e)
        mae_pts = max(0.0, e - mae_p)
        init_risk = max(1e-6, e - sl)
    else:
        mfe_p = min(e, float(mfe_price if mfe_price is not None else min(e, x)))
        mae_p = max(e, float(mae_price if mae_price is not None else max(e, x)))
        realized_pts = e - x
        mfe_pts = max(1e-6, e - mfe_p)
        mae_pts = max(0.0, mae_p - e)
        init_risk = max(1e-6, sl - e)

    # 1. Profit Capture Efficiency (PCE %)
    if realized_pts > 0:
        pce_pct = min(100.0, max(0.0, (realized_pts / mfe_pts) * 100.0))
    else:
        pce_pct = 0.0

    # 2. Adverse Risk Ratio (ARR) - How deep did it go into the stop?
    arr = round(mae_pts / init_risk, 3)

    # 3. Trailing Exit Efficiency
    if is_long:
        tse_pct = round((x / mfe_p) * 100.0, 2) if mfe_p > 0 else 100.0
    else:
        tse_pct = round((mfe_p / x) * 100.0, 2) if x > 0 else 100.0

    # 4. Institutional Trade Classification
    if realized_pts > 0:
        if pce_pct >= 75.0:
            classification = "PERFECT_RUN"
            recommendation = "Optimal exit capture; minimal money left on the table."
        elif pce_pct >= 40.0:
            classification = "ACCEPTABLE_CAPTURE"
            recommendation = "Decent profit capture; consider tighter trailing ratchet on final tranche."
        else:
            classification = "SUBOPTIMAL_HOLD"
            recommendation = "Large MFE surrendered; trailing stop was too loose or target not taken."
    else:
        if arr <= 1.05:
            classification = "CONTROLLED_LOSS"
            recommendation = "Disciplined stop-loss execution within initial risk parameter."
        else:
            classification = "CATASTROPHIC_SLIPPAGE"
            recommendation = "Stop loss slipped beyond initial risk; investigate gap risk or market order execution."

    return TradeEfficiencyMetrics(
        symbol=symbol.strip().upper(),
        direction=dir_u,
        entry_price=round(e, 2),
        exit_price=round(x, 2),
        initial_sl=round(sl, 2),
        mfe_price=round(mfe_p, 2),
        mae_price=round(mae_p, 2),
        realized_pnl_pts=round(realized_pts, 2),
        mfe_potential_pts=round(mfe_pts, 2),
        mae_risk_pts=round(mae_pts, 2),
        profit_capture_efficiency_pct=round(pce_pct, 2),
        adverse_risk_ratio=arr,
        trailing_exit_efficiency_pct=tse_pct,
        classification=classification,
        recommendation=recommendation,
    )
