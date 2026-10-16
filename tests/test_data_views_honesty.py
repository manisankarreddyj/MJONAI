"""Honesty + hit-rate contract for the interactive-app data views.

Pins the two fixes: build_ai_debates must render REAL recorded agent output (nulls when
absent) and never re-emit the fabricated theses/verdicts/models of the old view; and
build_signal_track_record must compute a direction-adjusted hit-rate (a LONG that rose or
a SHORT that fell counts as a hit), returning null rates — never a fabricated 0% — on no data.
"""
from unittest.mock import patch

import pytest

from apps.web import data_views as dv


@pytest.fixture(autouse=True)
def _clear_track_record_cache():
    """The 300s track-record TTL cache must never leak across tests."""
    dv._TRACK_RECORD_CACHE.clear()
    yield
    dv._TRACK_RECORD_CACHE.clear()

# Strings the OLD fabricated boardroom emitted; none may ever reappear.
_FABRICATED = (
    "DeepSeek-Distill",
    "Claude-3.5",
    "Confluent momentum",
    "Overhead liquidity resistance",
    "comprehensive Devil risk sentry clearance",
)


def test_debates_empty_db_returns_empty_never_fabricates():
    with patch("mjonai.db.repository.get_signals_intelligence_recent", return_value=[]):
        assert dv.build_ai_debates(limit=6) == []


def test_debates_reflect_real_columns_not_defaults():
    row = {
        "id": "s1", "symbol": "INFY", "strategy_id": "S01_MomentumRSI",
        "signal_direction": "LONG", "final_confidence": 71.0,
        "supervisor_decision": "APPROVED", "supervisor_reason": "Clean gates",
        "bull_verdict": "BUY", "bull_confidence": 78.0,
        "bull_key_reasons": ["volume breakout"], "bull_concerns": ["VIX high"],
        "bull_model_used": "RealModel", "was_executed": True,
        "generated_at": "2026-10-01T10:00:00+05:30",
    }
    with patch("mjonai.db.repository.get_signals_intelligence_recent", return_value=[row]):
        out = dv.build_ai_debates(limit=6)[0]
    assert out["bull_agent"]["verdict"] == "BUY"
    assert out["bull_agent"]["confidence"] == 78.0
    assert out["bull_agent"]["model"] == "RealModel"
    assert out["supervisor_cio"]["reason"] == "Clean gates"
    for f in _FABRICATED:
        assert f not in str(out), f"fabricated string leaked: {f}"


def test_debates_missing_reasoning_is_null_not_invented():
    row = {"id": "s2", "symbol": "TCS", "signal_direction": "SHORT"}
    with patch("mjonai.db.repository.get_signals_intelligence_recent", return_value=[row]):
        out = dv.build_ai_debates(limit=6)[0]
    assert out["bull_agent"]["verdict"] is None
    assert out["bull_agent"]["confidence"] is None
    assert out["supervisor_cio"]["reason"] is None
    for f in _FABRICATED:
        assert f not in str(out), f"fabricated string leaked: {f}"


def test_track_record_direction_adjusted():
    rows = [
        {"strategy_id": "S01", "signal_direction": "LONG",  "forward_return_1d": 0.02,  "forward_return_5d": 0.05},
        {"strategy_id": "S01", "signal_direction": "LONG",  "forward_return_1d": -0.01, "forward_return_5d": 0.01},
        {"strategy_id": "S02", "signal_direction": "SHORT", "forward_return_1d": -0.03, "forward_return_5d": 0.02},  # short that fell = hit
    ]
    with patch("mjonai.db.repository.get_signals_for_alphalens", return_value=rows):
        tr = dv.build_signal_track_record(days=90)
    s01 = next(s for s in tr["strategies"] if s["strategy_id"] == "S01")
    assert s01["n"] == 2
    assert s01["hit_rate_1d"] == 0.5            # only 1 of the 2 longs rose
    s02 = next(s for s in tr["strategies"] if s["strategy_id"] == "S02")
    assert s02["hit_rate_1d"] == 1.0           # the short fell → a hit
    assert tr["overall"]["n"] == 3


