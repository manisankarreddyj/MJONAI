"""
Unit and Institutional Test Suite for Inbound Telegram Commands Engine
(communication/telegram_commands.py)
"""

import pytest
from unittest.mock import patch, MagicMock

from mjonai.communication.telegram_commands import (
    process_command_text,
    handle_status,
    handle_pnl,
    handle_trades,
    handle_risk,
    handle_tax,
    handle_macro,
    handle_stop,
    handle_pause,
    handle_resume,
    handle_close,
    handle_help,
    _is_authorized,
)


def test_is_authorized():
    """Verify authorization checks against TELEGRAM_CHAT_ID."""
    with patch("mjonai.communication.telegram_commands._get_credentials", return_value=("mock_token", "12345678")):
        assert _is_authorized("12345678") is True
        assert _is_authorized("99999999") is False


def test_process_command_help():
    """Verify /help returns complete command documentation."""
    with patch("mjonai.communication.telegram_commands._send"):
        res = process_command_text("/help")
        assert res is not None
        assert "/status" in res
        assert "/risk" in res
        assert "/macro" in res
        assert "/panic" in res


def test_process_command_status():
    """Verify /status displays mode and health."""
    mock_trades = [{"id": 1, "symbol": "TCS"}]
    mock_risk = {"manual_pause_active": False, "risk_stop_active": False, "kill_line_active": False, "soft_stop_active": False}

    with patch("mjonai.db.repository.get_open_trades", return_value=mock_trades), \
         patch("mjonai.db.repository.get_trades_closed_today", return_value=[]), \
         patch("mjonai.risk.emergency_triggers.get_state", return_value=mock_risk), \
         patch("mjonai.communication.telegram_commands._send"):

        res = process_command_text("/status")
        assert res is not None
        assert "MJONAI STATUS" in res
        assert "ACTIVE" in res
        assert "Active Open Trades: <b>1</b>" in res


def test_process_command_pnl():
    """Verify /pnl displays mark-to-market live PnL."""
    mock_open_pnl = [
        {"symbol": "RELIANCE", "pnl": 2450.0, "pnl_pct": 2.1, "current_price": 1365.0, "direction": "LONG"},
        {"symbol": "INFY", "pnl": -500.0, "pnl_pct": -0.8, "current_price": 1820.0, "direction": "LONG"},
    ]
    with patch("mjonai.execution.paper.get_open_trades_with_pnl", return_value=mock_open_pnl), \
         patch("mjonai.communication.telegram_commands._send"):

        res = process_command_text("/pnl")
        assert res is not None
        assert "RELIANCE" in res
        assert "INFY" in res
        assert "Total Portfolio P&L: <b>+₹1,950.00</b>" in res


def test_process_command_risk():
    """Verify /risk displays drawdown limits and sentry status."""
    mock_state = {
        "peak_equity": 1000000.0,
        "consecutive_losses": 1,
        "manual_pause_active": False,
        "kill_line_active": False,
        "risk_stop_active": False,
        "soft_stop_active": False,
    }
    with patch("mjonai.risk.emergency_triggers.get_state", return_value=mock_state), \
         patch("mjonai.communication.telegram_commands._send"):

        res = process_command_text("/risk")
        assert res is not None
        assert "MJONAI RISK & SENTRY STATUS" in res
        assert "1/3" in res
        assert "₹1,000,000.00" in res


def test_process_command_macro():
    """Verify /macro and /intel return market state and FII flows."""
    mock_state = {"fii_net_cr": 1250.0, "vix": 14.2, "market_state": "BULL"}
    with patch("mjonai.db.repository.get_latest_market_state", return_value=mock_state), \
         patch("mjonai.communication.telegram_commands._send"):

        res = process_command_text("/macro")
        assert res is not None
        assert "MACRO INTELLIGENCE" in res
        assert "BULL" in res
        assert "+1,250" in res

        res_alias = process_command_text("/intel")
        assert res_alias is not None
        assert "MACRO INTELLIGENCE" in res_alias


def test_process_command_pause_and_resume():
    """Verify /pause and /resume commands toggle pause state."""
    with patch("mjonai.risk.emergency_triggers.set_manual_pause") as mock_pause, \
         patch("mjonai.risk.emergency_triggers.clear_manual_pause") as mock_resume, \
         patch("mjonai.communication.telegram_commands._send"):

        res_p = process_command_text("/pause")
        assert res_p is not None
        assert "MJONAI PAUSED" in res_p
        mock_pause.assert_called_once()

        res_r = process_command_text("/resume")
        assert res_r is not None
        assert "MJONAI RESUMED" in res_r
        mock_resume.assert_called_once()


