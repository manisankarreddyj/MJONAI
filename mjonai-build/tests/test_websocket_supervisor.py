"""
Unit and Institutional Test Suite for WebSocket Liveness Supervisor
(orchestration/websocket_supervisor.py)
"""

import pytest
from unittest.mock import patch, MagicMock

from orchestration.websocket_supervisor import (
    handle_websocket_health,
    get_supervisor_state,
    reset_supervisor_state,
)


@pytest.fixture(autouse=True)
def clean_state():
    """Reset supervisor state before each test."""
    reset_supervisor_state()
    yield
    reset_supervisor_state()


def test_websocket_supervisor_healthy_noop():
    """Verify healthy feed returns immediately without triggering restarts."""
    with patch("data.angelone.websocket.restart_websocket") as mock_restart, \
         patch("orchestration.websocket_supervisor.send_message") as mock_send:

        res = handle_websocket_health(ws_healthy=True)
        assert res["healthy"] is True
        assert res["rest_fallback"] is False
        mock_restart.assert_not_called()
        mock_send.assert_not_called()


def test_websocket_supervisor_stale_triggers_restart_and_alert():
    """Verify stale feed triggers alert, web event, and restart_websocket."""
    with patch("data.angelone.websocket.restart_websocket") as mock_restart, \
         patch("orchestration.websocket_supervisor.send_message") as mock_send, \
         patch("orchestration.websocket_supervisor.publish_event") as mock_pub:

        res = handle_websocket_health(ws_healthy=False)
        assert res["healthy"] is False
        assert res["consecutive_attempts"] == 1
        mock_restart.assert_called_once()
        mock_send.assert_called_once()
        mock_pub.assert_called_once()


def test_websocket_supervisor_rate_limits_alerts():
    """Verify duplicate alerts within cooldown window are throttled."""
    with patch("data.angelone.websocket.restart_websocket"), \
         patch("orchestration.websocket_supervisor.send_message") as mock_send:

        # First stale event -> alerts
        handle_websocket_health(ws_healthy=False)
        assert mock_send.call_count == 1

        # Immediate second stale event -> throttled (no second alert)
        handle_websocket_health(ws_healthy=False)
        assert mock_send.call_count == 1


def test_websocket_supervisor_consecutive_failures_trips_rest_fallback():
    """Verify 3 consecutive dropouts engages REST polling fallback."""
    with patch("data.angelone.websocket.restart_websocket"), \
         patch("orchestration.websocket_supervisor.send_message"):

        handle_websocket_health(ws_healthy=False)  # #1
        handle_websocket_health(ws_healthy=False)  # #2
        res3 = handle_websocket_health(ws_healthy=False)  # #3

        assert res3["consecutive_attempts"] == 3
        assert res3["rest_fallback"] is True

        state = get_supervisor_state()
        assert state["rest_fallback_active"] is True
        assert state["consecutive_attempts"] == 3


def test_websocket_supervisor_healthy_restores_state():
    """Verify healthy feed resets consecutive failure counters."""
    with patch("data.angelone.websocket.restart_websocket"), \
         patch("orchestration.websocket_supervisor.send_message"):

        # Trip to attempt 2
        handle_websocket_health(ws_healthy=False)
        handle_websocket_health(ws_healthy=False)
        assert get_supervisor_state()["consecutive_attempts"] == 2

        # Recover to healthy
        res_rec = handle_websocket_health(ws_healthy=True)
        assert res_rec["healthy"] is True
        assert res_rec["rest_fallback"] is False
        assert get_supervisor_state()["consecutive_attempts"] == 0
