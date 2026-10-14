"""
Module: data/derivatives/fo_ban_sentry.py
Purpose: Real-Time Market-Wide Position Limit (MWPL) Utilization & F&O Ban Sentry.
         Guards derivative execution against trading banned securities or entering near-ban traps:
         - MWPL >= 95% -> Active F&O Ban (Orders STRICTLY BLOCKED by Exchange)
         - 85% <= MWPL < 95% -> Ban Danger Zone (Entry Sentry Warning)
         - MWPL < 85% -> Normal Trading Permitted
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Set

from mjonai.core.time_utils import now_ist

logger = logging.getLogger(__name__)


class BanStatus(str, Enum):
    BANNED      = "BANNED"       # In active F&O ban (MWPL >= 95%)
    DANGER_ZONE = "DANGER_ZONE"  # Near ban threshold (85% <= MWPL < 95%)
    SAFE        = "SAFE"         # Normal operation (MWPL < 85%)


@dataclass(frozen=True)
class FOBanSnapshot:
    """
    Immutable F&O Ban & MWPL Utilization Assessment.
    """
    symbol: str
    mwpl_utilization_pct: float
    ban_status: BanStatus
    is_trade_allowed: bool
    timestamp: datetime
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "mwpl_utilization_pct": round(self.mwpl_utilization_pct, 2),
            "ban_status": self.ban_status.value,
            "is_trade_allowed": self.is_trade_allowed,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
        }


# In-memory MWPL registry
_MWPL_UTILIZATION_CACHE: Dict[str, float] = {}
_ACTIVE_BAN_LIST: Set[str] = set()
_ban_lock = threading.RLock()


def update_mwpl_utilization(symbol: str, mwpl_pct: float) -> None:
    """Register daily MWPL utilization percentage for a security."""
    clean = symbol.strip().upper()
    with _ban_lock:
        _MWPL_UTILIZATION_CACHE[clean] = mwpl_pct
        if mwpl_pct >= 95.0:
            _ACTIVE_BAN_LIST.add(clean)
        elif clean in _ACTIVE_BAN_LIST and mwpl_pct < 80.0:
            _ACTIVE_BAN_LIST.remove(clean)


def check_fo_ban_status(symbol: str) -> FOBanSnapshot:
    """
    Evaluate if an instrument is in the F&O Ban period or near the cutoff limit.
    """
    clean = symbol.strip().upper()
    now = now_ist()

    with _ban_lock:
        util = _MWPL_UTILIZATION_CACHE.get(clean, 0.0)
        is_banned = clean in _ACTIVE_BAN_LIST or util >= 95.0

    if is_banned:
        return FOBanSnapshot(
            symbol=clean,
            mwpl_utilization_pct=util if util > 0 else 95.0,
            ban_status=BanStatus.BANNED,
            is_trade_allowed=False,
            timestamp=now,
            message=f"F&O BAN ACTIVE for {clean} (MWPL: {util:.1f}% >= 95%): New orders strictly prohibited",
        )
    elif util >= 85.0:
        return FOBanSnapshot(
            symbol=clean,
            mwpl_utilization_pct=util,
            ban_status=BanStatus.DANGER_ZONE,
            is_trade_allowed=True,
            timestamp=now,
            message=f"F&O Ban Danger Zone for {clean} (MWPL: {util:.1f}% >= 85%): Approaching ban cutoff",
        )
    else:
        return FOBanSnapshot(
            symbol=clean,
            mwpl_utilization_pct=util,
            ban_status=BanStatus.SAFE,
            is_trade_allowed=True,
            timestamp=now,
            message=f"F&O Trading Safe for {clean} (MWPL: {util:.1f}% < 85%)",
        )


_LAST_FETCH_DATE: Optional[str] = None


def _ensure_ban_list_fresh() -> None:
    """Refresh the in-memory ban list at most once per calendar date.

    Best-effort by design: a failed fetch keeps yesterday's list (a stale
    ban list errs toward blocking, never toward silent permission).
    """
    global _LAST_FETCH_DATE
    today = now_ist().date().isoformat()
    if _LAST_FETCH_DATE == today:
        return
    fetch_live_nse_fo_ban_list()
    _LAST_FETCH_DATE = today


def fetch_live_nse_fo_ban_list() -> Set[str]:
    """
    Fetch the official real-time daily F&O Ban list directly from NSE Archives.
    URL: https://archives.nseindia.com/content/fo/fo_secban.csv
    """
    import ssl
    import urllib.request

    # Wired-gate hardening (2026-10-14): verified TLS. The old CERT_NONE
    # accepted any certificate — a MITM could blank the ban list and
    # silently re-permit banned underlyings.
    ctx = ssl.create_default_context()

    url = "https://archives.nseindia.com/content/fo/fo_secban.csv"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    banned_syms: Set[str] = set()

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            lines = content.strip().split("\n")
            for line in lines:
                parts = line.split(",")
                if len(parts) >= 2:
                    sym = parts[1].strip().upper()
                    if sym and not sym.startswith("SECURITIES") and not sym.startswith("SYMBOL"):
                        banned_syms.add(sym)

        with _ban_lock:
            for sym in banned_syms:
                _ACTIVE_BAN_LIST.add(sym)
                _MWPL_UTILIZATION_CACHE[sym] = 95.5

        logger.info(f"[fo_ban_sentry] Ingested {len(banned_syms)} banned securities from live NSE feed: {banned_syms}")
    except Exception as e:
        logger.warning(f"[fo_ban_sentry] Live NSE F&O Ban fetch skipped: {e}")

    return banned_syms


def get_active_ban_list() -> Set[str]:
    """Return a copy of the active banned symbols."""
    with _ban_lock:
        return set(_ACTIVE_BAN_LIST)
