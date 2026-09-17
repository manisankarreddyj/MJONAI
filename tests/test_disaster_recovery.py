"""
Test Suite: tests/test_disaster_recovery.py
Purpose: Unit tests for Disaster Recovery Manager, Distributed Leases, and Position Reconciliation.
"""

import os
import tempfile
import pytest
from datetime import datetime, timedelta

from apps.runtime.orchestration.disaster_recovery import (
    DisasterRecoveryManager,
    NodeRole,
    PositionDiscrepancy,
    ReconciliationReport,
)


def test_lease_acquisition_and_renewal():
    """Verify single node acquires PRIMARY lease and renews successfully."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        lease_path = os.path.join(tmp_dir, "test_lease.json")
        mgr = DisasterRecoveryManager(node_id="NODE_A", lease_file_path=lease_path, ttl_seconds=10)

        assert mgr.role == NodeRole.STANDBY
        acquired = mgr.acquire_or_renew_lease()
        assert acquired is True
        assert mgr.role == NodeRole.PRIMARY
        assert os.path.exists(lease_path)

        # Renewing with same node succeeds
        renewed = mgr.acquire_or_renew_lease()
        assert renewed is True
        assert mgr.role == NodeRole.PRIMARY


def test_split_brain_secondary_node_protection():
    """Verify secondary node cannot usurp active PRIMARY lease before TTL expires."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        lease_path = os.path.join(tmp_dir, "test_lease.json")
        mgr_a = DisasterRecoveryManager(node_id="NODE_A", lease_file_path=lease_path, ttl_seconds=60)
        mgr_b = DisasterRecoveryManager(node_id="NODE_B", lease_file_path=lease_path, ttl_seconds=60)

        # Node A acquires primary
        assert mgr_a.acquire_or_renew_lease() is True
        assert mgr_a.role == NodeRole.PRIMARY

        # Node B attempts to acquire while Node A lease is active -> blocked into STANDBY
        assert mgr_b.acquire_or_renew_lease() is False
        assert mgr_b.role == NodeRole.STANDBY

        # Node A releases lease
        mgr_a.release_lease()
        assert mgr_a.role == NodeRole.DRAINING

        # Node B can now claim primary
        assert mgr_b.acquire_or_renew_lease() is True
        assert mgr_b.role == NodeRole.PRIMARY


def test_broker_ledger_reconciliation_matched():
    """Verify perfect match between Broker net positions and DB open trades."""
    mgr = DisasterRecoveryManager(node_id="TEST_NODE")

    broker_positions = [
        {"tradingsymbol": "RELIANCE", "netqty": 50},
        {"tradingsymbol": "TCS", "netqty": 20},
    ]
    db_trades = [
        {"symbol": "RELIANCE", "quantity": 50, "side": "BUY"},
        {"symbol": "TCS", "quantity": 20, "side": "BUY"},
    ]

    report = mgr.reconcile_broker_positions(broker_positions, db_trades, notifier=lambda *a, **k: None)
    assert report.is_synchronized is True
    assert len(report.discrepancies) == 0
    assert sorted(report.matched_positions) == ["RELIANCE", "TCS"]


def test_broker_ledger_reconciliation_discrepancies():
    """Verify detection of missing_in_db, missing_in_broker, and quantity_mismatch."""
    mgr = DisasterRecoveryManager(node_id="TEST_NODE")

    broker_positions = [
        {"tradingsymbol": "RELIANCE", "netqty": 50},   # Mismatch: DB has 40
        {"tradingsymbol": "INFY", "netqty": 100},      # Missing in DB (phantom fill)
    ]
    db_trades = [
        {"symbol": "RELIANCE", "quantity": 40, "side": "BUY"},
        {"symbol": "HDFCBANK", "quantity": 25, "side": "BUY"}, # Missing in Broker (unrecorded SL hit)
    ]

    sent = []
    report = mgr.reconcile_broker_positions(
        broker_positions, db_trades, notifier=lambda msg: sent.append(msg)
    )
    assert report.is_synchronized is False
    assert len(report.discrepancies) == 3
    assert len(sent) == 1, "discrepancy must alert exactly once via the injected notifier"

    disc_types = {d.symbol: d.issue_type for d in report.discrepancies}
    assert disc_types["RELIANCE"] == "QUANTITY_MISMATCH"
    assert disc_types["INFY"] == "MISSING_IN_DB"
    assert disc_types["HDFCBANK"] == "MISSING_IN_BROKER"


def test_reconciliation_skipped_when_broker_unavailable():
    """Fail-closed: an unreadable broker feed must NOT flag DB rows as MISSING_IN_BROKER."""
    mgr = DisasterRecoveryManager(node_id="TEST_NODE")
    db_trades = [{"symbol": "ADANIENT", "quantity": 10, "side": "BUY"}]

    sent = []
    report = mgr.reconcile_broker_positions(
        [], db_trades, broker_available=False, notifier=lambda msg: sent.append(msg)
    )
    assert report.status == "SKIPPED_BROKER_UNAVAILABLE"
    assert report.broker_available is False
    assert report.discrepancies == []
    assert sent == [], "a skipped reconciliation must not emit a discrepancy alert"


def test_reconciliation_alert_deduplicated_within_cooldown():
    """Identical discrepancy sets must alert once, not once per 15-minute scan."""
    mgr = DisasterRecoveryManager(node_id="TEST_NODE", alert_cooldown_seconds=600)
    broker_positions = [{"tradingsymbol": "INFY", "netqty": 100}]
    db_trades = [{"symbol": "HDFCBANK", "quantity": 25, "side": "BUY"}]

    sent = []
    for _ in range(3):
        mgr.reconcile_broker_positions(
            broker_positions, db_trades, notifier=lambda msg: sent.append(msg)
        )
    assert len(sent) == 1

