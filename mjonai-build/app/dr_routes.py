"""
Module: app/dr_routes.py
Purpose: FastAPI Router for Disaster Recovery, High Availability Heartbeats,
         Broker-to-Database Reconciliation, and Container Health Probes.
"""

from datetime import datetime, timezone
import logging
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from core.time_utils import now_ist
from orchestration.disaster_recovery import get_dr_manager, NodeRole

logger = logging.getLogger(__name__)

dr_router = APIRouter(prefix="/api/dr", tags=["Disaster Recovery & High Availability"])
health_router = APIRouter(prefix="/api/health", tags=["Liveness & Readiness Probes"])


class FailoverRequest(BaseModel):
    target_role: str = Field(..., description="Target node role: PRIMARY, STANDBY, or DRAINING")
    reason: str = Field(default="ADMIN_REQUEST")


@health_router.get("/live", summary="Container Liveness Probe")
async def liveness_probe():
    """Kubernetes/Docker liveness probe: returns 200 if process is running."""
    return {"status": "ALIVE", "timestamp": now_ist().isoformat()}


@health_router.get("/ready", summary="Container Readiness Probe")
async def readiness_probe():
    """Kubernetes/Docker readiness probe: returns 200 if ready to serve traffic."""
    mgr = get_dr_manager()
    status_dict = mgr.get_status()
    return {
        "status": "READY",
        "role": status_dict["role"],
        "is_primary": status_dict["is_primary"],
        "timestamp": now_ist().isoformat(),
    }


@dr_router.get("/status", summary="Get DR Node Status")
async def get_dr_status():
    """Returns current node role, distributed lease expiration, and reconciliation metrics."""
    mgr = get_dr_manager()
    return mgr.get_status()


@dr_router.get("/heartbeat", summary="Uptime Monitoring Heartbeat")
async def get_dr_heartbeat():
    """Lightweight 200 OK ping for external monitors (BetterStack, Uptime Kuma, AWS Route53)."""
    mgr = get_dr_manager()
    mgr.acquire_or_renew_lease()
    return {
        "status": "OK",
        "node_id": mgr.node_id,
        "role": mgr.role.value,
        "timestamp": now_ist().isoformat(),
    }


@dr_router.post("/reconcile", summary="Trigger Position Ledger Reconciliation")
async def post_reconcile_ledger():
    """
    Trigger real-time reconciliation between broker net positions and database open trades.
    """
    mgr = get_dr_manager()
    from db.repository import get_open_trades

    try:
        from data.angelone.broker import get_net_positions
        broker_positions = get_net_positions() or []
    except Exception:
        broker_positions = []

    try:
        db_trades = get_open_trades() or []
    except Exception:
        db_trades = []

    report = mgr.reconcile_broker_positions(broker_positions, db_trades)
    return {
        "is_synchronized": report.is_synchronized,
        "matched_positions": report.matched_positions,
        "discrepancies": [
            {
                "symbol": d.symbol,
                "issue_type": d.issue_type,
                "broker_qty": d.broker_qty,
                "db_qty": d.db_qty,
                "details": d.details,
            }
            for d in report.discrepancies
        ],
        "total_broker_positions": report.total_broker_positions,
        "total_db_trades": report.total_db_trades,
        "timestamp": report.timestamp,
    }


@dr_router.post("/failover", summary="Administrative Role Failover")
async def post_dr_failover(req: FailoverRequest):
    """Administratively transition node between PRIMARY, STANDBY, and DRAINING."""
    mgr = get_dr_manager()
    role_str = req.target_role.upper()

    if role_str == "PRIMARY":
        acquired = mgr.acquire_or_renew_lease()
        if not acquired:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Unable to acquire primary lease — active lease held by another node."
            )
    elif role_str in ("STANDBY", "DRAINING"):
        mgr.release_lease()
        mgr.role = NodeRole(role_str)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid target role: {req.target_role}. Must be PRIMARY, STANDBY, or DRAINING."
        )

    return {
        "status": "UPDATED",
        "new_role": mgr.role.value,
        "reason": req.reason,
        "timestamp": now_ist().isoformat(),
    }
