"""
Test Suite: tests/test_discord_resilience.py
Purpose: Verification of Discord Webhook Rate Limiting, HTTP 429 Exponential Backoff Retry,
         and Institutional Rich Embed Formatting.
"""

from unittest.mock import MagicMock, patch
import pytest

from mjonai.communication.discord import (
    send_discord_webhook,
    send_discord_signal,
    send_discord_emergency,
    _DISCORD_RATE_LOCK,
    _discord_timestamps,
)


def test_send_discord_webhook_dry_run_when_unconfigured():
    """Verify mock dry-run when DISCORD_WEBHOOK_URL is missing."""
    with patch.dict("os.environ", {}, clear=True):
        res = send_discord_webhook(content="Test Alert")
        assert res["ok"] is False
        assert res["dry_run"] is True


def test_discord_rate_limit_429_backoff_and_retry():
    """Verify HTTP 429 Retry-After header triggers backoff and retries successfully."""
    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.headers = {"Retry-After": "0.01"}
    mock_resp_429.json.return_value = {"retry_after": 0.01}

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200

    with patch("requests.post", side_effect=[mock_resp_429, mock_resp_200]) as mock_post, \
         patch("time.sleep") as mock_sleep:

        res = send_discord_webhook(
            content="Heavy Traffic Alert",
            webhook_url="https://discord.com/api/webhooks/test/123",
            max_retries=3,
        )

        assert res["ok"] is True
        assert res["status_code"] == 200
        assert mock_post.call_count == 2
        mock_sleep.assert_called()


def test_send_discord_signal_rich_embed_structure():
    """Verify rich embed fields and color styling for buy signal."""
    fake_signal = {
        "symbol": "INFY",
        "strategy_id": "S01_MOMENTUM_RSI",
        "direction": "LONG",
        "confidence": 92,
        "entry_price": 1950.0,
        "stop_loss": 1920.0,
        "target": 2010.0,
        "quantity": 50,
        "risk_reward": 2.0,
        "total_cost": 22.50,
    }

    with patch("mjonai.communication.discord.send_discord_webhook") as mock_send:
        mock_send.return_value = {"ok": True}
        res = send_discord_signal(fake_signal)
        assert res["ok"] is True
        mock_send.assert_called_once()
        embeds = mock_send.call_args[1]["embeds"]
        assert len(embeds) == 1
        card = embeds[0]
        assert "INFY" in card["title"]
        assert card["color"] == 0x00FF88  # COLOR_BUY green
        fields = {f["name"]: f["value"] for f in card["fields"]}
        assert "1,950.00" in fields["Entry Price"]
        assert "1,920.00" in fields["Stop Loss"]
