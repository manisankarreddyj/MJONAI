"""
Module: communication/telegram_commands.py
Purpose: SOTA Inbound Interactive Remote Control Engine for MJONAI.
         Authorizes and executes trader commands: /status, /pnl, /trades, /risk,
         /macro, /stop, /panic, /pause, /resume, /close, and /help.
"""

import html
import logging
import os
import threading
import time
from typing import Dict, List, Any, Optional, Tuple, Union

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from mjonai.core.runtime_config import (
    TELEGRAM_TIMEOUT_SECONDS,
    TELEGRAM_POLL_TIMEOUT_SECONDS,
)
from mjonai.communication.telegram import _get_credentials, send_message, _format_inr

logger = logging.getLogger(__name__)

_last_update_id = 0


def _fresh_live_price(symbol: str) -> Optional[float]:
    """Fail-closed live-price lookup over the raw websocket cache.

    Reads the raw ``live_prices`` dict ONLY when the resolved token's last tick
    is fresh. A stale, unknown, or empty tick returns ``None`` so a caller can
    never price (or validate a stop against) a dead feed.
    """
    try:
        from mjonai.data.angelone.websocket import live_prices, is_token_fresh
        from mjonai.data.angelone.token_map import SYMBOL_MAP

        token = SYMBOL_MAP.get(str(symbol).upper()) if SYMBOL_MAP else None
        if not token:
            return None
        raw = live_prices.get(str(token)) if live_prices else None
        if raw is None or not is_token_fresh(str(token)):
            return None
        price = float(raw)
        return price if price > 0 else None
    except Exception:
        return None


def _is_authorized(chat_id: Any) -> bool:
    """
    Check if incoming message sender is the authorized trader chat ID.

    FAIL CLOSED: when TELEGRAM_CHAT_ID is not configured, every command
    is refused. The old fail-open behaviour handed full system control
    (/stop, /panic, /close) to anyone who found the bot token.
    """
    _, auth_chat = _get_credentials()
    if not auth_chat:
        logger.error("[TelegramCmd] TELEGRAM_CHAT_ID not configured - command REFUSED (fail-closed)")
        return False
    return str(chat_id) == str(auth_chat)


def _send(text: str, chat_id: Optional[str] = None) -> Dict[str, Any]:
    """Helper to dispatch formatted message to trader."""
    return send_message(text=text, chat_id=chat_id)


def _get_updates(offset: int) -> List[Dict[str, Any]]:
    """Fetch updates from Telegram Bot API."""
    token, _ = _get_credentials()
    if not token:
        return []

    try:
        import requests
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        r = requests.get(url, params={"offset": offset, "timeout": 10}, timeout=TELEGRAM_POLL_TIMEOUT_SECONDS)
        data = r.json()
        if data.get("ok"):
            return list(data.get("result") or [])
    except Exception as e:
        logger.debug(f"[TelegramCmd] getUpdates notice: {e}")
    return []


def handle_status() -> str:
    """Handle /status command: System mode, health state, and today's summary."""
    try:
        from mjonai.db.repository import get_open_trades, get_trades_closed_today
        from mjonai.risk.emergency_triggers import get_state
        from mjonai.core.time_utils import now_ist
        from mjonai.core.constants import SYSTEM_MODE

        trades = get_open_trades()
        risk = get_state()

        if risk.get("manual_pause_active"):
            paused = "⏸ MANUALLY PAUSED"
        elif risk.get("risk_stop_active"):
            paused = "🛑 RISK STOP ACTIVE"
        elif risk.get("kill_line_active"):
            paused = "🚨 KILL LINE ACTIVE"
        elif risk.get("soft_stop_active"):
            paused = "⚠️ SOFT STOP ACTIVE"
        else:
            paused = "✅ ACTIVE"

        closed_today = get_trades_closed_today()
        wins_today = sum(1 for t in closed_today if float(t.get("net_pnl") or 0.0) > 0)
        losses_today = sum(1 for t in closed_today if float(t.get("net_pnl") or 0.0) < 0)

        msg = f"""🖥 <b>MJONAI STATUS</b>
Mode: <b>{SYSTEM_MODE}</b>
Signals Engine: <b>{paused}</b>

<b>Today's Activity:</b>
• Active Open Trades: <b>{len(trades)}</b>
• Closed Trades Today: <b>{len(closed_today)}</b>
• Win/Loss Ratio: <b>{wins_today}W / {losses_today}L</b>

Time: {now_ist().strftime('%I:%M:%S %p IST')}"""
        _send(msg)
        return msg
    except Exception as e:
        err = f"❌ Status error: {html.escape(str(e))}"
        _send(err)
        return err


