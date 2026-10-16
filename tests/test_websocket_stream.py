"""
Unit tests for app/websocket_stream.py.
Validates high-frequency telemetry snapshot generation and WebSocketHub mechanics.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from apps.web.websocket_stream import get_live_telemetry_snapshot, WebSocketHub


def test_live_telemetry_snapshot_structure():
    """Verify telemetry snapshot payload schema conforms strictly to specification."""
    # build_open_trades shape (the WS single source of truth): side +
    # freshness-gated current_price + direction-adjusted unrealized.
    fake_enriched = [
        {
            "id": "t-101",
            "symbol": "RELIANCE",
            "side": "BUY",
            "strategy_id": "S01",
            "entry_price": 2500.0,
            "current_price": 2550.0,
            "price_source": "delayed_15m",
            "stale": False,
            "quantity": 25,
            "stop_loss": 2480.0,
            "target": 2600.0,
            "target_1": 2600.0,
            "unrealized_pnl": 1250.0,
            "unrealized_pct": 2.0,
        }
    ]

    with patch("apps.web.data_views.build_open_trades", return_value=fake_enriched):
        snapshot = get_live_telemetry_snapshot()
        assert snapshot["type"] == "TELEMETRY_PULSE"
        assert "session_state" in snapshot
        assert "operational_tier" in snapshot
        assert "sizing_multiplier" in snapshot
        assert snapshot["open_trades_count"] == 1
        assert snapshot["total_unrealized_pnl"] == 1250.0
        assert len(snapshot["open_trades"]) == 1
        row = snapshot["open_trades"][0]
        assert row["symbol"] == "RELIANCE"
        assert row["current_price"] == 2550.0
        assert row["pnl"] == 1250.0
        assert row["pnl_pct"] == 2.0
        assert row["stale"] is False


def test_live_telemetry_snapshot_stale_never_books_fiction():
    """A stale (no-LTP) row must surface stale:true, never entry-as-profit."""
    fake_enriched = [
        {
            "id": "t-102",
            "symbol": "INFY",
            "side": "BUY",
            "strategy_id": "S01",
            "entry_price": 1500.0,
            "current_price": None,
            "price_source": None,
            "stale": True,
            "quantity": 10,
            "stop_loss": 1450.0,
            "target": 1600.0,
            "target_1": 1600.0,
            "unrealized_pnl": None,
            "unrealized_pct": None,
        }
    ]

    with patch("apps.web.data_views.build_open_trades", return_value=fake_enriched):
        snapshot = get_live_telemetry_snapshot()
        assert snapshot["total_unrealized_pnl"] == 0.0
        row = snapshot["open_trades"][0]
        assert row["stale"] is True
        # Display continuity (entry flat) with zeroed PnL + stale flag —
        # the blotter renders a STALE badge, never a fake flat profit.
        assert row["current_price"] == 1500.0
        assert row["pnl"] == 0.0


def test_snapshot_pulse_logs_throttled_observability_line(caplog):
    """The 500ms WS cadence must not flood web.log — max 1 pulse line/60s."""
    import apps.web.websocket_stream as ws_mod

    fake_enriched = [
        {
            "id": "t-103", "symbol": "TCS", "side": "BUY", "strategy_id": "S01",
            "entry_price": 2400.0, "current_price": 2410.0, "price_source": "delayed_15m",
            "stale": False, "quantity": 4, "stop_loss": 2350.0, "target": 2500.0,
            "target_1": 2500.0, "unrealized_pnl": 40.0, "unrealized_pct": 0.42,
        }
    ]
    ws_mod._last_snapshot_log_ts = 0.0  # force the window open
    with patch("apps.web.data_views.build_open_trades", return_value=fake_enriched):
        with caplog.at_level("INFO", logger="apps.web.websocket_stream"):
            get_live_telemetry_snapshot()
            get_live_telemetry_snapshot()  # second tick inside the window: silent
    pulse_lines = [r for r in caplog.records if "[ws/stream] pulse" in r.getMessage()]
    assert len(pulse_lines) == 1
    assert "n=1" in pulse_lines[0].getMessage()
    assert "total_pnl=40.0" in pulse_lines[0].getMessage()


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
