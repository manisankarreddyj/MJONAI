"""
Module: forward_returns.py

Purpose: Calculate and store forward returns for every scanner signal.
         Feeds pattern-memory expectancy, per-signal IC analysis and
         Alphalens factor tear-sheets. Runs daily at 16:00 IST.

Honest-entry convention (P1.1 plan, 2026-09-14):
  - If the signal carries a stored `entry_price`, use it as base — this
    measures the quality of the proposed entry level, not hindsight.
  - Otherwise fall back to the close on the signal date from the price series.
  - Windows [1, 5, 10, 20] trading days (matching Alphalens consumers).
  - Price data uses yfinance with auto_adjust=True (Decision 6 Phase 1:
    adjusted closes are the correct reference for forward returns).

Runs REGARDLESS of whether a trade opened — rejected signals are just as
important for IC analysis as executed ones.
"""

from datetime import datetime
import bisect
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from mjonai.db.repository import (
    get_signals_needing_forward_returns,
    update_signal_forward_returns,
)

logger = logging.getLogger(__name__)

FORWARD_WINDOWS = [1, 5, 10, 20]
_FALLBACK_PERIOD = "6mo"

# Yahoo symbol resolution — mirrors the alias block in
# mjonai/data/angelone/historical.py (index identities + the TMPV
# post-demerger name). The old code appended ".NS" blindly, so every
# NIFTY/BANKNIFTY/commodity signal burned a 404 (189 errors in the 16:00
# job on 2026-10-16) and index signals NEVER got forward returns — an
# IC/track-record blind spot, not a data absence.
_YAHOO_ALIASES = {
    "NIFTY": "^NSEI", "NIFTY 50": "^NSEI", "NIFTY50": "^NSEI",
    "BANKNIFTY": "^NSEBANK", "NIFTY BANK": "^NSEBANK",
    "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
    "NIFTY FINANCIAL SERVICES": "NIFTY_FIN_SERVICE.NS",
    "INDIAVIX": "^INDIAVIX", "INDIA VIX": "^INDIAVIX",
    "TATAMOTORS": "TMPV.NS", "TATA MOTORS": "TMPV.NS",
}
# MCX/commodity names have no Yahoo equity mapping — skip quietly (info, not
# warning: expected absence, not a failure).
_NON_EQUITY_SKIPS = frozenset({
    "CRUDEOIL", "NATURALGAS", "GOLD", "SILVER", "COPPER", "CRUDE", "NG",
})


def _resolve_yahoo_symbol(symbol: Any) -> Optional[str]:
    """Map a signal symbol to its Yahoo ticker, or None when unmappable."""
    clean = str(symbol or "").upper().replace(".NS", "").replace(".BO", "").strip()
    if not clean:
        return None
    if clean in _YAHOO_ALIASES:
        return _YAHOO_ALIASES[clean]
    if clean in _NON_EQUITY_SKIPS:
        return None
    if clean.startswith("^"):
        return clean
    return f"{clean}.NS"


def _fetch_close_series(symbol: str) -> pd.Series:
    """Download adjusted close series for ``symbol`` via its Yahoo identity.

    Returns an empty Series on any failure so callers can degrade gracefully.
    """
    import yfinance as yf

    yf_symbol = _resolve_yahoo_symbol(symbol)
    if yf_symbol is None:
        logger.info(f"[forward_returns] {symbol}: no Yahoo mapping — skipped")
        return pd.Series(dtype=float)

    try:
        df = yf.download(
            yf_symbol,
            period=_FALLBACK_PERIOD,
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
        )
    except Exception as e:
        logger.warning(f"[forward_returns] download failed {symbol}: {e}")
        return pd.Series(dtype=float)

    if df is None or df.empty:
        return pd.Series(dtype=float)

    close = df["Close"].squeeze()
    if isinstance(close, pd.DataFrame):
        close = close.mean(axis=1)
    if not isinstance(close, pd.Series):
        try:
            close = pd.Series(close, index=df.index)
        except Exception:
            return pd.Series(dtype=float)
    return close.dropna()


def _as_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _day_of(idx: Any) -> Any:
    return idx.date() if hasattr(idx, "date") else idx


def _index_of_date(day, series: pd.Series) -> Optional[int]:
    for i, idx in enumerate(series.index):
        if _day_of(idx) == day:
            return i
    return None


def _first_index_at_or_after(day, series: pd.Series) -> Optional[int]:
    dates = [_day_of(idx) for idx in series.index]
    pos = bisect.bisect_left(dates, day)
    return pos if pos < len(dates) else None


def _resolve_entry(signal: Dict[str, Any], close_series: pd.Series) -> Optional[tuple]:
    """Return (entry_price, entry_idx) or None.

    Entry price precedence: stored signal `entry_price` (the proposed level,
    no hindsight) else the close on the signal date. Both require a matching
    trading day in the series; a missing date means NULLs stay in place.
    """
    generated_at = _as_datetime(signal.get("generated_at"))
    if generated_at is None:
        return None
    signal_date = generated_at.date()

    stored_entry = signal.get("entry_price")
    try:
        if stored_entry is not None:
            entry_price = float(stored_entry)
            entry_idx = _first_index_at_or_after(signal_date, close_series)
        else:
            entry_idx = _index_of_date(signal_date, close_series)
            if entry_idx is None:
                return None
            entry_price = float(close_series.iloc[entry_idx])
    except (TypeError, ValueError, IndexError):
        return None

    if entry_idx is None or entry_price is None or entry_price <= 0:
        return None
    return entry_price, entry_idx


