"""
Test Suite: tests/test_module10_extreme_edge_cases.py
Purpose: Extreme Edge Case, Stress, Concurrency, and Quant Boundary Verification for Module 10.
"""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch
import pytest

from mjonai.communication.telegram import (
    send_message,
    _chunk_text,
)
from mjonai.communication.telegram_commands import (
    process_callback_query,
    handle_sl,
    handle_positions,
    clear_callback_cache,
)
from mjonai.communication.eod_report import generate_eod_digest
from mjonai.communication.dispatcher import broadcast_signal


def test_ultra_long_message_chunking():
    """Edge Case 1: Ultra-long message (>10,000 chars) chunks properly at line boundaries."""
    long_lines = [f"Position #{i}: NIFTY_FUT_OPT_STRIKE_{i} PnL: +₹{i*100}" for i in range(250)]
    huge_msg = "\n".join(long_lines)
    assert len(huge_msg) > 10000

    chunks = _chunk_text(huge_msg, max_chars=4000)
    assert len(chunks) >= 3
    for c in chunks:
        assert len(c) <= 4000


def test_malformed_html_parse_recovery():
    """Edge Case 2: Telegram HTTP 400 parse error automatically strips HTML and retries."""
    mock_resp_400 = MagicMock()
    mock_resp_400.status_code = 400
    mock_resp_400.text = "Bad Request: can't parse entities in message"
    mock_resp_400.json.return_value = {"ok": False, "description": "can't parse entities"}

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {"ok": True, "result": {"message_id": 999}}

    with patch("mjonai.communication.telegram._get_credentials", return_value=("FAKE_TOKEN", "123456")), \
         patch("requests.post", side_effect=[mock_resp_400, mock_resp_200]) as mock_post:

        res = send_message("<b>Unclosed bold and <rogue_tag> test")
        assert res["ok"] is True
        assert mock_post.call_count == 2
        second_call_payload = mock_post.call_args_list[1][1]["json"]
        assert "parse_mode" not in second_call_payload
        assert "<rogue_tag>" not in second_call_payload["text"]


def test_concurrent_callback_query_idempotency_race_condition():
    """Edge Case 3: Rapid concurrent duplicate clicks trigger idempotency lock."""
    clear_callback_cache()
    executed_count = 0

    def fake_stop():
        nonlocal executed_count
        executed_count += 1

    with patch("mjonai.communication.telegram_commands.handle_stop", side_effect=fake_stop), \
         patch("mjonai.communication.telegram.answer_callback_query"), \
         patch("mjonai.communication.telegram.edit_message_text"):

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(
                    process_callback_query,
                    cb_id=f"CB-{i}",
                    data="cb:kill",
                    chat_id="123456",
                    msg_id=10,
                    original_text="Kill Warning"
                )
                for i in range(5)
            ]
            results = [f.result() for f in futures]

        # Only one should execute handle_stop, others get "Action already processed"
        assert executed_count == 1
        assert any("Master Kill Switch" in r for r in results)
        assert any("Action already processed" in r for r in results)


