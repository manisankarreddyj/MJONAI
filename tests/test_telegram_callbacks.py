"""
Test Suite: tests/test_telegram_callbacks.py
Purpose: Verification of Telegram Inline Keyboards, Callback Query Execution,
         Fail-Closed Authorization, and Anti-Double-Click Message Rewriting.
"""

from unittest.mock import MagicMock, patch
import pytest

from mjonai.communication.telegram import (
    build_inline_keyboard,
    send_signal_alert,
    send_emergency_kill_alert,
    answer_callback_query,
    edit_message_text,
)
from mjonai.communication.telegram_commands import (
    process_callback_query,
    _process_update,
)


def test_build_inline_keyboard():
    """Verify construction of Telegram InlineKeyboardMarkup schema."""
    kb = build_inline_keyboard([
        [
            {"text": "APPROVE", "callback_data": "cb:approve:SIG-101"},
            {"text": "VETO", "callback_data": "cb:veto:SIG-101"},
        ]
    ])
    assert "inline_keyboard" in kb
    assert len(kb["inline_keyboard"]) == 1
    assert len(kb["inline_keyboard"][0]) == 2
    assert kb["inline_keyboard"][0][0]["text"] == "APPROVE"
    assert kb["inline_keyboard"][0][0]["callback_data"] == "cb:approve:SIG-101"


def test_send_signal_alert_attaches_inline_buttons():
    """Verify trade entry signal alerts attach APPROVE and VETO buttons."""
    fake_signal = {
        "id": "SIG-TEST-42",
        "symbol": "TCS",
        "strategy_id": "ORB_15M",
        "direction": "LONG",
        "confidence": 88,
        "entry_price": 4250.0,
        "stop_loss": 4210.0,
        "target": 4330.0,
        "quantity": 25,
        "risk_reward": 2.0,
        "total_cost": 15.50,
    }

    with patch("mjonai.communication.telegram.send_message") as mock_send:
        mock_send.return_value = {"ok": True}
        res = send_signal_alert(fake_signal)
        assert res["ok"] is True
        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        reply_markup = kwargs.get("reply_markup")
        assert reply_markup is not None
        buttons = reply_markup["inline_keyboard"][0]
        assert buttons[0]["callback_data"] == "cb:approve:SIG-TEST-42"
        assert buttons[1]["callback_data"] == "cb:veto:SIG-TEST-42"


def test_send_emergency_kill_alert_attaches_kill_and_status_buttons():
    """Verify emergency kill alerts attach LOCKOUT and STATUS buttons."""
    with patch("mjonai.communication.telegram.send_message") as mock_send:
        mock_send.return_value = {"ok": True}
        res = send_emergency_kill_alert("Max Intraday Loss Breach", -6500.0, 3)
        assert res["ok"] is True
        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        reply_markup = kwargs.get("reply_markup")
        assert reply_markup is not None
        buttons = reply_markup["inline_keyboard"][0]
        assert buttons[0]["callback_data"] == "cb:kill"
        assert buttons[1]["callback_data"] == "cb:status"


def test_process_callback_query_kill():
    """Verify cb:kill triggers emergency kill switch and updates message."""
    with patch("mjonai.communication.telegram_commands.handle_stop") as mock_stop, \
         patch("mjonai.communication.telegram.answer_callback_query") as mock_ack, \
         patch("mjonai.communication.telegram.edit_message_text") as mock_edit:

        ack = process_callback_query(
            cb_id="CB-99",
            data="cb:kill",
            chat_id="123456",
            msg_id=101,
            original_text="Emergency Warning",
        )
        assert "Master Kill Switch" in ack
        mock_stop.assert_called_once()
        mock_ack.assert_called_once()
        mock_edit.assert_called_once()
        edit_text = mock_edit.call_args[1]["text"]
        assert "[🚨 EXECUTED: MASTER KILL SWITCH" in edit_text


def test_process_callback_query_approve_and_veto():
    """Verify cb:approve and cb:veto journal into the advisory queue and are
    labelled advisory-only (P1: the old handler only acked, so a tap looked
    like an execution)."""
    with patch("mjonai.communication.telegram.answer_callback_query") as mock_ack, \
         patch("mjonai.communication.telegram.edit_message_text") as mock_edit, \
         patch("mjonai.communication.telegram_commands._journal_disposition",
               return_value=True) as mock_journal:

        ack_app = process_callback_query("CB-1", "cb:approve:SIG-888", "123456", 201, "Signal Alert")
        assert "SIG-888" in ack_app
        assert "advisory only" in ack_app
        assert "advisory only" in mock_edit.call_args[1]["text"]
        mock_journal.assert_called_with("SIG-888", "APPROVED_FOR_MANUAL", "via Telegram button")

        ack_veto = process_callback_query("CB-2", "cb:veto:SIG-888", "123456", 202, "Signal Alert")
        assert "SIG-888" in ack_veto
        assert "advisory only" in ack_veto
        mock_journal.assert_called_with("SIG-888", "REJECTED", "via Telegram button")


def test_disposition_journal_outage_never_breaks_ack():
    """A journal outage must not break the callback ack path (best-effort)."""
    from mjonai.communication.telegram_commands import _journal_disposition
    with patch("apps.web.data_views.record_console_decision",
               side_effect=RuntimeError("DB down")):
        assert _journal_disposition("SIG-1", "APPROVED_FOR_MANUAL", "x") is False


def test_process_callback_query_pause_and_resume():
    """Verify cb:pause and cb:resume control manual trading state."""
    with patch("mjonai.communication.telegram_commands.handle_pause") as mock_pause, \
         patch("mjonai.communication.telegram_commands.handle_resume") as mock_resume, \
         patch("mjonai.communication.telegram.answer_callback_query"), \
         patch("mjonai.communication.telegram.edit_message_text"):

        process_callback_query("CB-3", "cb:pause", "123456", 301, "Status")
        mock_pause.assert_called_once()

        process_callback_query("CB-4", "cb:resume", "123456", 302, "Status")
        mock_resume.assert_called_once()


def test_unauthorized_callback_query_rejected_fail_closed():
    """Verify callback queries from unauthorized users are rejected fail-closed."""
    fake_update = {
        "update_id": 999,
        "callback_query": {
            "id": "CB-HACKER",
            "from": {"id": 999999999},
            "data": "cb:kill",
            "message": {"message_id": 55, "chat": {"id": 999999999}, "text": "Halt"},
        }
    }

    with patch("mjonai.communication.telegram_commands._is_authorized", return_value=False), \
         patch("mjonai.communication.telegram.answer_callback_query") as mock_ack, \
         patch("mjonai.communication.telegram_commands.handle_stop") as mock_stop:

        _process_update(fake_update)
        mock_stop.assert_not_called()
        mock_ack.assert_called_once_with("CB-HACKER", text="Unauthorized", show_alert=True)