def handle_pnl() -> str:
    """Handle /pnl command: Live mark-to-market P&L across all active positions."""
    try:
        from mjonai.execution.paper import get_open_trades_with_pnl

        trades = get_open_trades_with_pnl()
        if not trades:
            msg = "📊 <b>No open positions active.</b>"
            _send(msg)
            return msg

        lines = ["📊 <b>OPEN TRADES LIVE P&L</b>\n"]
        total_pnl = 0.0

        for t in trades:
            symbol = html.escape(str(t.get("symbol", "?")))
            pnl = float(t.get("pnl") or 0.0)
            pnl_pct = float(t.get("pnl_pct") or 0.0)
            price = float(t.get("current_price") or 0.0)
            direction = str(t.get("direction", "LONG")).upper()

            arrow = "🟢" if pnl >= 0 else "🔴"
            dir_emoji = "📈" if direction == "LONG" else "📉"
            pnl_str = _format_inr(pnl)
            sign_pct = "+" if pnl_pct > 0 else ("-" if pnl_pct < 0 else "")

            lines.append(f"{arrow} {dir_emoji} <b>{symbol}</b>: ₹{price:.2f} | P&L: <b>{pnl_str} ({sign_pct}{abs(pnl_pct):.2f}%)</b>")
            total_pnl += pnl

        tot_arrow = "🟢" if total_pnl >= 0 else "🔴"
        tot_pnl_str = _format_inr(total_pnl)
        lines.append(f"\n{tot_arrow} <b>Total Portfolio P&L: <b>{tot_pnl_str}</b></b>")

        msg = "\n".join(lines)
        _send(msg)
        return msg
    except Exception as e:
        err = f"❌ P&L calculation error: {html.escape(str(e))}"
        _send(err)
        return err


def handle_trades() -> str:
    """Handle /trades command: Complete portfolio breakdown and all-time win rates."""
    try:
        from mjonai.db.repository import (
            get_open_trades,
            get_trades_closed_today,
            get_all_closed_trades,
        )
        from mjonai.core.constants import SYSTEM_MODE

        open_trades = get_open_trades()
        all_closed = get_all_closed_trades(limit=1000)

        closed_count = len(all_closed)
        wins = sum(1 for t in all_closed if float(t.get("net_pnl") or 0.0) > 0)
        losses = sum(1 for t in all_closed if float(t.get("net_pnl") or 0.0) < 0)
        total_pnl = sum(float(t.get("net_pnl") or 0.0) for t in all_closed)
        win_rate = round((wins / max(1, closed_count)) * 100.0, 1) if closed_count > 0 else 0.0

        closed_today = get_trades_closed_today()
        pnl_today = sum(float(t.get("net_pnl") or 0.0) for t in closed_today)

        tot_arrow = "🟢" if total_pnl >= 0 else "🔴"
        today_arrow = "🟢" if pnl_today >= 0 else "🔴"

        msg = f"""📊 <b>MJONAI PORTFOLIO ANALYTICS</b>
Environment: <b>{SYSTEM_MODE}</b>

<b>Active Positions: {len(open_trades)}</b>
<b>Historical Closed Trades: {closed_count}</b>
• Scorecard: <b>{wins}W / {losses}L</b>
• Win Rate: <b>{win_rate:.1f}%</b>
• Cumulative Net PnL: {tot_arrow} <b>₹{total_pnl:+,.2f}</b>

<b>Today's Closed Trades: {len(closed_today)}</b>
• Today's Net PnL: {today_arrow} <b>₹{pnl_today:+,.2f}</b>"""
        _send(msg)
        return msg
    except Exception as e:
        err = f"❌ Trades error: {html.escape(str(e))}"
        _send(err)
        return err


