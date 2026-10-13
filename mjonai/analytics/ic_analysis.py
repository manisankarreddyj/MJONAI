"""
Module: analytics/ic_analysis.py

Purpose: Real rank information-coefficient (IC) analysis over stored forward
returns — the wiring that retires the docs' "IC analysis does not exist; do
not cite IC before it is built" caveat (2026-09-17).

What it computes (all from signal_intelligence_log forward returns, never
fetched on demand):
  * Per-window Spearman rank IC: Spearman(final_confidence, direction-adjusted
    forward return) for each horizon [1, 5, 10, 20] trading days.
  * Regime-split IC: the same per-window IC grouped by the signal's
    MARKET_STATE (the honestly-populated regime column; `market_regime` is
    schema-null and is deliberately NOT used — a regime split on an empty
    column would be fiction).
  * Honest floors: a window/regime cell with fewer than MIN_SAMPLES
    jointly-finite pairs is reported insufficient (ic=None), never a
    fabricated 0.0.

Direction adjustment: stored forward returns are raw price moves. A short
signal wins when price falls, so IC uses sign(direction) * return: +1 for
LONG/BUY, -1 for SHORT/SELL. Signals without a clean directional tag
(BIDIRECTIONAL / NON_DIRECTIONAL / unknown) are excluded from the directional
sample — signed returns are meaningless for them.

The same masking + floor logic protects the agent weight-log IC in the
learning loop: aligned forward returns now reach `calculate_information_coefficient`
instead of leaving rank-IC 0.0/NULL in `agent_weight_log`.
"""

from collections import defaultdict
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from mjonai.analytics.feedback_learning import (
    calculate_information_coefficient,
    newey_west_t_stat,
)

MIN_IC_SAMPLES = 5          # joint-finite pairs below this floor -> ic=None
DEFAULT_WINDOWS = (1, 5, 10, 20)
DEFAULT_FACTOR_COL = "final_confidence"
DEFAULT_REGIME_COL = "market_state"
_MAX_FETCH_BATCH = 100


def direction_sign(signal: Dict[str, Any]) -> Optional[float]:
    """Return +1 / -1 directional sign for a signal row, None if ambiguous.

    Uses `signal_type` first (BUY/SELL), falling back to `signal_direction`
    (LONG/SHORT). Non-directional rows yield None and are excluded from
    signed-return analysis.
    """
    sig_type = str(signal.get("signal_type") or "").upper()
    sig_dir = str(signal.get("signal_direction") or "").upper()
    if sig_type == "SELL" or sig_dir == "SHORT":
        return -1.0
    if sig_type == "BUY" or sig_dir == "LONG":
        return 1.0
    return None


def _finite(value: Any) -> Optional[float]:
    """Coerce a value to a finite float, or None for missing/non-finite."""
    if isinstance(value, (int, float)):
        f = float(value)
        return f if math.isfinite(f) else None
    return None


def adjusted_return_for_horizon(
    signal: Dict[str, Any], horizon_days: int
) -> Optional[float]:
    """Direction-signed forward return for a signal at ``horizon_days``.

    LONG/BUY -> +return, SHORT/SELL -> -return, ambiguous/non-finite -> None.
    """
    sign = direction_sign(signal)
    if sign is None:
        return None
    raw = _finite(signal.get(f"forward_return_{horizon_days}d"))
    if raw is None:
        return None
    return sign * raw


def _signal_month(signal: Dict[str, Any]) -> Optional[str]:
    """YYYY-MM month of a signal row, or None when no parseable timestamp.

    Reads ``generated_at`` then ``created_at`` (ISO strings or datetimes).
    Unparseable/missing stamps are skipped by the monthly series — the pooled
    IC still counts the row, so no data is lost, only the month attribution.
    """
    from datetime import datetime as _dt

    for key in ("generated_at", "created_at"):
        raw = signal.get(key)
        if raw is None:
            continue
        try:
            if isinstance(raw, _dt):
                stamp = raw
            else:
                stamp = _dt.fromisoformat(str(raw).strip().replace("Z", "+00:00"))
            return f"{stamp.year:04d}-{stamp.month:02d}"
        except (TypeError, ValueError):
            continue
    return None


