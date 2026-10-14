"""
Module: core/time_utils.py

Purpose: High-Performance Multi-Asset Timekeeper, Exchange Session Engine & Market State Provider.
         Single Source of Truth for: "WHAT TIME / SESSION STATE IS IT?"
         (Never decides trading actions, position migrations, or risk decisions).

Design Principles:
  1. High Performance by Default: O(1) in-memory hot-path operations, zero I/O or network on tick paths.
  2. Canonical UTC Internally: UTC is standard; exchange-local timezones applied at session boundaries.
  3. Rich MarketStatus & Explainability: OPEN, CLOSED, PRE_OPEN, POST_MARKET, SPECIAL_SESSION, HALTED, UNKNOWN.
     Provides explicit provenance: "Why is the market in this state?"
  4. Extensible Exchange Session Registry: Multi-session support (MCX morning/evening, US pre/after, Crypto 24/7).
  5. Multi-Asset Trading Date & Session IDs: Unique session_id for reliable database joins and research.
  6. Zero Business Logic: Does not decide what to trade or when to square-off. Pure time & session state only.
"""

from dataclasses import dataclass
from datetime import datetime, date, time, timezone, timedelta
from enum import Enum
import logging
from typing import Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)

# ── 1. TIMEZONES & CANONICAL TIME ────────────────────────────────────────────

UTC = timezone.utc

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo('Asia/Kolkata')
    EST = ZoneInfo('America/New_York')
except ImportError:
    try:
        import pytz
        IST = pytz.timezone('Asia/Kolkata')
        EST = pytz.timezone('America/New_York')
    except ImportError:
        IST = timezone(timedelta(hours=5, minutes=30))
        EST = timezone(timedelta(hours=-5))


def localize_ist(dt: Optional[Union[datetime, date, str]] = None) -> datetime:
    """
    Safely convert any datetime (naive, aware, UTC, or ISO string) into an IST-aware datetime.
    Guarantees zero TypeError: can't subtract offset-naive and offset-aware datetimes.
    """
    if dt is None:
        return datetime.now(IST)
    
    if isinstance(dt, str):
        clean_str = dt.replace('Z', '+00:00')
        parsed = datetime.fromisoformat(clean_str)
        return localize_ist(parsed)
    
    if isinstance(dt, date) and not isinstance(dt, datetime):
        d = datetime(dt.year, dt.month, dt.day, 0, 0, 0)
        return getattr(IST, 'localize', lambda x: x.replace(tzinfo=IST))(d) if hasattr(IST, 'localize') else d.replace(tzinfo=IST)
    
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return getattr(IST, 'localize', lambda x: x.replace(tzinfo=IST))(dt) if hasattr(IST, 'localize') else dt.replace(tzinfo=IST)
        return dt.astimezone(IST)
            
    return datetime.now(IST)


def to_utc(dt: Optional[Union[datetime, date, str]] = None) -> datetime:
    """Convert any datetime or ISO string to canonical UTC timezone."""
    if dt is None:
        return datetime.now(UTC)
    ist_dt = localize_ist(dt)
    return ist_dt.astimezone(UTC)


def now_ist() -> datetime:
    """Return current datetime in IST timezone."""
    return datetime.now(IST)


def today_ist() -> date:
    """Return today's date in IST timezone."""
    return datetime.now(IST).date()


# ── 2. ENUMS & DATA STRUCTURES ───────────────────────────────────────────────

class MarketStatus(str, Enum):
    OPEN = "OPEN"                        # Regular trading session active
    PRE_OPEN = "PRE_OPEN"                # Pre-market / auction session active
    POST_MARKET = "POST_MARKET"          # Post-closing / reconciliation window
    CLOSED = "CLOSED"                    # Exchange closed (weekend, holiday, off-hours)
    SPECIAL_SESSION = "SPECIAL_SESSION"  # Muhurat trading, Saturday DR testing
    HALTED = "HALTED"                    # Trading halted (circuit breaker / regulatory)
    UNKNOWN = "UNKNOWN"                  # State unverified


