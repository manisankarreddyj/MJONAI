"""
Module: data/angelone/websocket.py
Purpose: High-Performance AngelOne SmartWebSocketV2 Real-Time Tick & Quote Engine.
         Ingests streaming market ticks, extracts LTP, Cumulative Volume, and Open Interest (OI),
         maintains thread-safe in-memory stores, tracks token-level staleness, and manages auto-reconnections.

Architectural Principles:
  1. Multi-Mode Streaming: Supports Mode 1 (LTP), Mode 2 (Quote with Volume & OI), and Mode 3 (Full Depth).
  2. Complete Derivative Data: Real-time Open Interest (OI) & Day Volume maps for Options & Volume surge scanning.
  3. Token-Level Staleness Tracking: Granular timestamps per token to distinguish illiquid stocks from dead sockets.
  4. Thread-Safe O(1) Reads: Instant in-memory lookups for strategy scan loops without lock contention.
  5. Resilient Auto-Reconnect: Exponential backoff reconnector with Telegram alerts and watchdog integration.
"""

from datetime import datetime
from enum import Enum
import logging
import os
import random
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from mjonai.core.time_utils import is_market_open, now_ist
from mjonai.core.runtime_config import load_mjonai_env

load_mjonai_env()
logger = logging.getLogger(__name__)

# Top-level patch for SmartWebSocketV2._on_close signature mismatch with websocket-client
try:
    from SmartApi.smartWebSocketV2 import SmartWebSocketV2
    if hasattr(SmartWebSocketV2, "_on_close"):
        _orig_smart_on_close = SmartWebSocketV2._on_close
        def _safe_smart_on_close(self, wsapp=None, *args, **kwargs):
            try:
                return _orig_smart_on_close(self, wsapp)
            except Exception:
                pass
        SmartWebSocketV2._on_close = _safe_smart_on_close
except Exception:
    pass


# ── 1. ENUMS & SUBSCRIPTION MODES ─────────────────────────────────────────────

class WebSocketMode(int, Enum):
    """AngelOne SmartWebSocketV2 subscription modes."""
    LTP        = 1  # Mode 1: Last Traded Price only
    QUOTE      = 2  # Mode 2: Quote (LTP, Volume, High, Low, Open, Close, OI)
    SNAP_QUOTE = 3  # Mode 3: Full Market Depth (Best 5 Bids / Asks)


# ── 2. GLOBAL THREAD-SAFE TICK & QUOTE STORES ─────────────────────────────────

# In-Memory Fast Lookup Stores (Token -> Metric)
live_prices: Dict[str, float] = {}          # Token -> Last Traded Price (₹)
live_volumes: Dict[str, int] = {}           # Token -> Cumulative Traded Volume
live_oi: Dict[str, int] = {}                # Token -> Open Interest (F&O contracts)
live_day_open: Dict[str, float] = {}        # Token -> Today's Open Price (₹)
live_day_high: Dict[str, float] = {}        # Token -> Today's High Price (₹)
live_day_low: Dict[str, float] = {}         # Token -> Today's Low Price (₹)
live_prev_close: Dict[str, float] = {}      # Token -> Previous Trading Day Close (₹)
live_best_bid: Dict[str, float] = {}        # Token -> Best Bid Price (₹)
live_best_ask: Dict[str, float] = {}        # Token -> Best Ask Price (₹)
live_bid_qty: Dict[str, int] = {}           # Token -> Best Bid Quantity
live_ask_qty: Dict[str, int] = {}           # Token -> Best Ask Quantity
live_timestamps: Dict[str, datetime] = {}   # Token -> Last Received Tick Timestamp (IST)
total_ticks_received: int = 0               # Telemetry metric: Lifetime received ticks counter

# RLock (reentrant): composite accessors (e.g. get_live_depth computing the spread)
# re-enter this lock inside an already-held critical section. A plain Lock here
# self-deadlocked the reader thread (P0 bug).
_prices_lock = threading.RLock()
_tick_listeners: List[Callable[[Dict[str, Any]], None]] = []
_listeners_lock = threading.Lock()

# Connection State
_sws: Optional[Any] = None
_auth_token: Optional[str] = None
_feed_token: Optional[str] = None
_client_id: Optional[str] = None
_token_list: List[Dict[str, Any]] = []
# Guards read-modify-write mutations of _token_list (dynamic subscribe/unsubscribe
# racing the reconnect loop and start_websocket). Reads stay lock-free by design.
_token_list_lock = threading.Lock()
_correlation_id: str = "mjonai_live"
_active_mode: WebSocketMode = WebSocketMode.QUOTE  # Mode 2 (Quote + OI) by default

