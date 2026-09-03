# -*- coding: utf-8 -*-
"""
Module: communication/telegram.py
Purpose: SOTA Outbound Live Notification & Alert Gateway for MJONAI.
         Delivers Trade Signals, Exit PnL Alerts, Emergency Kill Switch Alarms,
         Pre-Market 09:00 AM Macro Briefs, and 03:30 PM EOD Performance Summaries.
"""

import hashlib
import html
import logging
import os
import threading
import time
from typing import Dict, List, Any, Optional, Union

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from core.time_utils import now_ist
from core.runtime_config import TELEGRAM_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

_recent_alerts: List[float] = []
_recent_hashes: Dict[str, float] = {}
_MAX_ALERTS_PER_MINUTE: int = 20
_ALERT_RATE_LOCK = threading.Lock()


def _get_credentials() -> tuple[Optional[str], Optional[str]]:
    """Dynamically resolve Telegram Bot Token and Chat ID from environment."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    return token, chat_id


def build_inline_keyboard(buttons: List[List[Dict[str, str]]]) -> Dict[str, Any]:
    """Construct Telegram InlineKeyboardMarkup JSON dictionary."""
    return {"inline_keyboard": buttons}


def _chunk_text(text: str, max_chars: int = 4000) -> List[str]:
    """Split message into safe chunks at newline boundaries to respect Telegram 4096 char limit."""
    if len(text) <= max_chars:
        return [text]
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_len = 0
    for line in text.split("\n"):
        if current_len + len(line) + 1 > max_chars:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_len = 0
            while len(line) > max_chars:
                chunks.append(line[:max_chars])
                line = line[max_chars:]
        current_chunk.append(line)
        current_len += len(line) + 1
    if current_chunk:
        chunks.append("\n".join(current_chunk))
    return chunks


def send_message(
    text: str,
    chat_id: Optional[str] = None,
    parse_mode: str = "HTML",
    reply_markup: Optional[Dict[str, Any]] = None,
    disable_notification: bool = False,
) -> Dict[str, Any]:
    """
    Send Telegram message safely with timeout, rate-limiting, HTML entities,
    message chunking (>4000 chars), HTML parse fallback, and optional inline keyboard markup.
    Protects against alert storms during network drops or rapid loop cycles.
    Returns status dictionary.
    """
    token, default_chat_id = _get_credentials()
    target_chat = chat_id or default_chat_id

    if not token or not target_chat:
        logger.debug("[Telegram] Mock Dry-Run: Credentials not set in environment.")
        return {"ok": False, "dry_run": True, "error": "Credentials missing"}

    now_ts = time.time()
    msg_hash = hashlib.md5(text.encode("utf-8")).hexdigest()

    with _ALERT_RATE_LOCK:
        # 1. Suppress duplicate message within 15 seconds (unless explicit interactive keyboard attached)
        last_sent = _recent_hashes.get(msg_hash)
        if reply_markup is None and last_sent is not None and (now_ts - last_sent) < 15.0:
            logger.debug(f"[Telegram] Debounced duplicate alert: {text[:40]}...")
            return {"ok": True, "debounced": True}

        # 2. Rate limit token bucket: prune timestamps older than 60s
        _recent_alerts[:] = [ts for ts in _recent_alerts if (now_ts - ts) < 60.0]
        if len(_recent_alerts) >= _MAX_ALERTS_PER_MINUTE:
            logger.warning(f"[Telegram] Rate limit reached ({len(_recent_alerts)}/min). Dropping message.")
            return {"ok": False, "rate_limited": True}

        _recent_alerts.append(now_ts)
        _recent_hashes[msg_hash] = now_ts

        # Cleanup hashes older than 120s
        if len(_recent_hashes) > 100:
            old_keys = [k for k, v in _recent_hashes.items() if (now_ts - v) > 120.0]
            for k in old_keys:
                _recent_hashes.pop(k, None)

    chunks = _chunk_text(text, max_chars=4000)
    last_res: Dict[str, Any] = {"ok": True}

    import requests
    import re

    for idx, chunk in enumerate(chunks):
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload: Dict[str, Any] = {
                "chat_id": target_chat,
                "text": chunk,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
                "disable_notification": disable_notification,
            }
            # Attach keyboard only to the last chunk
            if reply_markup is not None and idx == len(chunks) - 1:
                payload["reply_markup"] = reply_markup

            r = requests.post(url, json=payload, timeout=TELEGRAM_TIMEOUT_SECONDS)

            # Institutional HTML Parse Fallback
            if r.status_code == 400 and ("can't parse entities" in r.text or "parse_mode" in r.text):
                logger.warning("[Telegram] HTML parse error from Telegram API. Stripping tags and retrying as plain text.")
                plain_chunk = re.sub(r"<[^>]+>", "", chunk)
                payload["text"] = plain_chunk
                payload.pop("parse_mode", None)
                r = requests.post(url, json=payload, timeout=TELEGRAM_TIMEOUT_SECONDS)

            last_res = r.json()
        except Exception as e:
            logger.error(f"[Telegram] Send failed: {e}")
            last_res = {"ok": False, "error": str(e)}

    return last_res


def answer_callback_query(
    callback_query_id: str,
    text: Optional[str] = None,
    show_alert: bool = False,
) -> Dict[str, Any]:
    """
    Acknowledge Telegram callback query from inline keyboard buttons (<500ms).
    Removes the progress spinner on the trader's device.
    """
    token, _ = _get_credentials()
    if not token:
        return {"ok": False, "dry_run": True, "error": "Credentials missing"}

    try:
        import requests
        url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
        payload: Dict[str, Any] = {
            "callback_query_id": callback_query_id,
            "show_alert": show_alert,
        }
        if text:
            payload["text"] = text

        r = requests.post(url, json=payload, timeout=TELEGRAM_TIMEOUT_SECONDS)
        return r.json()
    except Exception as e:
        logger.error(f"[Telegram] answerCallbackQuery failed: {e}")
        return {"ok": False, "error": str(e)}


def edit_message_text(
    text: str,
    chat_id: Union[str, int],
    message_id: int,
    parse_mode: str = "HTML",
    reply_markup: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Update message text on Telegram to display execution confirmation and prevent double clicks.
    """
    token, _ = _get_credentials()
    if not token:
        return {"ok": False, "dry_run": True, "error": "Credentials missing"}

    try:
        import requests
        url = f"https://api.telegram.org/bot{token}/editMessageText"
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        r = requests.post(url, json=payload, timeout=TELEGRAM_TIMEOUT_SECONDS)
        return r.json()
    except Exception as e:
        logger.error(f"[Telegram] editMessageText failed: {e}")
        return {"ok": False, "error": str(e)}


