"""
Module: research/data/tradingtick_index.py
Purpose: TradingTick.in historical NIFTY / BANKNIFTY spot and futures DAILY bars.

TradingTick serves historical index spot and index futures as plain JSON:
  GET {base}/nifty/php-files/nifty-spot.php?action=filters            -> years/months
  GET {base}/nifty/php-files/nifty-spot.php?action=data&year={Y}&month={M}
                                                                -> [{...}, ...] daily spot rows
  GET {base}/nifty/php-files/nifty-fut.php?action=filters             -> years/months
  GET {base}/nifty/php-files/nifty-fut.php?action=data&year={Y}&month={M}
                                                                -> [{...}, ...] per-contract futures rows

Source contract (verified 2026-09-26):
  - NIFTY spot/futures: 2000+ / 2003 -> present (futures confirmed real at 2003-01).
  - BANKNIFTY spot: 2000+ (a "0" special year in the filter is tolerated); futures present.
  - Spot rows: date, day, OHLC, prev_close, change/perc, otc/perc, gap_up/perc, high_low.
  - Futures rows: per (date, expiry) contract — date, expiry, OHLC, ltp, settle_price,
    volume, turnover, oi, coi, spot, basis, built_up. One month typically holds a
    single on-going expiry (rows span the expiry's trading window).
  - `time` is epoch seconds UTC (spot day-open / futures row anchor) — converted to
    naive IST for +5:30 alignment with the rest of the engine.

Known source-side quality note (verified 2026-09-26): the NIFTY SPOT
endpoint pours garbage into prev_close/change/change_pct/otc/gap_up on the
rolling frontier (currently 2026-02-13 onwards, 115 rows) — those columns
carry near-constant nonsense (~24/25); the OHLC itself stays continuous and
trustworthy. The corrupted columns are stored verbatim (never fabricated or
"fixed"), matching the house rule that a broken feed must not present as a
real reading. Consumers needing prev-close semantics for those rows should
derive them from the prior row's close rather than the column. The futures
surface shows no such defect.

Canonical storage (two warehouses, one month file per underlying):
  {out_dir}/spot/{UNDERLYING}/{YYYY-MM}.parquet     natural key (trade_date)
  {out_dir}/futures/{UNDERLYING}/{YYYY-MM}.parquet  natural key (trade_date, expiry)

House columns mirror the engine's daily-bar vocabulary where meaningful;
source-only fields (otc/gap_up/built_up) are preserved verbatim — never
normalized or fabricated. This module is INDEX data (spot index + index
futures); option chain snapshots live in storage/parquet/fno_chain/eod/ and
index intraday in storage/parquet/tradingtick_1min/.
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

_SPOT_ENDPOINTS = {
    "NIFTY": "/nifty/php-files/nifty-spot.php",
    "BANKNIFTY": "/banknifty/php-files/bank-nifty-spot.php",
}
_FUT_ENDPOINTS = {
    "NIFTY": "/nifty/php-files/nifty-fut.php",
    "BANKNIFTY": "/banknifty/php-files/bank-nifty-fut.php",
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
            logger.warning("[tradingtick_index] %s failed (attempt %s): %s",
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


def _to_date(expiry_raw: object) -> pd.Timestamp:
    if expiry_raw is None or expiry_raw != expiry_raw:
        return pd.NaT
    try:
        ts = pd.Timestamp(expiry_raw)
        if ts is pd.NaT:
            return pd.NaT
        return ts.normalize()
    except (TypeError, ValueError):
        return pd.NaT


def list_years(underlying: str, surface: str) -> list[str]:
    """Years served for spot|futures. The BANKNIFTY spot filter carries a
    bogus '0' year entry — it is dropped (never a real data year)."""
    ep = _SPOT_ENDPOINTS if surface == "spot" else _FUT_ENDPOINTS
    u = underlying.upper()
    if u not in ep:
        raise ValueError(f"unsupported underlying {underlying!r} for {surface}")
    data = _get_json(BASE + ep[u] + "?action=filters")
    years = []
    if isinstance(data, dict):
        for y in data.get("years", []):
            s = str(y)
            if s.isdigit() and int(s) > 0:
                years.append(s)
    return years


def list_months(underlying: str, year: str, surface: str) -> list[str]:
    ep = _SPOT_ENDPOINTS if surface == "spot" else _FUT_ENDPOINTS
    data = _get_json(f"{BASE + ep[underlying.upper()]}?action=filters&year={year}")
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


def fetch_month(underlying: str, year: str, month: str, surface: str) -> pd.DataFrame | None:
    """Return one month of rows (spot: one day per row; futures: one row per
    (day, expiry) contract). None on an empty/foreign response."""
    ep = _SPOT_ENDPOINTS if surface == "spot" else _FUT_ENDPOINTS
    u = underlying.upper()
    if u not in ep:
        raise ValueError(f"unsupported underlying {underlying!r} for {surface}")
    url = f"{BASE + ep[u]}?action=data&year={year}&month={month}"
    rows = _get_json(url)
    if not isinstance(rows, list) or not rows:
        return None

    if surface == "spot":
        out = []
        for r in rows:
            ts = _to_ist(r.get("time"))
            out.append({
                "trade_date": ts,
                "underlying": u,
                "open": _currency(r.get("open")),
                "high": _currency(r.get("high")),
                "low": _currency(r.get("low")),
                "close": _currency(r.get("close")),
                "prev_close": _currency(r.get("prev_close")),
                "change": _currency(r.get("change")),
                "change_pct": _currency(r.get("change_perc")),
                "otc": _currency(r.get("otc")),
                "otc_pct": _currency(r.get("otc_perc")),
                "gap_up": _currency(r.get("gap_up")),
                "gap_up_pct": _currency(r.get("gap_up_perc")),
                "high_low": _currency(r.get("high_low")),
            })
    else:  # futures
        out = []
        for r in rows:
            ts = _to_ist(r.get("time"))
            expiry = _to_date(r.get("expiry"))
            out.append({
                "trade_date": ts,
                "expiry": expiry,
                "underlying": u,
                "open": _currency(r.get("open")),
                "high": _currency(r.get("high")),
                "low": _currency(r.get("low")),
                "close": _currency(r.get("close")),
                "ltp": _currency(r.get("ltp")),
                "settle_price": _currency(r.get("settle_price")),
                "volume": _currency(r.get("volume")),
                "turnover": _currency(r.get("turnover")),
                "oi": _currency(r.get("oi")),
                "coi": _currency(r.get("coi")),
                "spot": _currency(r.get("spot")),
                "basis": _currency(r.get("basis")),
                "built_up": r.get("built_up"),
            })
    if surface != "spot":
        out = [r for r in out if r.get("trade_date") is not pd.NaT
               and (r.get("expiry") is not pd.NaT) and r.get("expiry") is not None]
    if not out:
        return None
    return pd.DataFrame(out)


def enumerate_months(underlying: str, surface: str,
                     start: date, end: date) -> Iterator[tuple[str, str]]:
    """Yield (year, short-month) pairs covered within [start, end] inclusive."""
    u = underlying.upper()
    for year in list_years(u, surface):
        y = int(year)
        if y < start.year or y > end.year:
            continue
        for month in list_months(u, year, surface):
            m = _MONTH_SHORT.index(month) + 1
            if (y, m) < (start.year, start.month) or (y, m) > (end.year, end.month):
                continue
            yield year, month


def _month_path(out_dir: str, surface: str, underlying: str, ts: pd.Timestamp) -> str:
    return os.path.join(out_dir, surface, underlying, f"{ts:%Y-%m}.parquet")


def _merge_month(path: str, frame: pd.DataFrame, natural_key: list[str]) -> int:
    """Idempotent keep=last merge of one month's rows into the month file."""
    df = frame.copy()
    if os.path.exists(path):
        old = pd.read_parquet(path)
        df = pd.concat([old, df], ignore_index=True)
        df = df.drop_duplicates(subset=natural_key, keep="last")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df = df.sort_values(natural_key)
    df.to_parquet(path, index=False)
    return len(df)