def handle_risk() -> str:
    """Handle /risk command: Capital utilization, risk limits, and circuit breakers."""
    try:
        from mjonai.risk.emergency_triggers import get_state
        from mjonai.core.constants import TOTAL_CAPITAL, DAILY_LOSS_LIMIT_PCT, KILL_LINE_PCT

        risk_state = get_state()
        peak = float(risk_state.get("peak_equity") or TOTAL_CAPITAL)
        consec_losses = int(risk_state.get("consecutive_losses") or 0)

        if risk_state.get("kill_line_active"):
            status = "🚨 KILL LINE HALTED (15% Max DD)"
        elif risk_state.get("risk_stop_active"):
            status = "🛑 RISK STOP ACTIVE (3% Daily DD)"
        elif risk_state.get("soft_stop_active"):
            status = "⚠️ SOFT STOP ACTIVE (Cooling Off)"
        elif risk_state.get("manual_pause_active"):
            status = "⏸ MANUALLY PAUSED"
        else:
            status = "✅ ACTIVE & HEALTHY"

        msg = f"""🛡️ <b>MJONAI RISK & SENTRY STATUS</b>

• Risk Engine Status: <b>{status}</b>
• Peak Portfolio Equity: <b>₹{peak:,.2f}</b>
• Consecutive Losses: <b>{consec_losses}/3</b>
• Daily Loss Limit: <b>{DAILY_LOSS_LIMIT_PCT:.1f}%</b>
• Lifetime Kill Line: <b>{KILL_LINE_PCT:.1f}%</b>
• Manual Pause Active: <b>{risk_state.get('manual_pause_active', False)}</b>

Risk rules enforcing maximum capital protection."""
        _send(msg)
        return msg
    except Exception as e:
        err = f"❌ Risk status error: {html.escape(str(e))}"
        _send(err)
        return err


def handle_macro() -> str:
    """Handle /macro or /intel command: Live macro intelligence brief."""
    try:
        from mjonai.db.repository import get_latest_market_state

        state = get_latest_market_state() or {}
        fii_net = float(state.get("fii_net_cr") or 0.0)
        vix = float(state.get("vix") or 15.0)
        market_state = str(state.get("market_state") or "NEUTRAL")

        fii_str = f"₹{fii_net:+,.0f} Cr" if fii_net != 0 else "Normal"
        emoji = "🐂" if market_state == "BULL" else ("🐻" if market_state == "BEAR" else "➡️")

        msg = f"""🌐 <b>MJONAI MACRO INTELLIGENCE</b>

• Market Regime: {emoji} <b>{market_state}</b>
• India VIX: <b>{vix:.2f}</b>
• Institutional FII Flow: <b>{fii_str}</b>

Macro sentry operational and feeding strategy pipeline."""
        _send(msg)
        return msg
    except Exception as e:
        err = f"❌ Macro status error: {html.escape(str(e))}"
        _send(err)
        return err


