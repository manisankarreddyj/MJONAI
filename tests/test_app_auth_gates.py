"""
Auth-gate regression tests (2026-09-17 review).

The control plane (master kill switch, manual trade close, SL modify, role
failover, DR reconcile) and the research lab (/api/research/*) and the real-
time stream (/ws/stream) were ALL reachable WITHOUT any authentication — the
bearer-token gate existed only on the /api/* (views) router. Anyone who could
reach the port could liquidate the book or flip the DR role.

Every one of those surfaces must now honour the same token gate as /api/*,
and a remote-exposed server (MJONAI_APP_HOST set) without a token must refuse
API access fail-closed (503) instead of silently serving open.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from apps.web.main import create_app

API_TOKEN = "auth-gate-test-token"


@pytest.fixture()
def client(monkeypatch):
    app = create_app()  # env load happens here (may read the root .env)
    # Force the request-time env deterministically AFTER create_app: a known
    # token activates the gate; host is cleared so the fail-closed 503 branch
    # is not spuriously armed in the positive/negative tests.
    monkeypatch.setenv("MJONAI_APP_TOKEN", API_TOKEN)
    monkeypatch.delenv("MJONAI_APP_HOST", raising=False)
    return TestClient(app)


def _bearer() -> dict:
    return {"Authorization": f"Bearer {API_TOKEN}"}


# ── Control plane (previously unauthenticated) ──────────────────────────────


def test_kill_all_requires_token(client):
    res = client.post("/api/v1/control/kill-all")
    assert res.status_code == 401


def test_trade_close_and_sl_require_token(client):
    assert client.post("/api/v1/control/trade/t-1/close").status_code == 401
    assert (
        client.post(
            "/api/v1/control/trade/t-1/modify-sl",
            json={"new_stop_loss": 100.0},
        ).status_code
        == 401
    )


def test_strategy_toggle_and_scanner_require_token(client):
    assert (
        client.post("/api/v1/control/strategy/S01/toggle", json={"is_enabled": False}).status_code == 401
    )
    assert client.post("/api/v1/control/scanner/trigger").status_code == 401


def test_kill_all_allowed_with_bearer_token(client):
    with patch("apps.web.control_routes.close_all_paper_trades", return_value=[]):
        res = client.post("/api/v1/control/kill-all", headers=_bearer())
    assert res.status_code == 200
    assert res.json()["status"] == "SUCCESS"


def test_kill_all_allowed_with_query_token_browser_pwa(client):
    # Browser PWA cannot set fetch headers — the documented ?token= pattern.
    with patch("apps.web.control_routes.close_all_paper_trades", return_value=[]):
        res = client.post(f"/api/v1/control/kill-all?token={API_TOKEN}")
    assert res.status_code == 200


def test_strategy_toggle_allowed_with_bearer_token(client):
    res = client.post(
        "/api/v1/control/strategy/S01/toggle",
        json={"is_enabled": False},
        headers=_bearer(),
    )
    assert res.status_code == 200
    assert res.json()["is_enabled"] is False


# ── Disaster recovery / administrative surface ──────────────────────────────


def test_dr_endpoints_require_token(client):
    assert client.get("/api/dr/status").status_code == 401
    assert client.get("/api/dr/heartbeat").status_code == 401
    assert client.post("/api/dr/reconcile").status_code == 401
    assert (
        client.post("/api/dr/failover", json={"target_role": "STANDBY", "reason": "ADMIN_REQUEST"}).status_code
        == 401
    )


def test_dr_reconcile_allowed_with_token(client, monkeypatch):
    import mjonai.core.constants as const_mod

    monkeypatch.setattr(const_mod, "SYSTEM_MODE", "PAPER")
    with patch("mjonai.db.repository.get_open_trades", return_value=[]):
        res = client.post("/api/dr/reconcile", headers=_bearer())
    assert res.status_code == 200
    assert res.json()["status"] == "SKIPPED_BROKER_UNAVAILABLE"


# ── Research lab ─────────────────────────────────────────────────────────────


def test_research_endpoints_require_token(client):
    assert client.get("/api/research/status").status_code == 401
    assert client.post("/api/research/monte-carlo", json={
        "trades_pnl": [1000.0, -500.0],
        "initial_capital": 500000.0,
        "iterations": 200,
    }).status_code == 401


def test_research_status_allowed_with_token(client):
    res = client.get("/api/research/status", headers=_bearer())
    assert res.status_code == 200
    assert res.json()["status"] == "ONLINE"


# ── WebSocket stream ─────────────────────────────────────────────────────────


def test_websocket_stream_rejected_without_token(client):
    """The /ws/stream handshake must fail without a credential — it broadcasts
    telemetry and open trades, so it is a data-exposure surface."""
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/stream"):
            pass


def test_websocket_stream_connects_with_token(client):
    """Authenticated stream connects; close immediately after the handshake."""
    with client.websocket_connect(f"/ws/stream?token={API_TOKEN}") as ws:
        try:
            _ = ws.receive_json()
        except Exception:
            pass  # endpoint may not have pushed before close — connect is the assertion
        ws.close()


# ── Fail-closed on remote exposure without a token ──────────────────────────


def test_remote_exposure_without_token_is_fail_closed(monkeypatch):
    """MJONAI_APP_HOST set (deliberate remote access) but no token must NOT
    serve the API open — the 503 misconfiguration refusal is the correct
    outcome over silently authenticated-by-nobody endpoints."""
    app = create_app()
    monkeypatch.delenv("MJONAI_APP_TOKEN", raising=False)
    monkeypatch.setenv("MJONAI_APP_HOST", "0.0.0.0")
    client = TestClient(app)

    for method, path in [
        ("GET", "/api/status"),
        ("POST", "/api/v1/control/scanner/trigger"),
        ("GET", "/api/dr/status"),
        ("GET", "/api/research/status"),
    ]:
        res = client.request(method, path)
        assert res.status_code == 503, f"{method} {path} must fail closed"

    # Liveness probes stay public (credential-free by design).
    assert client.get("/api/health/live").status_code == 200


def test_report_page_requires_token(client):
    """P0: /report is the only server-rendered DATA page (real equity/trades
    embedded) — unlike the static shells, it must carry the bearer gate."""
    assert client.get("/report").status_code == 401
    res = client.get("/report", headers=_bearer())
    assert res.status_code == 200


def test_static_shells_stay_public(client):
    """Static shells carry no data (client-side fetch through gated /api) —
    gating them would only break bookmarkability for zero security gain."""
    assert client.get("/").status_code == 200
    assert client.get("/console").status_code == 200


def test_health_probes_remain_public(client):
    """Health/liveness probes are deliberately outside the token gate."""
    assert client.get("/api/health/live").status_code == 200
    assert client.get("/api/health/ready").status_code == 200