def load_series(out_dir: str, surface: str, underlying: str,
                start: date, end: date) -> pd.DataFrame:
    """Read the daily spot/futures series over [start, end] inclusive from the
    local parquet warehouse.

    Fail-closed by contract: a year-month file missing from the warehouse
    within [start, end] is an error (the caller receives a ValueError, never a
    silently incomplete series). The returned frame is sorted by natural key
    and carries the full source schema (spot: trade_date/OHLC/prev_close/
    change/otc/gap_up/high_low; futures: + expiry/ltp/settle/volume/turnover/
    oi/coi/spot/basis/built_up).
    """
    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    if s > e:
        return pd.DataFrame()
    u = underlying.upper()
    frames = []
    y, m = s.year, s.month
    while (y, m) <= (e.year, e.month):
        path = _month_path(out_dir, surface, u, pd.Timestamp(y, m, 1))
        if not os.path.exists(path):
            raise ValueError(
                f"[tradingtick_index] missing month {y:04d}-{m:02d} in "
                f"{surface}/{u} warehouse ({path})"
            )
        frames.append(pd.read_parquet(path))
        m += 1
        if m == 13:
            y += 1
            m = 1
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    nkey = ["trade_date"] if surface == "spot" else ["trade_date", "expiry"]
    df = df.drop_duplicates(subset=nkey, keep="last")
    df = df.sort_values(nkey).reset_index(drop=True)
    return df[df["trade_date"].between(s, e)]