def test_track_record_no_data_is_null_not_zero():
    with patch("mjonai.db.repository.get_signals_for_alphalens", return_value=[]):
        tr = dv.build_signal_track_record(days=90)
    assert tr["overall"]["n"] == 0
    assert tr["overall"]["hit_rate_1d"] is None
    assert tr["strategies"] == []


def test_track_record_serves_cached_copy_within_ttl():
    """The 300s cache must return the same payload without re-querying."""
    rows = [{"strategy_id": "S01", "signal_direction": "LONG",
             "forward_return_1d": 0.02, "forward_return_5d": 0.05}]
    with patch("mjonai.db.repository.get_signals_for_alphalens",
               return_value=rows) as q:
        first = dv.build_signal_track_record(days=90)
        second = dv.build_signal_track_record(days=90)
    assert q.call_count == 1  # second call served from cache, no rescan
    assert first is second or first == second


def test_track_record_cache_is_per_days():
    with patch("mjonai.db.repository.get_signals_for_alphalens",
               return_value=[]) as q:
        dv.build_signal_track_record(days=30)
        dv.build_signal_track_record(days=90)
    assert q.call_count == 2


def test_open_trades_dead_feed_is_null_not_entry():
    """P0: with no live tick and no history, the row must read null + stale —
    never entry-as-LTP with a fabricated flat P&L (the old chain fell back to
    price_high/low_since_entry, then entry itself)."""
    row = {"symbol": "RELIANCE", "quantity": 10, "entry_price": 2500.0,
           "direction": "LONG", "strategy_id": "S03", "system_mode": "PAPER",
           "price_high_since_entry": 2550.0, "current_sl": 2450.0}
    with patch("mjonai.db.repository.get_open_trades", return_value=[row]), \
         patch("mjonai.data.angelone.historical.fetch_historical_candles",
               side_effect=RuntimeError("offline")):
        out = dv.build_open_trades()[0]
    assert out["current_price"] is None
    assert out["unrealized_pnl"] is None
    assert out["unrealized_pct"] is None
    assert out["stale"] is True
    assert out["price_source"] is None
    assert out["entry_price"] == 2500.0  # entry itself untouched


def test_open_trades_delayed_fallback_is_labeled():
    """A 15m-candle fallback may still price the row, but only labelled
    delayed_15m — never presented as live."""
    import pandas as pd
    # NOTE: symbol must not end in "CE"/"PE" ("RELIANCE" does!) or the builder
    # takes the option-price branch instead of the 15m-candle branch.
    row = {"symbol": "INFY", "quantity": 10, "entry_price": 1500.0,
           "direction": "LONG", "strategy_id": "S03", "system_mode": "PAPER"}
    df = pd.DataFrame({"Close": [1490.0, 1510.0]})
    with patch("mjonai.db.repository.get_open_trades", return_value=[row]), \
         patch("mjonai.data.angelone.historical.fetch_historical_candles",
               return_value=df):
        out = dv.build_open_trades()[0]
    assert out["current_price"] == 1510.0
    assert out["price_source"] == "delayed_15m"
    assert out["stale"] is False
    assert out["unrealized_pnl"] == 100.0


def test_expected_days_band_math():
    """dist÷ATR pace band: raw/1.5 → raw/0.5, 1dp; never fabricates on bad input."""
    assert dv._expected_days_band(100.0, 20.0) == (3.3, 10.0)
    assert dv._expected_days_band(10.0, 50.0) == (0.1, 0.4)
    assert dv._expected_days_band(None, 20.0) == (None, None)
    assert dv._expected_days_band(100.0, None) == (None, None)
    assert dv._expected_days_band(100.0, 0.0) == (None, None)
    assert dv._expected_days_band(0.0, 20.0) == (None, None)
    assert dv._expected_days_band(float("nan"), 20.0) == (None, None)
    assert dv._expected_days_band("junk", 20.0) == (None, None)