# Watchdog & Reconnect Controls
_stop_requested: bool = False
_reconnect_attempts: int = 0
_MAX_RECONNECT_ATTEMPTS: int = 5
_reconnect_lock = threading.Lock()
_is_reconnecting: bool = False
# Set by on_open ONLY after subscriptions were accepted — proof the socket is not
# merely spawned but actually live. The reconnect loop waits on this so a failed
# reconnect is never reported as success (start_websocket only spawns a thread).
_connection_confirmed: threading.Event = threading.Event()

_last_price_time: Optional[datetime] = None
_STALE_THRESHOLD_SECONDS: int = 120  # 2 minutes with no ticks during market hours = stale
_startup_timestamp: float = time.time()


def _send_telegram(message: str) -> None:
    """Send Telegram alert safely without crashing or raising exceptions."""
    try:
        from mjonai.communication.telegram import send_message
        send_message(message)
    except Exception:
        pass


# ── 3. AUTHENTICATION & CONFIGURATION ─────────────────────────────────────────

def set_auth(auth_token: str, feed_token: str, client_id: str) -> None:
    """Store AngelOne authentication tokens for session and reconnect use."""
    global _auth_token, _feed_token, _client_id
    _auth_token = auth_token
    _feed_token = feed_token
    _client_id = client_id


def set_subscription_mode(mode: WebSocketMode) -> None:
    """Configure WebSocket subscription mode (LTP=1, QUOTE=2, SNAP_QUOTE=3)."""
    global _active_mode
    _active_mode = mode
    logger.info(f"[WebSocket] Subscription mode set to {mode.name} (Mode {mode.value})")


# ── 4. STALENESS & HEALTH WATCHDOG ────────────────────────────────────────────

def is_websocket_healthy() -> bool:
    """
    Returns True if the live feed is genuinely current during market hours:
      - Coverage: at least 60% of the subscribed tokens in _token_list ticked
        within _STALE_THRESHOLD_SECONDS, AND
      - Global recency: the last tick of any kind is within _STALE_THRESHOLD_SECONDS.
    Falls back to the global-recency-only check when no tokens are subscribed or
    no token has ever been timestamped. Returns True outside market hours
    (no ticks expected) or during the 90s startup warmup period.
    """
    if not is_market_open():
        return True  # Outside market hours — lack of ticks is expected

    # Allow a 90-second warmup period on engine startup ONLY IF socket is actively connecting/running
    if (time.time() - _startup_timestamp) < 90.0:
        if _sws is not None:
            return True

    now = now_ist()

    with _prices_lock:
        # Snapshot under the lock for a consistent read against timestamps
        subscribed = {t for item in _token_list for t in item.get("tokens", [])}
        timestamps_snapshot = dict(live_timestamps)
        last_price_time = _last_price_time

    def _globally_recent() -> bool:
        if last_price_time is None:
            return False  # Market open but never received any price
        return (now - last_price_time).total_seconds() < _STALE_THRESHOLD_SECONDS

    # Fallback: legacy behaviour when there is nothing to measure coverage on
    if not subscribed or not timestamps_snapshot:
        return _globally_recent()

    fresh_tokens = 0
    for tok in subscribed:
        ts = timestamps_snapshot.get(tok)
        if ts is not None and (now - ts).total_seconds() < _STALE_THRESHOLD_SECONDS:
            fresh_tokens += 1

    coverage = fresh_tokens / len(subscribed)

    # For targeted watchlists (e.g. <= 50 symbols or tests), require 60% coverage.
    # For broad universe subscriptions (e.g. 2,674 master universe tokens where many illiquid small-caps don't tick every 2 mins),
    # verify active stream flow: at least 25 distinct fresh tokens OR 5% coverage in addition to global recency.
    if len(subscribed) <= 50:
        is_covered = coverage >= 0.6
    else:
        is_covered = (fresh_tokens >= 25 or coverage >= 0.05)

    return is_covered and _globally_recent()


def get_token_staleness(token: str) -> Optional[float]:
    """Return seconds elapsed since last tick for a specific token. None if never received."""
    with _prices_lock:
        ts = live_timestamps.get(token.strip())
        if ts is None:
            return None
        return (now_ist() - ts).total_seconds()


# ── 5. WEBSOCKET EVENT HANDLERS (ON_DATA / ON_OPEN / ON_ERROR / ON_CLOSE) ─────

