"""Learning-loop regression tests (P1.1 Session A, 2026-09-14).

Covers the three caller-side defects and the re-wired forward-returns path:
  A1  pipeline reads the REAL pattern-memory column (laplace_win_rate).
  A2  trade close passes actual_rr to outcome writers.
  A3  get_latest_weights defaults are the boardroom-trimmed agent set.
  A4  forward returns compute from stored entry_price / signal-date close
      and land in the right DB fields (incl. honest skip on missing data).
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from mjonai.execution.orders import close_paper_trade
from mjonai.research.forward_returns import compute_forward_returns
from mjonai.strategy.pipeline import _pattern_expectancy_score


# ── A1: pattern-memory column alignment ───────────────────────────────────────

def test_pattern_expectancy_reads_real_laplace_column():
    record = {
        "setup_hash": "TESTHASH",
        "is_quarantined": False,
        "occurrences": 5,
        "laplace_win_rate": 62.5,   # the REAL schema field
        "laplace_win_rate_pct": None,  # the stale name is empty -> must NOT be read
    }
    with patch("mjonai.db.patterns.get_pattern", return_value=record):
        score = _pattern_expectancy_score(
            strategy_result={"setup_hash": "TESTHASH"},
            symbol="RELIANCE",
            market_state="TRENDING",
            vix=15.0,
            system_mode="PAPER",
        )
    assert score == 62.5


def test_pattern_expectancy_ignores_stale_column_only():
    # If only the stale column exists, no memory is returned (None) rather
    # than a fabricated 0.0 / value — honest-exclusion semantics (H3).
    record = {
        "setup_hash": "TESTHASH",
        "is_quarantined": False,
        "occurrences": 4,
        "laplace_win_rate_pct": 99.9,
    }
    with patch("mjonai.db.patterns.get_pattern", return_value=record):
        score = _pattern_expectancy_score(
            strategy_result={"setup_hash": "TESTHASH"},
            symbol="RELIANCE",
            market_state="TRENDING",
            vix=15.0,
            system_mode="PAPER",
        )
    assert score is None


# ── A2: actual_rr threaded through trade close ────────────────────────────────

def _make_open_long_trade(with_stop=True):
    trade = {
        "id": "777",
        "symbol": "RELIANCE",
        "entry_price": 100.0,
        "quantity": 10,
        "quantity_remaining": 10,
        "side": "BUY",
        "signal_id": "sig-1",
        "setup_hash": "TESTHASH",
        "system_mode": "PAPER",
        "total_cost": 0.0,
        "stop_loss": 90.0 if with_stop else None,
    }
    return trade


def test_close_passes_actual_rr_to_all_outcome_writers():
    trade = _make_open_long_trade()
    calls = {}

    def _capture_signal(**kwargs):
        calls["signal"] = kwargs

    def _capture_agent(**kwargs):
        calls["agent"] = kwargs

    def _capture_pattern(**kwargs):
        calls["pattern"] = kwargs

    with (
        patch("mjonai.db.repository.get_open_trades", return_value=[trade]),
        patch("mjonai.execution.orders.close_trade", return_value=True),
        patch("mjonai.execution.orders.get_closed_tranche_pnl", return_value={}),
        patch("mjonai.execution.orders.update_signal_outcome", side_effect=_capture_signal),
        patch("mjonai.execution.orders.update_agent_log_outcome", side_effect=_capture_agent),
        patch("mjonai.execution.orders.update_pattern_outcome", side_effect=_capture_pattern),
    ):
        result = close_paper_trade(trade_id="777", exit_price=120.0, exit_reason="TARGET", holding_days=2)

    assert result is not None
    # LONG: entry 100, SL 90 → risk 10; exit 120 → R-multiple = 20/10 = 2.0
    assert calls["signal"]["actual_rr"] == 2.0
    assert calls["signal"]["actual_pnl_gross"] == 200.0
    assert calls["agent"]["actual_rr"] == 2.0
    assert calls["pattern"]["actual_rr"] == 2.0


def test_close_without_stop_passes_none_actual_rr():
    trade = _make_open_long_trade(with_stop=False)
    calls = {}

    def _capture_signal(**kwargs):
        calls["signal"] = kwargs

    with (
        patch("mjonai.db.repository.get_open_trades", return_value=[trade]),
        patch("mjonai.execution.orders.close_trade", return_value=True),
        patch("mjonai.execution.orders.get_closed_tranche_pnl", return_value={}),
        patch("mjonai.execution.orders.update_signal_outcome", side_effect=_capture_signal),
        patch("mjonai.execution.orders.update_agent_log_outcome", return_value=True),
        patch("mjonai.execution.orders.update_pattern_outcome", return_value=True),
    ):
        result = close_paper_trade(trade_id="777", exit_price=120.0, exit_reason="TARGET", holding_days=2)

    assert result is not None
    # No stop loss known → no fabricated risk basis; NULL into the schema.
    assert calls["signal"].get("actual_rr") is None


def test_close_short_rr_direction():
    trade = _make_open_long_trade()
    trade["side"] = "SELL"
    trade["stop_loss"] = 110.0   # short: stop ABOVE entry (100)
    calls = {}

    def _capture_pattern(**kwargs):
        calls["pattern"] = kwargs

    with (
        patch("mjonai.db.repository.get_open_trades", return_value=[trade]),
        patch("mjonai.execution.orders.close_trade", return_value=True),
        patch("mjonai.execution.orders.get_closed_tranche_pnl", return_value={}),
        patch("mjonai.execution.orders.update_signal_outcome", return_value=True),
        patch("mjonai.execution.orders.update_agent_log_outcome", return_value=True),
        patch("mjonai.execution.orders.update_pattern_outcome", side_effect=_capture_pattern),
    ):
        result = close_paper_trade(trade_id="777", exit_price=90.0, exit_reason="STOP", holding_days=2)

    assert result is not None
    # SHORT: entry 100, SL 110 → risk 10; exit 90 → R = 10/10 = 1.0 (loss)
    assert calls["pattern"]["actual_rr"] == 1.0


# ── A3: boardroom-trimmed weight defaults ─────────────────────────────────────

def test_get_latest_weights_defaults_are_trimmed_board():
    from mjonai.db.system import get_latest_weights

    with patch("mjonai.db.system._execute_with_retry", side_effect=RuntimeError("offline")):
        weights = get_latest_weights(system_mode="PAPER")

    assert set(weights.keys()) == {"BULL", "BEAR", "SUPERVISOR"}
    assert weights == {"BULL": 1.0, "BEAR": 1.0, "SUPERVISOR": 1.0}


# ── A4: forward-returns computation ───────────────────────────────────────────

def _close_series(days=35, base=100.0, start=None):
    start = start or datetime(2026, 6, 1)
    index = [start + timedelta(days=i) for i in range(days)]
    return pd.Series([base + i for i in range(days)], index=pd.DatetimeIndex(index))


def test_forward_returns_uses_stored_entry_price():
    series = _close_series(days=30, base=100.0)
    signals = [
        {
            "id": "s1",
            "symbol": "RELIANCE",
            "generated_at": "2026-06-05T10:00:00+05:30",
            "entry_price": 100.0,   # stored proposed entry (no hindsight)
        }
    ]
    updated = {}

    with (
        patch("mjonai.research.forward_returns.get_signals_needing_forward_returns", return_value=signals),
        patch("mjonai.research.forward_returns._fetch_close_series", return_value=series),
        patch("mjonai.research.forward_returns.update_signal_forward_returns",
              side_effect=lambda sid, returns: updated.update({sid: returns})),
    ):
        stats = compute_forward_returns()

    assert stats["signals_processed"] == 1
    assert stats["signals_updated"] == 1
    assert stats["errors"] == 0
    payload = updated["s1"]
    # Entry idx = first at-or-after Jun 5 → idx 4 (price 104); +1d → 105.
    assert payload["forward_return_1d"] == pytest.approx(round((105.0 - 100.0) / 100.0, 6), rel=1e-9)
    assert payload["forward_return_5d"] == pytest.approx(round((109.0 - 100.0) / 100.0, 6), rel=1e-9)


def test_forward_returns_falls_back_to_signal_date_close():
    series = _close_series(days=30, base=100.0)
    signals = [
        {
            "id": "s2",
            "symbol": "TCS",
            "generated_at": "2026-06-05T10:00:00+05:30",
            "entry_price": None,   # no stored price → signal-date close 104
        }
    ]
    updated = {}

    with (
        patch("mjonai.research.forward_returns.get_signals_needing_forward_returns", return_value=signals),
        patch("mjonai.research.forward_returns._fetch_close_series", return_value=series),
        patch("mjonai.research.forward_returns.update_signal_forward_returns",
              side_effect=lambda sid, returns: updated.update({sid: returns})),
    ):
        stats = compute_forward_returns()

    assert stats["signals_updated"] == 1
    payload = updated["s2"]
    # entry=104 (close idx 4); +1d close 105 → ≈0.00962 (emitter rounds to 6dp)
    assert payload["forward_return_1d"] == pytest.approx(round((105.0 - 104.0) / 104.0, 6), rel=1e-9)


def test_forward_returns_skips_missing_generated_at():
    series = _close_series(days=30, base=100.0)
    signals = [{"id": "s3", "symbol": "INFY", "generated_at": None, "entry_price": 100.0}]
    updated = {}

    with (
        patch("mjonai.research.forward_returns.get_signals_needing_forward_returns", return_value=signals),
        patch("mjonai.research.forward_returns._fetch_close_series", return_value=series),
        patch("mjonai.research.forward_returns.update_signal_forward_returns",
              side_effect=lambda sid, returns: updated.update({sid: returns})),
    ):
        stats = compute_forward_returns()

    assert stats["signals_skipped"] == 1
    assert stats["signals_updated"] == 0
    assert updated == {}


def test_forward_returns_handles_empty_price_data():
    signals = [{"id": "s4", "symbol": "GARBAGE", "generated_at": "2026-06-05T10:00:00+05:30"}]
    with (
        patch("mjonai.research.forward_returns.get_signals_needing_forward_returns", return_value=signals),
        patch("mjonai.research.forward_returns._fetch_close_series", return_value=pd.Series(dtype=float)),
        patch("mjonai.research.forward_returns.update_signal_forward_returns", return_value=True),
    ):
        stats = compute_forward_returns()

    # Insufficient data — the failed symbol's signals ride the error bucket, no crash.
    assert stats["errors"] == 1
    assert stats["signals_updated"] == 0


def test_forward_returns_partial_window_keeps_nulls_for_missing():
    # 10 trading days (idx 0..9): +1d/+5d exist; +10d/+20d fall past the end → NULL.
    series = _close_series(days=10, base=100.0)
    signals = [
        {
            "id": "s5",
            "symbol": "RELIANCE",
            "generated_at": "2026-06-01T10:00:00+05:30",
            "entry_price": 100.0,   # stored entry; first at-or-after Jun 1 → idx 0 → 100
        }
    ]
    updated = {}

    with (
        patch("mjonai.research.forward_returns.get_signals_needing_forward_returns", return_value=signals),
        patch("mjonai.research.forward_returns._fetch_close_series", return_value=series),
        patch("mjonai.research.forward_returns.update_signal_forward_returns",
              side_effect=lambda sid, returns: updated.update({sid: returns})),
    ):
        stats = compute_forward_returns()

    assert stats["signals_updated"] == 1
    payload = updated["s5"]
    # entry idx 0 (price 100); +1d → idx1 (101) exists; +5d → idx5 (105) exists;
    # +10d/+20d → past index → NULL.
    assert payload["forward_return_1d"] is not None
    assert payload["forward_return_5d"] is not None
    assert payload["forward_return_10d"] is None
    assert payload["forward_return_20d"] is None


# ── A5: Yahoo identity resolution (index/commodity aliases) ───────────────────

def _mock_dl_frame():
    idx = [datetime(2026, 6, 1) + timedelta(days=i) for i in range(30)]
    return pd.DataFrame({"Close": [100.0 + i for i in range(30)]}, index=pd.DatetimeIndex(idx))


def test_yahoo_identity_index_aliases():
    from mjonai.research.forward_returns import _fetch_close_series, _resolve_yahoo_symbol

    assert _resolve_yahoo_symbol("NIFTY") == "^NSEI"
    assert _resolve_yahoo_symbol("BANKNIFTY") == "^NSEBANK"
    assert _resolve_yahoo_symbol("TATAMOTORS") == "TMPV.NS"
    assert _resolve_yahoo_symbol("RELIANCE") == "RELIANCE.NS"
    assert _resolve_yahoo_symbol("CRUDEOIL") is None
    assert _resolve_yahoo_symbol("") is None

    with patch("yfinance.download", return_value=_mock_dl_frame()) as dl:
        series = _fetch_close_series("NIFTY")
    dl.assert_called_once()
    assert dl.call_args[0][0] == "^NSEI"  # no more BANKNIFTY.NS-style 404s
    assert len(series) == 30


def test_yahoo_identity_unmappable_skips_quietly():
    from mjonai.research.forward_returns import _fetch_close_series

    with patch("yfinance.download") as dl:
        series = _fetch_close_series("CRUDEOIL")
    dl.assert_not_called()  # expected absence, not a failure
    assert series.empty


def test_unmappable_symbols_count_skipped_not_errors():
    series = _close_series(days=30, base=100.0)
    signals = [_sig("m1", sym="CRUDEOIL")]
    with (
        patch("mjonai.research.forward_returns.get_signals_needing_forward_returns",
              return_value=signals),
        patch("mjonai.research.forward_returns._fetch_close_series", return_value=series),
        patch("mjonai.research.forward_returns.update_signal_forward_returns",
              return_value=True),
    ):
        stats = compute_forward_returns()
    assert stats["signals_skipped"] == 1
    assert stats["errors"] == 0
    assert stats["signals_updated"] == 0


# ── A6: backlog drain loop ────────────────────────────────────────────────────

def _sig(sid, sym="RELIANCE"):
    return {"id": sid, "symbol": sym,
            "generated_at": "2026-06-05T10:00:00+05:30", "entry_price": 100.0}


def test_drain_loop_processes_multiple_batches():
    series = _close_series(days=30, base=100.0)
    batches = [[_sig("a1"), _sig("a2")], [_sig("a3")]]  # full then short → stop
    with (
        patch("mjonai.research.forward_returns.get_signals_needing_forward_returns",
              side_effect=batches) as get_batch,
        patch("mjonai.research.forward_returns._fetch_close_series", return_value=series),
        patch("mjonai.research.forward_returns.update_signal_forward_returns",
              return_value=True),
    ):
        stats = compute_forward_returns(limit=2)

    assert get_batch.call_count == 2
    assert stats["signals_processed"] == 3
    assert stats["signals_updated"] == 3
    assert stats["errors"] == 0


def test_drain_loop_runaway_guard_caps_batches():
    series = _close_series(days=30, base=100.0)
    import mjonai.research.forward_returns as fr

    with (
        patch.object(fr, "get_signals_needing_forward_returns",
                     return_value=[_sig("x")]) as get_batch,
        patch.object(fr, "_fetch_close_series", return_value=series),
        patch.object(fr, "update_signal_forward_returns", return_value=True),
    ):
        stats = compute_forward_returns(limit=1)  # every batch "full" → guard stops

    assert get_batch.call_count == fr._MAX_DRAIN_BATCHES
    assert stats["signals_processed"] == fr._MAX_DRAIN_BATCHES