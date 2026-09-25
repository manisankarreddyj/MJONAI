"""
Module: research/data/fno_tradingtick.py
Purpose: TradingTick.in historical NIFTY / BANKNIFTY option-chain ingester.

TradingTick serves per-(expiry, trading-day) chain snapshots as plain JSON:
  GET {base}/nifty-hoc/nifty-whoc-filters.php?type=year|month|expiryDate|date
  GET {base}/nifty-hoc/nifty-whoc-data.php?expiry={E}&date={D}
  GET {base}/banknifty/bank-nifty-hoc/bank-nifty-mhoc-{filters|data}.php?...

Each JSON row carries BOTH option sides at one strike:
  CE: Option, OI, OI_Change, Volume, Turnover, Close
  PE: PE_Option, PE_OI, PE_OI_Change, PE_Volume, PE_Turnover, PE_Close
  shared: Strike, ATM (points from ATM), Spot (underlying reference), PCR

Source contract (verified 2026-09-24):
  - NIFTY returns 2019 -> present; BANKNIFTY 2016 -> present (year filter).
  - The "Strike Range" select is CLIENT-SIDE only (ATM filtering); the server
    always returns the full chain.
  - The data endpoint has no documented limit, but the server is a free site:
    the ingester paces at >= 0.4s between requests and is resume-safe.

Canonical output row (one contract per trading day), close-only variant of the
NSE bhavcopy CANON shape so the two sources coexist in the SAME warehouse:
  trade_date, underlying, kind=OPT, option_type (CE|PE), strike, expiry,
  open/high/low/settle/prev_close/trades/lot_size = NaN (not provided — NEVER
  fabricated from Close), close/last = source Close, underlying_price = Spot,
  volume, turnover, oi, oi_change.

Storage: reuse fno_eod's {out_dir}/eod/{YYYY-MM}.parquet merge (idempotent,
natural-key dedup "keep last" — re-running the same (expiry,date) updates rows).
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Iterable, Iterator

import pandas as pd
import requests

from mjonai.research.data.fno_eod import _merge_month, _month_path

logger = logging.getLogger(__name__)

BASE = "https://tradingtick.in"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      "Referer": BASE + "/nifty/download-nifty-option-chain-historical-data.php"}

# Underlying -> (filter script, data script) relative to BASE.
_ENDPOINTS = {
    "NIFTY": ("/nifty/nifty-hoc/nifty-whoc-filters.php", "/nifty/nifty-hoc/nifty-whoc-data.php"),
    "BANKNIFTY": ("/banknifty/bank-nifty-hoc/bank-nifty-mhoc-filters.php",
                  "/banknifty/bank-nifty-hoc/bank-nifty-mhoc-data.php"),
}

# Minimum spacing between HTTP requests (free site — be polite).
MIN_INTERVAL = 0.4
# Bounded retries for transient failures (429/5xx/network). A permanent block
# surfaces as the final None and the crawl exits honestly instead of spinning.
MAX_RETRIES = 3
_last_request: float = 0.0


def _pace() -> None:
    """Sleep so consecutive requests never come faster than MIN_INTERVAL."""
    global _last_request
    dt = time.time() - _last_request
    if dt < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - dt)
    _last_request = time.time()


def _get_json(url: str, timeout: int = 30) -> object | None:
    for attempt in range(MAX_RETRIES):
        _pace()
        try:
            r = requests.get(url, headers=UA, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # network / 5xx / malformed JSON
            logger.warning("[fno_tradingtick] %s failed (attempt %s): %s",
                           url, attempt + 1, exc)
            time.sleep(1.5 * (attempt + 1))
    return None


def list_years(underlying: str) -> list[str]:
    f, _ = _ENDPOINTS[underlying.upper()]
    data = _get_json(BASE + f + "?type=year")
    return list(data) if isinstance(data, list) else []


def list_months(underlying: str, year: str) -> list[str]:
    f, _ = _ENDPOINTS[underlying.upper()]
    data = _get_json(f"{BASE + f}?type=month&year={year}")
    return list(data) if isinstance(data, list) else []


def list_expiries(underlying: str, year: str, month: str) -> list[str]:
    f, _ = _ENDPOINTS[underlying.upper()]
    data = _get_json(f"{BASE + f}?type=expiryDate&year={year}&month={month}")
    return list(data) if isinstance(data, list) else []


def list_dates(underlying: str, expiry: str) -> list[str]:
    f, _ = _ENDPOINTS[underlying.upper()]
    data = _get_json(f"{BASE + f}?type=date&expiry={expiry}")
    return list(data) if isinstance(data, list) else []


def fetch_chain(underlying: str, expiry: str, trade_date: str) -> pd.DataFrame | None:
    """Return CANON-shape close-only rows (one contract per row) for one
    (expiry, trading-day), or None when the server returns nothing usable.

    Never fabricates OHLC — absent fields stay NaN so downstream consumers
    treat them as unknown, exactly like a missing NSE bhavcopy column.
    """
    u = underlying.upper()
    if u not in _ENDPOINTS:
        raise ValueError(f"unsupported underlying {underlying!r}")
    _, d = _ENDPOINTS[u]
    json = _get_json(f"{BASE + d}?expiry={expiry}&date={trade_date}")
    rows = json["data"] if isinstance(json, dict) else None
    if not rows:
        return None

    out = []
    ts = pd.Timestamp(trade_date).normalize()
    exp = pd.Timestamp(expiry).normalize().date()
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            strike = float(r.get("Strike"))
        except (TypeError, ValueError):
            continue
        spot = pd.to_numeric(pd.Series([r.get("Spot", pd.NA)])).iloc[0]
        # CE side (canonical close/last from the CE fields)
        ce_close = pd.to_numeric(pd.Series([r.get("Close", pd.NA)])).iloc[0]
        pe_close = pd.to_numeric(pd.Series([r.get("PE_Close", pd.NA)])).iloc[0]
        for opt, close in (("CE", ce_close), ("PE", pe_close)):
            prefix = "" if opt == "CE" else "PE_"
            oi = pd.to_numeric(pd.Series([r.get(f"{prefix}OI", pd.NA)])).iloc[0]
            oich = pd.to_numeric(pd.Series([r.get(f"{prefix}OI_Change", pd.NA)])).iloc[0]
            vol = pd.to_numeric(pd.Series([r.get(f"{prefix}Volume", pd.NA)])).iloc[0]
            turn = pd.to_numeric(pd.Series([r.get(f"{prefix}Turnover", pd.NA)])).iloc[0]
            out.append({
                "trade_date": ts, "underlying": u, "kind": "OPT",
                "option_type": opt, "strike": strike, "expiry": exp,
                "open": float("nan"), "high": float("nan"), "low": float("nan"),
                "close": close, "last": close, "settle": float("nan"),
                "prev_close": float("nan"), "underlying_price": spot,
                "volume": vol, "turnover": turn, "trades": float("nan"),
                "oi": oi, "oi_change": oich, "lot_size": float("nan"),
            })
    if not out:
        return None
    return pd.DataFrame(out)


def enumerate_pairs(underlying: str, start: date, end: date) -> Iterator[tuple[str, str]]:
    """Yield (expiry, trade_date) string pairs covered by the source within
    [start, end] inclusive, walking the filter hierarchy (year -> months ->
    expiries -> trading dates). Dates outside the window are skipped."""
    u = underlying.upper()
    for year in list_years(u):
        y = int(year)
        if y < start.year or y > end.year:  # expiry-year fence
            continue
        for month_name in list_months(u, year):
            m = datetime.strptime(month_name, "%B").month
            if (y, m) < (start.year, start.month) or (y, m) > (end.year, end.month):
                continue
            for expiry in list_expiries(u, year, month_name):
                for d in list_dates(u, expiry):
                    d0 = date.fromisoformat(d)
                    if start <= d0 <= end:
                        yield expiry, d


def ingest_range(
    start: date, end: date, out_dir: str,
    underlyings: Iterable[str] = ("NIFTY", "BANKNIFTY"),
) -> dict:
    """Ingest [start, end] inclusive from TradingTick into the shared chain
    warehouse. Idempotent: re-running the same (expiry, date) merges by natural
    key (keep=last). Returns summary stats."""
    summary = {"pairs_ok": 0, "pairs_empty": 0, "errors": 0, "rows_total": 0,
               "skipped_dates": []}
    for u in underlyings:
        u = u.upper()
        if u not in _ENDPOINTS:
            logger.warning("[fno_tradingtick] unknown underlying %s — skipped", u)
            continue
        seen: set[tuple] = set()
        for expiry, d in enumerate_pairs(u, start, end):
            if (u, expiry, d) in seen:  # same expiry/date can surface twice across months
                continue
            seen.add((u, expiry, d))
            frame = fetch_chain(u, expiry, d)
            if frame is None or frame.empty:
                summary["pairs_empty"] += 1
                summary["skipped_dates"].append(f"{u} {d} {expiry}")
                continue
            try:
                n = _merge_month(_month_path(out_dir, pd.Timestamp(d)), frame)
                summary["rows_total"] += len(frame)
                summary["pairs_ok"] += 1
            except Exception as exc:  # warehouse write must not kill the crawl
                logger.warning("[fno_tradingtick] %s %s merge failed: %s", u, d, exc)
                summary["errors"] += 1
            if summary["pairs_ok"] % 50 == 0 and summary["pairs_ok"]:
                print(f"  {u} {d}: cumulative chains {summary['pairs_ok']:,} "
                      f"rows {summary['rows_total']:,}", flush=True)
    return summary


if __name__ == "__main__":
    import sys
    s = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2021, 1, 1)
    e = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()
    out = sys.argv[3] if len(sys.argv) > 3 else r"D:\MJONAI\storage\parquet\fno_chain"
    print(ingest_range(s, e, out))