def test_holding_window_map_matches_registry():
    """The display window map must mirror strategy/registry min/max — AST-read
    (no strategy import cost), so a registry window change fails here, not in
    the UI silently."""
    import ast
    from pathlib import Path

    reg = Path(__file__).resolve().parent.parent / "mjonai" / "strategy" / "registry"
    found: dict = {}
    for py in reg.glob("*.py"):
        if py.name in ("__init__.py", "base.py", "indicators.py", "quant_math.py"):
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        name, mn, mx = None, None, None
        for node in ast.walk(tree):
            if not isinstance(node, ast.AnnAssign) or not isinstance(node.value, ast.Constant):
                continue
            target = node.target.id if isinstance(node.target, ast.Name) else ""
            if target == "name" and isinstance(node.value.value, str):
                name = node.value.value.split("_")[0]
            elif target == "min_holding_days":
                mn = node.value.value
            elif target == "max_holding_days":
                mx = node.value.value
        if name and name.startswith("S") and mn is not None and mx is not None:
            found[name] = (mn, mx)
    assert found, "no strategy windows parsed — registry layout changed?"
    assert set(found) == set(dv.STRATEGY_HOLDING_WINDOW), (
        f"window-map keys drifted: registry={sorted(found)} map={sorted(dv.STRATEGY_HOLDING_WINDOW)}")
    for sid, window in found.items():
        assert dv.STRATEGY_HOLDING_WINDOW[sid] == window, f"{sid}: map has {dv.STRATEGY_HOLDING_WINDOW[sid]}, registry says {window}"


def _ohlc_frame(n=30, start=1500.0):
    import pandas as pd
    closes = [start + i for i in range(n)]
    return pd.DataFrame({
        "Open": [c - 1 for c in closes],
        "High": [c + 5 for c in closes],
        "Low": [c - 5 for c in closes],
        "Close": closes,
        "Volume": [1000] * n,
    })


def test_open_trades_eta_present_when_levels_and_atr_exist():
    """A swing row with entry + first target + daily bars gets a real ETA band
    and its declared window — the pace estimate is measured, not invented."""
    row = {"symbol": "INFY", "quantity": 10, "entry_price": 1500.0,
           "direction": "LONG", "strategy_id": "S02_MeanReversion",
           "system_mode": "PAPER", "target_1": 1560.0, "current_sl": 1450.0}
    with patch("mjonai.db.repository.get_open_trades", return_value=[row]), \
         patch("mjonai.data.angelone.historical.fetch_historical_candles",
               return_value=_ohlc_frame()):
        out = dv.build_open_trades()[0]
    assert (out["holding_window_min"], out["holding_window_max"]) == (2, 7)
    assert out["expected_days_min"] is not None and out["expected_days_max"] is not None
    assert 0 < out["expected_days_min"] < out["expected_days_max"]
    assert out["eta_basis"] == "dist÷ATR14-daily@0.5–1.5×"


def test_open_trades_eta_null_without_target_or_atr():
    """No target (or no bars) → ETA null with the window still shown; the UI
    renders '—', never a fabricated band."""
    row = {"symbol": "INFY", "quantity": 10, "entry_price": 1500.0,
           "direction": "LONG", "strategy_id": "S02_MeanReversion",
           "system_mode": "PAPER", "current_sl": 1450.0}  # no target_1/target
    with patch("mjonai.db.repository.get_open_trades", return_value=[row]), \
         patch("mjonai.data.angelone.historical.fetch_historical_candles",
               return_value=_ohlc_frame()):
        out = dv.build_open_trades()[0]
    assert out["expected_days_min"] is None and out["expected_days_max"] is None
    assert out["eta_basis"] is None
    assert (out["holding_window_min"], out["holding_window_max"]) == (2, 7)


def test_today_signals_carry_declared_window():
    """Pre-trade signal rows carry the strategy's designed window (no ETA —
    the row has no recorded levels to measure from)."""
    rows = [{"symbol": "TCS", "strategy_id": "S08_IntradayAllDay",
             "signal_direction": "BUY", "final_confidence": 70.0,
             "supervisor_decision": "APPROVED", "generated_at": "2026-10-16T10:00:00+05:30"}]
    with patch("mjonai.db.repository.get_signals_intelligence_today", return_value=rows):
        out = dv.build_today_signals(limit=5)[0]
    assert (out["holding_window_min"], out["holding_window_max"]) == (0, 1)


def _write_snapshot(tmp_path, payload):
    import json
    snap = tmp_path / "time_to_target.json"
    snap.write_text(json.dumps(payload), encoding="utf-8")
    return snap