class Exchange(str, Enum):
    NSE = "NSE"                          # National Stock Exchange Cash Equities
    NFO = "NFO"                          # NSE Futures & Options (Nifty / BankNifty)
    NSE_EVENING = "NSE_EVENING"          # Extended Evening Derivatives Session (18:00 - 21:00 IST)
    BSE = "BSE"                          # Bombay Stock Exchange Cash
    BFO = "BFO"                          # BSE Futures & Options (Sensex / Bankex)
    MCX = "MCX"                          # Multi Commodity Exchange (Crude, Gold, Metals)
    CDS = "CDS"                          # NSE Currency Derivatives (USDINR, EURINR)
    US_EQUITY = "US_EQUITY"              # NYSE / NASDAQ
    CRYPTO = "CRYPTO"                    # 24/7/365 Continuous Crypto Spot & Perpetuals

# NSE circular 111/2025: F&O weekly & monthly expiries moved to TUESDAY
# effective 2025-09-01 (previously Thursday). Monday=0 ... Sunday=6.
NSE_FO_EXPIRY_WEEKDAY: int = 1


@dataclass(frozen=True)
class SessionState:
    """
    Immutable snapshot of an exchange's session state.
    Provides complete provenance: 'Why is the market in this state?'
    """
    exchange: Exchange
    status: MarketStatus
    is_open: bool
    trading_date: date
    session_id: str
    reason: str
    minutes_elapsed: int
    minutes_remaining: int
    timestamp_utc: datetime
    timestamp_local: datetime


# ── 3. DYNAMIC EXCHANGE CALENDAR & HOLIDAY ENGINE ────────────────────────────

_holiday_cache: Dict[Tuple[str, int], Set[str]] = {}
_CALENDAR_FAILURES: set = set()
_special_session_overrides: Dict[Tuple[str, date], Tuple[time, time, str]] = {}
_manual_exchange_halt: Dict[str, Tuple[bool, str]] = {}
_USING_FALLBACK_CALENDAR: bool = False


def register_special_session(exchange: Union[Exchange, str], session_date: date, start_t: time, end_t: time, reason: str):
    """Register a special trading session (e.g. Muhurat Trading 18:15 - 19:15, Saturday DR 09:15 - 15:30)."""
    ex_str = exchange.value if isinstance(exchange, Exchange) else exchange.upper()
    _special_session_overrides[(ex_str, session_date)] = (start_t, end_t, reason)
    logger.info(f"[time_utils] Special session registered: {ex_str} on {session_date} ({start_t}-{end_t}) - {reason}")


def set_exchange_halt(exchange: Union[Exchange, str], is_halted: bool, reason: str = ""):
    """Set explicit market halt or resumption (e.g. index circuit breaker, technical halt)."""
    ex_str = exchange.value if isinstance(exchange, Exchange) else exchange.upper()
    _manual_exchange_halt[ex_str] = (is_halted, reason)
    if is_halted:
        logger.warning(f"[time_utils] Exchange {ex_str} HALTED: {reason}")
    else:
        logger.info(f"[time_utils] Exchange {ex_str} resumed trading.")


