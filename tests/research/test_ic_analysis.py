"""Rank-IC wiring regression tests (2026-09-17).

Covers the real Information Coefficient path that retires the docs' "do not
cite IC before it is built" caveat:
  I1  direction_sign maps LONG/BUY -> +1, SHORT/SELL -> -1, ambiguous -> None.
  I2  adjusted_return_for_horizon signs the forward return and rejects
      ambiguous/non-finite values.
  I3  compute_window_ic computes Spearman IC over direction-adjusted returns
      and floors honestly to ic=None on thin samples.
  I4  compute_ic_report produces per-window + regime-split tables and groups
      missing regimes under UNKNOWN.
  I5  format_ic_report_message renders insufficient cells honestly (never a
      fabricated 0.0).
"""

import pytest

from mjonai.analytics.ic_analysis import (
    MIN_IC_SAMPLES,
    adjusted_return_for_horizon,
    compute_ic_report,
    compute_window_ic,
    direction_sign,
    format_ic_report_message,
    monthly_ic_series,
    realized_directional_move,
)

# A monotonic conf->return relationship MUST yield IC == 1.0 (perfect Spearman).
_PERFECT_SIGNALS = [
    {
        "final_confidence": 90.0,
        "signal_direction": "LONG",
        "signal_type": "BUY",
        "forward_return_1d": 0.05,
        "forward_return_5d": 0.11,
        "forward_return_10d": 0.20,
        "forward_return_20d": 0.30,
    },
    {
        "final_confidence": 60.0,
        "signal_direction": "LONG",
        "signal_type": "BUY",
        "forward_return_1d": 0.02,
        "forward_return_5d": 0.07,
        "forward_return_10d": 0.13,
        "forward_return_20d": 0.22,
    },
    {
        "final_confidence": 40.0,
        "signal_direction": "LONG",
        "signal_type": "BUY",
        "forward_return_1d": -0.01,
        "forward_return_5d": 0.01,
        "forward_return_10d": 0.04,
        "forward_return_20d": 0.10,
    },
    {
        "final_confidence": 25.0,
        "signal_direction": "LONG",
        "signal_type": "BUY",
        "forward_return_1d": -0.04,
        "forward_return_5d": -0.05,
        "forward_return_10d": -0.03,
        "forward_return_20d": 0.01,
    },
    {
        "final_confidence": 10.0,
        "signal_direction": "LONG",
        "signal_type": "BUY",
        "forward_return_1d": -0.10,
        "forward_return_5d": -0.15,
        "forward_return_10d": -0.20,
        "forward_return_20d": -0.30,
    },
]


# ── I1: direction sign ────────────────────────────────────────────────────────

def test_direction_sign_long_buy_positive():
    assert direction_sign({"signal_type": "BUY", "signal_direction": "LONG"}) == 1.0


def test_direction_sign_short_sell_negative():
    assert direction_sign({"signal_type": "SELL", "signal_direction": "SHORT"}) == -1.0
    # direction column wins when type is absent
    assert direction_sign({"signal_type": "BUY", "signal_direction": "SHORT"}) == -1.0


def test_direction_sign_ambiguous_is_none():
    assert direction_sign({"signal_type": "BIDIRECTIONAL"}) is None
    assert direction_sign({}) is None
    assert direction_sign({"signal_direction": "NON_DIRECTIONAL"}) is None


# ── I2: adjusted return per horizon ───────────────────────────────────────────

def test_adjusted_return_horizon_flips_shorts():
    row = {"signal_direction": "SHORT", "signal_type": "SELL", "forward_return_1d": 0.05}
    # Short: price rose +5% against the signal -> -0.05 signed
    assert adjusted_return_for_horizon(row, 1) == -0.05


def test_adjusted_return_horizon_drops_non_finite():
    row = {"signal_direction": "LONG", "forward_return_1d": None}
    assert adjusted_return_for_horizon(row, 1) is None
    row_bad = {"signal_direction": "LONG", "forward_return_1d": float("nan")}
    assert adjusted_return_for_horizon(row_bad, 1) is None


def test_adjusted_return_horizon_ambiguous_direction_none():
    row = {"signal_direction": "BIDIRECTIONAL", "forward_return_1d": 0.05}
    assert adjusted_return_for_horizon(row, 1) is None


# ── I3: per-window IC with honest floor ───────────────────────────────────────

def test_window_ic_perfect_rank_is_1():
    cell = compute_window_ic(_PERFECT_SIGNALS, 1)
    assert cell["sufficient"] is True
    assert cell["n"] == 5
    assert cell["ic"] == 1.0


def test_window_ic_honest_floor_on_thin_sample():
    cell = compute_window_ic(_PERFECT_SIGNALS[:2], 1)
    assert cell["sufficient"] is False
    assert cell["ic"] is None
    assert cell["t_stat"] is None
    assert cell["n"] == 2


def test_window_ic_rejects_missing_return_rows():
    # All rows lack the 20d return -> no usable pairs -> honest floor.
    signals = [dict(s, **{"forward_return_20d": None}) for s in _PERFECT_SIGNALS]
    cell = compute_window_ic(signals, 20)
    assert cell["sufficient"] is False
    assert cell["ic"] is None
    assert cell["n"] == 0


# ── I4: full report per-window + regime split ────────────────────────────────

