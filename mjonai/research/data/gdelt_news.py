"""
Module: research/data/gdelt_news.py

Purpose: GDELT DOC 2.1 keyless news reader (no key, no account) — candidate
feed for the Bear prompt's news_red_flags mechanism, which exists in the
prompt contract but was never fed (pipeline never supplies headlines).

STATUS — UNVERIFIED LIVE (2026-10-14): api.gdeltproject.org answered HTTP 429
to every probe from this machine (twice, 20s apart), so the response parser
below is written against GDELT's DOCUMENTED artlist shape and unit-tested on
canned fixtures — it has never seen a real response. Nothing in the engine
calls this module yet (no scheduler slot, no Bear wiring): it activates only
after one successful live fetch from the owner machine (see verify_live()).
Shipping a parser without a consumer is deliberate — the alternative (wiring
an unverified shape into the debate) is fabrication-adjacent.

Documented shape (GDELT DOC 2.1, mode=artlist, format=json):
  {"articles": [{"url": ..., "url_mobile": ..., "title": ..., "seendate": ...,
                 "socialimage": ..., "domain": ..., "language": ...,
                 "sourcecountry": ...}, ...], ...}
Every field is optional to us: an article counts only with a non-blank string
title AND url; everything else degrades to None. seendate (YYYYMMDDHHMMSS) is
parsed best-effort; unparseable dates keep the row with date=None rather than
dropping real headlines.

Red-flag contract (mirrors the Bear prompt's documented triggers):
  auditor resignation, SEBI action, raid, fraud (+ CBI/ED/SFIO/scam/default).
A headline containing any phrase (case-insensitive) is a red flag. Keyword
matching over third-party headlines — disclosed as such, never a verdict.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DOC_BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

RED_FLAG_PHRASES = (
    "auditor resignation", "auditor resigns", "resignation of auditor",
    "sebi action", "sebi bars", "sebi imposes", "raid", "raided", "fraud",
    "cbi", "enforcement directorate", "sfio", "scam", "default",
    "insolvency", "nclt",
    # Extended 2026-10-14 from market_announcements/idea_rules.py (MIT,
    # Regulatory & Legal + Governance negatives only — positive-flavored
    # phrases like "approval" or "appointment" are deliberately excluded so
    # good news is never flagged as a red flag).
    "litigation", "lawsuit", "show cause notice", "penalty imposed",
    "insider trading", "pledge of shares", "rating downgrade",
)

_verified_live = False


def _parse_articles(payload: Any) -> List[Dict[str, Any]]:
    """Strict-shape parse: only documented fields, blanks refused."""
    if not isinstance(payload, dict):
        return []
    raw = payload.get("articles")
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        url = item.get("url") or item.get("url_mobile")
        if not isinstance(title, str) or not title.strip():
            continue
        if not isinstance(url, str) or not url.strip():
            continue
        seen = None
        raw_seen = item.get("seendate")
        if isinstance(raw_seen, str) and raw_seen.strip():
            for fmt in ("%Y%m%d%H%M%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    seen = datetime.strptime(raw_seen.strip(), fmt).replace(
                        tzinfo=timezone.utc).isoformat()
                    break
                except ValueError:
                    continue
        domain = item.get("domain")
        out.append({
            "title": title.strip(),
            "url": url.strip(),
            "seendate": seen,
            "domain": str(domain).strip() if isinstance(domain, str) else None,
        })
    return out


def fetch_headlines(query: str, maxrecords: int = 25,
                    timespan: str = "24h",
                    timeout: int = 30) -> List[Dict[str, Any]]:
    """Fetch raw headlines for a GDELT query. [] on any failure (fail-closed);
    never raises. Polite single call — callers pace repeated queries."""
    import requests

    q = str(query or "").strip()
    if not q:
        return []
    params = {"query": q, "mode": "artlist", "format": "json",
              "maxrecords": max(1, min(int(maxrecords), 250)),
              "timespan": timespan, "sort": "datedesc"}
    try:
        resp = requests.get(DOC_BASE, params=params, headers=UA, timeout=timeout)
        if resp.status_code == 429:
            logger.warning("[gdelt_news] rate-limited (429) — backing off, no data")
            return []
        if not resp.ok:
            logger.warning("[gdelt_news] HTTP %s for query %r", resp.status_code, q)
            return []
        return _parse_articles(resp.json())
    except Exception as exc:
        logger.warning("[gdelt_news] fetch failed for query %r: %s", q, exc)
        return []


def flag_red_flags(headlines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach matched red-flag phrases; unflagged headlines pass through
    untouched (callers decide what absence means — never 'all clear')."""
    out = []
    for art in headlines or []:
        title = str((art or {}).get("title") or "")
        lowered = title.lower()
        hits = [p for p in RED_FLAG_PHRASES if p in lowered]
        row = dict(art or {})
        row["red_flags"] = hits
        out.append(row)
    return out


def verify_live(query: str = "NIFTY") -> Dict[str, Any]:
    """One-shot live verification for the owner machine: single fetch,
    reports shape conformance. Run once; on success the module is cleared
    for wiring (scheduler slot + Bear feed)."""
    global _verified_live
    arts = fetch_headlines(query, maxrecords=5)
    ok = len(arts) > 0
    _verified_live = ok
    return {"live_ok": ok, "articles": len(arts),
            "sample": arts[0] if arts else None,
            "note": "GDELT reachable and shape-conformant" if ok
                    else "no data — still gated, nothing wired"}


def is_live_verified() -> bool:
    """Gate for future wiring: False until verify_live() succeeds once."""
    return _verified_live
