"""
Unit and Institutional Test Suite for Discord Gateway, Web Event Stream, and Dispatcher Hub
(communication/discord.py, communication/events.py, communication/dispatcher.py)
"""

import pytest
from unittest.mock import patch, MagicMock

from mjonai.communication.discord import (
    send_discord_webhook,
    send_discord_signal,
    send_discord_trade_closed,
    send_discord_emergency,
    send_discord_pre_market,
    send_discord_eod,
    COLOR_BUY,
    COLOR_SELL,
    COLOR_EMERGENCY,
)
from mjonai.communication.events import (
    publish_event,
    get_recent_events,
    clear_events_buffer,
    WebEvent,
)
from mjonai.communication.dispatcher import (
    broadcast_signal,
    broadcast_trade_closed,
    broadcast_emergency,
    broadcast_pre_market,
    broadcast_eod,
    broadcast_market_state,
)


def test_send_discord_webhook_dry_run():
    """Verify safe dry-run return when Discord webhook URL is unset."""
    with patch("mjonai.communication.discord._get_webhook_url", return_value=None):
        res = send_discord_webhook(content="Hello Discord")
        assert res["ok"] is False
        assert res.get("dry_run") is True


def test_send_discord_signal_formatting():
    """Verify Discord trade signal embed structure and color."""
    signal = {
        "symbol": "RELIANCE",
        "strategy_id": "S01_MomentumRSI",
        "direction": "LONG",
        "confidence": 85,
        "entry_price": 1365.0,
        "stop_loss": 1323.0,
        "target": 1470.0,
        "quantity": 10,
        "risk_reward": 2.5,
        "total_cost": 25.0,
        "cio_summary": "High momentum breakout cleared",
    }
    with patch("mjonai.communication.discord.send_discord_webhook", return_value={"ok": True}) as mock_hook:
        send_discord_signal(signal)
        mock_hook.assert_called_once()
        embeds = mock_hook.call_args[1]["embeds"]
        assert len(embeds) == 1
        assert embeds[0]["color"] == COLOR_BUY
        assert "RELIANCE" in embeds[0]["title"]


def test_web_events_ring_buffer_and_retrieval():
    """Verify Web Event bus publishing, sequence incrementing, and retrieval."""
    clear_events_buffer()

    ev1 = publish_event("SIGNAL_EMITTED", {"symbol": "TCS", "price": 4150.0})
    ev2 = publish_event("TRADE_CLOSED", {"symbol": "INFY", "pnl": 1200.0})

    assert ev1.event_id == 1
    assert ev2.event_id == 2

    recent = get_recent_events(limit=10)
    assert len(recent) == 2
    assert recent[0]["event_type"] == "SIGNAL_EMITTED"
    assert recent[1]["event_type"] == "TRADE_CLOSED"

    since = get_recent_events(since_id=1)
    assert len(since) == 1
    assert since[0]["payload"]["symbol"] == "INFY"


def test_dispatcher_fan_out_broadcast():
    """Verify unified dispatcher fans out concurrently to Telegram, Discord, and Web Stream."""
    clear_events_buffer()

    with patch("mjonai.communication.dispatcher.send_signal_alert", return_value={"ok": True}) as mock_tg, \
         patch("mjonai.communication.dispatcher.send_discord_signal", return_value={"ok": True}) as mock_dc:

        res = broadcast_signal({"symbol": "SBIN", "entry_price": 820.0})
        assert mock_tg.called
        assert mock_dc.called
        assert res["event_id"] > 0

        recent = get_recent_events(limit=1)
        assert len(recent) == 1
        assert recent[0]["event_type"] == "SIGNAL_EMITTED"
        assert recent[0]["payload"]["symbol"] == "SBIN"
