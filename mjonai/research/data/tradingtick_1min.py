"""
Module: research/data/tradingtick_1min.py
Purpose: TradingTick.in historical NIFTY / BANKNIFTY 1-minute index bars.

TradingTick serves historical intraday candles one trading day at a time as
plain JSON:
  GET {base}?action=years                              -> {"years": ["2015", ...]}
  GET {base}?action=months&year={YYYY}                 -> {"months": [{"value":"Jan","name":"January"}, ...]}
  GET {base}?action=dates&year={YYYY}&month={Jan}      -> {"dates": ["YYYY-MM-DD", ...]}
  GET {base}?year={YYYY}&month={Jan}&date={YYYY-MM-DD}&tf={1|3|5|15|30|60}
                                                       -> [{"time": <epoch s>, "open", "high", "low", "close"}, ...]

Endpoints (relative to https://tradingtick.in):
  NIFTY     /nifty/php-files/nifty1minchart.php
  BANKNIFTY /banknifty/php-files/bank-nifty-1min-chart-backend.php

Source contract (verified 2026-09-25):
  - Coverage 2015 -> present for both indices (~11.5 years), full trading days.
  - `time` is the bar-open epoch seconds in UTC; 375 one-minute bars per day
    from 09:15 to 15:29 IST. Higher timeframes resample locally from 1m.
  - OHLC ONLY. Volume is NOT provided — it stays NaN, never fabricated.
  - `dates` may arrive as a bare list or {"dates": [...]}; both are tolerated.
  - The server is a free site: requests pace at >= 0.4s (bounded retries).

Canonical per-day output (house OHLCV frame, matching the minute archive):
  DatetimeIndex (naive IST bar-open), columns Open/High/Low/Close/Volume
  (Volume all-NaN). Stars and short months parse strictly; a malformed day
  returns None so the crawl records it as an empty hole instead of corrupting
  the warehouse.

Storage: one monthly parquet per underlying:
  {out_dir}/{UNDERLYING}/{YYYY-MM}.parquet
  columns timestamp/Open/High/Low/Close/Volume, natural key (timestamp),
  idempotent keep=last merge — re-running the same (underlying, day) updates
  rows. Separate from storage/parquet/fno_chain/eod/ (chain snapshots); this
  is spot index bars.
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
    "NIFTY": "/nifty/php-files/nifty1minchart.php",
    "BANKNIFTY": "/banknifty/php-files/bank-nifty-1min-chart-backend.php",
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


def _get_json(url: str, timeout: int = 30) -> object | None:
    for attempt in range(MAX_RETRIES):
        _pace()
        try:
            r = requests.get(url, headers=UA, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # network / 5xx / malformed JSON
            logger.warning("[tradingtick_1min] %s failed (attempt %s): %s",
                           url, attempt + 1, exc)
            time.sleep(1.5 * (attempt + 1))
    return None


def _unwrap(payload: object, key: str) -> list:
    """Tolerate both bare-list and {"<key>": [...]} response shapes."""
    if isinstance(payload, dict):
        v = payload.get(key)
        return v if isinstance(v, list) else []
    return payload if isinstance(payload, list) else []


def _endpoint(underlying: str) -> str:
    u = underlying.upper()
    if u not in _ENDPOINTS:
        raise ValueError(f"unsupported underlying {underlying!r}")
    return BASE + _ENDPOINTS[u]


def list_years(underlying: str) -> list[str]:
    data = _get_json(_endpoint(underlying) + "?action=years")
    return [str(y) for y in _unwrap(data, "years")]


def list_months(underlying: str, year: str) -> list[str]:
    """Short month names ("Jan".."Dec") — the format the dates/candle calls need."""
    data = _get_json(f"{_endpoint(underlying)}?action=months&year={year}")
    months = []
    for m in _unwrap(data, "months"):
        if isinstance(m, dict):
            v = m.get("value")
            if v:
                months.append(str(v))
        else:
            months.append(str(m))
    # normalize to the canonical short form ("Jan", not "01" or "1")
    by_lower = {x.lower(): x for x in _MONTH_SHORT}
    by_num = {i + 1: x for i, x in enumerate(_MONTH_SHORT)}
    out = []
    for m in months:
        key = m.lower()[:3]
        if key in by_lower:
            out.append(by_lower[key])
        elif m.isdigit():
            n = int(m)
            if n in by_num:
                out.append(by_num[n])
    return out


def list_dates(underlying: str, year: str, month: str) -> list[str]:
    data = _get_json(
        f"{_endpoint(underlying)}?action=dates&year={year}&month={month}"
    )
    return [str(d) for d in _unwrap(data, "dates")]


def _to_ist_naive(epoch_s: int) -> pd.Timestamp:
    return pd.Timestamp(int(epoch_s), unit="s", tz="UTC").tz_convert(
        "Asia/Kolkata"
    ).tz_localize(None)


def fetch_day(
    underlying: str,
    trade_date: str,
    tf: int = 1,
) -> pd.DataFrame | None:
    """Return one trading day of 1-minute bars for `underlying`.

    Output: index = naive IST bar-open (name "timestamp"); columns
    Open/High/Low/Close/Volume where Volume is all-NaN (the source provides
    no volume — it is never fabricated). None on an empty or malformed day.
    """
    u = underlying.upper()
    y, m, d = trade_date.split("-")
    month = datetime(int(y), int(m), 1).strftime("%b")
    url = (
        f"{_endpoint(u)}?year={y}&month={month}&date={trade_date}&tf={int(tf)}"
    )
    rows = _get_json(url)
    bars = rows if isinstance(rows, list) else []
    if not bars:
        return None

    timestamps: list[pd.Timestamp] = []
    opens: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    for bar in bars:
        if not isinstance(bar, dict):
            continue
        try:
            ts = _to_ist_naive(int(bar["time"]))
            o = float(bar["open"])
            h = float(bar["high"])
            lo = float(bar["low"])
            c = float(bar["close"])
        except (KeyError, TypeError, ValueError):
            continue
        timestamps.append(ts)
        opens.append(o)
        highs.append(h)
        lows.append(lo)
        closes.append(c)

    if not timestamps:
        return None
    df = pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes},
        index=pd.DatetimeIndex(timestamps, name="timestamp"),
    )
    df["Volume"] = float("nan")
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df


def enumerate_days(
    underlying: str,
    start: date,
    end: date,
) -> Iterator[str]:
    """Yield "YYYY-MM-DD" strings for the covered trading days within
    [start, end] inclusive, walking year -> months -> dates. Days outside the
    window — or in a year/month the source does not serve — are never yielded."""
    u = underlying.upper()
    for year in list_years(u):
        y = int(year)
        if y < start.year or y > end.year:
            continue
        for month in list_months(u, year):
            m_num = _MONTH_SHORT.index(month) + 1
            if (y, m_num) < (start.year, start.month) or (y, m_num) > (end.year, end.month):
                continue
            for d in list_dates(u, year, month):
                d0 = date.fromisoformat(d)
                if start <= d0 <= end:
                    yield d


def _month_parquet(out_dir: str, underlying: str, ts: pd.Timestamp) -> str:
    return os.path.join(out_dir, underlying, f"{ts:%Y-%m}.parquet")


_NATKEY = ["timestamp"]


def _merge_day(path: str, frame: pd.DataFrame) -> int:
    """Idempotent keep=last merge of one day's bars into the month file."""
    df = frame.reset_index()
    df = df[["timestamp", "Open", "High", "Low", "Close", "Volume"]]
    if os.path.exists(path):
        old = pd.read_parquet(path)
        df = pd.concat([old, df], ignore_index=True)
        df = df.drop_duplicates(subset=_NATKEY, keep="last")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df = df.sort_values(_NATKEY)
    df.to_parquet(path, index=False)
    return len(df)


