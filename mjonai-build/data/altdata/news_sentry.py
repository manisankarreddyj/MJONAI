"""
Module: data/altdata/news_sentry.py
Purpose: SOTA Real-Time Financial News & Black Swan Wire Event Sentry.
         Monitors live corporate, regulatory, and geopolitical breaking headlines:
         - Severity Scoring (-100 Extreme Disaster to +100 Massive Catalyst)
         - Black Swan Freeze Sentry:
           * Severity <= -80 -> Immediate Emergency Capital Freeze (No new trades permitted)
           * -80 < Severity <= -40 -> Defensive Caution Alert (Halve position sizes)
           * Normal Headlines -> Standard Operation
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging
import re
import threading
from typing import Any, Dict, List, Optional

from core.time_utils import now_ist

logger = logging.getLogger(__name__)


class NewsImpactLevel(str, Enum):
    BLACK_SWAN_CRITICAL = "BLACK_SWAN_CRITICAL"  # Shock >= 80% negative (Emergency Freeze)
    DEFENSIVE_CAUTION   = "DEFENSIVE_CAUTION"    # Negative regulatory / earnings shock
    NEUTRAL_NOISE       = "NEUTRAL_NOISE"        # Normal daily noise
    BULLISH_CATALYST    = "BULLISH_CATALYST"     # Major positive policy / earnings beat


@dataclass(frozen=True)
class NewsHeadlineAlert:
    """
    Immutable Real-Time News Event Contract.
    """
    headline: str
    source: str
    impact_score: int             # -100 to +100
    impact_level: NewsImpactLevel
    is_emergency_freeze_active: bool
    affected_symbol: Optional[str]
    timestamp: datetime
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "headline": self.headline,
            "source": self.source,
            "impact_score": self.impact_score,
            "impact_level": self.impact_level.value,
            "is_emergency_freeze_active": self.is_emergency_freeze_active,
            "affected_symbol": self.affected_symbol,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
        }


# Critical Black Swan Keywords Regex
_BLACK_SWAN_KEYWORDS = [
    r"\b(WAR|MISSILE|INVASION|ATTACK|EXPLOSION|TERROR)\b",
    r"\b(SEBI BANS|RBI RESTRICTION|RBI CURB|ED RAID|FRAUD|SCAM)\b",
    r"\b(BANKRUPTCY|DEFAULT|INSOLVENCY|HALT TRADING|CIRCUIT DOWN)\b",
    r"\b(EMERGENCY RATE HIKE|SANCTION|LOCKDOWN)\b",
]

_news_lock = threading.RLock()
_RECENT_ALERTS: List[NewsHeadlineAlert] = []


def analyze_news_headline(
    headline: str,
    source: str = "WIRE_FEED",
    symbol: Optional[str] = None,
) -> NewsHeadlineAlert:
    """
    Analyze headline text and calculate impact score and emergency freeze state.
    """
    now = now_ist()
    h_upper = headline.strip().upper()

    score = 0
    # 1. Check for Black Swan keywords
    for pattern in _BLACK_SWAN_KEYWORDS:
        if re.search(pattern, h_upper):
            score -= 85
            break

    if "FRAUD" in h_upper or "RAID" in h_upper or "DEFAULT" in h_upper:
        score = min(score, -90)
    elif "UPGRADE" in h_upper or "RECORD PROFIT" in h_upper or "ORDER WIN" in h_upper:
        score = 65

    # 2. Classify Impact Level
    if score <= -80:
        level = NewsImpactLevel.BLACK_SWAN_CRITICAL
        freeze = True
        msg = f"BLACK SWAN NEWS ALERT: '{headline}' (Score: {score} | Emergency Trade Freeze Active)"
    elif score <= -40:
        level = NewsImpactLevel.DEFENSIVE_CAUTION
        freeze = False
        msg = f"Defensive News Caution: '{headline}' (Score: {score})"
    elif score >= 50:
        level = NewsImpactLevel.BULLISH_CATALYST
        freeze = False
        msg = f"Bullish Catalyst: '{headline}' (Score: +{score})"
    else:
        level = NewsImpactLevel.NEUTRAL_NOISE
        freeze = False
        msg = f"Neutral News: '{headline}'"

    alert = NewsHeadlineAlert(
        headline=headline,
        source=source,
        impact_score=score,
        impact_level=level,
        is_emergency_freeze_active=freeze,
        affected_symbol=symbol.upper() if symbol else None,
        timestamp=now,
        message=msg,
    )

    with _news_lock:
        _RECENT_ALERTS.append(alert)
        if len(_RECENT_ALERTS) > 50:
            _RECENT_ALERTS.pop(0)

    if freeze:
        logger.critical(f"[news_sentry] {msg}")

    return alert


def is_emergency_news_freeze_active() -> bool:
    """Check if any active black swan news freeze has been triggered today."""
    with _news_lock:
        for a in reversed(_RECENT_ALERTS):
            if a.is_emergency_freeze_active:
                return True
    return False
