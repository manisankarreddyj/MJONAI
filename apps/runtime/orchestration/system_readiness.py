"""
Module: orchestration/system_readiness.py
Purpose: SOTA Multi-Tier Operational Readiness & Degraded Mode Governance Engine for MJONAI.
         Classifies system health into 4 operational tiers, applying automated position sizing
         throttling and order submission gating during network or broker degradations.
"""

from dataclasses import dataclass, asdict
from enum import Enum
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class OperationalTier(str, Enum):
    """System operational readiness tiers."""
    TIER_1_OPTIMAL = "TIER_1_OPTIMAL"         # 100% health, full sizing (1.0x)
    TIER_2_DEGRADED = "TIER_2_DEGRADED"       # Flapping feed / REST fallback, throttled sizing (0.5x)
    TIER_3_RESTRICTED = "TIER_3_RESTRICTED"   # Data outage / circuit halt, zero new orders (0.0x)
    TIER_4_KILL_LOCK = "TIER_4_KILL_LOCK"     # Daily kill line breached, full system lockout (0.0x)


@dataclass(frozen=True)
class SystemReadinessReport:
    """Immutable evaluation contract for system operational readiness."""
    tier: OperationalTier
    sizing_multiplier: float
    is_order_placement_allowed: bool
    is_sl_monitoring_allowed: bool
    status_summary: str
    active_degradations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["tier"] = self.tier.value
        return d


def evaluate_system_readiness(
    websocket_healthy: bool = True,
    broker_connected: bool = True,
    internet_ok: bool = True,
    circuit_freeze_active: bool = False,
    daily_kill_line_breached: bool = False,
    database_ok: bool = True,
    api_latency_ms: Optional[int] = None,
) -> SystemReadinessReport:
    """
    Evaluate comprehensive system operational tier based on infrastructure and risk telemetry.
    """
    degradations: List[str] = []

    # 1. Check Tier 4: Kill Line Breached
    if daily_kill_line_breached:
        degradations.append("Daily loss or lifetime drawdown kill line breached")
        return SystemReadinessReport(
            tier=OperationalTier.TIER_4_KILL_LOCK,
            sizing_multiplier=0.0,
            is_order_placement_allowed=False,
            is_sl_monitoring_allowed=True,
            status_summary="System in Lockout: Kill line engaged",
            active_degradations=degradations,
        )

    # 2. Check Tier 3: Critical Outages or Market Halts
    if not internet_ok:
        degradations.append("No internet connectivity detected")
    if not broker_connected:
        degradations.append("Broker API disconnected")
    if circuit_freeze_active:
        degradations.append("Exchange index circuit breaker freeze active")
    if not database_ok:
        degradations.append("Primary database unreachable")

    if degradations:
        return SystemReadinessReport(
            tier=OperationalTier.TIER_3_RESTRICTED,
            sizing_multiplier=0.0,
            is_order_placement_allowed=False,
            is_sl_monitoring_allowed=broker_connected,
            status_summary="System Restricted: Critical network/infrastructure outage",
            active_degradations=degradations,
        )

    # 3. Check Tier 2: Degraded Feed or Elevated Latency
    if not websocket_healthy:
        degradations.append("WebSocket tick stream stale or disconnected; REST fallback active")
    if api_latency_ms is not None and api_latency_ms > 1500:
        degradations.append(f"Elevated API latency ({api_latency_ms}ms > 1500ms)")

    if degradations:
        return SystemReadinessReport(
            tier=OperationalTier.TIER_2_DEGRADED,
            sizing_multiplier=0.5,
            is_order_placement_allowed=True,
            is_sl_monitoring_allowed=True,
            status_summary="System Degraded: Operating with 50% position sizing throttle",
            active_degradations=degradations,
        )

    # 4. Tier 1: Optimal
    return SystemReadinessReport(
        tier=OperationalTier.TIER_1_OPTIMAL,
        sizing_multiplier=1.0,
        is_order_placement_allowed=True,
        is_sl_monitoring_allowed=True,
        status_summary="System Optimal: Full operational capacity",
        active_degradations=[],
    )