def ingest_range(start: date, end: date, out_dir: str,
                 surfaces: Iterable[str] = ("spot", "futures"),
                 underlyings: Iterable[str] = ("NIFTY", "BANKNIFTY")) -> dict:
    """Ingest [start, end] inclusive for the requested surfaces into
    {out_dir}/{surface}/{UNDERLYING}/{YYYY-MM}.parquet. Idempotent."""
    summary = {"months_total": 0, "months_empty": 0, "errors": 0,
               "rows_total": 0, "skipped": []}
    for surface in surfaces:
        summary[surface] = {}
        for u in underlyings:
            u = u.upper()
            ep = _SPOT_ENDPOINTS if surface == "spot" else _FUT_ENDPOINTS
            if u not in ep:
                logger.warning("[tradingtick_index] unknown underlying %s", u)
                continue
            nkey = ["trade_date"] if surface == "spot" else ["trade_date", "expiry"]
            for year, month in enumerate_months(u, surface, start, end):
                frame = fetch_month(u, year, month, surface)
                if frame is None or frame.empty:
                    summary["months_empty"] += 1
                    summary["skipped"].append(f"{surface} {u} {year}-{month}")
                    continue
                try:
                    n = _merge_month(
                        _month_path(out_dir, surface, u, pd.Timestamp(f"{year}-{month}-01")),
                        frame, nkey)
                    summary["rows_total"] += len(frame)
                    summary["months_total"] += 1
                    summary[surface].setdefault(u, 0)
                    summary[surface][u] += len(frame)
                except Exception as exc:
                    logger.warning("[tradingtick_index] %s %s %s-%s merge failed: %s",
                                   surface, u, year, month, exc)
                    summary["errors"] += 1
                if summary["months_total"] % 12 == 0 and summary["months_total"]:
                    print(f"  {surface} {u} {year}-{month}: cumulative months "
                          f"{summary['months_total']:,} rows {summary['rows_total']:,}",
                          flush=True)
    return summary


if __name__ == "__main__":
    import sys
    s = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2014, 1, 1)
    e = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date(2026, 8, 1)
    out = sys.argv[3] if len(sys.argv) > 3 else r"D:\MJONAI\storage\parquet\tradingtick_index"
    print(ingest_range(s, e, out))