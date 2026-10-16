"""Regression pins for research/analytics/tearsheet.py.

Monthly/annual chaining, partial-period flags, drawdown episodes — all pure
over recorded equity points; thin history yields empties, never zeros.
"""
from mjonai.research.analytics.tearsheet import (
    annual_returns,
    build_tearsheet,
    drawdown_episodes,
    monthly_returns,
)


def _pts(pairs):
    return [(d, e) for d, e in pairs]


def test_monthly_chains_month_end_over_prev():
    pts = _pts([
        ("2026-01-05", 100000.0), ("2026-01-30", 101000.0),
        ("2026-02-27", 102010.0), ("2026-03-31", 99969.8),
    ])
    out = monthly_returns(pts)
    assert [(m["y"], m["m"]) for m in out] == [(2026, 1), (2026, 2), (2026, 3)]
    assert out[0]["partial"] is True
    assert out[0]["r"] == round(101000.0 / 100000.0 - 1, 4)  # base = first point
    assert out[1]["partial"] is False
    assert out[1]["r"] == round(102010.0 / 101000.0 - 1, 4)
    assert out[2]["r"] == round(99969.8 / 102010.0 - 1, 4)


def test_annual_chains_over_prev_year_end():
    pts = _pts([
        ("2024-06-01", 100000.0), ("2024-12-31", 110000.0),
        ("2025-12-31", 121000.0),
    ])
    out = annual_returns(pts)
    assert [a["y"] for a in out] == [2024, 2025]
    assert out[0]["partial"] is True and out[0]["r"] == 0.1
    assert out[1]["partial"] is False and out[1]["r"] == 0.1


def test_drawdown_episodes_top_by_depth():
    pts = _pts([
        ("2026-01-01", 100.0), ("2026-01-02", 110.0),   # peak 110
        ("2026-01-03", 99.0),                            # trough -10%
        ("2026-01-04", 110.0),                           # recovered
        ("2026-01-05", 121.0),                           # peak 121
        ("2026-01-06", 114.95),                          # trough -5%, never regained
    ])
    out = drawdown_episodes(pts, top_n=5)
    assert len(out) == 2
    assert out[0]["depth_pct"] == -10.0
    assert out[0] == {"peak": "2026-01-02", "trough": "2026-01-03",
                      "recovery": "2026-01-04", "depth_pct": -10.0}
    assert out[1]["recovery"] is None  # unrecovered reads null, never a date
    assert out[1]["depth_pct"] == -5.0


def test_thin_history_yields_empties_never_zeros():
    assert monthly_returns([]) == []
    assert monthly_returns([("2026-01-01", 100.0)]) == []
    assert annual_returns([]) == []
    assert drawdown_episodes([("2026-01-01", 100.0)]) == []
    ts = build_tearsheet([("2026-01-01", float("nan"))])
    assert ts["months"] == [] and ts["annual"] == [] and ts["drawdowns"] == []
    assert "partial" in ts["disclosure"] or "First" in ts["disclosure"]


def test_garbage_points_skipped_not_fabricated():
    pts = [("2026-01-05", 100000.0), ("bogus", 5), ("2026-01-30", None),
           ("2026-01-31", 101000.0)]
    out = monthly_returns(pts)
    assert len(out) == 1 and out[0]["r"] == 0.01
