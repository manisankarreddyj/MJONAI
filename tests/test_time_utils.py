"""
Unit & Boundary Integration Tests for core/time_utils.py
Tests High-Performance O(1) Sessions, MarketStatus Enum, Immutable SessionState, Session IDs, and 3-Layer Fallback Isolation.
"""

from datetime import datetime, date, time, timezone, timedelta
import pytest
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from mjonai.core.time_utils import (
    IST,
    UTC,
    Exchange,
    MarketStatus,
    SessionState,
    localize_ist,
    to_utc,
    now_ist,
    today_ist,
    get_session_state,
    is_market_open,
    is_pre_market,
    is_post_market,
    is_eod_decision_window,
    is_trading_day,
    week_of_month,
    market_open_minutes,
    minutes_to_market_close,
    get_previous_trading_day,
    get_next_trading_day,
    register_special_session,
    set_exchange_halt,
    _load_holidays,
    _holiday_cache,
    _USING_FALLBACK_CALENDAR,
    _is_nse_holiday,
    get_nifty_monthly_expiry,
    get_nifty_weekly_expiry,
    is_expiry_day,
    days_to_expiry,
)


def test_timezone_sanitizer():
    """Verify localize_ist and to_utc handle naive, aware, and string inputs without crashing."""
    # 1. Naive datetime
    naive = datetime(2026, 8, 14, 10, 30, 0)
    ist_dt = localize_ist(naive)
    assert ist_dt.tzinfo is not None
    assert ist_dt.hour == 10
    assert ist_dt.minute == 30

    # 2. UTC aware datetime
    utc_dt = datetime(2026, 8, 14, 4, 0, 0, tzinfo=timezone.utc)
    ist_from_utc = localize_ist(utc_dt)
    assert ist_from_utc.hour == 9
    assert ist_from_utc.minute == 30  # UTC 04:00 is IST 09:30

    # 3. ISO String
    iso_str = "2026-08-14T09:15:00+05:30"
    ist_from_str = localize_ist(iso_str)
    assert ist_from_str.hour == 9
    assert ist_from_str.minute == 15

    # 4. Pure date
    p_date = date(2026, 8, 14)
    ist_from_date = localize_ist(p_date)
    assert ist_from_date.day == 14
    assert ist_from_date.hour == 0


def test_nse_market_boundaries_and_session_state():
    """Verify exact second-level boundary conditions and immutable SessionState for NSE."""
    base_date = date(2026, 8, 14)

    # 1. 08:30 IST -> Pre-Market Active
    dt_pre = datetime.combine(base_date, time(8, 30), tzinfo=IST)
    state_pre = get_session_state(dt_pre, Exchange.NSE)
    assert state_pre.status == MarketStatus.PRE_OPEN
    assert state_pre.is_open is False
    assert "Pre-market" in state_pre.reason
    assert is_pre_market(dt_pre, Exchange.NSE) is True

    # 2. 09:15:00 IST -> Market Open
    dt_open = datetime.combine(base_date, time(9, 15, 0), tzinfo=IST)
    state_open = get_session_state(dt_open, Exchange.NSE)
    assert state_open.status == MarketStatus.OPEN
    assert state_open.is_open is True
    assert state_open.minutes_elapsed == 0
    assert state_open.session_id == f"NSE_{base_date}_REGULAR"

    # 3. 15:12:00 IST -> EOD Decision Window (3:10 PM - 3:15 PM)
    dt_decision = datetime.combine(base_date, time(15, 12, 0), tzinfo=IST)
    assert is_eod_decision_window(dt_decision, Exchange.NSE) is True

    # 4. 15:30:00 IST -> Closing Minute
    dt_close = datetime.combine(base_date, time(15, 30, 0), tzinfo=IST)
    state_close = get_session_state(dt_close, Exchange.NSE)
    assert state_close.status == MarketStatus.OPEN
    assert state_close.minutes_remaining == 0

    # 5. 15:30:01 IST -> Post-Market
    dt_post = datetime.combine(base_date, time(15, 30, 1), tzinfo=IST)
    state_post = get_session_state(dt_post, Exchange.NSE)
    assert state_post.status == MarketStatus.POST_MARKET
    assert state_post.is_open is False
    assert is_post_market(dt_post, Exchange.NSE) is True


def test_special_session_and_halt_overrides():
    """Verify registration of special sessions (Muhurat/DR) and market halts with reasons."""
    test_date = date(2026, 10, 20)  # Diwali Laxmi Pujan
    
    # 1. Register 1-hour Muhurat trading session (18:15 to 19:15)
    register_special_session(Exchange.NSE, test_date, time(18, 15), time(19, 15), "Diwali Muhurat Trading 2026")
    
    dt_muhurat = datetime.combine(test_date, time(18, 30), tzinfo=IST)
    state_muhurat = get_session_state(dt_muhurat, Exchange.NSE)
    assert state_muhurat.status == MarketStatus.SPECIAL_SESSION
    assert state_muhurat.is_open is True
    assert "Muhurat Trading" in state_muhurat.reason

    # 2. Test Market Halt
    set_exchange_halt(Exchange.NSE, True, "Index Circuit Breaker Hit 10%")
    state_halted = get_session_state(datetime(2026, 8, 14, 11, 0, tzinfo=IST), Exchange.NSE)
    assert state_halted.status == MarketStatus.HALTED
    assert state_halted.is_open is False
    assert "Circuit Breaker" in state_halted.reason

    # Clean up halt
    set_exchange_halt(Exchange.NSE, False)