def _load_holidays(year: int, exchange: str = "NSE") -> Set[str]:
    """
    O(1) in-memory cache lookup.
    Loads official exchange calendar dynamically via pandas_market_calendars / exchange_calendars.
    """
    global _USING_FALLBACK_CALENDAR
    # Cash + F&O + evening derivatives follow the NSE holiday calendar.
    # pandas_market_calendars has no class named NFO / BFO / NSE_EVENING.
    if exchange in ("NSE", "BSE", "CDS", "NFO", "BFO", "NSE_EVENING"):
        exchange = "NSE"
    cache_key = (exchange, year)
    if cache_key in _holiday_cache:
        return _holiday_cache[cache_key]

    # 1. Primary: pandas_market_calendars
    try:
        import importlib
        mcal = importlib.import_module("pandas_market_calendars")
        import pandas as pd
        cal_name = 'NSE' if exchange in ('NSE', 'BSE', 'CDS') else exchange
        mcal_cal = mcal.get_calendar(cal_name)
        schedule = mcal_cal.schedule(start_date=f"{year}-01-01", end_date=f"{year}-12-31")
        all_weekdays = pd.bdate_range(start=f"{year}-01-01", end=f"{year}-12-31")
        trading_days = set(schedule.index.strftime('%Y-%m-%d'))
        weekdays = set(all_weekdays.strftime('%Y-%m-%d'))
        holidays = weekdays - trading_days
        _holiday_cache[cache_key] = holidays
        _USING_FALLBACK_CALENDAR = False
        return holidays
    except Exception as e:
        logger.warning(f"[time_utils] pandas_market_calendars unavailable for {exchange} ({year}): {e}")
        _USING_FALLBACK_CALENDAR = True

    # 2. Secondary: exchange_calendars
    try:
        import importlib
        xcals = importlib.import_module("exchange_calendars")
        cal_name = 'XNSE' if exchange in ('NSE', 'BSE', 'CDS') else exchange
        xcal = xcals.get_calendar(cal_name)
        holidays = {d.strftime('%Y-%m-%d') for d in xcal.regular_holidays.holidays(start=f"{year}-01-01", end=f"{year}-12-31")}
        _holiday_cache[cache_key] = holidays
        _USING_FALLBACK_CALENDAR = False
        return holidays
    except Exception:
        pass

    # Total calendar failure: record it so is_trading_day can FAIL
    # CLOSED instead of silently treating every weekday as tradable.
    _CALENDAR_FAILURES.add(cache_key)
    _holiday_cache[cache_key] = set()
    return set()


def _is_nse_holiday(dt: Union[date, str, datetime]) -> bool:
    """Compatibility alias for execution/tracker.py and data/earnings/earnings_check.py."""
    if isinstance(dt, str):
        try:
            parsed = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            d = parsed.date()
        except Exception:
            d = datetime.strptime(dt[:10], '%Y-%m-%d').date()
    elif isinstance(dt, datetime):
        d = dt.date()
    else:
        d = dt
    return not is_trading_day(d, Exchange.NSE)


# Legacy compatibility aliases
_CURRENT_YEAR = datetime.now(IST).year
_NSE_HOLIDAYS: Set[str] = _load_holidays(_CURRENT_YEAR, "NSE")
NSE_HOLIDAYS_2026 = _NSE_HOLIDAYS


# ── 4. HIGH-PERFORMANCE EXCHANGE SESSION LOGIC ───────────────────────────────

def _is_us_dst(dt: datetime) -> bool:
    """O(1) Daylight Saving Time check for US (EDT vs EST)."""
    try:
        aware_dt = dt if dt.tzinfo else dt.replace(tzinfo=IST)
        ny_dt = aware_dt.astimezone(EST)
        return bool(ny_dt.dst())
    except Exception:
        return 3 < dt.month < 11