def handle_stop() -> str:
    """Handle /stop or /panic command: Emergency liquidation of ALL positions."""
    try:
        from mjonai.execution.paper import close_all_paper_trades
        from mjonai.risk.emergency_triggers import set_manual_pause
        from mjonai.db.repository import get_open_trades, insert_risk_event
        from mjonai.core.time_utils import now_ist

        open_trades = get_open_trades()
        count = len(open_trades)

        if count == 0:
            msg = "ℹ️ <b>No open positions to close. Signals paused.</b>"
            set_manual_pause("Manual pause via /stop")
            _send(msg)
            return msg

        _send(f"🚨 <b>EMERGENCY STOP INITIATED</b>\nClosing {count} open position(s)...")

        close_all_paper_trades(exit_reason="MANUAL_PANIC_STOP")
        set_manual_pause("Emergency stop via Telegram /stop command")

        insert_risk_event(
            "MANUAL_STOP",
            f"/stop command — {count} position(s) closed at {now_ist().strftime('%H:%M IST %d %b %Y')}",
        )

        msg = f"""🛑 <b>EMERGENCY STOP COMPLETE</b>
• Positions Liquidated: <b>{count}</b>
• Signal Generation: <b>PAUSED</b>

Send /resume when ready to restart."""
        _send(msg)
        return msg
    except Exception as e:
        err = f"❌ Emergency stop failed: {html.escape(str(e))}"
        _send(err)
        return err


def handle_pause() -> str:
    """Handle /pause command."""
    try:
        from mjonai.risk.emergency_triggers import set_manual_pause
        set_manual_pause("Manual pause via Telegram")
        msg = "⏸ <b>MJONAI PAUSED</b>\nNew trade signals stopped.\nOpen trades remain monitored.\nSend /resume to restart."
        _send(msg)
        return msg
    except Exception as e:
        err = f"❌ Pause error: {html.escape(str(e))}"
        _send(err)
        return err


def handle_resume() -> str:
    """Handle /resume command."""
    try:
        from mjonai.risk.emergency_triggers import clear_manual_pause
        clear_manual_pause()
        msg = "✅ <b>MJONAI RESUMED</b>\nSignal generation active."
        _send(msg)
        return msg
    except Exception as e:
        err = f"❌ Resume error: {html.escape(str(e))}"
        _send(err)
        return err


def handle_close(args: str) -> str:
    """Handle /close SYMBOL command."""
    if not args or not args.strip():
        msg = "Usage: /close SYMBOL\nExample: /close SBIN"
        _send(msg)
        return msg

    symbol = args.strip().upper()
    try:
        from mjonai.db.repository import get_open_trades
        from mjonai.execution.paper import close_paper_trade

        open_trades = get_open_trades() or []
        target_trade = next((t for t in open_trades if str(t.get("symbol", "")).upper() == symbol), None)

        if not target_trade:
            msg = f"❌ No open position found for <b>{symbol}</b>"
            _send(msg)
            return msg

        tid = target_trade.get("id")

        # Fail closed on a stale/unknown feed: never book a manual close off a
        # dead tick (matches the close_all_paper_trades freshness contract).
        exit_price = _fresh_live_price(symbol)
        if exit_price is None:
            msg = (f"❌ No fresh price for <b>{symbol}</b> — manual close aborted "
                   "(live feed stale). Retry once the feed recovers.")
            _send(msg)
            return msg

        result = close_paper_trade(trade_id=str(tid), exit_price=exit_price, exit_reason="MANUAL_TELEGRAM_CLOSE")

        if result:
            pnl = float(result.get("net_pnl") or result.get("gross_pnl") or 0.0)
            price = float(result.get("exit_price") or exit_price)
            direction = str(target_trade.get("direction", target_trade.get("side", "LONG"))).upper()
            arrow = "🟢" if pnl >= 0 else "🔴"
            sign = "+" if pnl >= 0 else ""

            msg = f"""{arrow} <b>MANUAL CLOSE: {symbol} ({direction})</b>
Exit Price: ₹{price:.2f}
Realized Net P&L: <b>{sign}₹{pnl:,.2f}</b>"""
        else:
            msg = f"❌ Failed to close position for <b>{symbol}</b>"

        _send(msg)
        return msg
    except Exception as e:
        err = f"❌ Close failed for {symbol}: {html.escape(str(e))}"
        _send(err)
        return err