def test_weekend_and_holiday_logic():
    """Verify weekend, holiday exclusions and trading day arithmetic."""
    sat_holiday = date(2026, 8, 15)  # Independence Day Saturday
    assert is_trading_day(sat_holiday, Exchange.NSE) is False

    sun_day = date(2026, 8, 16)
    assert is_trading_day(sun_day, Exchange.NSE) is False

    mon_day = date(2026, 8, 17)
    assert is_trading_day(mon_day, Exchange.NSE) is True

    prev_day = get_previous_trading_day(mon_day, Exchange.NSE)
    assert prev_day == date(2026, 8, 14)  # Friday

    next_day = get_next_trading_day(date(2026, 8, 14), Exchange.NSE)
    assert next_day == date(2026, 8, 17)  # Monday


def test_multi_asset_sessions():
    """Verify MCX Commodity, Currency CDS, US Equities, NSE Evening Derivatives, and 24/7 Crypto sessions."""
    dt_evening = datetime(2026, 8, 14, 20, 0, 0, tzinfo=IST)

    assert is_market_open(dt_evening, Exchange.NSE) is False
    assert is_market_open(dt_evening, Exchange.NSE_EVENING) is True
    assert is_market_open(dt_evening, Exchange.MCX) is True
    assert is_market_open(dt_evening, Exchange.US_EQUITY) is True
    assert is_market_open(dt_evening, Exchange.CRYPTO) is True


def test_trading_day_walk_bounded_on_calendar_failure(monkeypatch):
    """P0: with is_trading_day failing CLOSED forever (dead holiday source),
    the walkers must raise MarketClosedError — never hang the EOD loop."""
    from mjonai.core import time_utils as tu
    from mjonai.core.exceptions import MarketClosedError
    monkeypatch.setattr(tu, "is_trading_day", lambda *a, **k: False)
    with pytest.raises(MarketClosedError):
        tu.get_previous_trading_day(date(2026, 8, 14), tu.Exchange.NSE)
    with pytest.raises(MarketClosedError):
        tu.get_next_trading_day(date(2026, 8, 14), tu.Exchange.NSE)
    with pytest.raises(MarketClosedError):
        tu.get_nifty_weekly_expiry(date(2026, 8, 14), tu.Exchange.NSE)
    with pytest.raises(MarketClosedError):
        tu.get_nifty_monthly_expiry(date(2026, 8, 14), tu.Exchange.NSE)


def test_exchange_calendar_dynamic_loading():
    """Verify dynamic loading of exchange calendar and fallback handling."""
    # 1. Test missing library graceful handling (should return empty set and not crash)
    test_year = 2099
    with patch("importlib.import_module", side_effect=ImportError("Mocked missing library")):
        _holiday_cache.pop(("TEST_EX", test_year), None)
        holidays = _load_holidays(test_year, "TEST_EX")
        assert isinstance(holidays, set)

    # 2. Test successful holiday cache lookup
    _holiday_cache[("NSE", 2026)] = {"2026-08-15", "2026-01-26"}
    cached = _load_holidays(2026, "NSE")
    assert "2026-08-15" in cached



def test_options_expiry_helpers():
    """Verify weekly and monthly options expiry calculation and DTE."""
    # August 2026: NSE circular 111/2025 - expiries moved to TUESDAY.
    # Last Tuesday of Aug 2026 is 2026-08-25.
    monthly_aug = get_nifty_monthly_expiry(date(2026, 8, 1))
    assert monthly_aug.weekday() == 1 or not is_trading_day(date(2026, 8, monthly_aug.day + 1))
    assert monthly_aug.month == 8

    # Weekly expiry: given Tuesday 2026-08-11 -> same-day expiry 2026-08-11
    weekly_exp = get_nifty_weekly_expiry(date(2026, 8, 11))
    assert weekly_exp == date(2026, 8, 11)

    # is_expiry_day check
    assert is_expiry_day(date(2026, 8, 11)) is True
    assert is_expiry_day(date(2026, 8, 12)) is False

    # days_to_expiry check
    dte = days_to_expiry(datetime(2026, 8, 11, 9, 30, tzinfo=IST), expiry=date(2026, 8, 11))
    assert 0.0 < dte < 1.0  # Expiring today at 15:30


def test_is_nse_holiday_helper():
    """Verify _is_nse_holiday correctly identifies weekdays vs holidays vs weekends."""
    assert _is_nse_holiday(date(2026, 8, 16)) is True   # Sunday
    assert _is_nse_holiday(date(2026, 8, 17)) is False  # Monday (trading day)
    assert _is_nse_holiday("2026-08-17") is False