def test_time_to_target_snapshot_absent_is_not_measured(monkeypatch, tmp_path):
    """No snapshot on disk → measured keys null, never fabricated medians."""
    monkeypatch.setattr(dv, "_TIME_TO_TARGET_PATH", tmp_path / "missing.json")
    assert dv.build_time_to_target()["available"] is False
    row = {"symbol": "INFY", "quantity": 1, "entry_price": 1500.0,
           "direction": "LONG", "strategy_id": "S02_MeanReversion",
           "system_mode": "PAPER", "target_1": 1560.0, "current_sl": 1450.0}
    with patch("mjonai.db.repository.get_open_trades", return_value=[row]), \
         patch("mjonai.data.angelone.historical.fetch_historical_candles",
               return_value=_ohlc_frame()):
        out = dv.build_open_trades()[0]
    assert out["measured_days_median"] is None
    assert out["measured_n_target"] is None
    assert out["expected_days_min"] is not None  # pace ETA is independent


def test_time_to_target_snapshot_enriches_rows(monkeypatch, tmp_path):
    """A present snapshot maps medians onto open rows + signal rows by short id."""
    snap = _write_snapshot(tmp_path, {
        "asof": "2026-10-16T00:00:00", "universe": {}, "window": {},
        "strategies": {
            "S02": {"median_days_to_target": 10.0, "p25_days_to_target": 6.0,
                    "p75_days_to_target": 13.0, "n_target": 25,
                    "insufficient_reason": None},
            "S08": {"median_days_to_target": None, "n_target": 136,
                    "insufficient_reason": "withheld: S08 is INTRADAY-design"},
        },
        "disclosure": "test",
    })
    monkeypatch.setattr(dv, "_TIME_TO_TARGET_PATH", snap)
    assert dv.build_time_to_target()["available"] is True

    row = {"symbol": "INFY", "quantity": 1, "entry_price": 1500.0,
           "direction": "LONG", "strategy_id": "S02_MeanReversion",
           "system_mode": "PAPER", "target_1": 1560.0, "current_sl": 1450.0}
    with patch("mjonai.db.repository.get_open_trades", return_value=[row]), \
         patch("mjonai.data.angelone.historical.fetch_historical_candles",
               return_value=_ohlc_frame()):
        out = dv.build_open_trades()[0]
    assert out["measured_days_median"] == 10.0
    assert out["measured_n_target"] == 25
    assert out["measured_insufficient"] is None

    sigs = [{"symbol": "SBIN", "strategy_id": "S08_IntradayAllDay",
             "signal_direction": "BUY", "final_confidence": 60.0,
             "supervisor_decision": "APPROVED", "generated_at": "2026-10-16T10:00:00+05:30"}]
    with patch("mjonai.db.repository.get_signals_intelligence_today", return_value=sigs):
        sig = dv.build_today_signals(limit=5)[0]
    # Withheld intraday median stays null WITH the reason (UI shows window only).
    assert sig["measured_days_median"] is None
    assert sig["measured_n_target"] == 136
    assert "INTRADAY" in sig["measured_insufficient"]


def test_tearsheet_thin_history_is_unavailable():
    """Fewer than 2 snapshots → available=false, never zero-filled tables."""
    with patch("mjonai.db.repository.get_snapshot_history", return_value=[]):
        assert dv.build_tearsheet(days=30)["available"] is False
    with patch("mjonai.db.repository.get_snapshot_history", return_value=[
            {"snapshot_date": "2026-10-01", "equity": 100000.0}]):
        assert dv.build_tearsheet(days=30)["available"] is False


def test_tearsheet_months_chain_over_snapshots():
    rows = [
        {"snapshot_date": "2026-08-29", "equity": 100000.0},
        {"snapshot_date": "2026-08-31", "equity": 101000.0},
        {"snapshot_date": "2026-09-30", "equity": 102010.0},
    ]
    with patch("mjonai.db.repository.get_snapshot_history", return_value=rows):
        ts = dv.build_tearsheet(days=90)
    assert ts["available"] is True
    assert [(m["y"], m["m"]) for m in ts["months"]] == [(2026, 8), (2026, 9)]
    assert ts["months"][1]["r"] == round(102010.0 / 101000.0 - 1, 4)
    assert ts["drawdowns"] == []  # monotonically up: no episodes, not zeros
