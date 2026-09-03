"""
Module: communication/__init__.py
Purpose: SOTA Multi-Channel Communication Gateway for MJONAI
         (Telegram Outbound & Inbound Remote Control, Discord Rich Embeds,
          Real-Time Web UI Event Stream, and Unified Dispatcher Hub).
"""

# 1. Telegram Gateway
from mjonai.communication.telegram import (
    send_message,
    send_mqi_alert,
    send_market_state_alert,
    send_signal_alert,
    send_trade_closed_alert,
    send_emergency_kill_alert,
    send_pre_market_brief_alert,
    send_eod_summary_alert,
    build_inline_keyboard,
    answer_callback_query,
    edit_message_text,
)

# 2. Interactive Inbound Commands
from mjonai.communication.telegram_commands import (
    process_command_text,
    process_callback_query,
    start_command_listener,
    handle_status,
    handle_pnl,
    handle_positions,
    handle_trades,
    handle_risk,
    handle_macro,
    handle_ai,
    handle_sl,
    handle_stop,
    handle_pause,
    handle_resume,
    handle_close,
    handle_help,
)

# 3. Discord Gateway
from mjonai.communication.discord import (
    send_discord_webhook,
    send_discord_signal,
    send_discord_trade_closed,
    send_discord_emergency,
    send_discord_pre_market,
    send_discord_eod,
)

# 4. Web UI Real-Time Event Stream
from mjonai.communication.events import (
    publish_event,
    get_recent_events,
    get_events_since,
    register_event_listener,
    unregister_event_listener,
    clear_events_buffer,
    WebEvent,
)

# 5. Unified Multi-Channel Fan-Out Dispatcher Hub
from mjonai.communication.dispatcher import (
    broadcast_signal,
    broadcast_trade_closed,
    broadcast_emergency,
    broadcast_pre_market,
    broadcast_eod,
    broadcast_market_state,
)

# 6. EOD Digest Generator
from mjonai.communication.eod_report import (
    generate_eod_digest,
    EODDigestResult,
)

__all__ = [
    # Telegram
    "send_message",
    "send_mqi_alert",
    "send_market_state_alert",
    "send_signal_alert",
    "send_trade_closed_alert",
    "send_emergency_kill_alert",
    "send_pre_market_brief_alert",
    "send_eod_summary_alert",
    "build_inline_keyboard",
    "answer_callback_query",
    "edit_message_text",
    # Inbound Commands
    "process_command_text",
    "process_callback_query",
    "start_command_listener",
    "handle_status",
    "handle_pnl",
    "handle_positions",
    "handle_trades",
    "handle_risk",
    "handle_macro",
    "handle_ai",
    "handle_sl",
    "handle_stop",
    "handle_pause",
    "handle_resume",
    "handle_close",
    "handle_help",
    # Discord
    "send_discord_webhook",
    "send_discord_signal",
    "send_discord_trade_closed",
    "send_discord_emergency",
    "send_discord_pre_market",
    "send_discord_eod",
    # Web Events
    "publish_event",
    "get_recent_events",
    "get_events_since",
    "register_event_listener",
    "unregister_event_listener",
    "clear_events_buffer",
    "WebEvent",
    # Dispatcher Hub
    "broadcast_signal",
    "broadcast_trade_closed",
    "broadcast_emergency",
    "broadcast_pre_market",
    "broadcast_eod",
    "broadcast_market_state",
    # EOD Digest
    "generate_eod_digest",
    "EODDigestResult",
]