def test_process_command_stop_and_panic():
    """Verify /panic and /stop trigger emergency liquidation."""
    mock_trades = [{"id": 1, "symbol": "TCS", "entry_price": 4150.0}]
    with patch("mjonai.db.repository.get_open_trades", return_value=mock_trades), \
         patch("mjonai.execution.paper.close_all_paper_trades", return_value=1) as mock_close_all, \
         patch("mjonai.risk.emergency_triggers.set_manual_pause"), \
         patch("mjonai.db.repository.insert_risk_event"), \
         patch("mjonai.communication.telegram_commands._send"):

        res = process_command_text("/panic")
        assert res is not None
        assert "EMERGENCY STOP COMPLETE" in res
        assert "Positions Liquidated: <b>1</b>" in res
        mock_close_all.assert_called_once_with(exit_reason="MANUAL_PANIC_STOP")


def test_process_command_close_symbol():
    """Verify /close SYMBOL closes the targeted trade."""
    mock_trades = [{"id": 101, "symbol": "SBIN", "entry_price": 820.0, "direction": "LONG"}]
    mock_close_res = {"trade_id": "101", "symbol": "SBIN", "net_pnl": 1500.0, "exit_price": 835.0}

    with patch("mjonai.db.repository.get_open_trades", return_value=mock_trades), \
         patch("mjonai.execution.paper.close_paper_trade", return_value=mock_close_res) as mock_close, \
         patch("mjonai.data.angelone.websocket.live_prices", {"SYM_SBIN": 835.0}), \
         patch("mjonai.data.angelone.websocket.is_token_fresh", return_value=True), \
         patch("mjonai.data.angelone.token_map.SYMBOL_MAP", {"SBIN": "SYM_SBIN"}), \
         patch("mjonai.communication.telegram_commands._send"):

        res = process_command_text("/close SBIN")
        assert res is not None
        assert "MANUAL CLOSE: SBIN" in res
        assert "+₹1,500.00" in res
        mock_close.assert_called_once()


def test_process_command_positions():
    """Verify /positions and /pos display open exit ladders."""
    mock_trades = [{
        "id": 101,
        "symbol": "TCS",
        "direction": "LONG",
        "entry_price": 4150.0,
        "current_sl": 4180.0,
        "target_1": 4300.0,
        "target_2": 4420.0,
        "quantity_remaining": 20,
        "sl_stage": "1R_LOCKED",
    }]
    with patch("mjonai.db.repository.get_open_trades", return_value=mock_trades), \
         patch("mjonai.communication.telegram_commands._send"):

        res = process_command_text("/positions")
        assert res is not None
        assert "OPEN POSITIONS & EXIT LADDERS" in res
        assert "TCS" in res
        assert "Trailing SL: <b>₹4180.00</b>" in res
        assert "T1: <b>₹4300.00</b>" in res

        res_alias = process_command_text("/pos")
        assert res_alias is not None
        assert "TCS" in res_alias


def test_process_command_ai():
    """Verify /ai SYMBOL triggers on-demand multi-agent debate room deliberation."""
    mock_debate_res = {
        "final_decision": "APPROVE",
        "consensus_score": 82,
        "summary": "Multi-agent consensus confirms breakout momentum.",
        "deciding_factor": "RRG Leading sector tailwind",
        "transcript": {
            "bull_initial_verdict": "STRONG_BUY",
            "bull_confidence": 85,
            "bear_initial_verdict": "APPROVE",
            "bear_confidence": 75,
            "rounds_conducted": 1,
        },
    }
    with patch("mjonai.agents.debate_room.conduct_adversarial_debate", return_value=mock_debate_res), \
         patch("mjonai.db.repository.get_latest_market_state", return_value={"market_state": "BULL"}), \
         patch("mjonai.communication.telegram_commands._send"):

        res = process_command_text("/ai RELIANCE")
        assert res is not None
        assert "AI DELIBERATION: RELIANCE" in res
        assert "82/100" in res
        assert "STRONG_BUY" in res
        assert "Multi-agent consensus" in res


def test_process_command_sl():
    """Verify /sl SYMBOL NEW_PRICE updates active trailing stop loss."""
    mock_trades = [{"id": 101, "symbol": "TCS", "entry_price": 4150.0, "current_sl": 4100.0, "direction": "LONG"}]
    with patch("mjonai.db.repository.get_open_trades", return_value=mock_trades), \
         patch("mjonai.data.angelone.websocket.live_prices", {"SYM_TCS": 4300.0}), \
         patch("mjonai.data.angelone.websocket.is_token_fresh", return_value=True), \
         patch("mjonai.data.angelone.token_map.SYMBOL_MAP", {"TCS": "SYM_TCS"}), \
         patch("mjonai.db.repository.update_trade_sl", return_value=True) as mock_update_sl, \
         patch("mjonai.communication.telegram_commands._send"):

        res = process_command_text("/sl TCS 4250.0")
        assert res is not None
        assert "TRAILING STOP LOSS UPDATED" in res
        assert "TCS" in res
        assert "₹4250.00" in res
        mock_update_sl.assert_called_once()