def monthly_ic_series(
    signals: Sequence[Dict[str, Any]],
    horizon_days: int,
    factor_col: str = DEFAULT_FACTOR_COL,
    min_month_samples: int = MIN_IC_SAMPLES,
) -> List[Dict[str, Any]]:
    """Per-month Spearman IC series for Newey-West inference hardening.

    Groups jointly-finite (factor, signed-return) pairs by signal month and
    computes one IC per month with the same floor as the pooled cell: months
    below ``min_month_samples`` pairs are dropped, never fabricated. Returns
    [{month, ic, n}] sorted chronologically — the input to ``newey_west_t_stat``.
    """
    from collections import defaultdict as _dd

    buckets: Dict[str, List[Tuple[float, float]]] = _dd(list)
    for row in signals:
        month = _signal_month(row)
        if month is None:
            continue
        ret = adjusted_return_for_horizon(row, horizon_days)
        if ret is None:
            continue
        f = _finite(row.get(factor_col))
        if f is None:
            continue
        buckets[month].append((f, ret))

    series = []
    for month in sorted(buckets):
        pairs = buckets[month]
        if len(pairs) < min_month_samples:
            continue
        factors = [p[0] for p in pairs]
        returns = [p[1] for p in pairs]
        ic, _t = calculate_information_coefficient(factors, returns)
        series.append({"month": month, "ic": ic, "n": len(pairs)})
    return series


def ic_autocorrelation(
    monthly_ics: Sequence[float],
    lag: int = 1,
) -> Optional[float]:
    """Autocorrelation of a monthly IC series (factor-stability diagnostic).

    Clean-room analog of alphalens' `factor_rank_autocorrelation`: where they
    correlate per-asset factor ranks across periods (turnover), we correlate
    our per-month IC values with themselves at `lag` — it answers "does last
    month's edge predict this month's", i.e. WHEN the Newey-West correction
    matters. Non-finite entries are dropped; fewer than 3 finite values or a
    zero-variance series returns None (an autocorrelation on a flat line is
    undefined, never a fabricated 0.0).
    """
    xs = [float(v) for v in monthly_ics if isinstance(v, (int, float)) and math.isfinite(float(v))]
    lag = max(1, int(lag))
    if len(xs) <= lag + 1:
        return None
    a = xs[:-lag]
    b = xs[lag:]
    mean_a = sum(a) / len(a)
    mean_b = sum(b) / len(b)
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b)) / len(a)
    var_a = sum((x - mean_a) ** 2 for x in a) / len(a)
    var_b = sum((y - mean_b) ** 2 for y in b) / len(b)
    if var_a <= 0.0 or var_b <= 0.0:
        return None
    corr = cov / math.sqrt(var_a * var_b)
    if not math.isfinite(corr):
        return None
    return round(max(-1.0, min(1.0, corr)), 4)


def realized_directional_move(
    signal: Dict[str, Any], windows: Sequence[int] = DEFAULT_WINDOWS
) -> Optional[float]:
    """Longest available direction-adjusted return for a signal row.

    Preference order 20d > 10d > 5d > 1d — the most mature realized window any
    signal has reached. Used by the learning loop to align agent confidence
    with a realized outcome that is a signed price move.
    """
    for w in sorted(windows, reverse=True):
        value = adjusted_return_for_horizon(signal, w)
        if value is not None:
            return value
    return None


def compute_window_ic(
    signals: Sequence[Dict[str, Any]],
    horizon_days: int,
    min_samples: int = MIN_IC_SAMPLES,
    factor_col: str = DEFAULT_FACTOR_COL,
) -> Dict[str, Any]:
    """Spearman rank IC for one horizon over direction-adjusted returns.

    Returns a cell dict: {horizon_days, n, ic, t_stat, sufficient}. When fewer
    than ``min_samples`` jointly-finite (factor, signed-return) pairs survive,
    ``ic``/``t_stat`` are None and ``sufficient`` is False — an honest floor,
    never a fabricated 0.0.
    """
    factors: List[float] = []
    returns: List[float] = []
    for row in signals:
        ret = adjusted_return_for_horizon(row, horizon_days)
        if ret is None:
            continue
        f = _finite(row.get(factor_col))
        if f is None:
            continue
        factors.append(f)
        returns.append(ret)

    n = len(factors)
    if n < min_samples:
        return {
            "horizon_days": int(horizon_days),
            "n": n,
            "ic": None,
            "t_stat": None,
            "sufficient": False,
            "n_months": 0,
            "ic_monthly_mean": None,
            "t_stat_nw": None,
            "ic_autocorr_lag1": None,
        }

    ic, t_stat = calculate_information_coefficient(factors, returns)
    monthly = monthly_ic_series(signals, horizon_days, factor_col=factor_col)
    monthly_vals = [m["ic"] for m in monthly]
    t_nw = (
        newey_west_t_stat(monthly_vals)
        if len(monthly) >= 2
        else None
    )
    return {
        "horizon_days": int(horizon_days),
        "n": n,
        "ic": ic,
        "t_stat": t_stat,
        "sufficient": True,
        "n_months": len(monthly),
        "ic_monthly_mean": (
            round(sum(monthly_vals) / len(monthly), 4)
            if monthly
            else None
        ),
        "t_stat_nw": t_nw,
        "ic_autocorr_lag1": ic_autocorrelation(monthly_vals),
    }