def test_ic_report_overall_and_regime_split():
    signals = [dict(s) for s in _PERFECT_SIGNALS]
    for i, s in enumerate(signals):
        s["market_state"] = "BULL" if i % 2 == 0 else "BEAR"

    report = compute_ic_report(signals)
    assert report["signal_count"] == 5
    assert report["factor_col"] == "final_confidence"
    assert set(report["overall"].keys()) == {"1", "5", "10", "20"}
    assert report["overall"]["1"]["ic"] == 1.0
    assert set(report["regime_split"].keys()) == {"BULL", "BEAR"}
    # BULL has 3 signed rows, BEAR 2 -> 3 >= 5 floor is not met for windows but
    # the report must still group them (cells may be insufficient honestly).
    assert report["regime_split"]["BULL"]["1"]["n"] == 3
    assert report["regime_split"]["BEAR"]["1"]["sufficient"] is False


def test_ic_report_missing_regime_grouped_unknown():
    signals = [dict(s) for s in _PERFECT_SIGNALS]  # no market_state key
    report = compute_ic_report(signals)
    assert set(report["regime_split"].keys()) == {"UNKNOWN"}
    assert report["regime_split"]["UNKNOWN"]["1"]["ic"] == 1.0


def test_ic_report_empty_signals():
    report = compute_ic_report([])
    assert report["signal_count"] == 0
    assert report["regime_split"] == {}


# ── I5: honest rendering ─────────────────────────────────────────────────────

def test_format_ic_report_message_honest_on_insufficient():
    signals = [dict(s) for s in _PERFECT_SIGNALS[:2]]
    msg = format_ic_report_message(compute_ic_report(signals))
    assert "insufficient" in msg
    assert "IC=0.0" not in msg or "IC=0.0" not in msg.split("insufficient")[0]


def test_format_ic_report_message_perfect_renders_real_ic():
    msg = format_ic_report_message(compute_ic_report(_PERFECT_SIGNALS))
    assert "Weekly IC Report" in msg
    assert "1d: IC=1.0" in msg
    assert "Regime split" in msg


# ── I6: realized_directional_move precedence (longest available window) ──────

def test_realized_directional_move_prefers_longest_window():
    row = {
        "signal_direction": "SHORT",
        "forward_return_1d": 0.01,
        "forward_return_10d": -0.99,  # should NOT win (5d present)
        "forward_return_5d": -0.50,
        "forward_return_20d": None,
    }
    # longest present is 10d -> signed = -1 (SHORT) * (-0.99) = +0.99
    assert realized_directional_move(row) == pytest.approx(0.99)


def test_realized_directional_move_none_when_no_returns():
    assert realized_directional_move({"signal_direction": "LONG"}) is None


# ── I7: Newey-West inference hardening (monthly IC series) ────────────────────

def _stamped(signals, month):
    out = []
    for i, s in enumerate(signals):
        row = dict(s)
        row["generated_at"] = f"{month}-{10 + (i % 18):02d}T10:00:00"
        out.append(row)
    return out


def test_monthly_ic_series_groups_by_signal_month():
    jan = _stamped(_PERFECT_SIGNALS, "2026-01")
    feb = _stamped(_PERFECT_SIGNALS, "2026-02")
    mar = _stamped(_PERFECT_SIGNALS, "2026-03")
    series = monthly_ic_series(jan + feb + mar, 1)
    assert [m["month"] for m in series] == ["2026-01", "2026-02", "2026-03"]
    assert all(m["ic"] == 1.0 and m["n"] == 5 for m in series)


def test_monthly_ic_series_drops_thin_months_and_unstamped_rows():
    jan = _stamped(_PERFECT_SIGNALS, "2026-01")
    thin = _stamped(_PERFECT_SIGNALS[:2], "2026-02")  # 2 < 5 floor
    unstamped = [dict(s) for s in _PERFECT_SIGNALS]  # no timestamp key
    series = monthly_ic_series(jan + thin + unstamped, 1)
    assert [m["month"] for m in series] == ["2026-01"]


def test_window_ic_carries_nw_fields_and_honest_floor():
    # Unstamped fixture: pooled IC intact, monthly leg honestly absent.
    cell = compute_window_ic(_PERFECT_SIGNALS, 1)
    assert cell["n_months"] == 0
    assert cell["ic_monthly_mean"] is None
    assert cell["t_stat_nw"] is None
    # Constant monthly ICs (zero variance) -> NW t undefined, not 0.0-as-signal.
    jan = _stamped(_PERFECT_SIGNALS, "2026-01")
    feb = _stamped(_PERFECT_SIGNALS, "2026-02")
    cell2 = compute_window_ic(jan + feb, 1)
    assert cell2["sufficient"] is True
    assert cell2["n_months"] == 2
    assert cell2["ic_monthly_mean"] == 1.0
    assert cell2["t_stat_nw"] is None


def test_window_ic_nw_t_finite_on_varying_months():
    jan = _stamped(_PERFECT_SIGNALS, "2026-01")
    # Inverted confidence order against the same returns -> Spearman IC -1.
    # (Reversing whole rows would keep pairs matched and stay +1; the
    # confidences themselves must be flipped.)
    inverted = []
    confs = [s["final_confidence"] for s in _PERFECT_SIGNALS]
    for s, c in zip(_PERFECT_SIGNALS, reversed(confs)):
        row = dict(s)
        row["final_confidence"] = c
        inverted.append(row)
    feb = _stamped(inverted, "2026-02")
    mar = _stamped(_PERFECT_SIGNALS, "2026-03")
    assert monthly_ic_series(feb, 1)[0]["ic"] == -1.0
    cell = compute_window_ic(jan + feb + mar, 1)
    assert cell["n_months"] == 3
    assert cell["ic_monthly_mean"] == pytest.approx(1 / 3, abs=1e-4)
    assert cell["t_stat_nw"] is not None and cell["t_stat_nw"] > 0