"""Regression tests: 5-level market-depth parsing + DepthArchive persistence.

Pins the contract that SNAP_QUOTE (Mode 3) frames parse all 5 bid/ask levels
into in-memory stores and durable parquet, that Mode 2 frames correctly leave
depth state untouched (never overwrite with a partial frame), and that the
DepthArchive deduplicates consecutive identical snapshots, flushes a correct
long-format schema, and reloads. All OFFLINE — synthetic frames only."""

from datetime import datetime, date, timedelta
from pathlib import Path
import sys

import pandas as pd
import pytest

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from mjonai.data.angelone.websocket import (
    live_depth_bids,
    live_depth_asks,
    live_best_bid,
    live_best_ask,
    _prices_lock,
    on_data,
    on_close,
    get_live_depth,
    get_live_depth_levels,
)
from mjonai.data.depth_archive import (
    DepthArchive,
    _snapshot_fingerprint,
    _snapshot_to_rows,
    depth_archive_tick_listener,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _mode3_frame(token="48864", price_paise=150000):
    """Synthetic SNAP_QUOTE frame with full 5-level depth (prices in paise)."""
    return {
        "token": token,
        "last_traded_price": price_paise,
        "volume_trade_for_the_day": 100000,
        "open_interest": 5000,
        "best_5_buy_data": [
            {"price": price_paise - 100, "quantity": 500, "noOfOrders": 3},
            {"price": price_paise - 200, "quantity": 800, "noOfOrders": 5},
            {"price": price_paise - 300, "quantity": 1200, "noOfOrders": 7},
            {"price": price_paise - 400, "quantity": 1500, "noOfOrders": 9},
            {"price": price_paise - 500, "quantity": 2000, "noOfOrders": 11},
        ],
        "best_5_sell_data": [
            {"price": price_paise + 100, "quantity": 600, "noOfOrders": 4},
            {"price": price_paise + 200, "quantity": 900, "noOfOrders": 6},
            {"price": price_paise + 300, "quantity": 1100, "noOfOrders": 8},
            {"price": price_paise + 400, "quantity": 1400, "noOfOrders": 10},
            {"price": price_paise + 500, "quantity": 1800, "noOfOrders": 12},
        ],
    }


def _mode2_frame(token="48864", price_paise=150000):
    """Synthetic QUOTE (Mode 2) frame — top-of-book only, NO best_5_* lists."""
    return {
        "token": token,
        "last_traded_price": price_paise,
        "volume_trade_for_the_day": 100000,
        "open_interest": 5000,
        "buy_price": price_paise - 100,
        "sell_price": price_paise + 100,
        "buy_quantity": 500,
        "sell_quantity": 600,
    }


@pytest.fixture(autouse=True)
def clean_state():
    with _prices_lock:
        live_depth_bids.clear()
        live_depth_asks.clear()
        live_best_bid.clear()
        live_best_ask.clear()
    yield
    with _prices_lock:
        live_depth_bids.clear()
        live_depth_asks.clear()
        live_best_bid.clear()
        live_best_ask.clear()


# ── websocket depth parsing ─────────────────────────────────────────────────

def test_mode3_parses_all_5_bid_and_ask_levels():
    on_data(data=_mode3_frame())
    with _prices_lock:
        bids = live_depth_bids.get("48864")
        asks = live_depth_asks.get("48864")
    assert bids is not None and len(bids) == 5
    assert asks is not None and len(asks) == 5
    # Prices converted from paise to ₹
    assert bids[0]["price"] == pytest.approx(1499.0)
    assert asks[0]["price"] == pytest.approx(1501.0)
    assert bids[0]["quantity"] == 500
    assert asks[0]["orders"] == 4   # level 1 ask
    assert asks[4]["orders"] == 12  # level 5 ask


def test_mode3_top_of_book_matches_level1():
    on_data(data=_mode3_frame())
    depth = get_live_depth("48864")
    assert depth is not None
    assert depth["best_bid"] == pytest.approx(1499.0)
    assert depth["best_ask"] == pytest.approx(1501.0)
    assert depth["depth_bids"] is not None and len(depth["depth_bids"]) == 5
    assert depth["depth_asks"] is not None and len(depth["depth_asks"]) == 5


def test_get_live_depth_levels_returns_full_snapshot():
    on_data(data=_mode3_frame())
    snap = get_live_depth_levels("48864")
    assert snap is not None
    assert len(snap["bids"]) == 5
    assert len(snap["asks"]) == 5
    # Best bid is first (highest price), best ask is first (lowest price)
    assert snap["bids"][0]["price"] > snap["bids"][4]["price"]
    assert snap["asks"][0]["price"] < snap["asks"][4]["price"]


def test_mode2_leaves_depth_state_untouched():
    """Mode 2 has no best_5_* lists — depth state must stay None, not overwritten."""
    on_data(data=_mode3_frame())
    on_data(data=_mode2_frame())
    with _prices_lock:
        assert live_depth_bids.get("48864") is not None
        assert live_depth_asks.get("48864") is not None
    # get_live_depth still returns the Mode 3 depth (last known)
    depth = get_live_depth("48864")
    assert depth["depth_bids"] is not None


def test_mode2_only_no_depth_state():
    """A token that has ONLY ever seen Mode 2 frames has no depth state."""
    on_data(data=_mode2_frame())
    assert get_live_depth_levels("48864") is None
    depth = get_live_depth("48864")
    assert depth["depth_bids"] is None
    assert depth["depth_asks"] is None


def test_on_close_clears_depth_stores():
    on_data(data=_mode3_frame())
    assert get_live_depth_levels("48864") is not None
    on_close()
    assert get_live_depth_levels("48864") is None


def test_tick_event_includes_depth():
    events = []
    from mjonai.data.angelone.websocket import register_tick_listener, unregister_tick_listener

    def _capture(ev):
        events.append(ev)

    register_tick_listener(_capture)
    try:
        on_data(data=_mode3_frame())
    finally:
        unregister_tick_listener(_capture)

    assert len(events) == 1
    assert events[0]["depth_bids"] is not None and len(events[0]["depth_bids"]) == 5
    assert events[0]["depth_asks"] is not None and len(events[0]["depth_asks"]) == 5


# ── DepthArchive unit tests ─────────────────────────────────────────────────

def _bids(levels=5, base=1499.0):
    return [
        {"price": base - i * 0.05, "quantity": 500 + i * 100, "orders": 3 + i}
        for i in range(levels)
    ]


def _asks(levels=5, base=1501.0):
    return [
        {"price": base + i * 0.05, "quantity": 600 + i * 100, "orders": 4 + i}
        for i in range(levels)
    ]


def test_fingerprint_none_when_both_sides_empty():
    assert _snapshot_fingerprint(None, None) is None
    assert _snapshot_fingerprint([], []) is None


def test_fingerprint_differs_on_price_change():
    fp1 = _snapshot_fingerprint(_bids(), _asks())
    bids2 = _bids()
    bids2[0]["price"] += 0.10
    fp2 = _snapshot_fingerprint(bids2, _asks())
    assert fp1 != fp2


def test_snapshot_to_rows_long_format():
    ts = datetime(2026, 10, 11, 10, 0, 0)
    rows = _snapshot_to_rows(ts, "RELIANCE", _bids(), _asks())
    assert len(rows) == 10  # 5 bids + 5 asks
    assert rows[0]["side"] == "bid"
    assert rows[0]["level"] == 1
    assert rows[5]["side"] == "ask"
    assert rows[5]["level"] == 1
    assert rows[0]["symbol"] == "RELIANCE"


def test_sink_deduplicates_consecutive_identical(tmp_path):
    arch = DepthArchive(root=str(tmp_path), flush_threshold=1000)
    ts = datetime(2026, 10, 11, 10, 0, 0)
    arch.sink_snapshot("RELIANCE", ts, _bids(), _asks())
    arch.sink_snapshot("RELIANCE", ts + timedelta(seconds=1), _bids(), _asks())
    assert arch.pending_count == 1  # second identical snapshot skipped


def test_sink_keeps_changed_snapshot(tmp_path):
    arch = DepthArchive(root=str(tmp_path), flush_threshold=1000)
    ts = datetime(2026, 10, 11, 10, 0, 0)
    arch.sink_snapshot("RELIANCE", ts, _bids(), _asks())
    bids2 = _bids()
    bids2[0]["price"] += 0.05
    arch.sink_snapshot("RELIANCE", ts + timedelta(seconds=1), bids2, _asks())
    assert arch.pending_count == 2


def test_flush_writes_long_format_parquet(tmp_path):
    arch = DepthArchive(root=str(tmp_path), flush_threshold=1000)
    ts = datetime(2026, 10, 11, 10, 0, 0)
    arch.sink_snapshot("RELIANCE", ts, _bids(), _asks())
    arch.flush()

    df = arch.to_dataframe("RELIANCE", day=date(2026, 10, 11))
    assert df is not None
    assert len(df) == 10
    assert list(df.columns) == ["timestamp", "symbol", "side", "level", "price", "quantity", "orders"]
    assert set(df["side"]) == {"bid", "ask"}
    assert sorted(df["level"].unique()) == [1, 2, 3, 4, 5]


def test_flush_appends_across_calls(tmp_path):
    arch = DepthArchive(root=str(tmp_path), flush_threshold=1000)
    ts = datetime(2026, 10, 11, 10, 0, 0)
    arch.sink_snapshot("RELIANCE", ts, _bids(), _asks())
    arch.flush()
    # Change depth so it isn't deduplicated
    bids2 = _bids()
    bids2[0]["price"] += 0.05
    arch.sink_snapshot("RELIANCE", ts + timedelta(seconds=2), bids2, _asks())
    arch.flush()

    df = arch.to_dataframe("RELIANCE", day=date(2026, 10, 11))
    assert len(df) == 20  # two snapshots × 10 rows


def test_to_dataframe_none_when_absent(tmp_path):
    arch = DepthArchive(root=str(tmp_path))
    assert arch.to_dataframe("INFY", day=date(2026, 10, 11)) is None
    assert arch.to_dataframe("INFY") is None


def test_to_dataframe_merges_days(tmp_path):
    arch = DepthArchive(root=str(tmp_path), flush_threshold=1000)
    arch.sink_snapshot("RELIANCE", datetime(2026, 10, 10, 10, 0), _bids(), _asks())
    arch.flush()
    # Different depth on day 2 so it isn't deduplicated
    bids2 = _bids()
    bids2[0]["price"] += 0.05
    arch.sink_snapshot("RELIANCE", datetime(2026, 10, 11, 10, 0), bids2, _asks())
    arch.flush()

    df = arch.to_dataframe("RELIANCE")
    assert len(df) == 20
    assert df["timestamp"].dt.date.nunique() == 2


# ── depth_archive_tick_listener ────────────────────────────────────────────

def test_listener_noop_on_mode2_frame(tmp_path):
    arch = DepthArchive(root=str(tmp_path), flush_threshold=1000)
    listener = depth_archive_tick_listener(
        archive=arch,
        token_to_symbol=lambda t: "RELIANCE" if t == "48864" else None,
    )
    ev = {"token": "48864", "ltp": 1500.0, "depth_bids": None, "depth_asks": None,
          "timestamp": datetime(2026, 10, 11, 10, 0)}
    listener(ev)
    assert arch.pending_count == 0


def test_listener_sinks_mode3_frame(tmp_path):
    arch = DepthArchive(root=str(tmp_path), flush_threshold=1000)
    listener = depth_archive_tick_listener(
        archive=arch,
        token_to_symbol=lambda t: "RELIANCE" if t == "48864" else None,
    )
    ev = {
        "token": "48864", "ltp": 1500.0,
        "depth_bids": _bids(), "depth_asks": _asks(),
        "timestamp": datetime(2026, 10, 11, 10, 0),
    }
    listener(ev)
    assert arch.pending_count == 1


def test_listener_throttle(tmp_path):
    arch = DepthArchive(root=str(tmp_path), flush_threshold=1000)
    listener = depth_archive_tick_listener(
        archive=arch,
        token_to_symbol=lambda t: "RELIANCE",
        min_interval_seconds=5.0,
    )
    ts0 = datetime(2026, 10, 11, 10, 0, 0)
    ev0 = {"token": "1", "depth_bids": _bids(), "depth_asks": _asks(), "timestamp": ts0}
    listener(ev0)
    # Second snapshot 1s later — throttled
    bids2 = _bids(); bids2[0]["price"] += 0.05
    ev1 = {"token": "1", "depth_bids": bids2, "depth_asks": _asks(),
           "timestamp": ts0 + timedelta(seconds=1)}
    listener(ev1)
    assert arch.pending_count == 1  # only first accepted
    # Third snapshot 6s later — past throttle, accepted
    ev2 = {"token": "1", "depth_bids": bids2, "depth_asks": _asks(),
           "timestamp": ts0 + timedelta(seconds=6)}
    listener(ev2)
    assert arch.pending_count == 2


def test_listener_unknown_token_skipped(tmp_path):
    arch = DepthArchive(root=str(tmp_path), flush_threshold=1000)
    listener = depth_archive_tick_listener(
        archive=arch,
        token_to_symbol=lambda t: None,  # no mapping
    )
    ev = {"token": "99999", "depth_bids": _bids(), "depth_asks": _asks(),
          "timestamp": datetime(2026, 10, 11, 10, 0)}
    listener(ev)
    assert arch.pending_count == 0
