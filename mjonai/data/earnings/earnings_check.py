"""
Module: data/earnings/earnings_check.py
Purpose: Quantitative Corporate Earnings & Board Meeting Risk Sentry.
         Guards trading strategies and execution routers against overnight binary gap risk.
         Blocks entry signals within configurable trading days prior to quarterly earnings announcements.

Architectural Principles:
  1. Multi-Tier Redundancy: Primary yfinance calendar -> Secondary NSE Board Meeting Scraper -> Fallback Degraded Mode.
  2. High-Speed TTL Caching: Sub-microsecond in-memory caching (6-hour validity) prevents rate limit exhaustion.
  3. Holiday-Aware Trading Day Countdown: Delegates to `core/time_utils` calendar engine for accurate trading day math.
  4. Type-Safe Contract & Tuple Dual-Access: Returns `EarningsRiskSnapshot` supporting tuple unpacking `(is_safe, msg)`.
  5. Configurable Risk Horizon: Supports dynamic `block_days` per strategy (e.g. 1 day for scalping, 5 for swing).
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
import logging
from pathlib import Path
import sys
import threading
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure workspace root is in sys.path
_root_dir = Path(__file__).resolve().parents[3]  # repo root (ADR-0008)
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

import pandas as pd
import requests
import yfinance as yf

from mjonai.core.time_utils import today_ist, now_ist, is_trading_day as _time_is_trading_day, Exchange
from mjonai.db.repository import insert_system_log

logger = logging.getLogger(__name__)

# Default block threshold (trading days)
DEFAULT_EARNINGS_BLOCK_DAYS: int = 3


# ── 1. ENUMS & DATA CONTRACTS ────────────────────────────────────────────────

class EarningsRiskLevel(str, Enum):
    """Institutional Event Risk Classification."""
    SAFE    = "SAFE"      # Earnings > block_days away
    WARNING = "WARNING"   # Approaching earnings window
    BLOCKED = "BLOCKED"   # Earnings <= block_days away (trade entry prohibited)
    UNKNOWN = "UNKNOWN"   # Earnings date could not be verified


@dataclass(frozen=True)
class EarningsRiskSnapshot:
    """
    Unified immutable earnings risk assessment contract.
    Supports tuple unpacking `(is_safe, message)` for 100% backwards compatibility.
    """
    symbol: str
    is_safe: bool
    earnings_date: Optional[date]
    trading_days_until: Optional[int]
    risk_level: EarningsRiskLevel
    source: str
    message: str
    timestamp: datetime

    def __iter__(self):
        """Enable tuple unpacking: `is_safe, message = check_earnings_risk(symbol)`."""
        return iter((self.is_safe, self.message))

    def __getitem__(self, item: Union[str, int]) -> Any:
        if isinstance(item, int):
            return (self.is_safe, self.message)[item]
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def to_tuple(self) -> Tuple[bool, str]:
        """Convert snapshot to legacy (is_safe, message) tuple."""
        return (self.is_safe, self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert earnings risk snapshot to dictionary."""
        return {
            "symbol": self.symbol,
            "is_safe": self.is_safe,
            "earnings_date": self.earnings_date.isoformat() if self.earnings_date else None,
            "trading_days_until": self.trading_days_until,
            "risk_level": self.risk_level.value,
            "source": self.source,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }


# ── 2. IN-MEMORY TTL CACHE ───────────────────────────────────────────────────

_EARNINGS_CACHE: Dict[str, Tuple[datetime, Optional[date], str]] = {}
_cache_lock = threading.Lock()


def clear_earnings_cache() -> None:
    """Clear all in-memory earnings calendar caches (useful for testing & market rollover)."""
    with _cache_lock:
        _EARNINGS_CACHE.clear()


def get_earnings_cache_size() -> int:
    """Return count of active symbols currently cached in memory."""
    with _cache_lock:
        return len(_EARNINGS_CACHE)


# ── 3. TRADING DAY COUNTDOWN MATH ─────────────────────────────────────────────