def on_data(wsapp: Any = None, data: Any = None, *args: Any, **kwargs: Any) -> None:
    """
    Called on every tick from SmartWebSocketV2.
    Parses LTP, Cumulative Volume, and Open Interest.
    Thread-safely updates in-memory stores.
    """
    global _last_price_time, total_ticks_received

    message: Dict[str, Any] = data if isinstance(data, dict) else (args[0] if args and isinstance(args[0], dict) else {})
    if not message:
        return

    try:
        token = str(message.get("token", "")).strip()
        if not token or token == "None":
            return

        raw_price = message.get("last_traded_price")
        if raw_price is None or raw_price == 0:
            return

        # Convert paise to rupees (AngelOne WebSocket sends all prices in paise)
        ltp = float(raw_price) / 100.0

        # Sanity check price bounds
        if ltp < 0.05 or ltp > 1000000.0:
            return

        # Extract Volume & Open Interest if present (Mode 2 & 3)
        raw_volume = message.get("volume_trade_for_the_day") or message.get("volume")
        volume = int(raw_volume) if raw_volume is not None else None

        raw_oi = message.get("open_interest") or message.get("oi")
        oi = int(raw_oi) if raw_oi is not None else None

        # Extract Day OHLC & Previous Close (Mode 2 Quote)
        raw_high = message.get("high_price_of_the_day") or message.get("high")
        day_high = float(raw_high) / 100.0 if raw_high is not None and float(raw_high) > 0 else None

        raw_low = message.get("low_price_of_the_day") or message.get("low")
        day_low = float(raw_low) / 100.0 if raw_low is not None and float(raw_low) > 0 else None

        raw_open = message.get("open_price_of_the_day") or message.get("open")
        day_open = float(raw_open) / 100.0 if raw_open is not None and float(raw_open) > 0 else None

        raw_close = message.get("closed_price") or message.get("close") or message.get("prev_close")
        prev_close = float(raw_close) / 100.0 if raw_close is not None and float(raw_close) > 0 else None

        # Extract Best Bid & Ask (Mode 2/3 Quote & Depth)
        raw_bid = message.get("best_5_buy_data", [{}])[0].get("price") if isinstance(message.get("best_5_buy_data"), list) and message.get("best_5_buy_data") else (message.get("buy_price") or message.get("best_bid") or message.get("bid"))
        best_bid = float(raw_bid) / 100.0 if raw_bid is not None and float(raw_bid) > 0 else None

        raw_ask = message.get("best_5_sell_data", [{}])[0].get("price") if isinstance(message.get("best_5_sell_data"), list) and message.get("best_5_sell_data") else (message.get("sell_price") or message.get("best_ask") or message.get("ask"))
        best_ask = float(raw_ask) / 100.0 if raw_ask is not None and float(raw_ask) > 0 else None

        raw_bid_qty = message.get("best_5_buy_data", [{}])[0].get("quantity") if isinstance(message.get("best_5_buy_data"), list) and message.get("best_5_buy_data") else (message.get("buy_quantity") or message.get("bid_qty"))
        bid_qty = int(raw_bid_qty) if raw_bid_qty is not None else None

        raw_ask_qty = message.get("best_5_sell_data", [{}])[0].get("quantity") if isinstance(message.get("best_5_sell_data"), list) and message.get("best_5_sell_data") else (message.get("sell_quantity") or message.get("ask_qty"))
        ask_qty = int(raw_ask_qty) if raw_ask_qty is not None else None

        current_time = now_ist()

        # WS01: Thread-safe batch update
        with _prices_lock:
            live_prices[token] = ltp
            live_timestamps[token] = current_time
            total_ticks_received += 1
            if volume is not None:
                live_volumes[token] = volume
            if oi is not None:
                live_oi[token] = oi
            if day_high is not None:
                live_day_high[token] = day_high
            if day_low is not None:
                live_day_low[token] = day_low
            if day_open is not None:
                live_day_open[token] = day_open
            if prev_close is not None:
                live_prev_close[token] = prev_close
            if best_bid is not None:
                live_best_bid[token] = best_bid
            if best_ask is not None:
                live_best_ask[token] = best_ask
            if bid_qty is not None:
                live_bid_qty[token] = bid_qty
            if ask_qty is not None:
                live_ask_qty[token] = ask_qty

        _last_price_time = current_time

        # Dispatch to registered tick listeners
        with _listeners_lock:
            listeners = list(_tick_listeners)
        if listeners:
            tick_event = {
                "token": token,
                "ltp": ltp,
                "volume": volume,
                "oi": oi,
                "high": day_high,
                "low": day_low,
                "open": day_open,
                "prev_close": prev_close,
                "bid": best_bid,
                "ask": best_ask,
                "bid_qty": bid_qty,
                "ask_qty": ask_qty,
                "timestamp": current_time,
            }
            for listener in listeners:
                try:
                    listener(tick_event)
                except Exception as ex:
                    logger.warning(f"[WebSocket] Listener callback error: {ex}")

    except Exception as e:
        logger.error(f"[WebSocket] Tick parse error: {e} | payload: {message}")


