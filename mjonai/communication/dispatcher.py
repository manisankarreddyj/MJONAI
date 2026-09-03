"""
Module: communication/dispatcher.py
Purpose: SOTA Central Multi-Channel Broadcast Façade & Fan-Out Hub for MJONAI.
         Delivers alerts concurrently across Telegram, Discord, and the Web UI Event Stream.
"""

import logging
from typing import Dict, List, Any, Optional

from mjonai.communication.telegram import (
    send_signal_alert,
    send_trade_closed_alert,
    send_emergency_kill_alert,
    send_pre_market_brief_alert,
    send_eod_summary_alert,
    send_market_state_alert,
    send_mqi_alert,
)
from mjonai.communication.discord import (
    send_discord_signal,
    send_discord_trade_closed,
    send_discord_emergency,
    send_discord_pre_market,
    send_discord_eod,
)
from mjonai.communication.events import publish_event

logger = logging.getLogger(__name__)


def _safe_dispatch(func, *args, **kwargs) -> Any:
    """Execute channel dispatch with strict error isolation (failures never cascade)."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"[Dispatcher] Channel call failed for {getattr(func, '__name__', str(func))}: {e}")
        return {"ok": False, "error": str(e)}


def broadcast_signal(signal: Dict[str, Any]) -> Dict[str, Any]:
    """Fan-out trade entry signal to Telegram, Discord, and Web Stream with channel error isolation."""
    tg_res = _safe_dispatch(send_signal_alert, signal)
    dc_res = _safe_dispatch(send_discord_signal, signal)
    ev_res = _safe_dispatch(publish_event, "SIGNAL_EMITTED", signal)
    ev_id = getattr(ev_res, "event_id", None) if hasattr(ev_res, "event_id") else None
    return {"telegram": tg_res, "discord": dc_res, "event_id": ev_id}


def broadcast_trade_closed(trade: Dict[str, Any]) -> Dict[str, Any]:
    """Fan-out trade exit notification to Telegram, Discord, and Web Stream with channel error isolation."""
    tg_res = _safe_dispatch(send_trade_closed_alert, trade)
    dc_res = _safe_dispatch(send_discord_trade_closed, trade)
    ev_res = _safe_dispatch(publish_event, "TRADE_CLOSED", trade)
    ev_id = getattr(ev_res, "event_id", None) if hasattr(ev_res, "event_id") else None
    return {"telegram": tg_res, "discord": dc_res, "event_id": ev_id}


def broadcast_emergency(reason: str, pnl_today: float, positions_closed: int) -> Dict[str, Any]:
    """Fan-out emergency kill switch alarm to Telegram, Discord, and Web Stream with channel error isolation."""
    tg_res = _safe_dispatch(send_emergency_kill_alert, reason, pnl_today, positions_closed)
    dc_res = _safe_dispatch(send_discord_emergency, reason, pnl_today, positions_closed)
    ev_res = _safe_dispatch(publish_event, "EMERGENCY_HALT", {
        "reason": reason,
        "pnl_today": pnl_today,
        "positions_closed": positions_closed,
    })
    ev_id = getattr(ev_res, "event_id", None) if hasattr(ev_res, "event_id") else None
    return {"telegram": tg_res, "discord": dc_res, "event_id": ev_id}


def broadcast_pre_market(
    gap_data: Dict[str, Any],
    fii_data: Dict[str, Any],
    sector_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Fan-out 09:00 AM macro briefing to Telegram, Discord, and Web Stream with channel error isolation."""
    tg_res = _safe_dispatch(send_pre_market_brief_alert, gap_data, fii_data, sector_data)
    dc_res = _safe_dispatch(send_discord_pre_market, gap_data, fii_data, sector_data)
    ev_res = _safe_dispatch(publish_event, "PRE_MARKET_BRIEF", {
        "gap": gap_data,
        "fii": fii_data,
        "sectors": sector_data,
    })
    ev_id = getattr(ev_res, "event_id", None) if hasattr(ev_res, "event_id") else None
    return {"telegram": tg_res, "discord": dc_res, "event_id": ev_id}


def broadcast_eod(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Fan-out 03:30 PM EOD performance scorecard to Telegram, Discord, and Web Stream with channel error isolation."""
    tg_res = _safe_dispatch(send_eod_summary_alert, summary)
    dc_res = _safe_dispatch(send_discord_eod, summary)
    ev_res = _safe_dispatch(publish_event, "EOD_SUMMARY", summary)
    ev_id = getattr(ev_res, "event_id", None) if hasattr(ev_res, "event_id") else None
    return {"telegram": tg_res, "discord": dc_res, "event_id": ev_id}


def broadcast_market_state(market_state: str, total_score: int, vix: float) -> Dict[str, Any]:
    """Fan-out market regime updates to Telegram and Web Stream with channel error isolation."""
    tg_res = _safe_dispatch(send_market_state_alert, market_state, total_score, vix)
    ev_res = _safe_dispatch(publish_event, "MARKET_STATE_UPDATED", {
        "market_state": market_state,
        "total_score": total_score,
        "vix": vix,
    })
    ev_id = getattr(ev_res, "event_id", None) if hasattr(ev_res, "event_id") else None
    return {"telegram": tg_res, "event_id": ev_id}
