"""
Module: data/angelone/__init__.py
Purpose: AngelOne data connector, live WebSocket stream, and historical candle engine.

Audit Note (TD-008): Add live available margin fetching via AngelOne RMS API
(getRMS/funds.net) at 08:30 AM startup to dynamically calibrate TOTAL_CAPITAL in LIVE mode.
"""

from data.angelone.historical import (
    CandleInterval,
    Exchange,
    DataProvider,
    fetch_historical_candles,
    clear_candle_cache,
    get_candle_cache_size,
)
from data.angelone.token_map import (
    TOKEN_MAP,
    SYMBOL_MAP,
    WATCHLIST_TOKENS,
    INDEX_STRIKE_INTERVALS,
    get_token_for_symbol,
    get_symbol_for_token,
    get_option_token,
    get_atm_strike,
    get_option_chain_tokens,
    sync_instrument_master,
    is_token_map_loaded,
)

# Raw tick stores (live_prices, live_volumes, live_oi, live_day_*, live_prev_close)
# are deliberately NOT re-exported here: they are mutable dicts mutated in place by
# the websocket thread, so holding a package-level reference bypasses the staleness
# guard and the on_close cache flush. Use the read-only accessors below (or import
# from data.angelone.websocket directly if raw access is genuinely required).

from data.angelone.websocket import (
    WebSocketMode,
    get_live_price,
    get_live_volume,
    get_live_oi,
    get_live_day_open,
    get_live_day_high,
    get_live_day_low,
    get_live_prev_close,
    get_live_bid,
    get_live_ask,
    get_live_spread_pct,
    is_spread_acceptable,
    get_live_quote,
    get_live_depth,
    get_live_spread,
    get_websocket_stats,
    clear_tick_caches,
    get_token_staleness,
    is_websocket_healthy,
    start_websocket,
    stop_websocket,
    restart_websocket,
    set_subscription_mode,
    total_ticks_received,
    get_total_ticks_received,
    reset_tick_counter,
    subscribe_additional_tokens,
    unsubscribe_tokens,
    register_tick_listener,
    unregister_tick_listener,
)

__all__ = [
    "CandleInterval",
    "Exchange",
    "DataProvider",
    "fetch_historical_candles",
    "clear_candle_cache",
    "get_candle_cache_size",
    "TOKEN_MAP",
    "SYMBOL_MAP",
    "WATCHLIST_TOKENS",
    "INDEX_STRIKE_INTERVALS",
    "get_token_for_symbol",
    "get_symbol_for_token",
    "get_option_token",
    "get_atm_strike",
    "get_option_chain_tokens",
    "sync_instrument_master",
    "is_token_map_loaded",
    "WebSocketMode",
    "get_live_price",
    "get_live_volume",
    "get_live_oi",
    "get_live_day_open",
    "get_live_day_high",
    "get_live_day_low",
    "get_live_prev_close",
    "get_live_bid",
    "get_live_ask",
    "get_live_spread_pct",
    "is_spread_acceptable",
    "get_live_quote",
    "get_token_staleness",
    "is_websocket_healthy",
    "start_websocket",
    "stop_websocket",
    "restart_websocket",
    "set_subscription_mode",
    "total_ticks_received",
    "get_total_ticks_received",
    "reset_tick_counter",
    "subscribe_additional_tokens",
    "unsubscribe_tokens",
    "register_tick_listener",
    "unregister_tick_listener",
]