def _calculate_returns_for_signal(
    signal: Dict[str, Any],
    close_series: pd.Series,
) -> Optional[Dict[str, Any]]:
    """Compute forward returns for one signal from the given close series."""
    resolved = _resolve_entry(signal, close_series)
    if resolved is None:
        return None
    entry_price, entry_idx = resolved

    returns: Dict[str, Any] = {}
    for window in FORWARD_WINDOWS:
        future_idx = entry_idx + window
        if future_idx < len(close_series):
            future_price = float(close_series.iloc[future_idx])
            returns[f"forward_return_{window}d"] = round(
                (future_price - entry_price) / entry_price, 6
            )
        else:
            returns[f"forward_return_{window}d"] = None
    return returns if any(v is not None for v in returns.values()) else None


_MAX_DRAIN_BATCHES = 10


def compute_forward_returns(limit: int = 1000) -> Dict[str, Any]:
    """Process signals that still lack forward returns, draining in batches.

    ``limit`` is the per-batch size; batches repeat until a short batch
    arrives (backlog drained) or ``_MAX_DRAIN_BATCHES`` is hit (runaway guard
    — a pathological backlog must not hold the 16:00 job forever). The old
    single-batch form left every signal past the first 1000 unfilled whenever
    daily inflow exceeded it (the standing 2026-10-15 backlog).

    Returns stats: signals_processed / signals_updated / signals_skipped /
    errors. Rejected signals are processed too — their forward returns are
    exactly what makes IC analysis honest.
    """
    stats = {"signals_processed": 0, "signals_updated": 0, "signals_skipped": 0, "errors": 0}

    for _ in range(max(1, _MAX_DRAIN_BATCHES)):
        signals = get_signals_needing_forward_returns(limit=limit)
        if not signals:
            logger.info("[forward_returns] no signals awaiting forward returns")
            break
        _process_forward_batch(signals, stats)
        if len(signals) < limit:
            break
    else:
        logger.warning(
            f"[forward_returns] backlog exceeds {_MAX_DRAIN_BATCHES * limit} — "
            "stopping at the runaway guard; remainder keeps for tomorrow")

    logger.info(
        f"[forward_returns] complete: {stats['signals_updated']}/{stats['signals_processed']} "
        f"updated, {stats['signals_skipped']} skipped, {stats['errors']} errors"
    )
    return stats


def _process_forward_batch(
    signals: List[Dict[str, Any]], stats: Dict[str, Any]
) -> None:
    """Fill forward returns for one batch of signals (mutates ``stats``)."""
    by_symbol: Dict[str, List[Dict[str, Any]]] = {}
    for signal in signals:
        symbol = signal.get("symbol")
        if not symbol:
            stats["signals_skipped"] += 1
            continue
        by_symbol.setdefault(symbol, []).append(signal)

    logger.info(f"[forward_returns] processing {len(signals)} signals across {len(by_symbol)} symbols")

    for symbol, symbol_signals in by_symbol.items():
        if _resolve_yahoo_symbol(symbol) is None:
            # No Yahoo identity (MCX names etc.) — expected absence, counted
            # as skipped, never as errors (the fetcher already info-logged it).
            stats["signals_skipped"] += len(symbol_signals)
            continue
        try:
            close_series = _fetch_close_series(symbol)
        except Exception as e:
            logger.warning(f"[forward_returns] symbol {symbol} failed: {e}")
            stats["errors"] += len(symbol_signals)
            continue

        if close_series.empty or len(close_series) < 5:
            logger.warning(f"[forward_returns] {symbol} insufficient data ({len(close_series)} rows)")
            stats["errors"] += len(symbol_signals)
            continue

        for signal in symbol_signals:
            stats["signals_processed"] += 1
            try:
                returns = _calculate_returns_for_signal(signal, close_series)
                if not returns:
                    stats["signals_skipped"] += 1
                    continue
                update_signal_forward_returns(signal["id"], returns)
                stats["signals_updated"] += 1
            except Exception as e:
                logger.warning(f"[forward_returns] signal {signal.get('id')}: {e}")
                stats["errors"] += 1


def forward_return_summary(limit: int = 5000) -> Dict[str, Any]:
    """Per-window mean/median sample-count summary of stored forward returns.

    Pure-read diagnostic for the 16:00 report path and research CLIs.
    """
    from mjonai.db.repository import get_signals_for_alphalens

    rows = get_signals_for_alphalens(limit=limit)
    if not rows:
        return {"signals": 0}
    frame = pd.DataFrame(rows)
    cols = [c for c in (f"forward_return_{w}d" for w in FORWARD_WINDOWS) if c in frame.columns]
    summary = {"signals": int(len(frame))}
    for col in cols:
        series = pd.to_numeric(frame[col], errors="coerce").dropna()
        if series.empty:
            summary[col] = {"mean": None, "median": None, "n": 0}
        else:
            summary[col] = {
                "mean": round(float(series.mean()), 6),
                "median": round(float(series.median()), 6),
                "n": int(len(series)),
            }
    return summary