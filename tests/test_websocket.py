"""
Production-Level Test Suite for data/angelone/websocket.py
Tests Tick Parsing, Mode 2 Quote (Volume & Open Interest), Token Staleness,
Thread Safety, Health Watchdog, and Cache Clearing on Disconnect.
"""

from datetime import datetime, timedelta
from pathlib import Path
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from mjonai.data.angelone.websocket import (
    WebSocketMode,
    live_prices,
    live_volumes,
    live_oi,
    live_timestamps,
    _prices_lock,
    on_data,
    on_close,
    get_live_price,
    get_live_volume,
    get_live_oi,
    get_live_quote,
    get_token_staleness,
    is_websocket_healthy,
    set_subscription_mode,
)
from mjonai.core.time_utils import now_ist


@pytest.fixture(autouse=True)
def clean_websocket_state():
    """Reset in-memory websocket stores before each test."""
    with _prices_lock:
        live_prices.clear()
        live_volumes.clear()
        live_oi.clear()
        live_timestamps.clear()
    yield
    with _prices_lock:
        live_prices.clear()
        live_volumes.clear()
        live_oi.clear()
        live_timestamps.clear()


def test_websocket_mode_enums():
    """Verify subscription modes correspond to AngelOne protocol specifications."""
    assert WebSocketMode.LTP.value == 1
    assert WebSocketMode.QUOTE.value == 2
    assert WebSocketMode.SNAP_QUOTE.value == 3


def test_on_data_parses_ltp_and_paise_conversion():
    """Verify on_data parses tick and converts paise (>100000) or direct rupees accurately."""
    mock_ws = MagicMock()
    # 250000 paise = ₹2500.00
    msg = {
        "token": "2885",
        "last_traded_price": 250000,
    }
    on_data(mock_ws, msg)

    assert get_live_price("2885") == 2500.0
    assert get_live_price(" 2885 ") == 2500.0


def test_on_data_extracts_volume_and_open_interest_in_mode2():
    """Verify Mode 2 Quote message extracts volume and open interest."""
    mock_ws = MagicMock()
    msg = {
        "token": "54321",
        "last_traded_price": 12550,  # ₹125.50
        "volume_trade_for_the_day": 850000,
        "open_interest": 1500000,
    }
    on_data(mock_ws, msg)

    assert get_live_price("54321") == 125.50
    assert get_live_volume("54321") == 850000
    assert get_live_oi("54321") == 1500000

    quote = get_live_quote("54321")
    assert quote is not None
    assert quote["ltp"] == 125.50
    assert quote["volume"] == 850000
    assert quote["oi"] == 1500000
    assert quote["timestamp"] is not None


def test_on_data_filters_anomalous_ticks():
    """Verify zero, null, and out-of-bound prices are rejected."""
    mock_ws = MagicMock()
    on_data(mock_ws, {"token": "100", "last_traded_price": 0})
    on_data(mock_ws, {"token": "101", "last_traded_price": None})
    on_data(mock_ws, {"token": "None", "last_traded_price": 50000})

    assert get_live_price("100") is None
    assert get_live_price("101") is None


def test_token_staleness_measurement():
    """Verify token staleness returns elapsed seconds."""
    mock_ws = MagicMock()
    on_data(mock_ws, {"token": "2885", "last_traded_price": 250000})

    staleness = get_token_staleness("2885")
    assert staleness is not None
    assert staleness >= 0.0

    # Non-existent token returns None
    assert get_token_staleness("999999") is None


def test_on_close_clears_all_caches():
    """Verify on_close flushes live prices, volumes, and OI to prevent trading on stale data."""
    mock_ws = MagicMock()
    on_data(mock_ws, {"token": "2885", "last_traded_price": 250000, "volume": 1000, "oi": 5000})
    assert get_live_price("2885") is not None

    with patch("mjonai.communication.telegram.send_message"):
        on_close(mock_ws)

    assert get_live_price("2885") is None
    assert get_live_volume("2885") is None
    assert get_live_oi("2885") is None


def test_concurrent_tick_writes_and_reads():
    """Thread safety test: Concurrent writers and readers never deadlock or corrupt store."""
    mock_ws = MagicMock()
    tokens = [str(i) for i in range(100)]

    def writer():
        for t in tokens:
            on_data(mock_ws, {"token": t, "last_traded_price": int(t) * 1000 + 100, "volume": int(t) * 10})

    def reader():
        for t in tokens:
            _ = get_live_quote(t)

    threads = [
        threading.Thread(target=writer),
        threading.Thread(target=reader),
        threading.Thread(target=writer),
        threading.Thread(target=reader),
    ]

    for th in threads:
        th.start()
    for th in threads:
        th.join()

    # Verify state integrity
    assert len(live_prices) == 100