def on_error(wsapp: Any = None, error: Any = None, *args: Any, **kwargs: Any) -> None:
    """Called on WebSocket error."""
    err = error if error is not None else (args[0] if args else "Unknown error")
    logger.error(f"[WebSocket Error] {now_ist().strftime('%H:%M:%S IST')} — {err}")


def on_close(wsapp: Any = None, *args: Any, **kwargs: Any) -> None:
    """
    Called when WebSocket disconnects.
    Clears stale prices immediately to prevent strategies executing on old data.
    Spawns background reconnect if shutdown was not intentionally requested.
    """
    global _stop_requested

    logger.warning(f"[WebSocket Closed] {now_ist().strftime('%H:%M:%S IST')}")

    # The previously-confirmed connection is void the moment the socket drops,
    # so a stale flag can never fake-confirm a later reconnect.
    _connection_confirmed.clear()

    with _prices_lock:
        live_prices.clear()
        live_volumes.clear()
        live_oi.clear()
        live_day_open.clear()
        live_day_high.clear()
        live_day_low.clear()
        live_prev_close.clear()
        live_best_bid.clear()
        live_best_ask.clear()
        live_bid_qty.clear()
        live_ask_qty.clear()
        live_timestamps.clear()

    logger.info(
        "[WebSocket] Live caches cleared - downstream consumers now see NO live "
        "prices until reconnection succeeds; risk gates fail closed on missing data"
    )

    # Send alert
    _send_telegram("⚠️ <b>MJONAI</b> — WebSocket disconnected. Initiating auto-recovery...")

    if _stop_requested:
        logger.info("[WebSocket] Stop was intentionally requested — skipping auto-reconnect")
        _stop_requested = False
        return

    # Trigger background reconnect thread
    threading.Thread(target=_reconnect_loop, daemon=True).start()


def _subscribe_in_chunks(client: Any, correlation_id: str, mode_val: int, token_list: List[Dict[str, Any]], max_chunk_size: int = 400) -> None:
    """Chunk subscriptions to strictly enforce AngelOne's 500-token per packet limit."""
    for item in token_list:
        exchange_type = item.get("exchangeType", 1)
        tokens = item.get("tokens", [])
        for i in range(0, len(tokens), max_chunk_size):
            chunk = tokens[i : i + max_chunk_size]
            payload = [{"exchangeType": exchange_type, "tokens": chunk}]
            client.subscribe(correlation_id, mode_val, payload)


def on_open(wsapp: Any = None, *args: Any, **kwargs: Any) -> None:
    """Called when WebSocket connection is established — subscribes token list."""
    logger.info(f"[WebSocket Connected] {now_ist().strftime('%H:%M:%S IST')}")

    if not _token_list:
        logger.warning("[WebSocket] No tokens to subscribe — token_list is empty")
        return

    client = wsapp if (wsapp is not None and hasattr(wsapp, "subscribe")) else _sws
    if client is not None:
        try:
            _subscribe_in_chunks(client, _correlation_id, _active_mode.value, _token_list)
            total_tokens = sum(len(item.get("tokens", [])) for item in _token_list)
            logger.info(f"[WebSocket] Subscribed to {total_tokens} instruments in Mode {_active_mode.name} (Chunked)")
            # Connection proven live: subscriptions accepted. Reconnect loop waits on this.
            _connection_confirmed.set()
        except Exception as e:
            logger.error(f"[WebSocket] Subscription error on open: {e}")


# ── 5b. RE-AUTH HOOK (C8b) ────────────────────────────────────────────────────
# Angel One tokens expire at the daily rollover; startup-era credentials cannot
# survive it (the old loop reused them until manual restart). main.py registers
# a TOTP-login-only callback here so stubborn recoveries can obtain fresh
# tokens mid-loop instead of reusing dead ones.

_reauth_callback: Optional[Callable[[], bool]] = None


def set_reauth_callback(fn: Optional[Callable[[], bool]]) -> None:
    """Register a no-args callable performing broker login + set_auth() WITHOUT
    restarting sockets (the reconnect loop owns socket lifecycle)."""
    global _reauth_callback
    _reauth_callback = fn


def _maybe_reauth(attempt: int, trigger_on_attempt: int = 3) -> None:
    """Invoke the re-auth hook once recovery has proven stubborn."""
    if attempt != trigger_on_attempt or _reauth_callback is None:
        return
    logger.info(
        "[WebSocket] Reconnects keep failing - invoking re-auth hook to refresh broker tokens"
    )
    try:
        if _reauth_callback():
            logger.info("[WebSocket] Re-auth OK - fresh tokens active for remaining reconnect attempts")
        else:
            logger.warning("[WebSocket] Re-auth hook returned False - continuing with existing tokens")
    except Exception as cb_err:
        logger.error(f"[WebSocket] Re-auth hook raised: {cb_err}")


