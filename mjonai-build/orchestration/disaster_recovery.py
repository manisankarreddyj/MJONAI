"""
Module: orchestration/disaster_recovery.py
Purpose: SOTA Active-Passive Disaster Recovery, Distributed Lease Sentry,
         and Post-Crash Broker-to-Database Reconciliation Engine for MJONAI.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import json
import logging
import os
import socket
import threading
from typing import Dict, List, Any, Optional

from core.time_utils import now_ist
from communication.telegram import send_message
from communication.events import publish_event

logger = logging.getLogger(__name__)


class NodeRole(str, Enum):
    PRIMARY = "PRIMARY"
    STANDBY = "STANDBY"
    RECOVERING = "RECOVERING"
    DRAINING = "DRAINING"


@dataclass
class PositionDiscrepancy:
    symbol: str
    issue_type: str  # MISSING_IN_DB, MISSING_IN_BROKER, QUANTITY_MISMATCH
    broker_qty: int
    db_qty: int
    details: str


@dataclass
class ReconciliationReport:
    timestamp: str
    is_synchronized: bool
    matched_positions: List[str]
    discrepancies: List[PositionDiscrepancy]
    total_broker_positions: int
    total_db_trades: int


class DisasterRecoveryManager:
    """
    Orchestrates distributed high-availability, lease heartbeat renewal,
    and broker ledger reconciliation for MJONAI trading nodes.
    """

    def __init__(
        self,
        node_id: Optional[str] = None,
        lease_file_path: Optional[str] = None,
        ttl_seconds: int = 60,
    ):
        self.node_id = node_id or f"{socket.gethostname()}_{os.getpid()}"
        self.lease_file_path = lease_file_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "cache", "mjonai_distributed_lease.json"
        )
        self.ttl_seconds = ttl_seconds
        self.role = NodeRole.STANDBY
        self._lock = threading.RLock()
        self.last_lease_renewal: Optional[datetime] = None
        self.last_reconciliation: Optional[ReconciliationReport] = None

    def acquire_or_renew_lease(self) -> bool:
        """
        Attempt to acquire or renew the distributed trading lease.
        Returns:
            bool: True if this node is granted PRIMARY status, False if STANDBY.
        """
        with self._lock:
            now = now_ist()
            os.makedirs(os.path.dirname(self.lease_file_path), exist_ok=True)

            current_lease: Optional[Dict[str, Any]] = None
            if os.path.exists(self.lease_file_path):
                try:
                    with open(self.lease_file_path, "r", encoding="utf-8") as f:
                        current_lease = json.load(f)
                except Exception as e:
                    logger.warning(f"[DR Manager] Failed to read lease file: {e}")

            can_claim = False
            if current_lease is None:
                can_claim = True
            else:
                lease_holder = current_lease.get("node_id")
                expires_at_str = current_lease.get("expires_at")
                
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                except (ValueError, TypeError):
                    expires_at = now - timedelta(seconds=1)

                if lease_holder == self.node_id or now > expires_at:
                    can_claim = True
                else:
                    can_claim = False

            if can_claim:
                expires_at = now + timedelta(seconds=self.ttl_seconds)
                new_lease = {
                    "node_id": self.node_id,
                    "acquired_at": now.isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "ttl_seconds": self.ttl_seconds,
                }
                try:
                    # Write atomically via temp file
                    tmp_path = f"{self.lease_file_path}.tmp"
                    with open(tmp_path, "w", encoding="utf-8") as f:
                        json.dump(new_lease, f, indent=2)
                    os.replace(tmp_path, self.lease_file_path)
                    
                    self.role = NodeRole.PRIMARY
                    self.last_lease_renewal = now
                    return True
                except Exception as e:
                    logger.error(f"[DR Manager] Failed to write lease file: {e}")
                    self.role = NodeRole.STANDBY
                    return False
            else:
                if self.role == NodeRole.PRIMARY:
                    logger.warning(f"[DR Manager] Lease lost to {current_lease.get('node_id')}. Stepping down to STANDBY.")
                self.role = NodeRole.STANDBY
                return False

    def release_lease(self) -> None:
        """Explicitly surrender lease on graceful shutdown."""
        with self._lock:
            if os.path.exists(self.lease_file_path):
                try:
                    with open(self.lease_file_path, "r", encoding="utf-8") as f:
                        current = json.load(f)
                    if current.get("node_id") == self.node_id:
                        os.remove(self.lease_file_path)
                        logger.info(f"[DR Manager] Lease released by node {self.node_id}.")
                except Exception as e:
                    logger.warning(f"[DR Manager] Error releasing lease: {e}")
            self.role = NodeRole.DRAINING

    def reconcile_broker_positions(
        self,
        broker_positions: List[Dict[str, Any]],
        db_open_trades: List[Dict[str, Any]],
    ) -> ReconciliationReport:
        """
        Reconcile Angel One Net Positions with local/Supabase open trades.
        Detects phantom fills, missing stops, and unrecorded executions.
        """
        with self._lock:
            now = now_ist()
            # Map broker positions by symbol -> net_qty
            b_map: Dict[str, int] = {}
            for p in broker_positions:
                sym = str(p.get("tradingsymbol") or p.get("symbol") or "").upper().strip()
                qty = int(p.get("netqty") or p.get("net_qty") or p.get("quantity") or 0)
                if qty != 0 and sym:
                    b_map[sym] = b_map.get(sym, 0) + qty

            # Map DB open trades by symbol -> net_qty
            db_map: Dict[str, int] = {}
            for t in db_open_trades:
                sym = str(t.get("symbol") or "").upper().strip()
                qty = int(t.get("quantity") or t.get("qty") or 0)
                side = str(t.get("side") or t.get("direction") or "BUY").upper()
                signed_qty = qty if "BUY" in side or "LONG" in side else -qty
                if signed_qty != 0 and sym:
                    db_map[sym] = db_map.get(sym, 0) + signed_qty

            matched: List[str] = []
            discrepancies: List[PositionDiscrepancy] = []

            all_symbols = set(b_map.keys()).union(set(db_map.keys()))

            for sym in sorted(all_symbols):
                b_qty = b_map.get(sym, 0)
                d_qty = db_map.get(sym, 0)

                if b_qty == d_qty:
                    matched.append(sym)
                elif b_qty != 0 and d_qty == 0:
                    discrepancies.append(PositionDiscrepancy(
                        symbol=sym,
                        issue_type="MISSING_IN_DB",
                        broker_qty=b_qty,
                        db_qty=0,
                        details=f"Broker has open position ({b_qty}) not tracked in database (phantom fill or external order)."
                    ))
                elif b_qty == 0 and d_qty != 0:
                    discrepancies.append(PositionDiscrepancy(
                        symbol=sym,
                        issue_type="MISSING_IN_BROKER",
                        broker_qty=0,
                        db_qty=d_qty,
                        details=f"DB tracks open trade ({d_qty}) but Broker net position is flat (unrecorded SL hit or manual liquidation)."
                    ))
                else:
                    discrepancies.append(PositionDiscrepancy(
                        symbol=sym,
                        issue_type="QUANTITY_MISMATCH",
                        broker_qty=b_qty,
                        db_qty=d_qty,
                        details=f"Quantity mismatch: Broker={b_qty} vs DB={d_qty}."
                    ))

            is_sync = len(discrepancies) == 0
            report = ReconciliationReport(
                timestamp=now.isoformat(),
                is_synchronized=is_sync,
                matched_positions=matched,
                discrepancies=discrepancies,
                total_broker_positions=len(b_map),
                total_db_trades=len(db_map),
            )
            self.last_reconciliation = report

            if not is_sync:
                logger.critical(f"[DR Reconciliation] ⚠️ Found {len(discrepancies)} position discrepancies!")
                disc_text = "\n".join([f"• <b>{d.symbol}</b>: {d.issue_type} (Broker: {d.broker_qty}, DB: {d.db_qty})" for d in discrepancies[:5]])
                send_message(
                    f"🚨 <b>MJONAI DISASTER RECOVERY ALERT</b>\n"
                    f"Position Ledger Discrepancy Detected:\n"
                    f"{disc_text}\n"
                    f"Action: Review broker terminal immediately."
                )
                publish_event("RECONCILIATION_FAILED", {"discrepancies_count": len(discrepancies), "timestamp": now.isoformat()})
            else:
                logger.info(f"[DR Reconciliation] ✅ All {len(matched)} positions synchronized between Broker and DB.")
                publish_event("RECONCILIATION_SUCCESS", {"matched_count": len(matched), "timestamp": now.isoformat()})

            return report

    def get_status(self) -> Dict[str, Any]:
        """Return real-time DR node status dictionary."""
        with self._lock:
            return {
                "node_id": self.node_id,
                "role": self.role.value,
                "is_primary": self.role == NodeRole.PRIMARY,
                "last_lease_renewal": self.last_lease_renewal.isoformat() if self.last_lease_renewal else None,
                "ttl_seconds": self.ttl_seconds,
                "last_reconciliation": {
                    "is_synchronized": self.last_reconciliation.is_synchronized if self.last_reconciliation else True,
                    "timestamp": self.last_reconciliation.timestamp if self.last_reconciliation else None,
                    "discrepancies_count": len(self.last_reconciliation.discrepancies) if self.last_reconciliation else 0,
                }
            }


# Singleton instance
_dr_manager_instance: Optional[DisasterRecoveryManager] = None
_instance_lock = threading.Lock()


def get_dr_manager() -> DisasterRecoveryManager:
    global _dr_manager_instance
    with _instance_lock:
        if _dr_manager_instance is None:
            _dr_manager_instance = DisasterRecoveryManager()
        return _dr_manager_instance