def test_total_ticks_counter_increments_and_resets():
    """Verify total_ticks_received tracks lifetime ticks and resets cleanly."""
    from mjonai.data.angelone.websocket import get_total_ticks_received, reset_tick_counter

    reset_tick_counter()
    assert get_total_ticks_received() == 0

    mock_ws = MagicMock()
    on_data(mock_ws, {"token": "100", "last_traded_price": 25000})
    on_data(mock_ws, {"token": "200", "last_traded_price": 35000})

    assert get_total_ticks_received() == 2

    reset_tick_counter()
    assert get_total_ticks_received() == 0


def test_dynamic_subscribe_and_unsubscribe_tokens():
    """Verify dynamic intraday token subscription and unsubscription."""
    from mjonai.data.angelone.websocket import (
        subscribe_additional_tokens,
        unsubscribe_tokens,
        _token_list,
    )
    import mjonai.data.angelone.websocket as ws_mod
    mock_sws = MagicMock()
    ws_mod._sws = mock_sws
    ws_mod._token_list = [{"exchangeType": 1, "tokens": ["1000", "2000"]}]

    # 1. Subscribe new tokens
    res = subscribe_additional_tokens(["3000", "4000"], exchange_type=1)
    assert res is True
    assert mock_sws.subscribe.called
    assert "3000" in ws_mod._token_list[0]["tokens"]
    assert "4000" in ws_mod._token_list[0]["tokens"]

    # 2. Unsubscribe token
    res_unsub = unsubscribe_tokens(["3000"], exchange_type=1)
    assert res_unsub is True
    assert "3000" not in ws_mod._token_list[0]["tokens"]
    assert "4000" in ws_mod._token_list[0]["tokens"]

    # Clean up mock
    ws_mod._sws = None


def test_on_data_extracts_day_ohlc_and_calculates_change_pct():
    """Verify Day Open, High, Low, Previous Close, and Change % extraction."""
    from mjonai.data.angelone.websocket import (
        get_live_day_open,
        get_live_day_high,
        get_live_day_low,
        get_live_prev_close,
        get_live_quote,
    )

    mock_ws = MagicMock()
    tick_payload = {
        "token": "2885",
        "last_traded_price": 250000,           # ₹2500.00
        "open_price_of_the_day": 248000,       # ₹2480.00
        "high_price_of_the_day": 252000,       # ₹2520.00
        "low_price_of_the_day": 247500,        # ₹2475.00
        "closed_price": 245000,                # ₹2450.00 (prev close)
        "volume_trade_for_the_day": 150000,
        "open_interest": 45000,
    }

    on_data(mock_ws, tick_payload)

    assert get_live_day_open("2885") == 2480.0
    assert get_live_day_high("2885") == 2520.0
    assert get_live_day_low("2885") == 2475.0
    assert get_live_prev_close("2885") == 2450.0

    quote = get_live_quote("2885")
    assert quote is not None
    assert quote["high"] == 2520.0
    assert quote["low"] == 2475.0
    assert quote["open"] == 2480.0
    assert quote["prev_close"] == 2450.0
    # Change % = ((2500 - 2450) / 2450) * 100 = 2.04%
    assert quote["change_pct"] is not None
    assert round(quote["change_pct"], 2) == 2.04


def test_event_driven_tick_listener_observer_pattern():
    """Verify registered callbacks receive real-time tick events."""
    from mjonai.data.angelone.websocket import register_tick_listener, unregister_tick_listener

    events_received = []

    def on_tick_callback(event):
        events_received.append(event)

    register_tick_listener(on_tick_callback)

    mock_ws = MagicMock()
    on_data(mock_ws, {"token": "999", "last_traded_price": 50000})

    assert len(events_received) == 1
    assert events_received[0]["token"] == "999"
    assert events_received[0]["ltp"] == 500.0

    # Unregister
    unregister_tick_listener(on_tick_callback)
    on_data(mock_ws, {"token": "999", "last_traded_price": 50500})
    assert len(events_received) == 1  # No new event received after unregister


def test_chunked_subscription_splits_large_token_lists():
    """Verify subscription lists exceeding 400 tokens are cleanly batched."""
    from mjonai.data.angelone.websocket import _subscribe_in_chunks

    mock_client = MagicMock()
    large_token_list = [{"exchangeType": 1, "tokens": [str(i) for i in range(1000)]}]

    _subscribe_in_chunks(mock_client, "test_corr", 2, large_token_list, max_chunk_size=400)

    # 1000 tokens / 400 = 3 chunked calls (400, 400, 200)
    assert mock_client.subscribe.call_count == 3