# ── 6. RESILIENT RECONNECT LOOP ───────────────────────────────────────────────

def _reconnect_loop() -> None:
    """
    Exponential backoff reconnect loop running in a dedicated daemon thread.
    Attempts up to _MAX_RECONNECT_ATTEMPTS before alerting supervisor.
    """
    global _reconnect_attempts, _is_reconnecting

    with _reconnect_lock:
        if _is_reconnecting:
            logger.info("[WebSocket] Reconnect already in progress — skipping duplicate trigger")
            return
        _is_reconnecting = True

    try:
        delays = [2, 5, 10, 15, 30]
        # No connection is confirmed when the recovery loop begins
        _connection_confirmed.clear()
        for attempt in range(1, _MAX_RECONNECT_ATTEMPTS + 1):
            delay = delays[min(attempt - 1, len(delays) - 1)]
            # Jitter the backoff window ±50%: when many sockets drop together
            # (broker restart, network blip) they must not retry in lockstep.
            sleep_for = delay * random.uniform(0.5, 1.5)
            logger.info(f"[WebSocket] Reconnect attempt {attempt}/{_MAX_RECONNECT_ATTEMPTS} (waiting {delay}s ±50%)...")
            time.sleep(sleep_for)

            # C8b: before the third try, refresh broker tokens via the re-auth
            # hook if one is registered — daily rollover kills startup tokens.
            _maybe_reauth(attempt)

            try:
                # Snapshot under the lock: the list can be mutated concurrently
                # by dynamic subscribe/unsubscribe during recovery.
                with _token_list_lock:
                    token_snapshot = [dict(item) for item in _token_list]
                start_websocket(token_snapshot, mode=_active_mode)
            except Exception as e:
                logger.error(f"[WebSocket] Reconnect attempt {attempt} failed: {e}")
                _reconnect_attempts += 1
                continue

            # start_websocket only spawns the socket thread — it proves nothing.
            # Wait for on_open to confirm a successful subscribe before declaring victory.
            if _connection_confirmed.wait(timeout=30):
                _connection_confirmed.clear()
                logger.info(f"[WebSocket] Reconnected successfully on attempt {attempt}")
                _reconnect_attempts = 0
                _send_telegram(f"✅ <b>MJONAI</b> — WebSocket reconnected successfully (attempt {attempt}/{_MAX_RECONNECT_ATTEMPTS}).")
                return

            logger.error(
                f"[WebSocket] Reconnect attempt {attempt} FAILED — no confirmed "
                f"connection within 30s of start_websocket()"
            )
            _reconnect_attempts += 1

        logger.critical("[WebSocket] All reconnect attempts failed — supervisor alert sent")
        _send_telegram(
            "🚨 <b>MJONAI — WebSocket Recovery Failed</b>\n"
            f"All {_MAX_RECONNECT_ATTEMPTS} reconnect attempts failed.\n"
            "Live feed DOWN - risk gates fail closed on missing prices; no fallback feed exists."
        )

    finally:
        _is_reconnecting = False


# ── 7. LIFECYCLE MANAGEMENT (START, RESTART, STOP, ACCESSORS) ─────────────────

def start_websocket(token_list: List[Dict[str, Any]], mode: WebSocketMode = WebSocketMode.QUOTE) -> None:
    """
    Start WebSocket connection in a daemon thread.
    Closes existing connection before creating a new socket.
    """
    global _sws, _token_list, _stop_requested, _active_mode

    with _token_list_lock:
        _token_list = token_list
    _active_mode = mode
    _stop_requested = False

    # Close existing connection if active
    if _sws is not None:
        try:
            _sws.close_connection()
            time.sleep(1)
        except Exception:
            pass

    try:
        from SmartApi.smartWebSocketV2 import SmartWebSocketV2

        # Safe monkeypatch for SmartWebSocketV2._on_close to handle variable arguments from websocket-client
        try:
            if hasattr(SmartWebSocketV2, "_on_close"):
                orig_on_close = SmartWebSocketV2._on_close
                def _safe_smart_on_close(self, *args, **kwargs):
                    try:
                        if len(args) == 1:
                            return orig_on_close(self, args[0])
                        elif len(args) > 1:
                            return orig_on_close(self, args[0])
                        return orig_on_close(self, None)
                    except Exception:
                        pass
                SmartWebSocketV2._on_close = _safe_smart_on_close
        except Exception:
            pass

        api_key = (os.getenv("ANGELONE_API_KEY") or "").strip()
        auth_token = (_auth_token or "").strip()
        client_id = (_client_id or "").strip()
        feed_token = (_feed_token or "").strip()

        if not (auth_token and api_key and client_id and feed_token):
            logger.warning("[WebSocket] Missing required credentials for live SmartWebSocketV2. Operating in offline/paper simulation mode.")
            return

        sws_instance = SmartWebSocketV2(auth_token, api_key, client_id, feed_token)
        _sws = sws_instance

        _sws.on_open = on_open
        _sws.on_data = on_data
        _sws.on_error = on_error
        _sws.on_close = on_close

        def run():
            try:
                logger.info("[WebSocket] Starting connect()...")
                sws_instance.connect()
                logger.info("[WebSocket] connect() loop exited.")
            except Exception:
                logger.exception("[WebSocket] connect() thread crashed")

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

        total_tokens = sum(len(item.get("tokens", [])) for item in token_list)
        logger.info(f"[WebSocket] Connecting for {total_tokens} symbols in Mode {mode.name}...")

    except Exception as e:
        logger.error(f"[WebSocket] Failed to initialize SmartWebSocketV2: {e}")
        raise


