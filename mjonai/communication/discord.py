"""
Module: communication/discord.py
Purpose: SOTA Discord Webhook Gateway with Rich Color-Coded Embed Cards.
         Dispatches Trade Signals, Exit PnL Alerts, Emergency Alarms,
         Pre-Market 09:00 AM Macro Briefs, and EOD Performance Scorecards.
"""

from datetime import datetime, timezone
import html
import logging
import os
from typing import Dict, List, Any, Optional, Union

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from mjonai.core.time_utils import now_ist
from mjonai.communication.telegram import _format_inr

logger = logging.getLogger(__name__)

# Discord embed color palette
COLOR_BUY = 0x00FF88        # Vibrant Green
COLOR_SELL = 0xFF3366       # Vibrant Red
COLOR_GOLD = 0xFFD700       # Gold / Neutral
COLOR_EMERGENCY = 0xFF0033  # Crimson Red
COLOR_INFO = 0x3399FF       # Cerulean Blue


def _get_webhook_url() -> Optional[str]:
    """Dynamically resolve Discord Webhook URL from environment."""
    return os.getenv("DISCORD_WEBHOOK_URL")


import threading
import time

_DISCORD_RATE_LOCK = threading.Lock()
_discord_timestamps: List[float] = []
_MAX_DISCORD_BURST: int = 5
_DISCORD_WINDOW_SECONDS: float = 2.0


