"""
Module: intelligence/news_catalyst.py
Purpose: SOTA Real-Time Corporate Catalyst & News Sentiment Sentry for Indian Equities.
         Parses Google Finance & Indian market RSS feeds with zero API cost to detect
         high-impact dealbreaker headlines (auditor resignations, SEBI raids, promoter
         pledge defaults, forensic audits) and positive breakout catalysts (USFDA approvals,
         mega order wins, PLI scheme allocations).
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import logging
import re
from typing import Dict, List, Any, Optional, Tuple, Set
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

DEFAULT_NEWS_TIMEOUT = 4.0

# ── High-Impact Dealbreakers (Immediate Hard Veto Signals) ──
DEALBREAKER_KEYWORDS = {
    "auditor resigns",
    "auditor resignation",
    "sebi ban",
    "sebi order",
    "sebi notice",
    "sebi investigation",
    "ed raid",
    "cbi raid",
    "cbi probe",
    "forensic audit",
    "accounting fraud",
    "insolvency",
    "nclt",
    "promoter pledge invocation",
    "pledge default",
    "tax evasion",
    "rating downgrade to default",
    "siphoning of funds",
}

# ── Bearish Headwinds ──
BEARISH_KEYWORDS = {
    "downgrade",
    "profit drops",
    "net loss",
    "margin contraction",
    "promoter sells",
    "insider selling",
    "strike at plant",
    "usfda form 483",
    "warning letter",
    "penalty",
    "lawsuit",
    "weak demand",
    "price cut",
}

# ── Bullish Catalysts ──
BULLISH_KEYWORDS = {
    "usfda approval",
    "major order win",
    "wins order",
    "secures order",
    "blockbuster profit",
    "profit surges",
    "revenue jumps",
    "bonus issue",
    "stock split",
    "capacity expansion",
    "pli scheme",
    "upgrade by",
    "target raised",
    "debt free",
    "promoter buys",
}


@dataclass(frozen=True)
class NewsSentimentResult:
    """Immutable contract representing real-time news & corporate catalyst analysis."""
    symbol: str
    sentiment: str  # "CRITICAL_DEALBREAKER", "BEARISH_HEADWIND", "NEUTRAL", "BULLISH_CATALYST"
    score: float  # -1.0 (Extreme Bearish) to +1.0 (Extreme Bullish)
    is_dealbreaker: bool
    red_flags: List[str]
    bullish_catalysts: List[str]
    headlines: List[str]
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def parse_rss_feed(xml_text: str) -> List[str]:
    """Parse RSS XML into a list of clean headline strings."""
    headlines: List[str] = []
    if not xml_text:
        return headlines

    try:
        root = ET.fromstring(xml_text)
        for item in root.findall(".//item"):
            title = item.find("title")
            if title is not None and title.text:
                clean_title = re.sub(r"<[^>]+>", "", title.text).strip()
                headlines.append(clean_title)
    except Exception as e:
        logger.debug(f"[NewsCatalyst] XML parse error: {e}")

    return headlines


def analyze_headlines(symbol: str, headlines: List[str]) -> NewsSentimentResult:
    """
    Classify headlines into sentiment regime and extract dealbreakers & catalysts.
    """
    if not headlines:
        return NewsSentimentResult(
            symbol=symbol,
            sentiment="NEUTRAL",
            score=0.0,
            is_dealbreaker=False,
            red_flags=[],
            bullish_catalysts=[],
            headlines=[],
        )

    red_flags: List[str] = []
    bull_catalysts: List[str] = []
    dealbreakers: List[str] = []

    pos_count = 0
    neg_count = 0

    for h in headlines:
        h_lower = h.lower()
        # Check dealbreakers
        for kw in DEALBREAKER_KEYWORDS:
            if kw in h_lower:
                dealbreakers.append(f"DEALBREAKER: {h}")
                red_flags.append(h)
                neg_count += 3

        # Check bearish keywords
        for kw in BEARISH_KEYWORDS:
            if kw in h_lower:
                red_flags.append(h)
                neg_count += 1

        # Check bullish keywords
        for kw in BULLISH_KEYWORDS:
            if kw in h_lower:
                bull_catalysts.append(h)
                pos_count += 1

    total_mentions = max(1, pos_count + neg_count)
    raw_score = (pos_count - neg_count) / total_mentions
    score = round(max(-1.0, min(1.0, raw_score)), 2)

    is_dealbreaker = len(dealbreakers) > 0

    if is_dealbreaker:
        sentiment = "CRITICAL_DEALBREAKER"
    elif score <= -0.30:
        sentiment = "BEARISH_HEADWIND"
    elif score >= 0.30:
        sentiment = "BULLISH_CATALYST"
    else:
        sentiment = "NEUTRAL"

    return NewsSentimentResult(
        symbol=symbol,
        sentiment=sentiment,
        score=score,
        is_dealbreaker=is_dealbreaker,
        red_flags=list(dict.fromkeys(red_flags))[:5],
        bullish_catalysts=list(dict.fromkeys(bull_catalysts))[:5],
        headlines=headlines[:10],
    )


def fetch_symbol_news(
    symbol: str,
    limit: int = 10,
    timeout: float = DEFAULT_NEWS_TIMEOUT,
) -> NewsSentimentResult:
    """
    Fetch and analyze real-time financial news for an Indian stock symbol.
    Uses Google News India RSS feed with fail-safe error isolation.
    """
    clean_sym = symbol.replace(".NS", "").replace("-EQ", "").strip()
    encoded_query = f"{clean_sym}+share+price+NSE+stock"
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"

    try:
        import httpx
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                headlines = parse_rss_feed(resp.text)
                return analyze_headlines(clean_sym, headlines[:limit])
    except Exception as e:
        logger.debug(f"[NewsCatalyst] Failed to fetch news for {symbol}: {e}")

    # Fallback to clean neutral result
    return NewsSentimentResult(
        symbol=clean_sym,
        sentiment="NEUTRAL",
        score=0.0,
        is_dealbreaker=False,
        red_flags=[],
        bullish_catalysts=[],
        headlines=[],
    )