def subscribe_tokens(tokens: List[str], exchange_type: int = 1, mode: Optional[WebSocketMode] = None) -> bool:
    """Canonical alias for subscribe_additional_tokens."""
    return subscribe_additional_tokens(tokens=tokens, exchange_type=exchange_type, mode=mode)


def restart_websocket() -> None:
    """Restart the existing websocket connection (used by supervisor upon staleness)."""
    logger.warning("[WebSocket] Restart requested by watchdog.")
    stop_websocket()
    time.sleep(1)
    start_websocket(_token_list, mode=_active_mode)


def stop_websocket() -> None:
    """Gracefully close WebSocket connection and prevent auto-reconnect."""
    global _sws, _stop_requested
    _stop_requested = True
    if _sws is not None:
        try:
            _sws.close_connection()
            logger.info("[WebSocket] Disconnected cleanly (stop requested)")
        except Exception as e:
            logger.error(f"[WebSocket] Error during close: {e}")


def _is_fresh(token: str) -> bool:
    """
    True if this token received a tick within _STALE_THRESHOLD_SECONDS of now.
    False when the token has no timestamp (never ticked) or its last tick is stale.
    Safe to call while already holding _prices_lock (reentrant lock).
    """
    tok = token.strip() if isinstance(token, str) else str(token).strip()
    with _prices_lock:
        ts = live_timestamps.get(tok)
    if ts is None:
        return False
    return (now_ist() - ts).total_seconds() < _STALE_THRESHOLD_SECONDS


def get_live_price(token: str) -> Optional[float]:
    """
    Get real-time Last Traded Price (LTP) for a token.
    Returns None if unmapped OR stale (no tick within _STALE_THRESHOLD_SECONDS) —
    stale prices are never served to strategies.
    """
    tok = token.strip()
    with _prices_lock:
        if not _is_fresh(tok):
            return None
        return live_prices.get(tok)


def is_token_fresh(token: str) -> bool:
    """
    Public staleness probe for a token: True only when its last tick landed
    within _STALE_THRESHOLD_SECONDS.

    Consumers that receive the raw ``live_prices`` dict (instead of calling
    ``get_live_price``) MUST gate their reads on this — otherwise a token that
    stopped ticking is served as if it were live (staleness-gate bypass).
    """
    return _is_fresh(token)


def get_live_volume(token: str) -> Optional[int]:
    """Get real-time cumulative day volume. Returns None if unmapped or stale."""
    tok = token.strip()
    with _prices_lock:
        if not _is_fresh(tok):
            return None
        return live_volumes.get(tok)


def get_live_oi(token: str) -> Optional[int]:
    """Get real-time Open Interest for an F&O token. Returns None if unmapped or stale."""
    tok = token.strip()
    with _prices_lock:
        if not _is_fresh(tok):
            return None
        return live_oi.get(tok)


def get_live_day_high(token: str) -> Optional[float]:
    """Get today's real-time Day High price (₹) for a token."""
    with _prices_lock:
        return live_day_high.get(token.strip())


def get_live_day_low(token: str) -> Optional[float]:
    """Get today's real-time Day Low price (₹) for a token."""
    with _prices_lock:
        return live_day_low.get(token.strip())


def get_live_day_open(token: str) -> Optional[float]:
    """Get today's real-time Day Open price (₹) for a token."""
    with _prices_lock:
        return live_day_open.get(token.strip())


def get_live_prev_close(token: str) -> Optional[float]:
    """Get previous trading day close price (₹) for a token."""
    with _prices_lock:
        return live_prev_close.get(token.strip())


def get_live_bid(token: str) -> Optional[float]:
    """Get real-time Best Bid price (₹) for a token."""
    with _prices_lock:
        return live_best_bid.get(token.strip())