def test_directional_sl_validation_long_and_short():
    """Edge Case 4: Strict validation of stop loss relative to position direction and LTP."""
    fake_open_trades = [
        {"id": "T-LONG", "symbol": "INFY", "direction": "LONG", "entry_price": 1900.0, "current_sl": 1880.0},
        {"id": "T-SHORT", "symbol": "TCS", "direction": "SHORT", "entry_price": 4200.0, "current_sl": 4250.0},
    ]

    with patch("mjonai.db.repository.get_open_trades", return_value=fake_open_trades), \
         patch("mjonai.data.angelone.websocket.live_prices", {"SYM_INFY": 1950.0, "SYM_TCS": 4150.0}), \
         patch("mjonai.data.angelone.websocket.is_token_fresh", return_value=True), \
         patch("mjonai.data.angelone.token_map.SYMBOL_MAP", {"INFY": "SYM_INFY", "TCS": "SYM_TCS"}), \
         patch("mjonai.db.repository.update_trade_sl", return_value=True), \
         patch("mjonai.communication.telegram_commands._send"):

        # 1. Negative SL rejected
        res = handle_sl("INFY -50.0")
        assert "must be strictly positive" in res

        # 2. LONG SL higher than LTP rejected
        res = handle_sl("INFY 1960.0")
        assert "must be below current price" in res

        # 3. LONG SL below LTP accepted
        res = handle_sl("INFY 1920.0")
        assert "TRAILING STOP LOSS UPDATED" in res
        assert "1920.00" in res

        # 4. SHORT SL lower than LTP rejected
        res = handle_sl("TCS 4100.0")
        assert "must be above current price" in res

        # 5. SHORT SL above LTP accepted
        res = handle_sl("TCS 4180.0")
        assert "TRAILING STOP LOSS UPDATED" in res
        assert "4180.00" in res


def test_short_position_targets_and_sl_in_positions():
    """Edge Case 5: Short positions have downward targets and upward default stop loss."""
    fake_trades = [
        {"id": "T-1", "symbol": "SBIN", "direction": "SHORT", "entry_price": 800.0, "quantity": 10},
    ]

    with patch("mjonai.db.repository.get_open_trades", return_value=fake_trades), \
         patch("mjonai.data.angelone.websocket.live_prices", {}), \
         patch("mjonai.communication.telegram_commands._send"):

        msg = handle_positions()
        assert "SBIN" in msg
        # Target 1 should be entry * 0.97 = 776.00
        assert "776.00" in msg
        # Stop loss should be entry * 1.02 = 816.00
        assert "816.00" in msg


def test_eod_report_zero_division_resilience():
    """Edge Case 6: EOD Report math handles 0 trades, only wins, and only losses gracefully."""
    # Scenario A: Zero trades
    digest_empty = generate_eod_digest(trades=[])
    assert digest_empty.total_trades == 0
    assert digest_empty.win_rate_pct == 0.0
    assert "<b>Net PnL:</b> 🟢 +₹0.00" in digest_empty.html_card

    # Scenario B: Only winning trades (0 losses -> profit factor division by zero)
    digest_wins = generate_eod_digest(trades=[
        {"symbol": "TCS", "status": "CLOSED", "pnl": 5000.0, "strategy_id": "ORB"}
    ])
    assert digest_wins.winning_trades == 1
    assert digest_wins.losing_trades == 0
    assert digest_wins.win_rate_pct == 100.0
    assert "1W / 0L" in digest_wins.html_card
    assert "TCS (+₹5,000.00)" in digest_wins.html_card

    # Scenario C: Only losing trades (0 wins)
    digest_losses = generate_eod_digest(trades=[
        {"symbol": "INFY", "status": "CLOSED", "pnl": -2000.0, "strategy_id": "PULLBACK"}
    ])
    assert digest_losses.winning_trades == 0
    assert digest_losses.losing_trades == 1
    assert digest_losses.win_rate_pct == 0.0
    assert "0W / 1L" in digest_losses.html_card


def test_isolated_channel_failure_cascade_prevention():
    """Edge Case 8: Both Telegram and Discord raising fatal exceptions does not break Event Bus."""
    with patch("mjonai.communication.dispatcher.send_signal_alert", side_effect=Exception("Telegram Network Dead")), \
         patch("mjonai.communication.dispatcher.send_discord_signal", side_effect=Exception("Discord API Dead")), \
         patch("mjonai.communication.dispatcher.publish_event") as mock_pub:

        mock_pub.return_value = MagicMock(event_id=888)
        res = broadcast_signal({"symbol": "TCS", "signal_direction": "LONG"})

        assert res["telegram"]["ok"] is False
        assert "Telegram Network Dead" in res["telegram"]["error"]
        assert res["discord"]["ok"] is False
        assert "Discord API Dead" in res["discord"]["error"]
        mock_pub.assert_called_once()