def send_mqi_alert(mqi_level: str, score: float, signals_allowed: int, no_trade: bool) -> Dict[str, Any]:
    """Send Market Quality Index (MQI) status alert."""
    time_str = now_ist().strftime("%d %b %Y %I:%M %p IST")
    safe_level = html.escape(str(mqi_level))

    if no_trade:
        msg = f"""🚫 <b>MJONAI -- NO TRADE DAY</b>
📅 {time_str}
MQI Level: <b>{safe_level}</b>
MQI Score: <b>{score:.0f}%</b>
System monitoring only. No signals will fire today.
Stay patient. Capital protected."""
    else:
        emoji = "🟢" if mqi_level == "HIGH" else "🟡"
        msg = f"""{emoji} <b>MJONAI -- MARKET READY</b>
📅 {time_str}
MQI Level: <b>{safe_level}</b>
MQI Score: <b>{score:.0f}%</b>
Signals Allowed: <b>{signals_allowed}</b>
System active. Scanning for opportunities."""

    return send_message(msg, disable_notification=True)


def send_market_state_alert(market_state: str, total_score: int, vix: float) -> Dict[str, Any]:
    """Send market regime status alert (BULL, BEAR, NEUTRAL)."""
    time_str = now_ist().strftime("%d %b %Y %I:%M %p IST")
    safe_state = html.escape(str(market_state))
    emoji = "🐂" if market_state == "BULL" else ("🐻" if market_state == "BEAR" else "➡️")

    msg = f"""{emoji} <b>MJONAI -- Market State</b>
📅 {time_str}
Market: <b>{safe_state}</b>
Score: <b>{total_score}/4</b>
India VIX: <b>{vix:.2f}</b>"""

    return send_message(msg, disable_notification=True)