def get_live_ask(token: str) -> Optional[float]:
    """Get real-time Best Ask price (₹) for a token."""
    with _prices_lock:
        return live_best_ask.get(token.strip())


def get_live_spread_pct(token: str) -> Optional[float]:
    """
    Calculate real-time Bid-Ask spread percentage: ((Ask - Bid) / Bid) * 100.
    Returns None if bid or ask quotes are unavailable.
    """
    tok = token.strip()
    with _prices_lock:
        bid = live_best_bid.get(tok)
        ask = live_best_ask.get(tok)
        if bid is not None and ask is not None and bid > 0:
            return round(((ask - bid) / bid) * 100.0, 4)
        return None


def get_live_spread(token: str) -> Optional[float]:
    """Calculate real-time Bid-Ask spread in basis points (bps)."""
    pct = get_live_spread_pct(token)
    return round(pct * 100.0, 2) if pct is not None else None


def get_live_depth(token: str) -> Optional[Dict[str, Any]]:
    """
    Get live top-of-book market depth for a token:
    {'best_bid': ..., 'best_ask': ..., 'bid_qty': ..., 'ask_qty': ...}
    """
    tok = token.strip()
    with _prices_lock:
        bid = live_best_bid.get(tok)
        ask = live_best_ask.get(tok)
        if bid is None and ask is None:
            return None
        # Spread computed inline under the already-held lock (do not rely on
        # lock reentrancy on the hot path — see _prices_lock note above).
        spread_pct = round(((ask - bid) / bid) * 100.0, 4) if (bid and ask and bid > 0) else None
        return {
            "best_bid": bid,
            "best_ask": ask,
            "bid_qty": live_bid_qty.get(tok, 0),
            "ask_qty": live_ask_qty.get(tok, 0),
            "spread_pct": spread_pct,
        }


def is_spread_acceptable(token: str, max_spread_pct: float = 0.25, fail_closed: bool = False) -> bool:
    """
    Institutional Slippage Guard:
    Returns True if spread is <= max_spread_pct.
    If spread is None (market depth / bid-ask quotes unavailable):
      - fail_closed=False: allows trade through (permissive for liquid cash equities)
      - fail_closed=True: blocks trade (strict fail-closed protection for options/derivatives)
    """
    spread = get_live_spread_pct(token)
    if spread is None:
        if fail_closed:
            logger.warning(f"[WebSocket] Spread check failed-closed for token {token}: no live depth/spread data")
            return False
        return True
    return spread <= max_spread_pct


def register_tick_listener(callback: Callable[[Dict[str, Any]], None]) -> None:
    """Register an event-driven tick listener callback (Observer Pattern)."""
    with _listeners_lock:
        if callback not in _tick_listeners:
            _tick_listeners.append(callback)


def unregister_tick_listener(callback: Callable[[Dict[str, Any]], None]) -> None:
    """Unregister an event-driven tick listener callback."""
    with _listeners_lock:
        if callback in _tick_listeners:
            _tick_listeners.remove(callback)


def get_live_quote(token: str) -> Optional[Dict[str, Any]]:
    """
    Get unified live quote snapshot for a token:
    {'ltp': ..., 'volume': ..., 'oi': ..., 'high': ..., 'low': ..., 'open': ..., 'prev_close': ..., 'bid': ..., 'ask': ..., 'spread_pct': ..., 'change_pct': ..., 'timestamp': ..., 'staleness_seconds': ...}
    """
    tok = token.strip()
    with _prices_lock:
        ltp = live_prices.get(tok)
        if ltp is None or not _is_fresh(tok):
            return None  # No quote at all, or the snapshot is stale
        ts = live_timestamps.get(tok)
        prev_close = live_prev_close.get(tok)
        change_pct = ((ltp - prev_close) / prev_close) * 100.0 if (prev_close and prev_close > 0) else None
        staleness = (now_ist() - ts).total_seconds() if ts else None
        bid = live_best_bid.get(tok)
        ask = live_best_ask.get(tok)
        spread_pct = round(((ask - bid) / bid) * 100.0, 4) if (bid and ask and bid > 0) else None

        return {
            "token": tok,
            "ltp": ltp,
            "volume": live_volumes.get(tok),
            "oi": live_oi.get(tok),
            "high": live_day_high.get(tok),
            "low": live_day_low.get(tok),
            "open": live_day_open.get(tok),
            "prev_close": prev_close,
            "bid": bid,
            "ask": ask,
            "bid_qty": live_bid_qty.get(tok),
            "ask_qty": live_ask_qty.get(tok),
            "spread_pct": spread_pct,
            "change_pct": change_pct,
            "timestamp": ts,
            "staleness_seconds": staleness,
        }


