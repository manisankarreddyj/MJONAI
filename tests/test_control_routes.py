"""
Unit tests for app/control_routes.py.
Validates the Executive Control Bus, Master Kill Switch, and Drag-and-Drop SL Updates.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from apps.web.main import create_app

@pytest.fixture
def client(monkeypatch):
    app = create_app()
    # These tests exercise the control-plane business logic, not auth — pin
    # the request-time env so a full-credentials machine cannot activate the
    # bearer gate (token/host may be loaded from the root .env).
    monkeypatch.delenv("MJONAI_APP_TOKEN", raising=False)
    monkeypatch.delenv("MJONAI_APP_HOST", raising=False)
    return TestClient(app)


def test_emergency_kill_all(client):
    """Verify Master Kill-Switch liquidates all positions fail-closed."""
    with patch("apps.web.control_routes.close_all_paper_trades", return_value=[{"id": "t1"}]) as mock_close:
        res = client.post("/api/v1/control/kill-all")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "SUCCESS"
        assert data["action"] == "MASTER_KILL_SWITCH_ENGAGED"
        assert data["positions_liquidated"] == 1
        mock_close.assert_called_once()


def test_strategy_toggle_matrix(client):
    """Verify strategy toggling enables and pauses quantitative strategies."""
    res = client.post("/api/v1/control/strategy/S01/toggle", json={"is_enabled": False})
    assert res.status_code == 200
    assert res.json()["is_enabled"] is False

    # Check status
    res2 = client.get("/api/v1/control/strategy/status")
    assert res2.status_code == 200
    assert res2.json()["strategy_overrides"]["S01"] is False

    # Re-enable
    res3 = client.post("/api/v1/control/strategy/S01/toggle", json={"is_enabled": True})
    assert res3.status_code == 200
    assert res3.json()["is_enabled"] is True


def test_modify_sl_wrong_side_rejection(client):
    """Verify that wrong-side stop modifications are strictly rejected with HTTP 422."""
    fake_trade = {
        "id": "trade-long-1",
        "symbol": "INFY",
        "direction": "BUY",
        "status": "OPEN",
        "entry_price": 1900.0,
        "current_price": 1950.0,
        "stop_loss": 1880.0,
    }

    with patch("apps.web.control_routes.get_trade_by_id", return_value=fake_trade):
        # Setting Long SL to 1960.0 (ABOVE current price 1950.0) MUST fail!
        res = client.post(
            "/api/v1/control/trade/trade-long-1/modify-sl",
            json={"new_stop_loss": 1960.0},
        )
        assert res.status_code == 422
        assert "Invalid Long SL" in res.json()["detail"]

        # Setting Long SL to 1930.0 (BELOW current price 1950.0) MUST succeed!
        with patch("apps.web.control_routes.update_trade_sl") as mock_update:
            res_ok = client.post(
                "/api/v1/control/trade/trade-long-1/modify-sl",
                json={"new_stop_loss": 1930.0},
            )
            assert res_ok.status_code == 200
            assert res_ok.json()["status"] == "SUCCESS"
            assert res_ok.json()["updated_stop_loss"] == 1930.0
            mock_update.assert_called_once()


def test_trigger_instant_scan(client):
    """Verify on-demand scanner execution endpoint."""
    res = client.post("/api/v1/control/scanner/trigger")
    assert res.status_code == 200
    assert res.json()["status"] == "TRIGGERED"