def send_signal_alert(signal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send approved trade entry signal alert to Telegram.
    Formats pricing, direction, real risk:reward, and CIO trade rationale.
    """
    try:
        from core.constants import SYSTEM_MODE

        time_str = now_ist().strftime("%d %b %Y %I:%M %p IST")
        symbol = html.escape(str(signal.get("symbol", "UNKNOWN")))
        strategy = html.escape(str(signal.get("strategy_id", "S00_Strategy")))
        sig_type = html.escape(str(signal.get("signal_type", "BUY")))
        direction = str(signal.get("direction", signal.get("signal_direction", "LONG"))).upper()
        confidence = int(float(signal.get("confidence") or 0))

        entry = float(signal.get("entry_price") or 0.0)
        sl = float(signal.get("stop_loss") or 0.0)
        target = float(signal.get("target") or 0.0)
        qty = int(signal.get("quantity") or 0)
        rr = float(signal.get("risk_reward") or 0.0)
        cost = float(signal.get("total_cost") or 0.0)

        mode_label = "🧪 PAPER TRADE ONLY" if SYSTEM_MODE == "RESEARCH" else "⚡ LIVE REAL-MONEY TRADE"
        direction_emoji = "📈" if direction == "LONG" else "📉"

        # Optional CIO executive summary if available
        cio_summary = signal.get("cio_summary") or signal.get("summary")
        cio_section = f"\n💡 <i>{html.escape(str(cio_summary))}</i>\n" if cio_summary else ""

        msg = f"""🎯 <b>MJONAI -- TRADE SIGNAL ({direction_emoji} {direction})</b>
📅 {time_str}

Asset: <b>{symbol}</b>
Strategy: <b>{strategy}</b>
Action: <b>{sig_type}</b>
Conviction: <b>{confidence}%</b>

Entry: <b>₹{entry:.2f}</b>
Stop Loss: <b>₹{sl:.2f}</b>
Target: <b>₹{target:.2f}</b>
Quantity: <b>{qty} units</b>
Real R:R: <b>1 : {rr:.2f}</b> (post-friction)
Est. Friction: ₹{cost:.2f}
{cio_section}
<i>{mode_label}</i>"""

        sig_id = str(signal.get("id") or signal.get("signal_id") or "")
        keyboard = None
        if sig_id:
            keyboard = build_inline_keyboard([
                [
                    {"text": "✅ APPROVE", "callback_data": f"cb:approve:{sig_id}"},
                    {"text": "🛡️ VETO", "callback_data": f"cb:veto:{sig_id}"},
                ]
            ])

        return send_message(msg, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"[Telegram] send_signal_alert error: {e}")
        return {"ok": False, "error": str(e)}


def _format_inr(amount: float) -> str:
    """Format rupee amount with clean currency sign."""
    abs_amt = abs(amount)
    prefix = "+₹" if amount > 0 else ("-₹" if amount < 0 else "₹")
    return f"{prefix}{abs_amt:,.2f}"


def send_trade_closed_alert(trade: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send trade exit and realized PnL notification.
    Highlights Target Hit (TP1/TP2), Trailing Stop Loss, or EOD Square-off.
    """
    try:
        time_str = now_ist().strftime("%d %b %Y %I:%M %p IST")
        symbol = html.escape(str(trade.get("symbol", "UNKNOWN")))
        direction = str(trade.get("direction", "LONG")).upper()
        exit_reason = html.escape(str(trade.get("exit_reason", "MANUAL_EXIT")))

        pnl = float(trade.get("realized_pnl") or trade.get("pnl") or 0.0)
        pnl_pct = float(trade.get("pnl_pct") or 0.0)
        entry_price = float(trade.get("entry_price") or 0.0)
        exit_price = float(trade.get("exit_price") or 0.0)
        qty = int(trade.get("quantity") or 0)
        holding_days = int(trade.get("holding_days") or 0)

        emoji = "💰 🟢" if pnl > 0 else ("🛑 🔴" if pnl < 0 else "⚖️ ⚪")
        sign_pct = "+" if pnl_pct > 0 else ("-" if pnl_pct < 0 else "")
        pnl_str = _format_inr(pnl)

        msg = f"""{emoji} <b>MJONAI -- POSITION CLOSED</b>
📅 {time_str}

Asset: <b>{symbol}</b> ({direction})
Exit Reason: <b>{exit_reason}</b>
Realized PnL: <b>{pnl_str} ({sign_pct}{abs(pnl_pct):.2f}%)</b>

Entry: ₹{entry_price:.2f}
Exit: ₹{exit_price:.2f}
Quantity: {qty} units
Holding Time: {holding_days} days"""

        return send_message(msg)
    except Exception as e:
        logger.error(f"[Telegram] send_trade_closed_alert error: {e}")
        return {"ok": False, "error": str(e)}


def send_emergency_kill_alert(reason: str, pnl_today: float, positions_closed: int) -> Dict[str, Any]:
    """Send high-priority critical alarm when circuit breaker or emergency kill switch trips."""
    time_str = now_ist().strftime("%d %b %Y %I:%M %p IST")
    safe_reason = html.escape(str(reason))
    pnl_str = _format_inr(pnl_today)

    msg = f"""🚨🚨🚨 <b>MJONAI -- EMERGENCY KILL SWITCH TRIPPED</b> 🚨🚨🚨
📅 {time_str}

<b>Action Taken:</b>
• All trading suspended immediately.
• Open positions flattened: <b>{positions_closed}</b>
• Today's Realized PnL: <b>{pnl_str}</b>

<b>Trigger Reason:</b>
⚠️ <i>{safe_reason}</i>

Manual supervisor clearance required to resume system."""

    keyboard = build_inline_keyboard([
        [
            {"text": "🚨 FLATTEN & LOCKOUT", "callback_data": "cb:kill"},
            {"text": "📊 VIEW STATUS", "callback_data": "cb:status"},
        ]
    ])
    return send_message(msg, reply_markup=keyboard)


def send_pre_market_brief_alert(
    gap_data: Dict[str, Any],
    fii_data: Dict[str, Any],
    sector_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Send 09:00 AM daily pre-market macro briefing."""
    time_str = now_ist().strftime("%d %b %Y 09:00 AM IST")

    gap_pts = gap_data.get("gap_points", 0.0)
    gap_type = html.escape(str(gap_data.get("gap_type", "COMMON_GAP")))
    macro_score = gap_data.get("global_macro_score", 50.0)

    fii_regime = html.escape(str(fii_data.get("liquidity_regime", "NEUTRAL")))
    fii_ls = fii_data.get("fii_long_short_ratio", 1.0)

    top_sector = html.escape(str(sector_data.get("top_sector_pick", "NIFTY")))
    leading = ", ".join([html.escape(s) for s in sector_data.get("leading_sectors", [])]) or "Broad Market"

    msg = f"""🌅 <b>MJONAI -- PRE-MARKET MACRO BRIEF</b>
📅 {time_str}

🌐 <b>Gift Nifty Opening Bias:</b>
• Gap Forecast: <b>{gap_pts:+.1f} pts ({gap_type})</b>
• Global Macro Score: <b>{macro_score:.0f}/100</b>

🏛️ <b>Institutional Liquidity:</b>
• FII Flow Regime: <b>{fii_regime}</b>
• FII Index Futures L/S: <b>{fii_ls:.2f}</b>

📊 <b>Sector Leadership (RRG):</b>
• Top Pick: <b>{top_sector}</b>
• Leading Sectors: <b>{leading}</b>

System armed for 09:15 AM opening bell."""

    return send_message(msg)


def send_eod_summary_alert(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Send 03:30 PM end-of-day trading performance scorecard."""
    time_str = now_ist().strftime("%d %b %Y 03:30 PM IST")

    net_pnl = float(summary.get("net_pnl") or 0.0)
    gross_pnl = float(summary.get("gross_pnl") or 0.0)
    friction = float(summary.get("total_friction") or 0.0)
    win_rate = float(summary.get("win_rate_pct") or 0.0)
    total_trades = int(summary.get("total_trades") or 0)
    winning_trades = int(summary.get("winning_trades") or 0)
    open_trades = int(summary.get("open_trades_count") or 0)

    emoji = "🏆 🟢" if net_pnl > 0 else ("📉 🔴" if net_pnl < 0 else "⚖️ ⚪")
    net_pnl_str = _format_inr(net_pnl)

    msg = f"""{emoji} <b>MJONAI -- EOD PERFORMANCE SCORECARD</b>
📅 {time_str}

<b>Daily PnL Summary:</b>
• Net PnL (Post-Friction): <b>{net_pnl_str}</b>
• Gross PnL: ₹{gross_pnl:,.2f}
• Total Friction (STT/Tax/Slippage): ₹{friction:,.2f}

<b>Execution Metrics:</b>
• Total Trades Closed: <b>{total_trades}</b>
• Win Rate: <b>{win_rate:.1f}%</b> ({winning_trades}/{total_trades} winners)
• Overnight Open Positions: <b>{open_trades}</b>

System standing by for evening analysis."""

    return send_message(msg)
