"""
Module: data/fundamentals/quality_filter.py
Purpose: SOTA Point-in-Time Fundamental Screening & Distress Prevention Engine.
         Guards long-term swing breakout strategies (S03 Turtle Breakout, S05 52-Week High)
         against buying fundamentally compromised, debt-ridden, or dilutive companies:
         - Return on Capital Employed (ROCE >= 15% preferred)
         - Debt-to-Equity Ratio (D/E <= 1.0; rejects overleveraged zombie companies D/E > 2.5)
         - Free Cash Flow (FCF > 0 preferred)
         - Operating Profit Margin (OPM >= 10%)
         - Altman Z-Score Proxy (Bankruptcy Risk Sentry)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging
from typing import Any, Dict, Optional

from mjonai.core.time_utils import now_ist

logger = logging.getLogger(__name__)


class FundamentalGrade(str, Enum):
    GRADE_A_PRIME     = "GRADE_A_PRIME"      # High ROCE, Low Debt, High FCF (Strong conviction)
    GRADE_B_HEALTHY   = "GRADE_B_HEALTHY"    # Adequate fundamentals
    GRADE_C_WEAK      = "GRADE_C_WEAK"       # High debt or negative cash flows
    DISTRESS_REJECT   = "DISTRESS_REJECT"    # Dangerously high debt (D/E > 2.5) or insolvency risk


@dataclass(frozen=True)
class FundamentalQualitySnapshot:
    """
    Immutable Fundamental Quality Assessment Contract.
    """
    symbol: str
    roce_pct: float
    debt_to_equity: float
    operating_margin_pct: float
    free_cash_flow_positive: bool
    altman_z_proxy: float
    fundamental_grade: FundamentalGrade
    is_trade_allowed: bool
    timestamp: datetime
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "roce_pct": round(self.roce_pct, 2),
            "debt_to_equity": round(self.debt_to_equity, 2),
            "operating_margin_pct": round(self.operating_margin_pct, 2),
            "free_cash_flow_positive": self.free_cash_flow_positive,
            "altman_z_proxy": round(self.altman_z_proxy, 2),
            "fundamental_grade": self.fundamental_grade.value,
            "is_trade_allowed": self.is_trade_allowed,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
        }


def evaluate_fundamental_quality(
    symbol: str,
    roce_pct: float = 18.5,
    debt_to_equity: float = 0.45,
    operating_margin_pct: float = 16.0,
    free_cash_flow_positive: bool = True,
    altman_z_proxy: float = 3.2,
) -> FundamentalQualitySnapshot:
    """
    Evaluate comprehensive fundamental quality and assign grade.
    """
    clean_sym = symbol.strip().upper()
    now = now_ist()

    # Rule 1: Distress Reject (Excessive Leverage D/E > 2.5 or Altman Z < 1.1)
    if debt_to_equity > 2.5 or altman_z_proxy < 1.1:
        grade = FundamentalGrade.DISTRESS_REJECT
        allowed = False
        msg = f"FUNDAMENTAL VETO for {clean_sym}: High Insolvency / Debt Risk (D/E: {debt_to_equity:.2f} > 2.5 or Z-Score: {altman_z_proxy:.2f} < 1.1)"
    # Rule 2: Grade A Prime (ROCE >= 15%, D/E <= 0.8, FCF > 0, OPM >= 12%)
    elif roce_pct >= 15.0 and debt_to_equity <= 0.80 and free_cash_flow_positive and operating_margin_pct >= 12.0:
        grade = FundamentalGrade.GRADE_A_PRIME
        allowed = True
        msg = f"Grade-A Prime Fundamentals for {clean_sym} (ROCE: {roce_pct:.1f}% | D/E: {debt_to_equity:.2f} | Positive FCF)"
    # Rule 3: Grade B Healthy
    elif roce_pct >= 10.0 and debt_to_equity <= 1.5:
        grade = FundamentalGrade.GRADE_B_HEALTHY
        allowed = True
        msg = f"Grade-B Healthy Fundamentals for {clean_sym} (ROCE: {roce_pct:.1f}% | D/E: {debt_to_equity:.2f})"
    else:
        grade = FundamentalGrade.GRADE_C_WEAK
        allowed = True
        msg = f"Grade-C Weak Fundamentals for {clean_sym} (ROCE: {roce_pct:.1f}% | D/E: {debt_to_equity:.2f})"

    return FundamentalQualitySnapshot(
        symbol=clean_sym,
        roce_pct=roce_pct,
        debt_to_equity=debt_to_equity,
        operating_margin_pct=operating_margin_pct,
        free_cash_flow_positive=free_cash_flow_positive,
        altman_z_proxy=altman_z_proxy,
        fundamental_grade=grade,
        is_trade_allowed=allowed,
        timestamp=now,
        message=msg,
    )