def ingest_range(
    start: date,
    end: date,
    out_dir: str,
    underlyings: Iterable[str] = ("NIFTY", "BANKNIFTY"),
    tf: int = 1,
) -> dict:
    """Ingest [start, end] inclusive from TradingTick into the per-underlying
    1-minute warehouse. Idempotent (keep=last by timestamp). Returns stats."""
    summary = {"days_ok": 0, "days_empty": 0, "errors": 0, "bars_total": 0,
               "skipped_days": []}
    for u in underlyings:
        u = u.upper()
        if u not in _ENDPOINTS:
            logger.warning("[tradingtick_1min] unknown underlying %s — skipped", u)
            continue
        seen: set[str] = set()
        for d in enumerate_days(u, start, end):
            if d in seen:
                continue
            seen.add(d)
            frame = fetch_day(u, d, tf=tf)
            if frame is None or frame.empty:
                summary["days_empty"] += 1
                summary["skipped_days"].append(f"{u} {d}")
                continue
            try:
                n = _merge_day(_month_parquet(out_dir, u, pd.Timestamp(d)), frame)
                summary["bars_total"] += len(frame)
                summary["days_ok"] += 1
            except Exception as exc:  # warehouse write must not kill the crawl
                logger.warning("[tradingtick_1min] %s %s merge failed: %s", u, d, exc)
                summary["errors"] += 1
            if summary["days_ok"] % 100 == 0 and summary["days_ok"]:
                print(f"  {u} {d}: cumulative days {summary['days_ok']:,} "
                      f"bars {summary['bars_total']:,}", flush=True)
    return summary


if __name__ == "__main__":
    import sys
    s = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2015, 1, 1)
    e = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()
    out = sys.argv[3] if len(sys.argv) > 3 else r"D:\MJONAI\storage\parquet\tradingtick_1min"
    print(ingest_range(s, e, out))