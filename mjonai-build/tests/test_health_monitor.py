"""
Unit and Institutional Test Suite for Continuous System Health & Telemetry Monitor
(orchestration/health_monitor.py)
"""

import pytest
from unittest.mock import patch, MagicMock

from orchestration.health_monitor import (
    collect_health_log,
    _collect_health_log,
    _get_hardware_metrics,
    _check_internet_socket,
    SystemHealthMetrics,
)


def test_get_hardware_metrics_ranges():
    """Verify CPU, RAM, and Disk percentage values are non-negative and bounded."""
    cpu, ram, disk = _get_hardware_metrics()
    assert 0.0 <= cpu <= 100.0
    assert 0.0 <= ram <= 100.0
    assert 0.0 <= disk <= 100.0


def test_check_internet_socket_probe():
    """Verify TCP socket internet check with mocked success and failure."""
    with patch("socket.socket") as mock_sock:
        mock_instance = MagicMock()
        mock_sock.return_value.__enter__.return_value = mock_instance

        # 1. Success case
        assert _check_internet_socket() is True

        # 2. Failure case
        mock_instance.connect.side_effect = OSError("Network unreachable")
        assert _check_internet_socket() is False


def test_collect_health_log_persists_and_returns_contract():
    """Verify collect_health_log generates typed contract and calls repository persistence."""
    with patch("db.repository.insert_health_log") as mock_insert, \
         patch("orchestration.health_monitor._get_hardware_metrics", return_value=(12.5, 45.0, 33.2)), \
         patch("orchestration.health_monitor._check_internet_socket", return_value=True):

        metrics: SystemHealthMetrics = collect_health_log(
            websocket_healthy=True,
            angelone_connected=True,
            live_prices_count=150,
            stale_symbols=0,
            active_trades=3,
            supabase_latency_ms=45,
            groq_latency_ms=180,
        )

        assert metrics.internet_ok is True
        assert metrics.websocket_healthy is True
        assert metrics.cpu_pct == 12.5
        assert metrics.ram_pct == 45.0
        assert metrics.live_prices_count == 150
        assert metrics.supabase_latency_ms == 45
        assert metrics.groq_latency_ms == 180

        mock_insert.assert_called_once()
        payload = mock_insert.call_args[0][0]
        assert payload["oracle_cpu_pct"] == 12.5
        assert payload["live_prices_count"] == 150


def test_collect_health_log_ram_critical_alert():
    """Verify emergency alert is dispatched when RAM exceeds critical threshold."""
    with patch("db.repository.insert_health_log"), \
         patch("orchestration.health_monitor._get_hardware_metrics", return_value=(20.0, 96.5, 50.0)), \
         patch("orchestration.health_monitor.send_message") as mock_alert:

        metrics = collect_health_log(websocket_healthy=True)
        assert metrics.ram_pct == 96.5
        mock_alert.assert_called_once()
        msg = mock_alert.call_args[0][0]
        assert "RAM at <b>96.5%</b>" in msg


def test_legacy_collect_health_log_alias():
    """Verify backwards-compatible _collect_health_log function."""
    with patch("orchestration.health_monitor.collect_health_log") as mock_collect:
        _collect_health_log(websocket_healthy=True, active_trades=2)
        mock_collect.assert_called_once()
