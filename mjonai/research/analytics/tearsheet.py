"""
Module: mjonai/research/analytics/tearsheet.py
Purpose: fund-tearsheet analytics over the recorded equity curve — monthly
returns, annual returns, and top drawdown episodes.

VISUAL SOURCE (clean-room, no code copied): the Vibe-Trading RunDetail
tearsheet (MonthlyReturnsHeatmap + AnnualReturnsChart + TopDrawdownsPanel over
a MonthlyReturn[]/AnnualReturn[]/DrawdownEpisode[] model built from the equity
series). Re-implemented against our own daily-portfolio-snapshot ledger and
rendered in vendored ECharts + plain HTML tables.

All functions are pure over (date, equity) points, oldest-first. A series
with fewer than 2 finite points yields empty outputs — never fabricated
zeros. The first month/year in the window is flagged partial when history
starts mid-period (its base is the first recorded point, not a true
period-open).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _clean(points: Sequence[Tuple[Any, Any]]) -> List[Tuple[date, float]]:
    """Parse (date-ish, equity) pairs to sorted finite (date, equity) points."""
    from datetime import datetime

    out: List[Tuple[date, float]] = []
    for d, e in points:
        try:
            f = float(e)
        except (TypeError, ValueError):
            continue
        if not (f > 0) or not (f < float("inf")):
            continue
        try:
            dd = d.date() if isinstance(d, datetime) else date.fromisoformat(str(d)[:10])
        except (TypeError, ValueError):
            continue
        out.append((dd, f))
    out.sort(key=lambda p: p[0])
    # One point per day (last wins on duplicates).
    dedup: Dict[date, float] = {}
    for dd, f in out:
        dedup[dd] = f
    return sorted(dedup.items())


def monthly_returns(points: Sequence[Tuple[Any, Any]]) -> List[Dict[str, Any]]:
    """Month-end chained returns: r = month_last / prev_month_last - 1.

    The first month is partial (base = first recorded point) and flagged.
    """
    clean = _clean(points)
    if len(clean) < 2:
        return []
    # Month-end equity per (year, month).
    month_end: Dict[Tuple[int, int], float] = {}
    for dd, f in clean:
        month_end[(dd.year, dd.month)] = f
    keys = sorted(month_end)
    out: List[Dict[str, Any]] = []
    for i, (y, m) in enumerate(keys):
        if i == 0:
            base = clean[0][1]
            partial = True
        else:
            base = month_end[keys[i - 1]]
            partial = False
        last = month_end[(y, m)]
        r = (last / base - 1.0) if base > 0 else None
        out.append({"y": y, "m": m,
                    "r": None if r is None else round(r, 4),
                    "partial": partial})
    return out


def annual_returns(points: Sequence[Tuple[Any, Any]]) -> List[Dict[str, Any]]:
    """Year-end chained returns, same partial-first-period contract."""
    clean = _clean(points)
    if len(clean) < 2:
        return []
    year_end: Dict[int, float] = {}
    for dd, f in clean:
        year_end[dd.year] = f
    years = sorted(year_end)
    out: List[Dict[str, Any]] = []
    for i, y in enumerate(years):
        if i == 0:
            base = clean[0][1]
            partial = True
        else:
            base = year_end[years[i - 1]]
            partial = False
        last = year_end[y]
        r = (last / base - 1.0) if base > 0 else None
        out.append({"y": y, "r": None if r is None else round(r, 4),
                    "partial": partial})
    return out


def drawdown_episodes(
    points: Sequence[Tuple[Any, Any]],
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """Top-N drawdown episodes by depth: peak/trough/recovery dates + depth %.

    An episode runs from a new equity peak through its trough to the first bar
    that regains the peak (recovery=None when never regained in-sample).
    """
    clean = _clean(points)
    if len(clean) < 2:
        return []
    episodes: List[Dict[str, Any]] = []
    peak = clean[0][1]
    peak_day = clean[0][0]
    trough = peak
    trough_day = peak_day
    in_dd = False
    for dd, f in clean[1:]:
        if f >= peak:
            if in_dd:
                episodes.append((peak_day, trough_day, dd,
                                 (trough / peak - 1.0) if peak > 0 else 0.0))
                in_dd = False
            peak, peak_day = f, dd
            trough, trough_day = f, dd
        elif f < trough:
            trough, trough_day = f, dd
            in_dd = True
    if in_dd:
        episodes.append((peak_day, trough_day, None,
                         (trough / peak - 1.0) if peak > 0 else 0.0))
    episodes.sort(key=lambda e: e[3])
    return [{
        "peak": p.isoformat(), "trough": t.isoformat(),
        "recovery": (r.isoformat() if r else None),
        "depth_pct": round(d * 100.0, 2),
    } for p, t, r, d in episodes[:max(0, top_n)]]


def build_tearsheet(
    points: Sequence[Tuple[Any, Any]],
    top_n: int = 5,
) -> Dict[str, Any]:
    """Full tearsheet payload (months + annual + drawdowns + disclosure)."""
    return {
        "months": monthly_returns(points),
        "annual": annual_returns(points),
        "drawdowns": drawdown_episodes(points, top_n=top_n),
        "disclosure": (
            "Fund-tearsheet analytics over the recorded equity curve. First "
            "month/year is partial when history starts mid-period; an "
            "unrecovered drawdown reads recovery=null, never a guessed date."
        ),
    }
