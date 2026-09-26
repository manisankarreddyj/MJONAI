"""
Module: research/data/tradingtick_strike_ohlc.py
Purpose: TradingTick.in historical per-strike DAILY OHLC for index options
(NIFTY monthly expiries 2019-02 -> present, BANKNIFTY monthly expiries
2016-06 -> present).

TradingTick serves historical per-strike option candles as plain JSON:
  GET {base}/nifty/chart-files/option-chart.php?action=filters   -> years
  GET {base}/nifty/chart-files/option-chart.php?action=months&year={Y}   -> months
  GET {base}/nifty/chart-files/option-chart.php?action=expiries&year={Y}&month={M}   -> expiries
  GET {base}/nifty/chart-files/option-chart.php?action=strikes&year={Y}&month={M}&expiry={E}&option={CE|PE}   -> strikes
  GET {base}/nifty/chart-files/option-chart.php?year={Y}&month={M}&expiry={E}&option={CE|PE}&strike={S}&tf={any}
                                                              -> [{"time", "open", "high", "low", "close"}, ...]

Endpoints (relative to https://tradingtick.in):
  NIFTY     /nifty/chart-files/option-chart.php
  BANKNIFTY /banknifty/chart-files/bank-nifty-option-chart.php

Source contract (verified 2026-09-26):
  - The chart serves ONE expiry per (year, month) — the MONTHLY expiry. The
    weekly-expiry era (NIFTY from 2021-02) still enumerates a single expiry per
    month (the monthly contract); WEEKLY expiries do NOT appear in this chart
    endpoint. Per-strike history for weeklies lives nowhere on TradingTick.
  - The `tf` parameter is accepted but IGNORED — the endpoint only serves daily
    bars (one row per trading day the contract was listed; ~1 month per strike).
  - Rows: {time (epoch seconds UTC, day anchor at midnight IST), open, high,
    low, close}. Values may be null on thinly-traded strikes; they are stored
    as NaN (never fabricated or backfilled to prior close — the source page's
    own JS "Fix null OHLC" is a display convenience, not data).
  - Strikes are strings; the strike list may not include today's-live strikes.

Coverage (verified 2026-09-26): NIFTY 2019-02 (2019-01 serves no expiry) ->
present; BANKNIFTY 2016-06 -> present. BN years enumeration carries a bogus
null entry — dropped. 2014/2015 option chains do not exist on TradingTick.

Canonical storage — a SEPARATE warehouse from storage/parquet/fno_chain/eod/
(the chain-snapshot warehouse stays atomic and untouched):
  {out_dir}/{UNDERLYING}/{YYYY-MM}.parquet
  columns trade_date/expiry/option_type/strike/open/high/low/close
  natural key (trade_date, expiry, option_type, strike), idempotent keep=last
  merge. Provenance is deliberately kept apart from the NSE bhavcopy overlay
  warehouse; consumers join with it on (trade_date, expiry, option_type,
  strike) when Open/High/Low are needed for pre-2024 rows.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime
from typing import Iterable, Iterator

import pandas as pd
import requests

logger = logging.getLogger(__name__)

BASE = "https://tradingtick.in"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

_ENDPOINTS = {
    "NIFTY": "/nifty/chart-files/option-chart.php",
    "BANKNIFTY": "/banknifty/chart-files/bank-nifty-option-chart.php",
}

_MONTH_SHORT = [datetime(2000, m, 1).strftime("%b") for m in range(1, 13)]

MIN_INTERVAL = 0.4
MAX_RETRIES = 3
_last_request: float = 0.0


def _pace() -> None:
    global _last_request
    dt = time.time() - _last_request
    if dt < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - dt)
    _last_request = time.time()


def _get_json(url: str, timeout: int = 40) -> object | None:
    for attempt in range(MAX_RETRIES):
        _pace()
        try:
            r = requests.get(url, headers=UA, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # network / 5xx / malformed JSON
            logger.warning("[tradingtick_strike] %s failed (attempt %s): %s",
                           url, attempt + 1, exc)
            time.sleep(1.5 * (attempt + 1))
    return None


def _currency(value: object) -> float:
    """Return a float, or NaN when the source gives a non-numeric value."""
    try:
        f = float(value)
        return f if f == f else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def _to_ist(epoch_s: object) -> pd.Timestamp:
    if epoch_s is None or epoch_s != epoch_s:  # None or NaN
        return pd.NaT
    try:
        ts = pd.Timestamp(int(epoch_s), unit="s", tz="UTC").tz_convert(
            "Asia/Kolkata"
        )
        return ts.tz_localize(None)
    except (TypeError, ValueError):
        return pd.NaT


def _check_underlying(underlying: str) -> str:
    u = underlying.upper()
    if u not in _ENDPOINTS:
        raise ValueError(f"unsupported underlying {underlying!r}")
    return u


def list_years(underlying: str) -> list[str]:
    """Years served for option charts. The BANKNIFTY year list carries a bogus
    null entry — it is dropped (never a real data year)."""
    u = _check_underlying(underlying)
    data = _get_json(BASE + _ENDPOINTS[u] + "?action=filters")
    years = []
    if isinstance(data, dict):
        for y in data.get("years", []):
            s = str(y) if y is not None else ""
            if s.isdigit() and int(s) > 0:
                years.append(s)
    return years


def list_months(underlying: str, year: str) -> list[str]:
    u = _check_underlying(underlying)
    data = _get_json(f"{BASE + _ENDPOINTS[u]}?action=months&year={year}")
    months = []
    if isinstance(data, dict):
        for m in data.get("months", []):
            if isinstance(m, dict):
                v = m.get("value")
                if v:
                    months.append(str(v))
            else:
                months.append(str(m))
    by_lower = {x.lower(): x for x in _MONTH_SHORT}
    out = []
    for m in months:
        key = str(m).lower()[:3]
        if key in by_lower:
            out.append(by_lower[key])
    return out


def list_expiries(underlying: str, year: str, month: str) -> list[str]:
    u = _check_underlying(underlying)
    data = _get_json(
        f"{BASE + _ENDPOINTS[u]}?action=expiries&year={year}&month={month}")
    expiries = []
    if isinstance(data, dict):
        expiries = [str(e) for e in data.get("expiries", []) if e]
    return expiries


def list_strikes(underlying: str, year: str, month: str,
                 expiry: str, option: str) -> list[str]:
    u = _check_underlying(underlying)
    data = _get_json(
        f"{BASE + _ENDPOINTS[u]}?action=strikes&year={year}&month={month}"
        f"&expiry={expiry}&option={option}")
    strikes = []
    if isinstance(data, dict):
        strikes = [str(s) for s in data.get("strikes", []) if s is not None]
    return strikes


def fetch_strike(underlying: str, year: str, month: str, expiry: str,
                 option: str, strike: str) -> pd.DataFrame | None:
    """Return the daily OHLC frame for one (expiry, option, strike) contract.
    None on an empty/foreign response. The `tf` arg is accepted but ignored
    by the source (daily only)."""
    u = _check_underlying(underlying)
    option = option.upper()
    if option not in ("CE", "PE"):
        raise ValueError(f"unsupported option {option!r}")
    url = (f"{BASE + _ENDPOINTS[u]}?year={year}&month={month}&expiry={expiry}"
           f"&option={option}&strike={strike}&tf=1D")
    rows = _get_json(url)
    if not isinstance(rows, list) or not rows:
        return None
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        ts = _to_ist(r.get("time"))
        if ts is pd.NaT:
            continue
        out.append({
            "trade_date": ts,
            "expiry": pd.Timestamp(expiry).normalize(),
            "option_type": option,
            "strike": float(strike),
            "open": _currency(r.get("open")),
            "high": _currency(r.get("high")),
            "low": _currency(r.get("low")),
            "close": _currency(r.get("close")),
        })
    if not out:
        return None
    return pd.DataFrame(out)


def enumerate_strikes(underlying: str,
                      start: date, end: date) -> Iterator[tuple[str, str, str, str, str]]:
    """Yield (year, short-month, expiry, option, strike) tuples within
    [start, end] inclusive, using the source's own enumeration."""
    u = _check_underlying(underlying)
    for year in list_years(u):
        y = int(year)
        if y < start.year or y > end.year:
            continue
        for month in list_months(u, year):
            m = _MONTH_SHORT.index(month) + 1
            if (y, m) < (start.year, start.month) or (y, m) > (end.year, end.month):
                continue
            for exp in list_expiries(u, year, month):
                for option in ("CE", "PE"):
                    for strike in list_strikes(u, year, month, exp, option):
                        yield year, month, exp, option, strike


