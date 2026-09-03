"""
Test Suite: tests/test_module12_extreme_edge_cases.py
Purpose: Extreme Edge Case, Concurrency, and Stress Verification for Module 12 (DR & Deployment).
"""

import concurrent.futures
import json
import os
import tempfile
import pytest

from apps.runtime.orchestration.disaster_recovery import DisasterRecoveryManager, NodeRole
from apps.runtime.orchestration.crash_supervisor import CrashSupervisor
from fastapi.testclient import TestClient
from apps.web.main import create_app


def test_concurrent_split_brain_race_condition():
    """Edge Case 1: 10 concurrent nodes race for lease; strictly ONE wins PRIMARY."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        lease_path = os.path.join(tmp_dir, "race_lease.json")

        def try_claim(node_idx: int) -> bool:
            mgr = DisasterRecoveryManager(node_id=f"NODE_{node_idx}", lease_file_path=lease_path, ttl_seconds=30)
            return mgr.acquire_or_renew_lease()

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(try_claim, i) for i in range(10)]
            results = [f.result() for f in futures]

        # Strictly 1 winner
        winners = sum(1 for r in results if r is True)
        assert winners == 1, f"Expected exactly 1 winner, got {winners}"


def test_corrupted_truncated_lease_file_auto_healing():
    """Edge Case 2: Partial/corrupt JSON lease file is safely overwritten without crash."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        lease_path = os.path.join(tmp_dir, "corrupt_lease.json")
        # Write malformed garbage
        with open(lease_path, "w", encoding="utf-8") as f:
            f.write("{corrupt_garbage_missing_brackets: True")

        mgr = DisasterRecoveryManager(node_id="HEALING_NODE", lease_file_path=lease_path, ttl_seconds=30)
        acquired = mgr.acquire_or_renew_lease()
        assert acquired is True
        assert mgr.role == NodeRole.PRIMARY

        # File is healed with valid JSON
        with open(lease_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["node_id"] == "HEALING_NODE"


def test_reconciliation_signed_short_positions():
    """Edge Case 3: Reconciling short option / intraday positions (-50 qty)."""
    mgr = DisasterRecoveryManager(node_id="TEST_NODE")

    # Short 50 NIFTY PE on broker
    broker_positions = [
        {"tradingsymbol": "NIFTY24SEP24000PE", "netqty": -50},
    ]
    # Sell 50 in DB
    db_trades = [
        {"symbol": "NIFTY24SEP24000PE", "quantity": 50, "side": "SELL"},
    ]

    report = mgr.reconcile_broker_positions(broker_positions, db_trades)
    assert report.is_synchronized is True
    assert len(report.discrepancies) == 0
    assert report.matched_positions == ["NIFTY24SEP24000PE"]


def test_crash_supervisor_extreme_backoff_clamping():
    """Edge Case 4: 1,000 consecutive crashes do not produce math overflow or exceed max delay."""
    sup = CrashSupervisor(base_delay_seconds=2.0, max_delay_seconds=60.0)
    sup.consecutive_crashes = 1000

    delay = sup.compute_backoff_delay()
    assert delay <= 60.0 * 1.25  # Max delay + jitter cap
    assert delay >= 60.0 * 0.75


def test_api_failover_invalid_role_400():
    """Edge Case 5: Attempting failover to non-existent role returns HTTP 400."""
    client = TestClient(create_app())
    resp = client.post("/api/dr/failover", json={"target_role": "SUPERUSER_ADMIN"})
    assert resp.status_code == 400
    assert "Invalid target role" in resp.json()["detail"]
