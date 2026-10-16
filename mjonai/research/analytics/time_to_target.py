"""
Module: mjonai/research/analytics/time_to_target.py
Purpose: measured time-to-target statistics over research backtest trades.

For one strategy's pooled TradeResults (the triple-barrier outcome of the
standardized research exits — dynamic 2×ATR stop, 2R target, max-holding-bars
vertical barrier), summarize how long TARGET exits actually took:
median / p25 / p75 of holding_bars among TARGET exits, plus the target-hit
rate and the full exit-reason mix.

A median is PUBLISHED only when at least `min_target_hits` TARGET exits back
it — below the floor the row reads "insufficient", never a number dressed as
measurement. (The floor is descriptive-honesty, not the WFE ≥30 robustness
bar: these medians describe past travel times, they do not certify an edge.)

Direction-agnostic by construction: LONG and SHORT trades pool together —
holding_bars measures bars held either way.
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional, Sequence


def _pct(sorted_vals: Sequence[float], pct: float) -> Optional[float]:
    """Linear-interpolated percentile over pre-sorted values (no numpy dep)."""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    rank = (len(sorted_vals) - 1) * (pct / 100.0)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = rank - lo
    return float(sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac)


def summarize_time_to_target(
    trades: Sequence[Any],
    *,
    min_target_hits: int = 10,
) -> Dict[str, Any]:
    """
    Pool one strategy's backtest trades into a time-to-target summary.

    Each trade needs `.exit_reason` (TARGET/STOPLOSS/TIMEOUT/END_OF_DATA) and
    `.holding_bars` (int). Anything else is ignored (never fabricated).

    Returns a JSON-safe dict. `median_days_to_target` is a float only when
    `n_target >= min_target_hits`; otherwise None with an explicit reason.
    On daily bars 1 bar ≈ 1 trading day, hence "days" in the key names — the
    caller must only feed daily-bar trades (the CLI enforces this).
    """
    n = 0
    target_bars: List[float] = []
    stop_bars: List[float] = []
    timeout_bars: List[float] = []
    eod = 0

    for t in trades:
        reason = str(getattr(t, "exit_reason", "") or "").upper()
        try:
            bars = int(getattr(t, "holding_bars"))
        except (TypeError, ValueError):
            continue
        if bars < 0:
            continue
        n += 1
        if reason == "TARGET":
            target_bars.append(float(bars))
        elif reason == "STOPLOSS":
            stop_bars.append(float(bars))
        elif reason == "TIMEOUT":
            timeout_bars.append(float(bars))
        elif reason == "END_OF_DATA":
            eod += 1
        # Unknown reasons still count toward n (they happened) but toward no leg.

    target_bars.sort()
    out: Dict[str, Any] = {
        "n_trades": n,
        "n_target": len(target_bars),
        "n_stop": len(stop_bars),
        "n_timeout": len(timeout_bars),
        "n_end_of_data": eod,
        "target_hit_rate": round(len(target_bars) / n, 3) if n else None,
        "median_days_to_target": None,
        "p25_days_to_target": None,
        "p75_days_to_target": None,
        "median_days_to_stop": round(statistics.median(stop_bars), 1) if stop_bars else None,
        "median_days_to_timeout": round(statistics.median(timeout_bars), 1) if timeout_bars else None,
        "insufficient_reason": None,
    }
    if len(target_bars) >= max(1, int(min_target_hits)):
        out["median_days_to_target"] = round(statistics.median(target_bars), 1)
        out["p25_days_to_target"] = round(_pct(target_bars, 25), 1)
        out["p75_days_to_target"] = round(_pct(target_bars, 75), 1)
    else:
        out["insufficient_reason"] = (
            f"only {len(target_bars)} TARGET exits (< {min_target_hits} floor) — "
            "no median published"
        )
    return out
