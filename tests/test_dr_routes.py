"""
Test Suite: tests/test_dr_routes.py
Purpose: API tests for /api/dr/* and /api/health/* endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from apps.web.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_liveness_probe_returns_200(client):
    """Verify /api/health/live returns HTTP 200 ALIVE."""
    resp = client.get("/api/health/live")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ALIVE"
    assert "timestamp" in data


def test_readiness_probe_returns_200(client):
    """Verify /api/health/ready returns HTTP 200 READY."""
    resp = client.get("/api/health/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "READY"
    assert "role" in data


def test_dr_status_endpoint(client):
    """Verify /api/dr/status returns node role and lease metadata."""
    resp = client.get("/api/dr/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "node_id" in data
    assert "role" in data
    assert "is_primary" in data


def test_dr_heartbeat_endpoint(client):
    """Verify /api/dr/heartbeat returns OK for uptime monitors."""
    resp = client.get("/api/dr/heartbeat")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "OK"
    assert "node_id" in data


def test_dr_reconcile_endpoint(client):
    """Verify /api/dr/reconcile executes position audit cleanly."""
    resp = client.post("/api/dr/reconcile")
    assert resp.status_code == 200
    data = resp.json()
    assert "is_synchronized" in data
    assert "discrepancies" in data
    assert isinstance(data["matched_positions"], list)


def test_dr_failover_endpoint(client):
    """Verify /api/dr/failover transitions role to STANDBY or PRIMARY."""
    resp = client.post("/api/dr/failover", json={"target_role": "STANDBY", "reason": "MAINTENANCE"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "UPDATED"
    assert data["new_role"] == "STANDBY"