def handle_positions() -> str:
    """Handle /positions or /pos command: Detailed open position exit ladders and targets."""
    try:
        from mjonai.db.repository import get_open_trades

        open_trades = get_open_trades() or []
        if not open_trades:
            msg = "📊 <b>No open positions active.</b>"
            _send(msg)
            return msg

        lines = ["📊 <b>OPEN POSITIONS & EXIT LADDERS</b>\n"]

        for t in open_trades:
            raw_symbol = str(t.get("symbol", ""))
            symbol = html.escape(raw_symbol or "?")
            direction = str(t.get("direction", t.get("side", "LONG"))).upper()
            entry = float(t.get("entry_price") or 0.0)
            if direction == "LONG":
                sl = float(t.get("current_sl") or t.get("stop_loss") or (entry * 0.98))
                t1 = float(t.get("target_1") or (entry * 1.03))
                t2 = float(t.get("target_2") or (entry * 1.06))
            else:
                sl = float(t.get("current_sl") or t.get("stop_loss") or (entry * 1.02))
                t1 = float(t.get("target_1") or (entry * 0.97))
                t2 = float(t.get("target_2") or (entry * 0.94))
            qty = int(t.get("quantity_remaining") or t.get("quantity") or 1)
            stage = html.escape(str(t.get("sl_stage", "INITIAL")))

            ltp = _fresh_live_price(raw_symbol)
            if ltp is None:
                ltp = entry
                price_label = "Current Price (stale feed — entry shown)"
            else:
                price_label = "Current Price"

            pnl = (ltp - entry) * qty if direction == "LONG" else (entry - ltp) * qty
            arrow = "🟢" if pnl >= 0 else "🔴"
            dir_emoji = "📈" if direction == "LONG" else "📉"
            pnl_str = _format_inr(pnl)

            lines.append(f"""{arrow} {dir_emoji} <b>{symbol}</b> ({direction} — {qty} units)
• {price_label}: <b>₹{ltp:.2f}</b> (Entry: ₹{entry:.2f})
• Trailing SL: <b>₹{sl:.2f}</b> [Stage: {stage}]
• Targets: T1: <b>₹{t1:.2f}</b> | T2: <b>₹{t2:.2f}</b>
• MTM P&L: <b>{pnl_str}</b>
""")

        msg = "\n".join(lines).strip()
        _send(msg)
        return msg
    except Exception as e:
        err = f"❌ Positions error: {html.escape(str(e))}"
        _send(err)
        return err


def handle_ai(args: str) -> str:
    """Handle /ai or /debate SYMBOL command: On-demand multi-agent consensus deliberation."""
    if not args or not args.strip():
        msg = "Usage: /ai SYMBOL\nExample: /ai RELIANCE"
        _send(msg)
        return msg

    symbol = args.strip().upper()
    try:
        from mjonai.agents.debate_room import conduct_adversarial_debate
        from mjonai.db.repository import get_latest_market_state

        _send(f"🤖 <i>Convening Multi-Agent Debate Room for <b>{symbol}</b>...</i>")

        macro_ctx = get_latest_market_state() or {}
        mock_signal = {
            "symbol": symbol,
            "strategy_id": "OnDemand_Technical_Scan",
            "entry_price": 1000.0,
            "stop_loss": 980.0,
            "target": 1050.0,
            "risk_reward": 2.5,
            "signal_direction": "LONG",
            "confidence": 75,
        }

        debate_res = conduct_adversarial_debate(
            signal=mock_signal,
            macro_context=macro_ctx,
        )

        transcript = debate_res.get("transcript", {})
        verdict = debate_res.get("final_decision", "NEJECT")
        score = debate_res.get("consensus_score", 50)
        summary = html.escape(str(debate_res.get("summary", "")))
        deciding = html.escape(str(debate_res.get("deciding_factor", "")))

        bull_verdict = transcript.get("bull_initial_verdict", "NEUTRAL")
        bull_conf = transcript.get("bull_confidence", 50)
        bear_verdict = transcript.get("bear_initial_verdict", "NEUTRAL")
        bear_conf = transcript.get("bear_confidence", 50)

        emoji = "🟢 APPROVE" if verdict == "APPROVE" else "🔴 REJECT"

        msg = f"""🏛️ <b>AI DELIBERATION: {symbol}</b>

<b>Consensus Outcome:</b> {emoji}
<b>Conviction Score:</b> <b>{score}/100</b>
<b>Rounds Conducted:</b> {transcript.get('rounds_conducted', 1)}

🐂 <b>Bull Analyst:</b> {bull_verdict} ({bull_conf}% conf)
🐻 <b>Bear Sentry:</b> {bear_verdict} ({bear_conf}% conf)

💡 <b>CIO Assessment:</b>
<i>{summary}</i>
<b>Deciding Factor:</b> {deciding}"""

        _send(msg)
        return msg
    except Exception as e:
        err = f"❌ AI Deliberation failed for {symbol}: {html.escape(str(e))}"
        _send(err)
        return err