def send_discord_webhook(
    content: Optional[str] = None,
    embeds: Optional[List[Dict[str, Any]]] = None,
    webhook_url: Optional[str] = None,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Send formatted payload to Discord Webhook with proactive token bucket rate limiting,
    timeout safety, and HTTP 429 Retry-After backoff handling.
    """
    url = webhook_url or _get_webhook_url()
    if not url:
        logger.debug("[Discord] Mock Dry-Run: DISCORD_WEBHOOK_URL not set.")
        return {"ok": False, "dry_run": True, "error": "Webhook URL missing"}

    payload: Dict[str, Any] = {}
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds

    import requests

    for attempt in range(max_retries):
        # 1. Token Bucket Proactive Throttle: max 5 requests per 2 seconds
        with _DISCORD_RATE_LOCK:
            now = time.time()
            _discord_timestamps[:] = [t for t in _discord_timestamps if (now - t) < _DISCORD_WINDOW_SECONDS]
            if len(_discord_timestamps) >= _MAX_DISCORD_BURST:
                sleep_duration = _DISCORD_WINDOW_SECONDS - (now - _discord_timestamps[0]) + 0.05
                time.sleep(max(0.05, sleep_duration))
                now = time.time()
            _discord_timestamps.append(now)

        try:
            r = requests.post(url, json=payload, timeout=5)
            if r.status_code in (200, 204):
                return {"ok": True, "status_code": r.status_code}
            elif r.status_code == 429:
                retry_after = 1.0
                try:
                    retry_after = float(r.headers.get("Retry-After") or r.json().get("retry_after", 1.0))
                except Exception:
                    pass
                logger.warning(f"[Discord] Rate limit HTTP 429 hit. Backing off for {retry_after:.2f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(min(retry_after, 5.0))
                continue
            else:
                return {"ok": False, "status_code": r.status_code, "text": r.text}
        except Exception as e:
            logger.error(f"[Discord] Send failed on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                return {"ok": False, "error": str(e)}
            time.sleep(0.5 * (2 ** attempt))

    return {"ok": False, "error": "Exceeded maximum retry attempts"}


def send_discord_signal(signal: Dict[str, Any]) -> Dict[str, Any]:
    """Send trade entry signal embed to Discord."""
    try:
        from mjonai.core.constants import SYSTEM_MODE

        symbol = str(signal.get("symbol", "UNKNOWN"))
        strategy = str(signal.get("strategy_id", "Quantitative Strategy"))
        direction = str(signal.get("direction", signal.get("signal_direction", "LONG"))).upper()
        confidence = int(float(signal.get("confidence") or 0))

        entry = float(signal.get("entry_price") or 0.0)
        sl = float(signal.get("stop_loss") or 0.0)
        target = float(signal.get("target") or 0.0)
        qty = int(signal.get("quantity") or 0)
        rr = float(signal.get("risk_reward") or 0.0)
        cost = float(signal.get("total_cost") or 0.0)

        color = COLOR_BUY if direction == "LONG" else COLOR_SELL
        mode_str = "🧪 Paper Trade" if SYSTEM_MODE == "RESEARCH" else "⚡ LIVE REAL-MONEY"

        risk_capital = abs(entry - sl) * qty
        fields = [
            {"name": "Asset & Strategy", "value": f"**{symbol}** ({strategy})", "inline": False},
            {"name": "Direction", "value": f"**{direction}**", "inline": True},
            {"name": "Conviction", "value": f"**{confidence}%**", "inline": True},
            {"name": "Mode", "value": f"*{mode_str}*", "inline": True},
            {"name": "Entry Price", "value": f"₹{entry:,.2f}", "inline": True},
            {"name": "Stop Loss", "value": f"₹{sl:,.2f}", "inline": True},
            {"name": "Target (TP1)", "value": f"₹{target:,.2f}", "inline": True},
            {"name": "Quantity", "value": f"{qty} units", "inline": True},
            {"name": "Real R:R", "value": f"1 : {rr:.2f}", "inline": True},
            {"name": "Capital at Risk", "value": f"₹{risk_capital:,.2f}", "inline": True},
            {"name": "Est. Friction", "value": f"₹{cost:.2f}", "inline": True},
        ]

        cio_summary = signal.get("cio_summary") or signal.get("summary")
        if cio_summary:
            fields.append({"name": "💡 CIO Summary", "value": f"*{cio_summary}*", "inline": False})

        embed = {
            "title": f"🎯 MJONAI Trade Signal: {symbol} ({direction})",
            "color": color,
            "fields": fields,
            "timestamp": now_ist().isoformat(),
            "footer": {"text": "MJONAI Quantitative Trading Engine"},
        }
        return send_discord_webhook(embeds=[embed])
    except Exception as e:
        logger.error(f"[Discord] send_discord_signal error: {e}")
        return {"ok": False, "error": str(e)}


def send_discord_trade_closed(trade: Dict[str, Any]) -> Dict[str, Any]:
    """Send position exit notification embed with realized PnL to Discord."""
    try:
        symbol = str(trade.get("symbol", "UNKNOWN"))
        direction = str(trade.get("direction", "LONG")).upper()
        exit_reason = str(trade.get("exit_reason", "MANUAL_EXIT"))

        pnl = float(trade.get("realized_pnl") or trade.get("pnl") or 0.0)
        pnl_pct = float(trade.get("pnl_pct") or 0.0)
        entry_price = float(trade.get("entry_price") or 0.0)
        exit_price = float(trade.get("exit_price") or 0.0)
        qty = int(trade.get("quantity") or 0)
        holding_days = int(trade.get("holding_days") or 0)

        color = COLOR_BUY if pnl >= 0 else COLOR_SELL
        pnl_str = _format_inr(pnl)
        sign_pct = "+" if pnl_pct >= 0 else ""

        embed = {
            "title": f"💰 Position Closed: {symbol} ({direction})",
            "color": color,
            "fields": [
                {"name": "Exit Reason", "value": f"**{exit_reason}**", "inline": True},
                {"name": "Realized P&L", "value": f"**{pnl_str} ({sign_pct}{pnl_pct:.2f}%)**", "inline": True},
                {"name": "Holding Time", "value": f"{holding_days} days", "inline": True},
                {"name": "Entry Price", "value": f"₹{entry_price:,.2f}", "inline": True},
                {"name": "Exit Price", "value": f"₹{exit_price:,.2f}", "inline": True},
                {"name": "Quantity", "value": f"{qty} units", "inline": True},
            ],
            "timestamp": now_ist().isoformat(),
            "footer": {"text": "MJONAI Execution Ledger"},
        }
        return send_discord_webhook(embeds=[embed])
    except Exception as e:
        logger.error(f"[Discord] send_discord_trade_closed error: {e}")
        return {"ok": False, "error": str(e)}


def send_discord_emergency(reason: str, pnl_today: float, positions_closed: int) -> Dict[str, Any]:
    """Send high-priority emergency kill switch embed to Discord."""
    pnl_str = _format_inr(pnl_today)
    embed = {
        "title": "🚨🚨🚨 EMERGENCY KILL SWITCH TRIPPED 🚨🚨🚨",
        "description": f"**Trigger Reason:**\n⚠️ *{reason}*",
        "color": COLOR_EMERGENCY,
        "fields": [
            {"name": "Action Taken", "value": "• All trading halted immediately\n• All open positions flattened", "inline": False},
            {"name": "Positions Liquidated", "value": f"**{positions_closed}**", "inline": True},
            {"name": "Today's Realized P&L", "value": f"**{pnl_str}**", "inline": True},
        ],
        "timestamp": now_ist().isoformat(),
        "footer": {"text": "Manual supervisor clearance required to restart"},
    }
    return send_discord_webhook(embeds=[embed])


def send_discord_pre_market(gap_data: Dict[str, Any], fii_data: Dict[str, Any], sector_data: Dict[str, Any]) -> Dict[str, Any]:
    """Send 09:00 AM daily pre-market macro brief to Discord."""
    gap_pts = float(gap_data.get("gap_points") or 0.0)
    gap_type = str(gap_data.get("gap_type", "COMMON_GAP"))
    fii_regime = str(fii_data.get("liquidity_regime", "NEUTRAL"))
    fii_ls = float(fii_data.get("fii_long_short_ratio") or 1.0)
    top_sector = str(sector_data.get("top_sector_pick", "NIFTY"))

    embed = {
        "title": "🌅 MJONAI — Pre-Market Macro Intelligence Brief",
        "color": COLOR_GOLD,
        "fields": [
            {"name": "Gift Nifty Opening Gap", "value": f"**{gap_pts:+.1f} pts** ({gap_type})", "inline": True},
            {"name": "FII Liquidity Regime", "value": f"**{fii_regime}** (L/S: {fii_ls:.2f})", "inline": True},
            {"name": "Leading Sector Pick (RRG)", "value": f"**{top_sector}**", "inline": True},
        ],
        "timestamp": now_ist().isoformat(),
        "footer": {"text": "System armed for 09:15 AM opening bell"},
    }
    return send_discord_webhook(embeds=[embed])


def send_discord_eod(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Send 03:30 PM EOD performance scorecard to Discord."""
    net_pnl = float(summary.get("net_pnl") or 0.0)
    gross_pnl = float(summary.get("gross_pnl") or 0.0)
    friction = float(summary.get("total_friction") or 0.0)
    win_rate = float(summary.get("win_rate_pct") or 0.0)
    total_trades = int(summary.get("total_trades") or 0)
    winners = int(summary.get("winning_trades") or 0)
    open_trades = int(summary.get("open_trades_count") or 0)

    color = COLOR_BUY if net_pnl >= 0 else COLOR_SELL
    net_str = _format_inr(net_pnl)

    embed = {
        "title": "🏆 MJONAI — End of Day Performance Scorecard",
        "color": color,
        "fields": [
            {"name": "Net P&L (Post-Friction)", "value": f"**{net_str}**", "inline": True},
            {"name": "Win Rate", "value": f"**{win_rate:.1f}%** ({winners}/{total_trades} winners)", "inline": True},
            {"name": "Overnight Positions", "value": f"**{open_trades}**", "inline": True},
            {"name": "Gross P&L", "value": f"₹{gross_pnl:,.2f}", "inline": True},
            {"name": "Total Friction", "value": f"₹{friction:,.2f}", "inline": True},
        ],
        "timestamp": now_ist().isoformat(),
        "footer": {"text": "MJONAI Quantitative Trading Engine"},
    }
    return send_discord_webhook(embeds=[embed])
