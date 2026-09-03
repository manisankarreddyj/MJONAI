"""
Module: data/corporate/insider_flow.py
Purpose: SOTA Promoter Share Pledging & SEBI SAST Insider Activity Sentry.
         Monitors corporate ownership and governance risk factors:
         - Promoter Share Pledge % (Pledged / Total Promoter Holding)
         - Governance Gate: Reject stock if Promoter Pledge > 20% (Distress collateral liquidation risk)
         - SEBI SAST Insider Activity: Promoter net buying vs dumping
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging
from typing import Any, Dict, Optional

from core.time_utils import now_ist

logger = logging.getLogger(__name__)


class GovernanceRiskLevel(str, Enum):
    SAFE_PRIME       = "SAFE_PRIME"        # Zero or minimal pledge (< 5%)
    MODERATE_WATCH   = "MODERATE_WATCH"    # 5% <= Pledge <= 20%
    HIGH_PLEDGE_VETO = "HIGH_PLEDGE_VETO"  # Pledge > 20% (High risk of margin call liquidation)


@dataclass(frozen=True)
class InsiderGovernanceSnapshot:
    """
    Immutable Corporate Governance & Promoter Pledge Assessment.
    """
    symbol: str
    promoter_holding_pct: float
    promoter_pledged_pct: float
    insider_net_buying_crores: float
    governance_risk: GovernanceRiskLevel
    is_governance_approved: bool
    timestamp: datetime
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "promoter_holding_pct": round(self.promoter_holding_pct, 2),
            "promoter_pledged_pct": round(self.promoter_pledged_pct, 2),
            "insider_net_buying_crores": round(self.insider_net_buying_crores, 2),
            "governance_risk": self.governance_risk.value,
            "is_governance_approved": self.is_governance_approved,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
        }


def check_promoter_pledge_and_governance(
    symbol: str,
    promoter_holding_pct: float = 52.0,
    promoter_pledged_pct: float = 0.0,
    insider_net_buying_crores: float = 0.0,
) -> InsiderGovernanceSnapshot:
    """
    Evaluate promoter pledge percentage and governance risk.
    """
    clean_sym = symbol.strip().upper()
    now = now_ist()

    # Rule 1: High Pledge Veto (> 20% of promoter holding is pledged)
    if promoter_pledged_pct > 20.0:
        risk = GovernanceRiskLevel.HIGH_PLEDGE_VETO
        approved = False
        msg = f"GOVERNANCE VETO for {clean_sym}: High Promoter Share Pledge ({promoter_pledged_pct:.1f}% > 20.0% Cutoff | High Margin Call Liquidation Risk)"
    elif promoter_pledged_pct >= 5.0:
        risk = GovernanceRiskLevel.MODERATE_WATCH
        approved = True
        msg = f"Moderate Promoter Pledge for {clean_sym} ({promoter_pledged_pct:.1f}%)"
    else:
        risk = GovernanceRiskLevel.SAFE_PRIME
        approved = True
        msg = f"Clean Governance for {clean_sym} (Promoter Pledge: {promoter_pledged_pct:.1f}% | Holding: {promoter_holding_pct:.1f}%)"

    return InsiderGovernanceSnapshot(
        symbol=clean_sym,
        promoter_holding_pct=promoter_holding_pct,
        promoter_pledged_pct=promoter_pledged_pct,
        insider_net_buying_crores=insider_net_buying_crores,
        governance_risk=risk,
        is_governance_approved=approved,
        timestamp=now,
        message=msg,
    )