def is_trading_day(d: Union[date, datetime]) -> bool:
    """
    Return True if date is a Monday-Friday weekday and not an official NSE market holiday.
    """
    return _time_is_trading_day(d, Exchange.NSE)


def trading_days_until(target: date, reference_date: Optional[date] = None) -> int:
    """
    Count actual exchange trading days between reference_date (exclusive) and target (inclusive).
    Returns 0 if target date is today or in the past.
    """
    ref = reference_date or today_ist()
    if target <= ref:
        return 0

    count = 0
    candidate = ref
    while candidate < target:
        candidate = candidate + timedelta(days=1)
        if is_trading_day(candidate):
            count += 1
    return count


# ── 4. DATA PROVIDERS (YFINANCE & NSE SCRAPER) ───────────────────────────────

def _get_earnings_yfinance(symbol: str) -> Optional[date]:
    """
    Fetch next earnings announcement date via yfinance.
    Filters out historical dates to return only the nearest upcoming future date.
    """
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
    try:
        yf_sym = f"{clean_sym}.NS"
        if clean_sym in ("TATAMOTORS", "TATA MOTORS"):
            yf_sym = "TMPV.NS"
        elif clean_sym in ("M&M", "MM"):
            yf_sym = "M&M.NS"
        elif clean_sym in ("BAJAJ-AUTO", "BAJAJ AUTO"):
            yf_sym = "BAJAJ-AUTO.NS"

        ticker = yf.Ticker(yf_sym)
        calendar = ticker.calendar

        if not calendar:
            return None

        earnings_dates = calendar.get("Earnings Date")
        if not earnings_dates or not isinstance(earnings_dates, list):
            return None

        today = today_ist()
        converted: List[date] = []
        for item in earnings_dates:
            try:
                if isinstance(item, date):
                    converted.append(item)
                elif isinstance(item, pd.Timestamp):
                    converted.append(item.date())
            except Exception:
                continue

        # Keep only upcoming dates (>= today)
        future_dates = sorted([d for d in converted if d >= today])
        return future_dates[0] if future_dates else None

    except Exception as e:
        logger.debug(f"[Earnings] yfinance query failed for {clean_sym}: {e}")
        return None


def _get_earnings_nse(symbol: str) -> Optional[date]:
    """
    Fallback: Scrape upcoming board meeting dates from NSE corporate calendar.
    Requires realistic User-Agent and Referer headers to bypass HTTP 403 anti-scraping filters.
    """
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com",
        })

        # Step 1: Establish session cookies from homepage
        session.get("https://www.nseindia.com", timeout=6)

        # Step 2: Query corporate board meetings endpoint
        url = f"https://www.nseindia.com/api/corporate-board-meetings?symbol={clean_sym}&market=equities"
        response = session.get(url, timeout=6)

        if response.status_code != 200:
            logger.debug(f"[Earnings] NSE returned HTTP {response.status_code} for {clean_sym}")
            return None

        data = response.json()
        if not data or not isinstance(data, list):
            return None

        today = today_ist()
        upcoming_dates: List[date] = []

        for meeting in data:
            purpose = str(meeting.get("purpose", "")).lower()
            if "financial" not in purpose and "result" not in purpose:
                continue

            date_str = meeting.get("bm_date") or meeting.get("date")
            if not date_str:
                continue

            try:
                # Format: "17-Jul-2026"
                meeting_date = datetime.strptime(date_str.strip(), "%d-%b-%Y").date()
                if meeting_date >= today:
                    upcoming_dates.append(meeting_date)
            except ValueError:
                continue

        return min(upcoming_dates) if upcoming_dates else None

    except Exception as e:
        logger.debug(f"[Earnings] NSE scraper error for {clean_sym}: {e}")
        return None


# ── 5. MASTER RISK CHECK GATEWAY ─────────────────────────────────────────────

class EarningsDataUnavailableError(RuntimeError):
    """H12: raised when the earnings calendar cannot be verified and the
    caller has NOT explicitly opted into degraded-permissive behaviour."""


