"""
Unit tests for app/websocket_stream.py.
Validates high-frequency telemetry snapshot generation and WebSocketHub mechanics.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from app.websocket_stream import get_live_telemetry_snapshot, WebSocketHub


def test_live_telemetry_snapshot_structure():
    """Verify telemetry snapshot payload schema conforms strictly to specification."""
    fake_open_trades = [
        {
            "id": "t-101",
            "symbol": "RELIANCE",
            "direction": "BUY",
            "entry_price": 2500.0,
            "current_price": 2550.0,
            "stop_loss": 2480.0,
            "trailing_stop": 2500.0,
            "target_1": 2600.0,
            "pnl": 1250.0,
            "pnl_pct": 2.0,
            "strategy_id": "S01",
        }
    ]

    with patch("app.websocket_stream.get_open_trades", return_value=fake_open_trades):
        snapshot = get_live_telemetry_snapshot()
        assert snapshot["type"] == "TELEMETRY_PULSE"
        assert "session_state" in snapshot
        assert "operational_tier" in snapshot
        assert "sizing_multiplier" in snapshot
        assert snapshot["open_trades_count"] == 1
        assert snapshot["total_unrealized_pnl"] == 1250.0
        assert len(snapshot["open_trades"]) == 1
        assert snapshot["open_trades"][0]["symbol"] == "RELIANCE"


def test_websocket_hub_broadcast_and_pruning():
    """Verify WebSocketHub broadcasts cleanly and prunes dead sockets without exception."""
    async def _run():
        hub = WebSocketHub()

        healthy_ws = AsyncMock()
        healthy_ws.send_text = AsyncMock()

        dead_ws = AsyncMock()
        async def fail_send(text):
            raise ConnectionResetError("Client dropped connection")
        dead_ws.send_text = fail_send

        await hub.connect(healthy_ws)
        await hub.connect(dead_ws)
        assert len(hub.active_connections) == 2

        await hub.broadcast({"type": "PING"})
        assert len(hub.active_connections) == 1
        assert healthy_ws in hub.active_connections
        assert dead_ws not in hub.active_connections

    asyncio.run(_run())