def handle_sl(args: str) -> str:
    """Handle /sl SYMBOL NEW_PRICE command: Remotely adjust trailing stop loss."""
    parts = args.strip().split() if args else []
    if len(parts) < 2:
        msg = "Usage: /sl SYMBOL NEW_PRICE\nExample: /sl TCS 4250.0"
        _send(msg)
        return msg

    symbol = parts[0].upper()
    try:
        new_sl = float(parts[1])
    except ValueError:
        msg = f"❌ Invalid price: {parts[1]}"
        _send(msg)
        return msg

    if new_sl <= 0.0:
        msg = f"❌ Stop loss price must be strictly positive: ₹{new_sl:.2f}"
        _send(msg)
        return msg

    try:
        from mjonai.db.repository import get_open_trades, update_trade_sl

        open_trades = get_open_trades() or []
        target = next((t for t in open_trades if str(t.get("symbol", "")).upper() == symbol), None)

        if not target:
            msg = f"❌ No open position found for <b>{symbol}</b>"
            _send(msg)
            return msg

        tid = str(target.get("id"))
        prev_sl = float(target.get("current_sl") or target.get("stop_loss") or 0.0)
        direction = str(target.get("direction", target.get("side", "LONG"))).upper()

        # Protective-side validation must use a FRESH tick; a stale/absent feed
        # fails closed rather than anchoring the check to entry or a dead price.
        ltp = _fresh_live_price(symbol)
        if ltp is None:
            msg = (f"❌ No fresh price for <b>{symbol}</b> — stop-loss update aborted "
                   "(live feed stale). Retry once the feed recovers.")
            _send(msg)
            return msg

        # Institutional Directional Protection: SL must be on protective side of LTP
        if direction == "LONG" and new_sl >= ltp:
            msg = f"❌ Invalid SL for LONG {symbol}: ₹{new_sl:.2f} must be below current price ₹{ltp:.2f}"
            _send(msg)
            return msg
        elif direction == "SHORT" and new_sl <= ltp:
            msg = f"❌ Invalid SL for SHORT {symbol}: ₹{new_sl:.2f} must be above current price ₹{ltp:.2f}"
            _send(msg)
            return msg

        success = update_trade_sl(
            trade_id=tid,
            sl_stage="MANUAL_REMOTE",
            current_sl=new_sl,
            trailing_sl=new_sl,
        )

        if success:
            msg = f"""🎯 <b>TRAILING STOP LOSS UPDATED</b>
Asset: <b>{symbol}</b>
Previous SL: ₹{prev_sl:.2f}
New Active SL: <b>₹{new_sl:.2f}</b>
Stage: <b>MANUAL_REMOTE</b>"""
        else:
            msg = f"❌ Failed to persist SL update for {symbol} in ledger"

        _send(msg)
        return msg
    except Exception as e:
        err = f"❌ SL adjustment failed for {symbol}: {html.escape(str(e))}"
        _send(err)
        return err


