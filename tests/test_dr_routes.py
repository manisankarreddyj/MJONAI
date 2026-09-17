"""
Test Suite: tests/test_dr_routes.py
Purpose: API tests for /api/dr/* and /api/health/* endpoints.
"""

import sys
import types

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


def test_dr_reconcile_endpoint_paper_fail_closed(client, monkeypatch):
    """PAPER has no live broker ledger -> reconcile SKIPS, never fabricates MISSING_IN_BROKER."""
    import mjonai.core.constants as const_mod

    monkeypatch.setattr(const_mod, "SYSTEM_MODE", "PAPER")
    seen = {}

    def fake_get_open_trades(system_mode=None):
        seen["system_mode"] = system_mode
        return [{"symbol": "ADANIENT", "quantity": 10, "side": "BUY"}]

    monkeypatch.setattr("mjonai.db.repository.get_open_trades", fake_get_open_trades)

    resp = client.post("/api/dr/reconcile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["broker_available"] is False
    assert data["status"] == "SKIPPED_BROKER_UNAVAILABLE"
    assert data["discrepancies"] == []
    assert seen["system_mode"] == "PAPER", "DB trades must be mode-scoped"


def test_dr_reconcile_live_detects_discrepancies(client, monkeypatch):
    """LIVE with a readable broker feed reconciles mode-scoped DB trades against it."""
    import apps.runtime.orchestration.disaster_recovery as drmod
    import mjonai.core.constants as const_mod

    monkeypatch.setattr(const_mod, "SYSTEM_MODE", "LIVE")
    broker_mod = types.ModuleType("mjonai.data.angelone.broker")
    broker_mod.get_net_positions = lambda: [{"tradingsymbol": "INFY", "netqty": 100}]
    monkeypatch.setitem(sys.modules, "mjonai.data.angelone.broker", broker_mod)
    monkeypatch.setattr(
        "mjonai.db.repository.get_open_trades",
        lambda system_mode=None: [{"symbol": "HDFCBANK", "quantity": 25, "side": "BUY"}],
    )
    sent = []
    monkeypatch.setattr(drmod, "send_message", lambda msg: sent.append(msg))

    resp = client.post("/api/dr/reconcile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["broker_available"] is True
    assert data["status"] == "DISCREPANCIES"
    assert {d["symbol"] for d in data["discrepancies"]} == {"INFY", "HDFCBANK"}
    assert data["system_mode"] == "LIVE"



def test_dr_failover_endpoint(client):
    """Verify /api/dr/failover transitions role to STANDBY or PRIMARY."""
    resp = client.post("/api/dr/failover", json={"target_role": "STANDBY", "reason": "MAINTENANCE"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "UPDATED"
    assert data["new_role"] == "STANDBY"