def _month_path(out_dir: str, underlying: str, ts: pd.Timestamp) -> str:
    return os.path.join(out_dir, underlying, f"{ts:%Y-%m}.parquet")


def _merge_month(path: str, frame: pd.DataFrame) -> int:
    """Idempotent keep=last merge of one contract's rows into the month file.
    Bars are bucketed to the month of their trade_date (an expiry's chart can
    span into the prior month's trading window)."""
    df = frame.copy()
    if os.path.exists(path):
        old = pd.read_parquet(path)
        df = pd.concat([old, df], ignore_index=True)
        df = df.drop_duplicates(
            subset=["trade_date", "expiry", "option_type", "strike"], keep="last")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df = df.sort_values(["trade_date", "expiry", "option_type", "strike"])
    df.to_parquet(path, index=False)
    return len(df)


def load_series(out_dir: str, underlying: str,
                start: date, end: date) -> pd.DataFrame:
    """Read the per-strike daily OHLC series over [start, end] inclusive from
    the local parquet warehouse.

    Fail-closed by contract: a year-month file missing from the warehouse
    within [start, end] is an error (ValueError, never a silently incomplete
    series). The returned frame is sorted by natural key and carries
    trade_date/expiry/option_type/strike/open/high/low/close.
    """
    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    if s > e:
        return pd.DataFrame()
    u = _check_underlying(underlying)
    frames = []
    y, m = s.year, s.month
    while (y, m) <= (e.year, e.month):
        path = _month_path(out_dir, u, pd.Timestamp(y, m, 1))
        if not os.path.exists(path):
            raise ValueError(
                f"[tradingtick_strike] missing month {y:04d}-{m:02d} in "
                f"{u} warehouse ({path})"
            )
        frames.append(pd.read_parquet(path))
        m += 1
        if m == 13:
            y += 1
            m = 1
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    nkey = ["trade_date", "expiry", "option_type", "strike"]
    df = df.drop_duplicates(subset=nkey, keep="last")
    df = df.sort_values(nkey).reset_index(drop=True)
    return df[df["trade_date"].between(s, e)]


