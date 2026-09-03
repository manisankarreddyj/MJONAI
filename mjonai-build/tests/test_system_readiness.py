"""
Unit test suite for orchestration/system_readiness.py
Validates multi-tier operational readiness, sizing throttling, and circuit halts.
"""

import pytest
from orchestration.system_readiness import (
    OperationalTier,
    SystemReadinessReport,
    evaluate_system_readiness,
)


def test_system_readiness_tier1_optimal():
    """Verify Tier 1 Optimal health provides full sizing capacity."""
    rep = evaluate_system_readiness(
        websocket_healthy=True,
        broker_connected=True,
        internet_ok=True,
        circuit_freeze_active=False,
        daily_kill_line_breached=False,
        database_ok=True,
        api_latency_ms=120,
    )
    assert rep.tier == OperationalTier.TIER_1_OPTIMAL
    assert rep.sizing_multiplier == 1.0
    assert rep.is_order_placement_allowed is True
    assert len(rep.active_degradations) == 0


def test_system_readiness_tier2_degraded_websocket_fallback():
    """Verify Tier 2 Degraded state throttles position sizing to 0.5x when WebSocket drops."""
    rep = evaluate_system_readiness(
        websocket_healthy=False,  # Dropped feed!
        broker_connected=True,
        internet_ok=True,
        api_latency_ms=200,
    )
    assert rep.tier == OperationalTier.TIER_2_DEGRADED
    assert rep.sizing_multiplier == 0.5
    assert rep.is_order_placement_allowed is True
    assert any("WebSocket" in d for d in rep.active_degradations)


def test_system_readiness_tier3_restricted_broker_disconnect():
    """Verify Tier 3 Restricted blocks all fresh orders when broker disconnects or circuit halts."""
    # Case A: Broker disconnected
    rep_brk = evaluate_system_readiness(broker_connected=False)
    assert rep_brk.tier == OperationalTier.TIER_3_RESTRICTED
    assert rep_brk.sizing_multiplier == 0.0
    assert rep_brk.is_order_placement_allowed is False

    # Case B: Exchange Circuit Freeze
    rep_halt = evaluate_system_readiness(circuit_freeze_active=True)
    assert rep_halt.tier == OperationalTier.TIER_3_RESTRICTED
    assert rep_halt.sizing_multiplier == 0.0
    assert rep_halt.is_order_placement_allowed is False


def test_system_readiness_tier4_kill_lock():
    """Verify Tier 4 Kill Lock completely locks out trading after daily risk breaches."""
    rep_kill = evaluate_system_readiness(daily_kill_line_breached=True)
    assert rep_kill.tier == OperationalTier.TIER_4_KILL_LOCK
    assert rep_kill.sizing_multiplier == 0.0
    assert rep_kill.is_order_placement_allowed is False
