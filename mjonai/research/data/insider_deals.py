"""
Module: research/data/insider_deals.py

Purpose: NSE bulk + block deal ingest — official daily CSVs (no scraping).

Endpoints (both live, verified 2026-10-14):
  bulk  https://nsearchives.nseindia.com/content/equities/bulk.csv
  block https://nsearchives.nseindia.com/content/equities/block.csv
Columns: Date, Symbol, Security Name, Client Name, Buy/Sell, Quantity Traded,
Trade Price / Wght. Avg. Price (+ Remarks on bulk). A "NO RECORDS" body is a
valid empty day, not an error.

Scope honesty (stated plainly): these feeds cover large client-level trades
only. Promoter-pledge % and shareholding still need SHP filings — no free
source — so pledge stays feed-gated (None) and this module never claims it.
The URLs serve the CURRENT day only (no date parameter, no history): the
warehouse therefore grows forward from first fetch; backfill of past days is
impossible by construction and never faked.

Storage: storage/parquet/insider_deals/{YYYY-MM}.parquet, natural key
(trade_date, symbol, client, side), keep=last, idempotent merge.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BULK_URL = "https://nsearchives.nseindia.com/content/equities/bulk.csv"
BLOCK_URL = "https://nsearchives.nseindia.com/content/equities/block.csv"
PACE_SECONDS = 0.4
DEFAULT_INSIDER_DIR = os.path.join("storage", "parquet", "insider_deals")

_NATKEY = ["trade_date", "symbol", "client", "side"]


def _fetch_csv(url: str, timeout: int = 30) -> Optional[List[Dict[str, Any]]]:
    """Fetch one deals CSV into normalized rows, or None on empty/failure."""
    import requests

    try:
        resp = requests.get(url, headers=UA, timeout=timeout)
    except Exception as exc:
        logger.warning("[insider_deals] fetch failed for %s: %s", url, exc)
        return None
    if not resp.ok:
        logger.warning("[insider_deals] HTTP %s for %s", resp.status_code, url)
        return None
    try:
        text = resp.content.decode("utf-8", errors="ignore")
        lines = [ln for ln in text.strip().splitlines() if ln.strip()]
        if len(lines) < 2 or lines[1].startswith("NO RECORDS"):
            return None
        header = [h.strip() for h in lines[0].split(",")]
        rows = []
        for line in lines[1:]:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) != len(header):
                continue
            rec = dict(zip(header, parts))
            try:
                import pandas as _pd
                day = _pd.to_datetime(str(rec.get("Date", "")).strip(),
                                      dayfirst=True).date().isoformat()
                rows.append({
                    "trade_date": day,
                    "symbol": str(rec.get("Symbol", "")).strip().upper(),
                    "client": str(rec.get("Client Name", "")).strip(),
                    "side": str(rec.get("Buy/Sell", "")).strip().upper(),
                    "quantity": int(float(rec.get("Quantity Traded") or 0)),
                    "price": float((rec.get("Trade Price / Wght. Avg. Price") or 0)),
                })
            except (TypeError, ValueError):
                continue
        return rows or None
    except Exception as exc:
        logger.warning("[insider_deals] parse failed for %s: %s", url, exc)
        return None


def _month_path(out_dir: str, day: date) -> Path:
    return Path(out_dir) / f"{day:%Y-%m}.parquet"


def _resolve_dir(out_dir: Optional[str]) -> Path:
    return Path(out_dir) if out_dir else Path(DEFAULT_INSIDER_DIR)


def merge_rows(rows: List[Dict[str, Any]],
               out_dir: Optional[str] = None) -> int:
    """Idempotent natural-key keep=last merge. Returns stored row count."""
    import pandas as pd

    if not rows:
        return 0
    out_dir = str(_resolve_dir(out_dir))
    frame = pd.DataFrame(rows)
    months = 0
    for month, group in frame.groupby(pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m")):
        path = Path(out_dir) / f"{month}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            try:
                old = pd.read_parquet(path)
                group = pd.concat([old, group], ignore_index=True)
            except Exception as exc:
                logger.warning("[insider_deals] month unreadable, overwriting: %s", exc)
        group = group.drop_duplicates(subset=_NATKEY, keep="last")
        group.to_parquet(path, index=False)
        months += 1
    return len(frame)


def refresh_insider_deals(out_dir: Optional[str] = None) -> Dict[str, Any]:
    """Scheduler job body: fetch both files, merge, never raises.

    An empty day on either file is normal (block deals often have none) —
    recorded as zero, never as an error and never as fabricated rows.
    """
    summary: Dict[str, Any] = {"bulk_rows": 0, "block_rows": 0, "status": "ok"}
    try:
        bulk = _fetch_csv(BULK_URL)
        time.sleep(PACE_SECONDS)
        block = _fetch_csv(BLOCK_URL)
        if bulk:
            merge_rows(bulk, out_dir)
            summary["bulk_rows"] = len(bulk)
        if block:
            merge_rows(block, out_dir)
            summary["block_rows"] = len(block)
        if not bulk and not block:
            summary["status"] = "empty (no deals published)"
    except Exception as exc:
        logger.warning("[insider_deals] refresh failed: %s", exc)
        summary["status"] = f"error: {exc}"
    return summary


def get_symbol_deals(symbol: str, days: int = 10,
                     out_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Recent deals for one symbol (newest first), [] when none/unknown."""
    import pandas as pd

    clean = str(symbol or "").strip().upper().replace(".NS", "").replace(".BO", "")
    if not clean:
        return []
    root = _resolve_dir(out_dir)
    if not root.is_dir():
        return []
    frames = []
    for path in sorted(root.glob("*.parquet"), reverse=True)[:4]:
        try:
            frames.append(pd.read_parquet(path))
        except Exception:
            continue
    if not frames:
        return []
    import pandas as _pd
    df = _pd.concat(frames, ignore_index=True)
    df = df[df["symbol"].astype(str).str.upper() == clean]
    if df.empty:
        return []
    df = df.sort_values("trade_date", ascending=False).head(max(1, int(days * 3)))
    return [{"trade_date": str(r["trade_date"]), "client": str(r["client"]),
             "side": str(r["side"]), "quantity": int(r["quantity"]),
             "price": float(r["price"])} for _, r in df.iterrows()]


def describe_symbol_deals(symbol: str, days: int = 10,
                          out_dir: Optional[str] = None) -> Optional[str]:
    """One-line insider-activity summary for Bear context, or None when the
    registry holds nothing for the symbol (caller keeps 'None known')."""
    deals = get_symbol_deals(symbol, days, out_dir)
    if not deals:
        return None
    buys = [d for d in deals if d["side"] == "BUY"]
    sells = [d for d in deals if d["side"] == "SELL"]
    bits = []
    if buys:
        top = max(buys, key=lambda d: d["quantity"])
        bits.append(f"{top['client']} bought {top['quantity']:,} @ Rs.{top['price']:.2f} ({top['trade_date']})")
    if sells:
        top = max(sells, key=lambda d: d["quantity"])
        bits.append(f"{top['client']} sold {top['quantity']:,} @ Rs.{top['price']:.2f} ({top['trade_date']})")
    return "Bulk/block: " + "; ".join(bits) if bits else None
