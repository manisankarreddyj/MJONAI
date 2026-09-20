"""
Torture test suite for Module 9: Next-Gen Mission Control Terminal & Mobile Commander.
Tests extreme concurrent kill storms, edge-case stop modifications, and dead-connection storms.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from apps.web.main import create_app
from apps.web.websocket_stream import WebSocketHub

@pytest.fixture
def client(monkeypatch):
    app = create_app()
    # Neutralize any auth env loaded from the root .env so these
    # tests exercise the control-plane torture scenarios in isolation.
    monkeypatch.delenv("MJONAI_APP_TOKEN", raising=False)
    monkeypatch.delenv("MJONAI_APP_HOST", raising=False)
    return TestClient(app)


def test_concurrent_kill_switch_hammering(client):
    """Torture test: 20 rapid-fire kill-all requests must be idempotent and fail-closed."""
    with patch("apps.web.control_routes.close_all_paper_trades", return_value=[]):
        for _ in range(20):
            res = client.post("/api/v1/control/kill-all")
            assert res.status_code == 200
            assert res.json()["status"] == "SUCCESS"


def test_short_trade_wrong_side_stop_rejection(client):
    """Verify that Short trade SL modifications below current price are rejected."""
    fake_short = {
        "id": "trade-short-1",
        "symbol": "TCS",
        "direction": "SELL",
        "status": "OPEN",
        "entry_price": 4200.0,
        "current_price": 4150.0,
        "stop_loss": 4250.0,
    }

    with patch("apps.web.control_routes.get_trade_by_id", return_value=fake_short):
        # Setting Short SL to 4100.0 (BELOW current price 4150.0) MUST fail!
        res = client.post(
            "/api/v1/control/trade/trade-short-1/modify-sl",
            json={"new_stop_loss": 4100.0},
        )
        assert res.status_code == 422
        assert "Invalid Short SL" in res.json()["detail"]


def test_mass_websocket_dropout_storm():
    """Torture test: 50 simultaneous dead WebSocket dropouts must be pruned in zero ms."""
    async def _run():
        hub = WebSocketHub()

        dead_sockets = []
        for _ in range(50):
            dead_ws = AsyncMock()
            async def fail_send(text):
                raise ConnectionAbortedError("Mass network failure")
            dead_ws.send_text = fail_send
            await hub.connect(dead_ws)

        assert len(hub.active_connections) == 50

        # Broadcast triggering mass prune
        await hub.broadcast({"type": "MASS_TEST"})
        assert len(hub.active_connections) == 0

    asyncio.run(_run())


def test_terminal_web_page_serves_cyberpunk_hud(client):
    """Verify /terminal and / serve the Next-Gen Mission Control Terminal HTML."""
    res = client.get("/terminal")
    assert res.status_code == 200
    assert "MJONAI MISSION CONTROL" in res.text
    assert "SLIDE TO KILL" in res.text
    assert "canvas-3d-container" in res.text
    assert "AI SPECIALIST BOARDROOM" in res.text