def test_live_bid_ask_spread_and_slippage_guard():
    """Verify best bid/ask parsing, spread percentage, and institutional slippage guard."""
    from mjonai.data.angelone.websocket import (
        get_live_bid,
        get_live_ask,
        get_live_spread_pct,
        is_spread_acceptable,
        get_live_quote,
    )

    mock_ws = MagicMock()
    # 1. Normal liquid stock: Bid = 2500.0, Ask = 2500.5 (Spread = 0.02%)
    tick_liquid = {
        "token": "2885",
        "last_traded_price": 250000,
        "best_5_buy_data": [{"price": 250000, "quantity": 500}],
        "best_5_sell_data": [{"price": 250050, "quantity": 400}],
    }
    on_data(mock_ws, tick_liquid)

    assert get_live_bid("2885") == 2500.0
    assert get_live_ask("2885") == 2500.5
    spread = get_live_spread_pct("2885")
    assert spread is not None
    assert round(spread, 3) == 0.02
    assert is_spread_acceptable("2885", max_spread_pct=0.25) is True

    # 2. Illiquid option: Bid = 100.0, Ask = 105.0 (Spread = 5.0% > 0.25% threshold)
    tick_illiquid = {
        "token": "9988",
        "last_traded_price": 10000,
        "best_5_buy_data": [{"price": 10000, "quantity": 50}],
        "best_5_sell_data": [{"price": 10500, "quantity": 25}],
    }
    on_data(mock_ws, tick_illiquid)

    assert get_live_spread_pct("9988") == 5.0
    # Guard blocks execution!
    assert is_spread_acceptable("9988", max_spread_pct=0.25) is False


def test_get_live_depth_reentrant_lock_no_deadlock():
    """FIX 1 regression: get_live_depth under a held _prices_lock must not self-deadlock."""
    import mjonai.data.angelone.websocket as ws_mod
    from mjonai.data.angelone.websocket import get_live_depth

    mock_ws = MagicMock()
    on_data(mock_ws, {
        "token": "2885",
        "last_traded_price": 250000,
        "best_5_buy_data": [{"price": 250000, "quantity": 500}],
        "best_5_sell_data": [{"price": 250050, "quantity": 400}],
    })

    result = {}

    def reader():
        # Re-enter the lock from the same thread: a plain Lock deadlocks here forever,
        # an RLock (plus the inline spread computation in get_live_depth) proceeds.
        with ws_mod._prices_lock:
            result["depth"] = get_live_depth("2885")
        result["quote"] = get_live_quote("2885")

    th = threading.Thread(target=reader, daemon=True)
    th.start()
    th.join(timeout=10)

    assert not th.is_alive(), "get_live_depth deadlocked — _prices_lock is not reentrant"

    depth = result.get("depth")
    assert depth is not None
    assert depth["best_bid"] == 2500.0
    assert depth["best_ask"] == 2500.5
    assert round(depth["spread_pct"], 3) == 0.02
    assert result.get("quote") is not None


def test_is_websocket_healthy_requires_token_coverage_not_one_hot_tick():
    """FIX 3 regression: health reflects per-token coverage, not just one fresh tick."""
    import mjonai.data.angelone.websocket as ws_mod
    tokens = [f"710{i}" for i in range(5)]
    fresh_ts = now_ist()
    stale_ts = fresh_ts - timedelta(seconds=ws_mod._STALE_THRESHOLD_SECONDS * 10)

    saved_token_list = ws_mod._token_list
    saved_last_price_time = ws_mod._last_price_time

    try:
        with patch("mjonai.data.angelone.websocket.is_market_open", return_value=True):
            with ws_mod._prices_lock:
                for i, tok in enumerate(tokens):
                    live_prices[tok] = 100.0 + i
                    # Only token 0 is fresh; the rest stopped ticking long ago
                    live_timestamps[tok] = fresh_ts if i == 0 else stale_ts
            ws_mod._token_list = [{"exchangeType": 1, "tokens": list(tokens)}]
            ws_mod._last_price_time = fresh_ts  # global recency passes...

            # ...but coverage is only 1/5 (20% < 60%) -> unhealthy
            assert is_websocket_healthy() is False

            # 2/5 (40%) still below threshold -> unhealthy
            with ws_mod._prices_lock:
                live_timestamps[tokens[1]] = fresh_ts
            assert is_websocket_healthy() is False

            # Majority fresh: 4/5 (80% >= 60%) -> healthy
            with ws_mod._prices_lock:
                for tok in tokens[2:]:
                    live_timestamps[tok] = fresh_ts
            assert is_websocket_healthy() is True
    finally:
        ws_mod._token_list = saved_token_list
        ws_mod._last_price_time = saved_last_price_time


def test_get_live_price_returns_none_for_stale_timestamp():
    """FIX 4 regression: stale tokens must never be served to strategies."""
    import mjonai.data.angelone.websocket as ws_mod
    mock_ws = MagicMock()
    on_data(mock_ws, {
        "token": "7777",
        "last_traded_price": 250000,
        "volume_trade_for_the_day": 12345,
        "open_interest": 999,
    })

    # Fresh sanity check before ageing the timestamp
    assert get_live_price("7777") == 2500.0

    stale_ts = now_ist() - timedelta(seconds=ws_mod._STALE_THRESHOLD_SECONDS + 30)
    with ws_mod._prices_lock:
        live_timestamps["7777"] = stale_ts

    assert get_live_price("7777") is None
    assert get_live_volume("7777") is None
    assert get_live_oi("7777") is None
    assert get_live_quote("7777") is None


