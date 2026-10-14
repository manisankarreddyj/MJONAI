"""
Module: research/data/cm_delivery.py

Purpose: NSE cash-market (CM) delivery statistics — official daily bhavcopy
ingest + in-memory registry feed for delivery_tracker.

Clean-room extension of the F&O bhavcopy pattern (mjonai/research/data/fno_eod.py):
same official-archives source class (nsearchives.nseindia.com, no scraping),
same natural-key keep=last merge discipline, same polite pacing. The CM file
carries DELIV_QTY + DELIV_PER per symbol — the delivery evidence the tracker
module was built for but never fed.

Honesty contract: EQ series only (BE/SM/others excluded — different settlement
semantics); a missing/unpublished day returns None (never zeros); the registry
is fed only from fetched rows, never synthesized.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
NSEARCHIVES_CM = "https://nsearchives.nseindia.com/products/content/"
PACE_SECONDS = 0.4
DEFAULT_CM_DELIVERY_DIR = os.path.join("storage", "parquet", "cm_delivery")

_NATKEY = ["trade_date", "symbol"]


def bhavcopy_url(day: date) -> str:
    """Official CM full-bhavcopy URL for one date (DDMMYYYY naming)."""
    return NSEARCHIVES_CM + f"sec_bhavdata_full_{day:%d%m%Y}.csv"


def fetch_cm_day(day: date, timeout: int = 30) -> Optional[List[Dict[str, Any]]]:
    """Fetch + parse one CM bhavcopy day into EQ delivery rows.

    Returns [{trade_date, symbol, traded_qty, deliverable_qty, deliv_per}] or
    None when the day is unpublished (holiday/weekend) or unreadable. Only
    SERIES == EQ rows are kept.
    """
    import requests

    try:
        resp = requests.get(bhavcopy_url(day), headers=UA, timeout=timeout)
    except Exception as exc:
        logger.warning("[cm_delivery] fetch failed for %s: %s", day.isoformat(), exc)
        return None
    if resp.status_code == 404:
        return None
    if not resp.ok:
        logger.warning("[cm_delivery] HTTP %s for %s", resp.status_code, day.isoformat())
        return None
    try:
        text = resp.content.decode("utf-8", errors="ignore")
        lines = text.strip().splitlines()
        if not lines:
            return None
        header = [h.strip() for h in lines[0].split(",")]
        rows = []
        for line in lines[1:]:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) != len(header):
                continue
            rec = dict(zip(header, parts))
            if rec.get("SERIES") != "EQ":
                continue
            try:
                rows.append({
                    "trade_date": day.isoformat(),
                    "symbol": str(rec.get("SYMBOL", "")).strip().upper(),
                    "traded_qty": int(float(rec.get("TTL_TRD_QNTY") or 0)),
                    "deliverable_qty": int(float(rec.get("DELIV_QTY") or 0)),
                    "deliv_per": float(rec.get("DELIV_PER") or 0),
                })
            except (TypeError, ValueError):
                continue
        return rows or None
    except Exception as exc:
        logger.warning("[cm_delivery] parse failed for %s: %s", day.isoformat(), exc)
        return None


def _month_path(out_dir: str, day: date) -> Path:
    return Path(out_dir) / f"{day:%Y-%m}.parquet"


def merge_day(rows: List[Dict[str, Any]], out_dir: str = DEFAULT_CM_DELIVERY_DIR) -> int:
    """Idempotent natural-key keep=last merge of one day's rows. Returns row count."""
    import pandas as pd

    if not rows:
        return 0
    day = rows[0]["trade_date"]
    path = _month_path(out_dir, date.fromisoformat(day))
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    if path.exists():
        try:
            old = pd.read_parquet(path)
            frame = pd.concat([old, frame], ignore_index=True)
        except Exception as exc:
            logger.warning("[cm_delivery] existing month unreadable, overwriting: %s", exc)
    frame = frame.drop_duplicates(subset=_NATKEY, keep="last")
    frame.to_parquet(path, index=False)
    return len(frame)


def backfill_range(start: date, end: date,
                   out_dir: str = DEFAULT_CM_DELIVERY_DIR) -> Dict[str, Any]:
    """Crawl [start, end] inclusive with polite pacing. Resume-safe: each day
    merges idempotently, so re-runs only fill holes."""
    summary: Dict[str, Any] = {"days_total": 0, "days_fetched": 0,
                               "days_empty": 0, "errors": 0, "rows_total": 0}
    day = start
    first = True
    while day <= end:
        summary["days_total"] += 1
        if not first:
            time.sleep(PACE_SECONDS)
        first = False
        try:
            rows = fetch_cm_day(day)
        except Exception as exc:
            logger.warning("[cm_delivery] error on %s: %s", day.isoformat(), exc)
            summary["errors"] += 1
            day += timedelta(days=1)
            continue
        if not rows:
            summary["days_empty"] += 1
        else:
            try:
                merge_day(rows, out_dir)
                summary["days_fetched"] += 1
                summary["rows_total"] += len(rows)
            except Exception as exc:
                logger.warning("[cm_delivery] merge failed on %s: %s", day.isoformat(), exc)
                summary["errors"] += 1
        day += timedelta(days=1)
    return summary


def refresh_delivery_cache(out_dir: str = DEFAULT_CM_DELIVERY_DIR,
                           lookback_days: int = 5) -> Dict[str, Any]:
    """Scheduler job body: resolve the latest published bhavcopy (today back
    up to `lookback_days`, covering weekends/holidays + publish lag), merge it,
    and feed every EQ row into the delivery_tracker registry.

    Returns a summary dict (never raises — a failed refresh must not break
    the scheduler lane). An unfed symbol stays absent from the registry
    (fail-closed: get_delivery_snapshot returns None, never a baseline).
    """
    from mjonai.core.time_utils import today_ist
    from mjonai.data.market.delivery_tracker import register_delivery_data

    summary: Dict[str, Any] = {"as_of": None, "symbols": 0, "status": "empty"}
    try:
        today = today_ist()
        rows = None
        for back in range(max(1, lookback_days)):
            day = today - timedelta(days=back)
            rows = fetch_cm_day(day)
            if rows:
                merge_day(rows, out_dir)
                summary["as_of"] = day.isoformat()
                break
            time.sleep(PACE_SECONDS)
        if not rows:
            summary["status"] = "no published bhavcopy in window"
            return summary
        fed = 0
        for r in rows:
            try:
                register_delivery_data(r["symbol"], r["traded_qty"],
                                       r["deliverable_qty"], r["trade_date"])
                fed += 1
            except Exception:
                continue
        summary["symbols"] = fed
        summary["status"] = "ok"
    except Exception as exc:
        logger.warning("[cm_delivery] refresh failed: %s", exc)
        summary["status"] = f"error: {exc}"
    return summary