def check_earnings_risk(
    symbol: str,
    block_days: int = DEFAULT_EARNINGS_BLOCK_DAYS,
    use_cache: bool = True,
    cache_ttl_hours: float = 6.0,
    allow_degraded_permissive: bool = False,
) -> EarningsRiskSnapshot:
    """
    Quantitative Earnings Risk Assessment Gateway.
    Checks whether a symbol has an upcoming earnings announcement within `block_days` trading days.

    Args:
        symbol: Canonical ticker symbol (e.g. "RELIANCE", "INFY", "TCS")
        block_days: Number of trading days before earnings to block trades (default: 3)
        use_cache: Enable in-memory TTL caching (default: True)
        cache_ttl_hours: Cache retention duration in hours (default: 6.0)
        allow_degraded_permissive: H12 — when BOTH calendar sources fail, False
            (default) raises EarningsDataUnavailableError so callers can fail
            CLOSED; True restores the old permissive fallback (RESEARCH only).

    Returns:
        EarningsRiskSnapshot: Type-safe assessment object supporting `(is_safe, msg)` tuple unpacking.
    """
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
    now = now_ist()

    # 1. In-Memory Cache Lookup
    if use_cache:
        with _cache_lock:
            cached = _EARNINGS_CACHE.get(clean_sym)
            if cached is not None:
                cached_time, cached_date, cached_source = cached
                if (now - cached_time).total_seconds() < (cache_ttl_hours * 3600):
                    if cached_date is not None:
                        days_away = trading_days_until(cached_date)
                        is_safe = days_away > block_days
                        risk_level = EarningsRiskLevel.SAFE if is_safe else EarningsRiskLevel.BLOCKED
                        msg = (
                            f"Earnings in {days_away} trading day(s) ({cached_date}) [{cached_source}] - signal blocked"
                            if not is_safe else
                            f"Earnings {days_away} trading day(s) away ({cached_date}) [{cached_source}] - safe"
                        )
                        return EarningsRiskSnapshot(
                            symbol=clean_sym,
                            is_safe=is_safe,
                            earnings_date=cached_date,
                            trading_days_until=days_away,
                            risk_level=risk_level,
                            source=cached_source,
                            message=msg,
                            timestamp=now,
                        )

    # 2. Primary Provider: yfinance Calendar
    earnings_date = _get_earnings_yfinance(clean_sym)
    source = "YFINANCE"

    # 3. Secondary Provider: NSE Board Meetings Calendar
    if earnings_date is None:
        earnings_date = _get_earnings_nse(clean_sym)
        if earnings_date is not None:
            source = "NSE_SCRAPER"

    # 4. Cache Resolution
    if use_cache:
        with _cache_lock:
            _EARNINGS_CACHE[clean_sym] = (now, earnings_date, source if earnings_date else "UNKNOWN")

    # 5. Evaluate Risk Level
    if earnings_date is not None:
        days_away = trading_days_until(earnings_date)
        is_safe = days_away > block_days
        risk_level = EarningsRiskLevel.SAFE if is_safe else EarningsRiskLevel.BLOCKED

        if not is_safe:
            msg = f"Earnings in {days_away} trading day(s) ({earnings_date}) [{source}] - signal blocked"
            logger.warning(f"[Earnings] {clean_sym} - {msg}")
        else:
            msg = f"Earnings {days_away} trading day(s) away ({earnings_date}) [{source}] - safe"
            logger.info(f"[Earnings] {clean_sym} - {msg}")

        return EarningsRiskSnapshot(
            symbol=clean_sym,
            is_safe=is_safe,
            earnings_date=earnings_date,
            trading_days_until=days_away,
            risk_level=risk_level,
            source=source,
            message=msg,
            timestamp=now,
        )

    # 6. Fallback Degraded Mode (Both providers failed)
    # H12: this used to return is_safe=True unconditionally ("Degraded
    # permissive mode") — a blackout bypass whenever both sources failed.
    # Now the CALLER decides: RESEARCH may proceed degraded; capital modes
    # get EarningsDataUnavailableError and fail CLOSED at the gate.
    warning_msg = f"[WARN] Earnings date unknown for {clean_sym} - source unavailable"
    logger.warning(f"[Earnings] {clean_sym} - {warning_msg}")
    insert_system_log(
        "EARNINGS_CHECK",
        f"Could not verify earnings announcement calendar for {clean_sym}",
        level="WARNING"
    )

    if not allow_degraded_permissive:
        raise EarningsDataUnavailableError(
            f"Earnings calendar unavailable for {clean_sym}; "
            "refusing to default to safe (H12)."
        )

    return EarningsRiskSnapshot(
        symbol=clean_sym,
        is_safe=True,  # Degraded permissive mode — explicitly opted in (RESEARCH)
        earnings_date=None,
        trading_days_until=None,
        risk_level=EarningsRiskLevel.UNKNOWN,
        source="DEGRADED_FALLBACK",
        message=warning_msg,
        timestamp=now,
    )