def _window_table(
    signals: Sequence[Dict[str, Any]],
    windows: Sequence[int],
    min_samples: int,
    factor_col: str,
) -> Dict[str, Any]:
    return {
        str(w): compute_window_ic(signals, w, min_samples=min_samples, factor_col=factor_col)
        for w in windows
    }


def compute_ic_report(
    signals: Sequence[Dict[str, Any]],
    windows: Sequence[int] = DEFAULT_WINDOWS,
    min_samples: int = MIN_IC_SAMPLES,
    factor_col: str = DEFAULT_FACTOR_COL,
    regime_col: str = DEFAULT_REGIME_COL,
) -> Dict[str, Any]:
    """Full per-window + regime-split IC report over stored forward returns.

    Structure:
        {
          windows, min_samples, factor_col, regime_col, signal_count,
          overall:   {horizon: window-cell, ...},
          regime_split: {MARKET_STATE: {horizon: window-cell, ...}, ...},
        }
    Regime groups are keyed by the values actually present in ``regime_col``
    (upper-cased); empty/missing regime rows are grouped under "UNKNOWN".
    """
    by_regime: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in signals:
        reg = str(row.get(regime_col) or "").upper().strip()
        by_regime[reg if reg else "UNKNOWN"].append(row)

    return {
        "windows": [int(w) for w in windows],
        "min_samples": int(min_samples),
        "factor_col": str(factor_col),
        "regime_col": str(regime_col),
        "signal_count": len(signals),
        "overall": _window_table(signals, windows, min_samples, factor_col),
        "regime_split": {
            reg: _window_table(sub, windows, min_samples, factor_col)
            for reg, sub in sorted(by_regime.items())
        },
    }


def format_ic_report_message(report: Dict[str, Any]) -> str:
    """Compact Telegram-ready rendering of an IC report (honest by default).

    Windows where the sample is insufficient render as "insufficient (n=N)",
    never as a fake 0.0. Regimes with no sufficient cell are collapsed to a
    single line so a near-empty week stays readable.
    """
    lines: List[str] = []
    lines.append("🔬 <b>MJONAI Weekly IC Report</b>")
    lines.append(f"Signals with forward returns: {report.get('signal_count', 0)}")
    lines.append(f"Factor: {report.get('factor_col', DEFAULT_FACTOR_COL)} "
                 f"· Floor: ≥{report.get('min_samples', MIN_IC_SAMPLES)} samples")
    lines.append("")

    lines.append("<b>Overall (per window):</b>")
    for horizon, cell in sorted(
        report.get("overall", {}).items(), key=lambda kv: int(kv[0])
    ):
        lines.append(_render_cell(horizon, cell))

    lines.append("")
    lines.append("<b>Regime split:</b>")
    regime_split = report.get("regime_split", {})
    if not regime_split:
        lines.append("  • no regime-tagged signals")
        return "\n".join(lines)

    shown_regimes = 0
    for reg in sorted(regime_split):
        cells = regime_split[reg]
        sufficient = [c for c in cells.values() if c.get("sufficient")]
        if not sufficient:
            n = max(c.get("n", 0) for c in cells.values())
            lines.append(f"  • {reg}: insufficient sample (n={n})")
            continue
        shown_regimes += 1
        lines.append(f"  • {reg}:")
        for horizon, cell in sorted(cells.items(), key=lambda kv: int(kv[0])):
            lines.append(f"      " + _render_cell(horizon, cell))

    if shown_regimes == 0:
        lines.append("  (no regime had a sufficient sample this week)")
    return "\n".join(lines)


def _render_cell(horizon: str, cell: Dict[str, Any]) -> str:
    label = f"{horizon}d"
    n = cell.get("n", 0)
    if not cell.get("sufficient"):
        return f"  • {label}: insufficient (n={n})"
    ic = cell.get("ic")
    t = cell.get("t_stat")
    base = f"  • {label}: IC={ic} (t={t}, n={n})"
    t_nw = cell.get("t_stat_nw")
    n_months = cell.get("n_months", 0)
    if t_nw is not None and n_months and n_months >= 2:
        base += f" · NW t={t_nw} (M={n_months})"
    return base