"""
Unit and Institutional Test Suite for Outbound Telegram Notification Gateway
(communication/telegram.py)
"""

import pytest
from unittest.mock import patch, MagicMock

from communication.telegram import (
    send_message,
    send_mqi_alert,
    send_market_state_alert,
    send_signal_alert,
    send_trade_closed_alert,
    send_emergency_kill_alert,
    send_pre_market_brief_alert,
    send_eod_summary_alert,
)


def test_send_message_dry_run_when_credentials_absent():
    """Verify safe dry-run return when Telegram credentials are unset in env."""
    with patch("communication.telegram._get_credentials", return_value=(None, None)):
        res = send_message("Hello MJONAI")
        assert res["ok"] is False
        assert res.get("dry_run") is True


def test_send_mqi_alert_formatting():
    """Verify MQI alert text formatting for normal and no-trade days."""
    with patch("communication.telegram.send_message", return_value={"ok": True}) as mock_send:
        # 1. Market Ready
        send_mqi_alert("HIGH", 85.0, 3, False)
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "MARKET READY" in msg
        assert "HIGH" in msg
        assert "85%" in msg

        # 2. No Trade Day
        mock_send.reset_mock()
        send_mqi_alert("LOW", 25.0, 0, True)
        mock_send.assert_called_once()
        msg_no_trade = mock_send.call_args[0][0]
        assert "NO TRADE DAY" in msg_no_trade
        assert "Capital protected" in msg_no_trade


def test_send_market_state_alert_formatting():
    """Verify market state alert text formatting."""
    with patch("communication.telegram.send_message", return_value={"ok": True}) as mock_send:
        send_market_state_alert("BULL", 4, 13.8)
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "Market State" in msg
        assert "BULL" in msg
        assert "4/4" in msg
        assert "13.80" in msg


def test_send_signal_alert_long_and_short():
    """Verify trade signal notification formatting."""
    signal = {
        "symbol": "RELIANCE",
        "strategy_id": "S01_MomentumRSI",
        "signal_type": "BUY",
        "direction": "LONG",
        "confidence": 82,
        "entry_price": 1365.0,
        "stop_loss": 1323.0,
        "target": 1470.0,
        "quantity": 10,
        "risk_reward": 2.5,
        "total_cost": 28.5,
        "cio_summary": "Strong multi-timeframe breakout cleared by risk sentry",
    }
    with patch("communication.telegram.send_message", return_value={"ok": True}) as mock_send:
        send_signal_alert(signal)
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "RELIANCE" in msg
        assert "S01_MomentumRSI" in msg
        assert "82%" in msg
        assert "₹1365.00" in msg
        assert "1 : 2.50" in msg
        assert "Strong multi-timeframe breakout" in msg


def test_send_trade_closed_alert():
    """Verify trade exit notification with realized PnL."""
    trade = {
        "symbol": "TCS",
        "direction": "LONG",
        "exit_reason": "TARGET_TP1_HIT",
        "realized_pnl": 4250.0,
        "pnl_pct": 3.8,
        "entry_price": 4150.0,
        "exit_price": 4307.7,
        "quantity": 25,
        "holding_days": 4,
    }
    with patch("communication.telegram.send_message", return_value={"ok": True}) as mock_send:
        send_trade_closed_alert(trade)
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "POSITION CLOSED" in msg
        assert "TCS" in msg
        assert "TARGET_TP1_HIT" in msg
        assert "+₹4,250.00" in msg
        assert "+3.80%" in msg
        assert "4 days" in msg


def test_send_emergency_kill_alert():
    """Verify emergency kill switch alarm text."""
    with patch("communication.telegram.send_message", return_value={"ok": True}) as mock_send:
        send_emergency_kill_alert("Daily Max Drawdown 2.5% Breached", -12500.0, 3)
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "EMERGENCY KILL SWITCH TRIPPED" in msg
        assert "Daily Max Drawdown 2.5% Breached" in msg
        assert "-₹12,500.00" in msg
        assert "3" in msg


def test_send_pre_market_brief_and_eod_scorecard():
    """Verify 09:00 AM macro briefing and 03:30 PM EOD scorecard alerts."""
    with patch("communication.telegram.send_message", return_value={"ok": True}) as mock_send:
        # Pre-Market Brief
        gap_data = {"gap_points": 45.0, "gap_type": "BREAKAWAY_GAP", "global_macro_score": 78.0}
        fii_data = {"liquidity_regime": "MEGA_BULLISH", "fii_long_short_ratio": 1.65}
        sector_data = {"top_sector_pick": "REALTY", "leading_sectors": ["REALTY", "METAL"]}

        send_pre_market_brief_alert(gap_data, fii_data, sector_data)
        msg_pre = mock_send.call_args[0][0]
        assert "PRE-MARKET MACRO BRIEF" in msg_pre
        assert "+45.0 pts (BREAKAWAY_GAP)" in msg_pre
        assert "MEGA_BULLISH" in msg_pre
        assert "REALTY" in msg_pre

        # EOD Scorecard
        mock_send.reset_mock()
        summary = {
            "net_pnl": 8650.0,
            "gross_pnl": 9200.0,
            "total_friction": 550.0,
            "win_rate_pct": 75.0,
            "total_trades": 4,
            "winning_trades": 3,
            "open_trades_count": 2,
        }
        send_eod_summary_alert(summary)
        msg_eod = mock_send.call_args[0][0]
        assert "EOD PERFORMANCE SCORECARD" in msg_eod
        assert "+₹8,650.00" in msg_eod
        assert "75.0%" in msg_eod
        assert "3/4 winners" in msg_eod