def check_earnings_risk_bulk(
    symbols: List[str],
    block_days: int = DEFAULT_EARNINGS_BLOCK_DAYS,
    use_cache: bool = True
) -> Dict[str, EarningsRiskSnapshot]:
    """
    High-throughput batch earnings risk assessment across universe constituents.
    """
    results: Dict[str, EarningsRiskSnapshot] = {}
    for sym in symbols:
        results[sym] = check_earnings_risk(sym, block_days=block_days, use_cache=use_cache)
    return results


def is_iv_crush_zone(symbol: str, window_days: int = 1) -> bool:
    """
    Institutional Volatility Sentry:
    Returns True if an earnings announcement occurs today or within `window_days` trading days.
    Guards option buyers against massive post-earnings Implied Volatility (IV) crush.
    """
    snapshot = check_earnings_risk(symbol, block_days=window_days)
    if snapshot.trading_days_until is not None:
        return snapshot.trading_days_until <= window_days
    return False


def is_post_earnings_window(symbol: str, window_days: int = 2) -> bool:
    """
    Post-Earnings Announcement Drift (PEAD) Detector:
    Returns True if an earnings event was recently completed within the last `window_days` trading days.
    """
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
    now = today_ist()

    # Query historical calendar via yfinance
    try:
        ticker = yf.Ticker(f"{clean_sym}.NS")
        calendar = ticker.calendar
        if calendar and "Earnings Date" in calendar:
            earnings_dates = calendar["Earnings Date"]
            if isinstance(earnings_dates, list):
                for item in earnings_dates:
                    dt = item.date() if isinstance(item, (datetime, pd.Timestamp)) else item
                    if isinstance(dt, date) and dt < now:
                        days_ago = trading_days_until(now, reference_date=dt)
                        if 0 <= days_ago <= window_days:
                            return True
    except Exception as e:
        logger.debug(f"[Earnings] PEAD check error for {clean_sym}: {e}")

    return False


# ── 6. SELF-DIAGNOSTIC DEMONSTRATION HARNESS ─────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("===================================================================")
    print("MJONAI QUANTITATIVE EARNINGS EVENT RISK SENTRY")
    print("===================================================================")

    test_symbols = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "TATAMOTORS"]
    print(f"Evaluation Date (IST) : {today_ist().isoformat()}")
    print(f"Block Horizon         : {DEFAULT_EARNINGS_BLOCK_DAYS} Trading Days")
    print("-------------------------------------------------------------------")

    for sym in test_symbols:
        snapshot = check_earnings_risk(sym, block_days=DEFAULT_EARNINGS_BLOCK_DAYS)
        status_tag = "[SAFE]" if snapshot.is_safe else "[BLOCKED]"
        date_str = snapshot.earnings_date.isoformat() if snapshot.earnings_date else "UNKNOWN"
        days_str = f"{snapshot.trading_days_until}d" if snapshot.trading_days_until is not None else "N/A"
        print(f"  - {sym:<12} | Status: {status_tag:<9} | Days Away: {days_str:<5} | Date: {date_str:<12} | Source: {snapshot.source}")

    print("-------------------------------------------------------------------")
    print(f"In-Memory Cached Symbols : {get_earnings_cache_size()}")
    print("===================================================================")