def get_total_ticks_received() -> int:
    """Return cumulative count of all valid ticks ingested since startup."""
    with _prices_lock:
        return total_ticks_received


def reset_tick_counter() -> None:
    """Reset tick counter (e.g. at daily market open)."""
    global total_ticks_received
    with _prices_lock:
        total_ticks_received = 0


# ── 8. DYNAMIC INTRADAY SUBSCRIPTION APIS ─────────────────────────────────────

def subscribe_additional_tokens(
    tokens: List[str],
    exchange_type: int = 1,  # 1 = NSE Cash, 2 = NFO Derivatives, 3 = BSE, 4 = BFO
    mode: Optional[WebSocketMode] = None
) -> bool:
    """
    Dynamically subscribe additional instruments (e.g. newly active option strikes)
    during intraday market hours without restarting the socket connection.
    Chunked into 400-token batches to strictly respect broker packet limits.
    """
    global _sws, _token_list, _active_mode

    if not tokens:
        return False

    clean_tokens = [t.strip() for t in tokens if t and t.strip()]
    if not clean_tokens:
        return False

    target_mode = mode if mode is not None else _active_mode

    # Update internal token list so auto-reconnects preserve new tokens.
    # Read-modify-write is guarded: a concurrent unsubscribe or reconnect must not
    # interleave and silently drop tokens.
    with _token_list_lock:
        found_exchange = False
        for item in _token_list:
            if item.get("exchangeType") == exchange_type:
                existing = set(item.get("tokens", []))
                existing.update(clean_tokens)
                item["tokens"] = list(existing)
                found_exchange = True
                break
        if not found_exchange:
            _token_list.append({"exchangeType": exchange_type, "tokens": clean_tokens})

    # If socket is active, send live subscription packets in chunks
    if _sws is not None:
        try:
            sub_payload = [{"exchangeType": exchange_type, "tokens": clean_tokens}]
            _subscribe_in_chunks(_sws, _correlation_id, target_mode.value, sub_payload)
            logger.info(f"[WebSocket] Dynamically subscribed {len(clean_tokens)} new tokens on exchange {exchange_type}")
            return True
        except Exception as e:
            logger.error(f"[WebSocket] Dynamic subscribe error: {e}")
            return False

    return True


def unsubscribe_tokens(
    tokens: List[str],
    exchange_type: int = 1
) -> bool:
    """
    Dynamically unsubscribe instruments to reduce WebSocket bandwidth.
    The live unsubscribe is attempted FIRST; _token_list is only shrunk once the
    broker accepted the request. On failure nothing is removed (rollback), so an
    auto-reconnect resubscribes exactly what was still wanted.
    """
    global _sws

    if not tokens:
        return False

    clean_tokens = [t.strip() for t in tokens if t and t.strip()]
    unsub_payload = [{"exchangeType": exchange_type, "tokens": clean_tokens}]

    # 1. Live unsubscribe first (if socket active and supports it)
    if _sws is not None and hasattr(_sws, "unsubscribe"):
        try:
            _sws.unsubscribe(_correlation_id, _active_mode.value, unsub_payload)
        except Exception as e:
            logger.warning(f"[WebSocket] Dynamic unsubscribe error: {e}")
            return False  # Rollback: token list intentionally left untouched

    # 2. Only now remove from the internal list so reconnects stay consistent
    with _token_list_lock:
        for item in _token_list:
            if item.get("exchangeType") == exchange_type:
                item["tokens"] = [t for t in item.get("tokens", []) if t not in clean_tokens]

    logger.info(f"[WebSocket] Dynamically unsubscribed {len(clean_tokens)} tokens")
    return True


def get_websocket_stats() -> Dict[str, Any]:
    """Observability telemetry for the AngelOne WebSocket streaming engine."""
    with _prices_lock:
        price_count = len(live_prices)
        vol_count = len(live_volumes)
        oi_count = len(live_oi)

    return {
        "is_healthy": is_websocket_healthy(),
        "total_ticks_received": get_total_ticks_received(),
        "tracked_price_tokens": price_count,
        "tracked_volume_tokens": vol_count,
        "tracked_oi_tokens": oi_count,
    }


def clear_tick_caches() -> None:
    """Clear all in-memory live tick and depth caches (for testing and daily market rollover)."""
    with _prices_lock:
        live_prices.clear()
        live_volumes.clear()
        live_oi.clear()
        live_day_open.clear()
        live_day_high.clear()
        live_day_low.clear()
        live_prev_close.clear()
        live_best_bid.clear()
        live_best_ask.clear()
        live_bid_qty.clear()
        live_ask_qty.clear()
        live_timestamps.clear()