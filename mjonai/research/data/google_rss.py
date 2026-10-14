"""
Module: research/data/google_rss.py

Purpose: Google News RSS keyless headline reader (no key, no account) — the
VERIFIED live path for the Bear prompt's news_red_flags mechanism.

Why RSS and not GDELT: api.gdeltproject.org answered HTTP 429 from both this
machine and the owner machine (2026-10-14), while news.google.com/rss serves
~100 items per query with title/pubDate/source/link (verified live the same
night — Economic Times et al, India edition). Same red-flag contract as the
staged gdelt_news module (phrases mirror the Bear prompt's documented VETO
triggers); the flagger itself is shared, not duplicated.

Flow (never in the hot path): a twice-daily scheduler refresh stores capped
headlines to storage/research/news_headlines.json; the pipeline matches the
debated symbol/root against stored titles and sets news_red_flags (flagged
only) on the Bear context. Absent store or no match leaves the key unset
(Bear renders "None detected"). A headline merely containing a keyword is
NOT a verdict — the Bear LLM still judges; the feed only surfaces candidates.
"""
from __future__ import annotations

import html
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
SEARCH_BASE = "https://news.google.com/rss/search"
STORE_PATH = Path("storage") / "research" / "news_headlines.json"
QUERIES = ("NIFTY NSE", "Sensex BSE", "RBI SEBI stock market")
MAX_PER_QUERY = 30
STORE_CAP = 200
PACE_SECONDS = 1.0


def _fetch_rss(query: str, timeout: int = 30) -> List[Dict[str, Any]]:
    """One RSS query into headline dicts (stdlib only). [] on any failure."""
    import urllib.parse
    import urllib.request
    import xml.etree.ElementTree as ET

    try:
        params = urllib.parse.urlencode(
            {"q": query, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"})
        req = urllib.request.Request(f"{SEARCH_BASE}?{params}", headers=UA)
        raw = urllib.request.urlopen(req, timeout=timeout).read().decode(
            "utf-8", errors="ignore")
        root = ET.fromstring(raw)
    except Exception as exc:
        logger.warning("[google_rss] fetch failed for query %r: %s", query, exc)
        return []
    out = []
    for item in root.iter("item"):
        try:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not title or not link:
                continue
            pub = (item.findtext("pubDate") or "").strip() or None
            source_el = item.find("source")
            source = (source_el.text or "").strip() if source_el is not None else None
            out.append({
                "title": html.unescape(title),
                "url": link,
                "published": pub,
                "source": source or None,
            })
        except Exception:
            continue
    return out


def refresh_headlines(queries: tuple = QUERIES,
                      store_path: Optional[Path] = None) -> Dict[str, Any]:
    """Scheduler job body: fetch all queries politely, flag, cap, store.
    Never raises. Returns a summary."""
    from mjonai.research.data.gdelt_news import flag_red_flags

    target = Path(store_path) if store_path else STORE_PATH
    summary: Dict[str, Any] = {"queries": 0, "headlines": 0, "flagged": 0,
                               "status": "ok"}
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        seen_urls = set()
        flagged_all: List[Dict[str, Any]] = []
        for i, query in enumerate(queries):
            if i:
                time.sleep(PACE_SECONDS)
            arts = _fetch_rss(query)
            summary["queries"] += 1
            for art in flag_red_flags(arts):
                if art["url"] in seen_urls:
                    continue
                seen_urls.add(art["url"])
                if art.get("red_flags"):
                    flagged_all.append(art)
        flagged_all.sort(key=lambda a: a.get("published") or "", reverse=True)
        flagged_all = flagged_all[:STORE_CAP]
        payload = {"fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                   "queries": list(queries), "flagged": flagged_all}
        tmp = target.with_suffix(".json.part")
        import json
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(target)
        summary["headlines"] = len(seen_urls)
        summary["flagged"] = len(flagged_all)
    except Exception as exc:
        logger.warning("[google_rss] refresh failed: %s", exc)
        summary["status"] = f"error: {exc}"
    return summary


def red_flags_for_symbol(symbol: str, store_path: Optional[Path] = None,
                         limit: int = 5) -> List[str]:
    """Flagged-headline titles mentioning the symbol/root (newest first).
    [] when the store is absent/unreadable — the caller keeps 'None detected'.

    Matching is substring on uppercased titles against the symbol and its
    underlying root (so RELIANCE26AUGFUT matches RELIANCE headlines).
    """
    target = Path(store_path) if store_path else STORE_PATH
    clean = str(symbol or "").strip().upper().replace(".NS", "").replace(".BO", "")
    if not clean or not target.is_file():
        return []
    try:
        import json
        data = json.loads(target.read_text(encoding="utf-8"))
        roots = {clean}
        try:
            from mjonai.strategy.config import extract_underlying_symbol
            roots.add(str(extract_underlying_symbol(clean)).upper())
        except Exception:
            pass
        hits = []
        for art in (data.get("flagged") or []):
            title = str((art or {}).get("title") or "")
            upper = title.upper()
            if any(r and r in upper for r in roots):
                flags = ", ".join((art.get("red_flags") or []))
                hits.append(f"{title} [{flags}]")
                if len(hits) >= max(1, limit):
                    break
        return hits
    except Exception:
        return []