def test_close_and_sl_fail_closed_on_stale_feed():
    """2026-09-18 freshness contract: a stale/unknown live tick must NEVER
    price a manual close or validate a stop-loss update."""
    mock_trades = [{"id": 101, "symbol": "TCS", "entry_price": 4150.0,
                    "current_sl": 4100.0, "direction": "LONG"}]

    with patch("mjonai.db.repository.get_open_trades", return_value=mock_trades), \
         patch("mjonai.data.angelone.websocket.live_prices", {"SYM_TCS": 4300.0}), \
         patch("mjonai.data.angelone.websocket.is_token_fresh", return_value=False), \
         patch("mjonai.data.angelone.token_map.SYMBOL_MAP", {"TCS": "SYM_TCS"}), \
         patch("mjonai.execution.paper.close_paper_trade") as mock_close, \
         patch("mjonai.db.repository.update_trade_sl") as mock_update_sl, \
         patch("mjonai.communication.telegram_commands._send"):

        res_close = process_command_text("/close TCS")
        assert "aborted" in res_close
        mock_close.assert_not_called()

        res_sl = process_command_text("/sl TCS 4250.0")
        assert "aborted" in res_sl
        mock_update_sl.assert_not_called()



# ── Regression tests: 2026-08-23 F3 control-plane fixes ────────────────────


def test_unconfigured_chat_id_fails_closed():
    """S2-A6-01: with no TELEGRAM_CHAT_ID configured, commands must be
    REFUSED - the old fail-open handed /stop //panic //close to anyone
    who found the bot token."""
    from mjonai.communication.telegram_commands import _is_authorized

    with patch("mjonai.communication.telegram_commands._get_credentials", return_value=("token", None)):
        assert _is_authorized(chat_id="999999") is False
        assert _is_authorized(chat_id=None) is False


def test_configured_chat_id_still_authorizes_owner():
    from mjonai.communication.telegram_commands import _is_authorized

    with patch("mjonai.communication.telegram_commands._get_credentials", return_value=("token", "12345678")):
        assert _is_authorized(chat_id="12345678") is True
        assert _is_authorized(chat_id="someone_else") is False


def test_verdict_normalization_exact_tokens():
    """S2-A6-04: 'NO_BUY' must NOT count as APPROVE; CAUTION must survive."""
    from mjonai.agents.llm_bridge import extract_and_validate_json

    raw = '{"verdict": "NO_BUY", "confidence": 80, "reasons": ["x"]}'
    data = extract_and_validate_json(raw)
    assert data["verdict"] == "NEUTRAL"          # unknown -> neutral, never approve

    caution = extract_and_validate_json('{"verdict": "CAUTION", "confidence": 60, "reasons": ["y"]}')
    assert caution["verdict"] == "CAUTION"       # preserved for round-2 trigger

    veto = extract_and_validate_json('{"verdict": "REJECT", "confidence": 90, "reasons": ["z"]}')
    assert veto["verdict"] == "VETO"

    approve = extract_and_validate_json('{"verdict": "APPROVE", "confidence": 90, "reasons": ["a"]}')
    assert approve["verdict"] == "APPROVE"


def test_handle_tax_routes_and_annualises():
    """/tax surfaces the authoritative FY summary (a trade is placed inside the CURRENT FY)."""
    from datetime import datetime
    from mjonai.execution.tax import current_indian_financial_year
    fy_start, fy_end = current_indian_financial_year()
    exit_dt = datetime(fy_end.year, fy_end.month, 15)          # inside current FY window
    entry_dt = datetime(fy_end.year - 2, fy_end.month, 15)      # >365d -> LTCG
    trade = {
        "gross_pnl": 200000.0, "asset_class": "EQUITY",
        "entry_time": entry_dt.isoformat(), "exit_time": exit_dt.isoformat(),
    }
    with patch("mjonai.communication.telegram_commands._send"), \
         patch("mjonai.db.repository.get_all_closed_trades", return_value=[trade]):
        out = handle_tax()
    assert "TOTAL FY TAX DUE" in out
    assert "9,750" in out  # LTCG ₹200k − ₹125k exemption = ₹75k @ 13% = ₹9,750