def ingest_range(start: date, end: date, out_dir: str,
                 underlyings: Iterable[str] = ("NIFTY", "BANKNIFTY")) -> dict:
    """Ingest [start, end] inclusive per-strike daily OHLC for the underlying(s)
    into {out_dir}/{UNDERLYING}/{YYYY-MM}.parquet. Idempotent (keep=last merge
    on the natural key)."""
    summary = {"contracts_total": 0, "contracts_empty": 0, "rows_total": 0,
               "errors": 0, "skipped": []}
    for u in underlyings:
        u = u.upper()
        try:
            _check_underlying(u)
        except ValueError:
            logger.warning("[tradingtick_strike] unknown underlying %s", u)
            continue
        summary[u] = 0
        for year, month, expiry, option, strike in enumerate_strikes(u, start, end):
            frame = fetch_strike(u, year, month, expiry, option, strike)
            if frame is None or frame.empty:
                summary["contracts_empty"] += 1
                summary["skipped"].append(f"{u} {expiry} {option} {strike}")
                continue
            try:
                buckets: dict[str, pd.DataFrame] = {}
                for ts, g in frame.groupby(frame["trade_date"].dt.to_period("M")):
                    buckets[str(ts)] = g
                for ym, g in buckets.items():
                    _merge_month(
                        _month_path(out_dir, u, pd.Timestamp(f"{ym}-01")), g)
                summary["contracts_total"] += 1
                summary["rows_total"] += len(frame)
                summary[u] = summary[u] + len(frame)
            except Exception as exc:
                logger.warning("[tradingtick_strike] %s %s %s %s merge failed: %s",
                               u, expiry, option, strike, exc)
                summary["errors"] += 1
            if summary["contracts_total"] % 50 == 0 and summary["contracts_total"]:
                print(f"  {u} {expiry} {option} {strike}: cumulative contracts "
                      f"{summary['contracts_total']:,} rows {summary['rows_total']:,}",
                      flush=True)
    return summary


if __name__ == "__main__":
    import sys
    s = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2019, 2, 1)
    e = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date(2026, 7, 1)
    out = sys.argv[3] if len(sys.argv) > 3 else r"D:\MJONAI\storage\parquet\tradingtick_strike"
    print(ingest_range(s, e, out))