def handle_help() -> str:
    """Handle /help command: Command cheatsheet."""
    msg = """🤖 <b>MJONAI COMMAND SUITE</b>

📊 <b>Monitoring:</b>
/status — Engine mode, health & today's tally
/pnl — Mark-to-market live P&L on open trades
/positions — Open trades with targets & trailing SL
/trades — Full historical portfolio scorecard
/risk — Drawdown %, circuit breakers & limits
/macro — Gift Nifty, FII flows & market regime

🧠 <b>Intelligence:</b>
/ai SYMBOL — On-demand Bull/Bear debate room deliberation

⚙️ <b>Control:</b>
/sl SYMBOL PRICE — Remotely adjust trailing stop loss
/pause — Pause new signals
/resume — Resume signal generation
/close SYMBOL — Close a single open position

🚨 <b>Emergency:</b>
/stop or /panic — Close ALL positions & halt signals

/help — This documentation message"""
    _send(msg)
    return msg


def process_command_text(text: str, chat_id: Optional[str] = None) -> Optional[str]:
    """
    Pure functional dispatcher for incoming Telegram commands.
    Used by polling thread and automated test suites.
    """
    if not text:
        return None

    parts = text.strip().split(None, 1)
    if not parts:
        return None

    command = parts[0].lower().split("@")[0]  # strip @botname if present
    args = parts[1] if len(parts) > 1 else ""

    logger.info(f"[TelegramCmd] Processing command: {command} {args}")

    if command == "/status":
        return handle_status()
    elif command == "/pnl":
        return handle_pnl()
    elif command in ("/positions", "/pos"):
        return handle_positions()
    elif command == "/trades":
        return handle_trades()
    elif command == "/risk":
        return handle_risk()
    elif command in ("/macro", "/intel"):
        return handle_macro()
    elif command in ("/ai", "/debate"):
        return handle_ai(args)
    elif command == "/sl":
        return handle_sl(args)
    elif command in ("/stop", "/panic"):
        return handle_stop()
    elif command == "/pause":
        return handle_pause()
    elif command == "/resume":
        return handle_resume()
    elif command == "/close":
        return handle_close(args)
    elif command == "/help":
        return handle_help()
    else:
        return None


_CALLBACK_LOCK = threading.Lock()
_processed_callbacks: Dict[str, float] = {}


def clear_callback_cache() -> None:
    """Clear callback idempotency cache for testing."""
    with _CALLBACK_LOCK:
        _processed_callbacks.clear()