def get_session_state(
    dt: Optional[Union[datetime, date, str]] = None,
    exchange: Union[Exchange, str] = Exchange.NSE
) -> SessionState:
    """
    Master High-Performance Session Resolver.
    Returns complete, immutable SessionState with status, session_id, and explainable reason.
    """
    exch = Exchange(exchange.upper()) if isinstance(exchange, str) else exchange
    ist_dt = localize_ist(dt)
    target_date = ist_dt.date()
    target_time = ist_dt.time()
    ex_str = exch.value
    utc_dt = ist_dt.astimezone(UTC)

    # 1. Check Explicit Manual Halt
    if ex_str in _manual_exchange_halt:
        is_halted, halt_reason = _manual_exchange_halt[ex_str]
        if is_halted:
            return SessionState(
                exchange=exch,
                status=MarketStatus.HALTED,
                is_open=False,
                trading_date=target_date,
                session_id=f"{ex_str}_{target_date}_HALTED",
                reason=f"Exchange trading halted: {halt_reason}",
                minutes_elapsed=0,
                minutes_remaining=0,
                timestamp_utc=utc_dt,
                timestamp_local=ist_dt,
            )

    # 2. Check Special Session Overrides (e.g. Diwali Muhurat / Saturday DR)
    override_key = (ex_str, target_date)
    if override_key in _special_session_overrides:
        start_t, end_t, session_name = _special_session_overrides[override_key]
        if start_t <= target_time <= end_t:
            mins_elapsed = int((datetime.combine(target_date, target_time) - datetime.combine(target_date, start_t)).total_seconds() // 60)
            mins_rem = int((datetime.combine(target_date, end_t) - datetime.combine(target_date, target_time)).total_seconds() // 60)
            return SessionState(
                exchange=exch,
                status=MarketStatus.SPECIAL_SESSION,
                is_open=True,
                trading_date=target_date,
                session_id=f"{ex_str}_{target_date}_SPECIAL",
                reason=f"Active special session: {session_name} ({start_t}-{end_t})",
                minutes_elapsed=mins_elapsed,
                minutes_remaining=mins_rem,
                timestamp_utc=utc_dt,
                timestamp_local=ist_dt,
            )

    # 3. Crypto 24/7/365 Continuous Session
    if exch == Exchange.CRYPTO:
        return SessionState(
            exchange=exch,
            status=MarketStatus.OPEN,
            is_open=True,
            trading_date=target_date,
            session_id=f"CRYPTO_{target_date}_24H",
            reason="Crypto spot and perpetual markets trade 24/7/365",
            minutes_elapsed=target_time.hour * 60 + target_time.minute,
            minutes_remaining=1440 - (target_time.hour * 60 + target_time.minute),
            timestamp_utc=utc_dt,
            timestamp_local=ist_dt,
        )

    # 4. Weekend Check (Saturday / Sunday)
    weekday = ist_dt.weekday()
    if weekday >= 5:
        day_name = "Saturday" if weekday == 5 else "Sunday"
        return SessionState(
            exchange=exch,
            status=MarketStatus.CLOSED,
            is_open=False,
            trading_date=target_date,
            session_id=f"{ex_str}_{target_date}_WEEKEND",
            reason=f"Exchange closed on {day_name}",
            minutes_elapsed=0,
            minutes_remaining=0,
            timestamp_utc=utc_dt,
            timestamp_local=ist_dt,
        )

    # 5. Holiday Check
    holidays = _load_holidays(target_date.year, ex_str)
    date_str = target_date.strftime('%Y-%m-%d')
    if date_str in holidays:
        # MCX allows evening session even on certain Indian holidays
        if exch == Exchange.MCX:
            close_t = time(23, 30) if _is_us_dst(ist_dt) else time(23, 55)
            if time(17, 0) <= target_time <= close_t:
                mins_elapsed = int((datetime.combine(target_date, target_time) - datetime.combine(target_date, time(17, 0))).total_seconds() // 60)
                mins_rem = int((datetime.combine(target_date, close_t) - datetime.combine(target_date, target_time)).total_seconds() // 60)
                return SessionState(
                    exchange=exch,
                    status=MarketStatus.OPEN,
                    is_open=True,
                    trading_date=target_date,
                    session_id=f"MCX_{target_date}_EVENING_HOLIDAY",
                    reason="MCX evening commodity session open on domestic holiday",
                    minutes_elapsed=mins_elapsed,
                    minutes_remaining=mins_rem,
                    timestamp_utc=utc_dt,
                    timestamp_local=ist_dt,
                )
        return SessionState(
            exchange=exch,
            status=MarketStatus.CLOSED,
            is_open=False,
            trading_date=target_date,
            session_id=f"{ex_str}_{target_date}_HOLIDAY",
            reason=f"{ex_str} scheduled trading holiday ({date_str})",
            minutes_elapsed=0,
            minutes_remaining=0,
            timestamp_utc=utc_dt,
            timestamp_local=ist_dt,
        )

    # 6. Session Timings Evaluation per Exchange
    if exch in (Exchange.NSE, Exchange.NFO, Exchange.BSE, Exchange.BFO):
        if target_time < time(8, 0):
            return SessionState(exch, MarketStatus.CLOSED, False, target_date, f"NSE_{target_date}_EARLY", "Pre-market not yet started", 0, 0, utc_dt, ist_dt)
        elif time(8, 0) <= target_time < time(9, 15):
            mins_to_open = int((datetime.combine(target_date, time(9, 15)) - datetime.combine(target_date, target_time)).total_seconds() // 60)
            return SessionState(exch, MarketStatus.PRE_OPEN, False, target_date, f"NSE_{target_date}_PRE", f"Pre-market window ({mins_to_open}m to open)", 0, mins_to_open, utc_dt, ist_dt)
        elif time(9, 15) <= target_time <= time(15, 30):
            mins_elapsed = int((datetime.combine(target_date, target_time) - datetime.combine(target_date, time(9, 15))).total_seconds() // 60)
            mins_rem = int((datetime.combine(target_date, time(15, 30)) - datetime.combine(target_date, target_time)).total_seconds() // 60)
            return SessionState(exch, MarketStatus.OPEN, True, target_date, f"NSE_{target_date}_REGULAR", "Regular continuous trading session", mins_elapsed, mins_rem, utc_dt, ist_dt)
        elif time(15, 30) < target_time <= time(16, 30):
            return SessionState(exch, MarketStatus.POST_MARKET, False, target_date, f"NSE_{target_date}_POST", "Post-closing reconciliation session", 0, 0, utc_dt, ist_dt)
        else:
            return SessionState(exch, MarketStatus.CLOSED, False, target_date, f"NSE_{target_date}_CLOSED", "Market closed for the day", 0, 0, utc_dt, ist_dt)

    elif exch == Exchange.MCX:
        close_t = time(23, 30) if _is_us_dst(ist_dt) else time(23, 55)
        if time(9, 0) <= target_time <= close_t:
            mins_elapsed = int((datetime.combine(target_date, target_time) - datetime.combine(target_date, time(9, 0))).total_seconds() // 60)
            mins_rem = int((datetime.combine(target_date, close_t) - datetime.combine(target_date, target_time)).total_seconds() // 60)
            dst_label = "US Summer EDT (closes 23:30)" if close_t == time(23, 30) else "US Winter EST (closes 23:55)"
            return SessionState(exch, MarketStatus.OPEN, True, target_date, f"MCX_{target_date}_COMMODITY", f"MCX active session [{dst_label}]", mins_elapsed, mins_rem, utc_dt, ist_dt)
        else:
            return SessionState(exch, MarketStatus.CLOSED, False, target_date, f"MCX_{target_date}_CLOSED", "MCX closed (trading 09:00 - 23:30/23:55)", 0, 0, utc_dt, ist_dt)

    elif exch == Exchange.CDS:
        if time(9, 0) <= target_time <= time(17, 0):
            mins_elapsed = int((datetime.combine(target_date, target_time) - datetime.combine(target_date, time(9, 0))).total_seconds() // 60)
            mins_rem = int((datetime.combine(target_date, time(17, 0)) - datetime.combine(target_date, target_time)).total_seconds() // 60)
            return SessionState(exch, MarketStatus.OPEN, True, target_date, f"CDS_{target_date}_REGULAR", "Currency derivatives session active", mins_elapsed, mins_rem, utc_dt, ist_dt)
        else:
            return SessionState(exch, MarketStatus.CLOSED, False, target_date, f"CDS_{target_date}_CLOSED", "Currency CDS market closed (09:00 - 17:00 IST)", 0, 0, utc_dt, ist_dt)

    elif exch == Exchange.NSE_EVENING:
        if time(18, 0) <= target_time <= time(21, 0):
            mins_elapsed = int((datetime.combine(target_date, target_time) - datetime.combine(target_date, time(18, 0))).total_seconds() // 60)
            mins_rem = int((datetime.combine(target_date, time(21, 0)) - datetime.combine(target_date, target_time)).total_seconds() // 60)
            return SessionState(exch, MarketStatus.OPEN, True, target_date, f"NSE_EVENING_{target_date}", "NSE Extended Evening Derivatives active (18:00 - 21:00 IST)", mins_elapsed, mins_rem, utc_dt, ist_dt)
        else:
            return SessionState(exch, MarketStatus.CLOSED, False, target_date, f"NSE_EVENING_{target_date}_CLOSED", "NSE Evening session closed (18:00 - 21:00 IST)", 0, 0, utc_dt, ist_dt)

    elif exch == Exchange.US_EQUITY:
        # Convert to US Eastern Time
        # ZoneInfo handles US DST automatically; the old hasattr guard
        # silently fell back to a fixed UTC-5 offset year-round.
        est_dt = utc_dt.astimezone(EST)
        est_t = est_dt.time()
        if time(9, 30) <= est_t <= time(16, 0):
            mins_elapsed = int((datetime.combine(est_dt.date(), est_t) - datetime.combine(est_dt.date(), time(9, 30))).total_seconds() // 60)
            mins_rem = int((datetime.combine(est_dt.date(), time(16, 0)) - datetime.combine(est_dt.date(), est_t)).total_seconds() // 60)
            return SessionState(exch, MarketStatus.OPEN, True, est_dt.date(), f"US_{est_dt.date()}_REGULAR", "US Equity regular session active (09:30 - 16:00 EST)", mins_elapsed, mins_rem, utc_dt, ist_dt)
        elif time(4, 0) <= est_t < time(9, 30):
            return SessionState(exch, MarketStatus.PRE_OPEN, False, est_dt.date(), f"US_{est_dt.date()}_PRE", "US Pre-Market trading session", 0, 0, utc_dt, ist_dt)
        elif time(16, 0) < est_t <= time(20, 0):
            return SessionState(exch, MarketStatus.POST_MARKET, False, est_dt.date(), f"US_{est_dt.date()}_POST", "US After-Hours trading session", 0, 0, utc_dt, ist_dt)
        else:
            return SessionState(exch, MarketStatus.CLOSED, False, est_dt.date(), f"US_{est_dt.date()}_CLOSED", "US market closed", 0, 0, utc_dt, ist_dt)

    return SessionState(exch, MarketStatus.UNKNOWN, False, target_date, f"{ex_str}_{target_date}_UNKNOWN", "Unknown exchange session", 0, 0, utc_dt, ist_dt)


# ── 5. PUBLIC CONVENIENCE APIS (100% BACKWARDS COMPATIBLE) ───────────────────

def is_market_open(
    dt: Optional[Union[datetime, date, str]] = None,
    exchange: Union[Exchange, str] = Exchange.NSE,
    mode: str = "LIVE"
) -> bool:
    """Return True if exchange is currently in an active trading session."""
    state = get_session_state(dt, exchange)
    return state.is_open


def is_pre_market(
    dt: Optional[Union[datetime, date, str]] = None,
    exchange: Union[Exchange, str] = Exchange.NSE
) -> bool:
    """Return True if exchange is in pre-market window."""
    state = get_session_state(dt, exchange)
    return state.status == MarketStatus.PRE_OPEN


def is_post_market(
    dt: Optional[Union[datetime, date, str]] = None,
    exchange: Union[Exchange, str] = Exchange.NSE
) -> bool:
    """Return True if exchange is in post-market reconciliation window."""
    state = get_session_state(dt, exchange)
    return state.status == MarketStatus.POST_MARKET


def is_eod_decision_window(
    dt: Optional[Union[datetime, date, str]] = None,
    exchange: Union[Exchange, str] = Exchange.NSE
) -> bool:
    """Return True if currently in the 3:10 PM - 3:15 PM IST session window."""
    ist_dt = localize_ist(dt) if dt is not None else now_ist()
    state = get_session_state(ist_dt, exchange)
    if not state.is_open:
        return False
    t = ist_dt.time()
    return time(15, 10) <= t < time(15, 15)


def is_trading_day(
    dt: Optional[Union[datetime, date, str]] = None,
    exchange: Union[Exchange, str] = Exchange.NSE
) -> bool:
    """Return True if date is a scheduled trading day (skipping weekends & holidays)."""
    ist_dt = localize_ist(dt) if dt is not None else now_ist()
    exch = Exchange(exchange.upper()) if isinstance(exchange, str) else exchange
    if exch == Exchange.CRYPTO:
        return True
    if ist_dt.weekday() >= 5:
        return False
    year_key = (exch.value, ist_dt.year)
    if year_key in _CALENDAR_FAILURES:
        # FAIL CLOSED: without a real holiday calendar we cannot know
        # the market is open. Override only with explicit env opt-in.
        import os as _os
        if _os.getenv("MJONAI_ALLOW_FALLBACK_CALENDAR", "0") != "1":
            logger.critical(
                f"[time_utils] Holiday calendar UNAVAILABLE for {exch.value} {ist_dt.year} "
                f"- failing CLOSED (treated as non-trading day). "
                f"Set MJONAI_ALLOW_FALLBACK_CALENDAR=1 to override."
            )
            return False

    holidays = _load_holidays(ist_dt.year, exch.value)
    return ist_dt.strftime('%Y-%m-%d') not in holidays


def week_of_month(dt: Optional[Union[datetime, date, str]] = None) -> int:
    """Return week number within the month (1-5). Formula: ((day - 1) // 7) + 1."""
    ist_dt = localize_ist(dt) if dt is not None else now_ist()
    return ((ist_dt.day - 1) // 7) + 1


def market_open_minutes(
    dt: Optional[Union[datetime, date, str]] = None,
    exchange: Union[Exchange, str] = Exchange.NSE
) -> int:
    """Return minutes elapsed since market open (negative if before open)."""
    state = get_session_state(dt, exchange)
    if state.status == MarketStatus.OPEN:
        return state.minutes_elapsed
    elif state.status == MarketStatus.PRE_OPEN:
        return -state.minutes_remaining
    return 0


def minutes_to_market_close(
    dt: Optional[Union[datetime, date, str]] = None,
    exchange: Union[Exchange, str] = Exchange.NSE
) -> int:
    """Return minutes remaining until market close (0 if closed)."""
    state = get_session_state(dt, exchange)
    return state.minutes_remaining


# A full year without a single trading day is impossible (longest real gap is
# a ~5-day holiday week). Past this bound the calendar itself is broken (e.g.
# a failed holiday source failing CLOSED forever) — raise instead of hanging.
_MAX_TRADING_DAY_SCAN_DAYS = 366


def _bounded_trading_day_walk(start: date, exch: Exchange, step_days: int,
                              what: str) -> date:
    curr = start
    for _ in range(_MAX_TRADING_DAY_SCAN_DAYS):
        if is_trading_day(curr, exch):
            return curr
        curr += timedelta(days=step_days)
    from mjonai.core.exceptions import MarketClosedError
    raise MarketClosedError(
        f"{what}: no trading day within {_MAX_TRADING_DAY_SCAN_DAYS} days of "
        f"{start.isoformat()} ({exch.value}) — holiday calendar unavailable, refusing to hang"
    )


def get_previous_trading_day(
    dt: Optional[Union[datetime, date, str]] = None,
    exchange: Union[Exchange, str] = Exchange.NSE
) -> date:
    """Return previous active trading day, skipping weekends and holidays automatically."""
    curr = localize_ist(dt).date() if dt is not None else today_ist()
    exch = Exchange(exchange.upper()) if isinstance(exchange, str) else exchange
    return _bounded_trading_day_walk(curr - timedelta(days=1), exch, -1,
                                     "get_previous_trading_day")


def get_next_trading_day(
    dt: Optional[Union[datetime, date, str]] = None,
    exchange: Union[Exchange, str] = Exchange.NSE
) -> date:
    """Return next active trading day, skipping weekends and holidays automatically."""
    curr = localize_ist(dt).date() if dt is not None else today_ist()
    exch = Exchange(exchange.upper()) if isinstance(exchange, str) else exchange
    return _bounded_trading_day_walk(curr + timedelta(days=1), exch, +1,
                                     "get_next_trading_day")


# ── 6. OPTIONS EXPIRY UTILITIES (NSE INDEX & EQUITY DERIVATIVES) ──────────────

def get_nifty_monthly_expiry(
    dt: Optional[Union[datetime, date, str]] = None,
    exchange: Union[Exchange, str] = Exchange.NSE
) -> date:
    """
    Return official monthly F&O expiry date for the given month.
    Rule: Last Thursday of the month. If that Thursday is a market holiday,
    it rolls back to the previous trading day (Wednesday/Tuesday).
    """
    target = localize_ist(dt).date() if dt is not None else today_ist()
    exch = Exchange(exchange.upper()) if isinstance(exchange, str) else exchange
    if target.month == 12:
        next_month = date(target.year + 1, 1, 1)
    else:
        next_month = date(target.year, target.month + 1, 1)
    last_day = next_month - timedelta(days=1)

    # Step backward to find the last expiry weekday (Tuesday post-Sep-2025)
    offset = (last_day.weekday() - NSE_FO_EXPIRY_WEEKDAY) % 7
    candidate = last_day - timedelta(days=offset)

    # If the last Thursday is a holiday, walk backward to prior trading day
    # (bounded — see _bounded_trading_day_walk; an open-ended loop here hangs
    # the EOD path when the calendar source is down).
    return _bounded_trading_day_walk(candidate, exch, -1, "get_nifty_monthly_expiry")


def get_nifty_weekly_expiry(
    dt: Optional[Union[datetime, date, str]] = None,
    exchange: Union[Exchange, str] = Exchange.NSE
) -> date:
    """
    Return active weekly expiry date for the current week.
    Rule: expiry weekday of the current week (or previous trading day if that day is a holiday).
    """
    target = localize_ist(dt).date() if dt is not None else today_ist()
    exch = Exchange(exchange.upper()) if isinstance(exchange, str) else exchange
    days_ahead = (NSE_FO_EXPIRY_WEEKDAY - target.weekday()) % 7
    candidate = target + timedelta(days=days_ahead)

    return _bounded_trading_day_walk(candidate, exch, -1, "get_nifty_weekly_expiry")


def is_expiry_day(
    dt: Optional[Union[datetime, date, str]] = None,
    exchange: Union[Exchange, str] = Exchange.NSE
) -> bool:
    """Return True if target date is either a Weekly or Monthly Options Expiry day."""
    target = localize_ist(dt).date() if dt is not None else today_ist()
    exch = Exchange(exchange.upper()) if isinstance(exchange, str) else exchange
    return target == get_nifty_weekly_expiry(target, exch) or target == get_nifty_monthly_expiry(target, exch)


def days_to_expiry(
    dt: Optional[Union[datetime, date, str]] = None,
    expiry: Optional[date] = None,
    exchange: Union[Exchange, str] = Exchange.NSE
) -> float:
    """
    Return remaining days to expiry (DTE) as a float (e.g. 2.4 days).
    Essential for accurate Black-Scholes Greeks and Theta decay.
    """
    ist_dt = localize_ist(dt) if dt is not None else now_ist()
    exch = Exchange(exchange.upper()) if isinstance(exchange, str) else exchange
    if expiry is None:
        expiry = get_nifty_weekly_expiry(ist_dt, exch)

    expiry_dt = datetime.combine(expiry, time(15, 30), tzinfo=IST)
    diff_seconds = (expiry_dt - ist_dt).total_seconds()
    return max(0.0, diff_seconds / 86400.0)


# ── 7. SELF-DIAGNOSTIC TEST HARNESS ──────────────────────────────────────────

if __name__ == "__main__":
    now = now_ist()
    state = get_session_state(now, Exchange.NSE)
    print("===================================================================")
    print("MJONAI HIGH-PERFORMANCE TIMEKEEPER & SESSION ENGINE")
    print("===================================================================")
    print(f"Current IST Time       : {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Current UTC Time       : {to_utc(now).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"NSE Session Status     : {state.status.value} (is_open={state.is_open})")
    print(f"NSE Session ID         : {state.session_id}")
    print(f"Session Reason         : {state.reason}")
    print(f"Minutes Elapsed / Left : {state.minutes_elapsed}m elapsed, {state.minutes_remaining}m left")
    print(f"Trading Day?           : {is_trading_day(now, Exchange.NSE)}")
    print(f"Previous Trading Day   : {get_previous_trading_day(now)}")
    print(f"Next Trading Day       : {get_next_trading_day(now)}")
    print("-------------------------------------------------------------------")
    print("MULTI-ASSET SESSION STATUS & PROVENANCE:")
    for ex in [Exchange.NSE, Exchange.MCX, Exchange.CDS, Exchange.US_EQUITY, Exchange.CRYPTO]:
        s = get_session_state(now, ex)
        print(f"  - {ex.value:<10} : {s.status.value:<10} | {s.reason}")
    print("===================================================================")