def process_callback_query(
    cb_id: str,
    data: str,
    chat_id: Union[str, int],
    msg_id: Optional[int] = None,
    original_text: str = "",
) -> str:
    """
    Route and execute inline keyboard callback queries.
    Acknowledges query in <500ms, executes action, enforces idempotency,
    and updates message text to prevent double-clicks.
    """
    from mjonai.core.time_utils import now_ist
    from mjonai.communication.telegram import answer_callback_query, edit_message_text

    # 1. Idempotency Check: protect against rapid multi-click race conditions
    now_ts = time.time()
    action_key = f"{chat_id}:{data}"
    with _CALLBACK_LOCK:
        for k in list(_processed_callbacks.keys()):
            if (now_ts - _processed_callbacks[k]) >= 30.0:
                _processed_callbacks.pop(k, None)
        if action_key in _processed_callbacks and (now_ts - _processed_callbacks[action_key]) < 5.0:
            ack_text = "⚠️ Action already processed."
            answer_callback_query(cb_id, text=ack_text)
            return ack_text
        _processed_callbacks[action_key] = now_ts

    ack_text = "Processing..."
    result_text = ""

    if data == "cb:kill":
        handle_stop()
        ack_text = "🚨 Master Kill Switch Engaged!"
        result_text = f"{original_text}\n\n<b>[🚨 EXECUTED: MASTER KILL SWITCH by Trader at {now_ist().strftime('%H:%M:%S IST')}]</b>"

    elif data.startswith("cb:approve:"):
        sig_id = data.split(":", 2)[2]
        ack_text = f"✅ Signal {sig_id[:8]} Approved!"
        result_text = f"{original_text}\n\n<b>[✅ APPROVED by Trader at {now_ist().strftime('%H:%M:%S IST')}]</b>"

    elif data.startswith("cb:veto:"):
        sig_id = data.split(":", 2)[2]
        ack_text = f"🛡️ Signal {sig_id[:8]} Vetoed!"
        result_text = f"{original_text}\n\n<b>[🛡️ VETOED by Trader at {now_ist().strftime('%H:%M:%S IST')}]</b>"

    elif data.startswith("cb:close:"):
        trade_id = data.split(":", 2)[2]
        from mjonai.db.repository import get_open_trades, close_trade
        open_trades = get_open_trades() or []
        target = next((t for t in open_trades if str(t.get("id")) == trade_id), None)
        if not target:
            ack_text = f"ℹ️ Trade {trade_id[:8]} already closed."
            result_text = f"{original_text}\n\n<b>[ℹ️ ALREADY CLOSED by Engine]</b>"
        else:
            close_trade(trade_id=trade_id, exit_price=0.0, exit_reason="MANUAL_TELEGRAM_CLOSE")
            ack_text = f"🛑 Position {trade_id[:8]} Closed!"
            result_text = f"{original_text}\n\n<b>[🛑 CLOSED by Trader at {now_ist().strftime('%H:%M:%S IST')}]</b>"

    elif data == "cb:pause":
        handle_pause()
        ack_text = "⏸ System Paused."
        result_text = f"{original_text}\n\n<b>[⏸ SYSTEM PAUSED by Trader at {now_ist().strftime('%H:%M:%S IST')}]</b>"

    elif data == "cb:resume":
        handle_resume()
        ack_text = "▶ System Resumed."
        result_text = f"{original_text}\n\n<b>[▶ SYSTEM RESUMED by Trader at {now_ist().strftime('%H:%M:%S IST')}]</b>"

    elif data == "cb:status":
        status_msg = handle_status()
        send_message(status_msg, chat_id=str(chat_id))
        ack_text = "Status refreshed."

    else:
        ack_text = f"Unknown action: {data}"

    answer_callback_query(cb_id, text=ack_text)
    if msg_id and result_text:
        edit_message_text(text=result_text, chat_id=chat_id, message_id=msg_id)

    return ack_text


def _process_update(update: Dict[str, Any]) -> None:
    """Process a single Telegram update dict from API (messages and callback queries)."""
    # 1. Handle Inline Button Callbacks (callback_query)
    if "callback_query" in update:
        cb = update["callback_query"]
        cb_id = str(cb.get("id", ""))
        from_user = cb.get("from", {})
        user_id = from_user.get("id")
        msg = cb.get("message", {})
        chat_id = msg.get("chat", {}).get("id") or user_id
        data = str(cb.get("data", ""))
        msg_id = msg.get("message_id")
        orig_text = str(msg.get("text") or "")

        if not _is_authorized(chat_id) and not _is_authorized(user_id):
            from mjonai.communication.telegram import answer_callback_query
            answer_callback_query(cb_id, text="Unauthorized", show_alert=True)
            return

        process_callback_query(
            cb_id=cb_id,
            data=data,
            chat_id=str(chat_id),
            msg_id=msg_id,
            original_text=orig_text,
        )
        return

    # 2. Handle Text Messages
    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = str(message.get("text") or "").strip()

    if not text or not _is_authorized(chat_id):
        return

    process_command_text(text, chat_id=chat_id)


def _poll_loop() -> None:
    """Main polling loop for Telegram commands."""
    global _last_update_id
    logger.info("Telegram command listener polling thread started.")

    while True:
        try:
            updates = _get_updates(_last_update_id + 1)
            for update in updates:
                _last_update_id = int(update.get("update_id", _last_update_id))
                _process_update(update)
        except Exception as e:
            logger.debug(f"[TelegramCmd] Poll loop notice: {e}")

        time.sleep(2)


def start_command_listener() -> None:
    """Start the Telegram command polling loop in a background daemon thread."""
    t = threading.Thread(target=_poll_loop, daemon=True, name="TelegramCmdListener")
    t.start()
    logger.info("Telegram command listener daemon initialized.")
