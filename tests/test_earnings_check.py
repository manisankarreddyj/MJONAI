"""
Unit & Boundary Integration Tests for data/earnings/earnings_check.py
Corporate Earnings & Board Meeting Risk Sentry.
"""

from datetime import date, datetime, timedelta
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import pytest

# Ensure workspace root is in sys.path
_root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

from mjonai.data.earnings.earnings_check import (
    EarningsDataUnavailableError,
    EarningsRiskLevel,
    EarningsRiskSnapshot,
    DEFAULT_EARNINGS_BLOCK_DAYS,
    is_trading_day,
    trading_days_until,
    check_earnings_risk,
    check_earnings_risk_bulk,
    is_iv_crush_zone,
    is_post_earnings_window,
    clear_earnings_cache,
    get_earnings_cache_size,
)


@pytest.fixture(autouse=True)
def clean_cache():
    """Ensure clean in-memory earnings cache between tests."""
    clear_earnings_cache()
    yield
    clear_earnings_cache()


# ── 1. ENUMS & DATA CONTRACT TESTS ───────────────────────────────────────────

def test_earnings_risk_level_enums():
    assert EarningsRiskLevel.SAFE.value == "SAFE"
    assert EarningsRiskLevel.WARNING.value == "WARNING"
    assert EarningsRiskLevel.BLOCKED.value == "BLOCKED"
    assert EarningsRiskLevel.UNKNOWN.value == "UNKNOWN"


def test_earnings_risk_snapshot_contract():
    now = datetime.now()
    earnings_dt = date(2026, 8, 25)
    snap = EarningsRiskSnapshot(
        symbol="RELIANCE",
        is_safe=False,
        earnings_date=earnings_dt,
        trading_days_until=2,
        risk_level=EarningsRiskLevel.BLOCKED,
        source="YFINANCE",
        message="Earnings in 2 trading day(s) - blocked",
        timestamp=now,
    )
    assert snap.symbol == "RELIANCE"
    assert snap.is_safe is False
    assert snap.trading_days_until == 2
    assert snap.risk_level == EarningsRiskLevel.BLOCKED
    assert snap["is_safe"] is False
    assert snap.get("source") == "YFINANCE"

    # Tuple Unpacking Compatibility
    is_safe, msg = snap.to_tuple()
    assert is_safe is False
    assert "blocked" in msg

    # Serialization
    d = snap.to_dict()
    assert isinstance(d, dict)
    assert d["symbol"] == "RELIANCE"
    assert d["risk_level"] == "BLOCKED"
    assert d["earnings_date"] == "2026-08-25"


# ── 2. TRADING DAY & COUNTDOWN MATH TESTS ─────────────────────────────────────

def test_is_trading_day_weekend_and_weekdays():
    # A known Saturday / Sunday
    saturday = date(2026, 8, 22)
    sunday = date(2026, 8, 23)
    monday = date(2026, 8, 24)

    assert is_trading_day(saturday) is False
    assert is_trading_day(sunday) is False
    # Monday is a trading day if not a holiday
    assert isinstance(is_trading_day(monday), bool)


def test_trading_days_until_past_and_future():
    today = date(2026, 8, 17)  # Monday

    # Target is today or in past -> 0
    assert trading_days_until(date(2026, 8, 16), reference_date=today) == 0
    assert trading_days_until(today, reference_date=today) == 0

    # Target is 1 day ahead (Tuesday 2026-08-18) -> 1 trading day
    tuesday = date(2026, 8, 18)
    assert trading_days_until(tuesday, reference_date=today) == 1

    # Over a weekend (Friday to Monday) -> 1 trading day
    friday = date(2026, 8, 21)
    next_monday = date(2026, 8, 24)
    assert trading_days_until(next_monday, reference_date=friday) == 1


# ── 3. RISK ASSESSMENT & BLOCKING LOGIC ───────────────────────────────────────

@patch("mjonai.data.earnings.earnings_check.today_ist")
@patch("mjonai.data.earnings.earnings_check._get_earnings_yfinance")
def test_check_earnings_risk_blocked(mock_get_yf, mock_today):
    mock_today.return_value = date(2026, 8, 17)  # Monday
    mock_get_yf.return_value = date(2026, 8, 19)  # Wednesday (2 trading days away)

    snap = check_earnings_risk("RELIANCE", block_days=3)
    assert snap.is_safe is False
    assert snap.risk_level == EarningsRiskLevel.BLOCKED
    assert snap.trading_days_until == 2
    assert "signal blocked" in snap.message

    # Tuple unpacking test
    is_safe, msg = snap.to_tuple()
    assert is_safe is False
    assert "blocked" in msg


@patch("mjonai.data.earnings.earnings_check.today_ist")
@patch("mjonai.data.earnings.earnings_check._get_earnings_yfinance")
def test_check_earnings_risk_safe(mock_get_yf, mock_today):
    mock_today.return_value = date(2026, 8, 17)  # Monday
    mock_get_yf.return_value = date(2026, 9, 15)  # 20+ trading days away

    snap = check_earnings_risk("TCS", block_days=3)
    assert snap.is_safe is True
    assert snap.risk_level == EarningsRiskLevel.SAFE
    assert snap.trading_days_until is not None and snap.trading_days_until > 3
    assert "safe" in snap.message


@patch("mjonai.data.earnings.earnings_check._get_earnings_yfinance")
@patch("mjonai.data.earnings.earnings_check._get_earnings_nse")
@patch("mjonai.data.earnings.earnings_check.today_ist")
def test_check_earnings_risk_nse_fallback(mock_today, mock_nse, mock_yf):
    mock_today.return_value = date(2026, 8, 17)
    mock_yf.return_value = None  # yfinance fails
    mock_nse.return_value = date(2026, 8, 18)  # NSE returns tomorrow

    snap = check_earnings_risk("INFY", block_days=3)
    assert snap.is_safe is False
    assert snap.source == "NSE_SCRAPER"
    assert snap.trading_days_until == 1


@patch("mjonai.data.earnings.earnings_check._get_earnings_yfinance")
@patch("mjonai.data.earnings.earnings_check._get_earnings_nse")
@patch("mjonai.data.earnings.earnings_check.insert_system_log")
def test_check_earnings_risk_degraded_unknown_fallback(mock_log, mock_nse, mock_yf):
    """H12 settlement: both sources failing now FAILS CLOSED by default —
    the old unconditional permissive fallback was a blackout bypass. The
    permissive path survives only behind an explicit opt-in (RESEARCH)."""
    mock_yf.return_value = None
    mock_nse.return_value = None

    with pytest.raises(EarningsDataUnavailableError):
        check_earnings_risk("UNKNOWN_CORP", block_days=3)

    snap = check_earnings_risk(
        "UNKNOWN_CORP", block_days=3, allow_degraded_permissive=True
    )
    assert snap.is_safe is True  # explicit opt-in only (RESEARCH)
    assert snap.risk_level == EarningsRiskLevel.UNKNOWN
    assert snap.source == "DEGRADED_FALLBACK"
    assert snap.earnings_date is None
    assert mock_log.call_count >= 1  # both paths logged the source failure


# ── 4. IN-MEMORY TTL CACHE & BULK VECTOR TESTS ───────────────────────────────

@patch("mjonai.data.earnings.earnings_check.today_ist")
@patch("mjonai.data.earnings.earnings_check._get_earnings_yfinance")
def test_in_memory_ttl_cache_deduplication(mock_get_yf, mock_today):
    mock_today.return_value = date(2026, 8, 17)
    mock_get_yf.return_value = date(2026, 9, 10)

    # 1. First call queries provider and stores in cache
    s1 = check_earnings_risk("HDFCBANK", use_cache=True)
    assert get_earnings_cache_size() == 1
    assert mock_get_yf.call_count == 1

    # 2. Second call resolves directly from cache without hitting yfinance
    s2 = check_earnings_risk("HDFCBANK", use_cache=True)
    assert mock_get_yf.call_count == 1  # No additional network call
    assert s1.earnings_date == s2.earnings_date

    # 3. Clear cache
    clear_earnings_cache()
    assert get_earnings_cache_size() == 0


@patch("mjonai.data.earnings.earnings_check.today_ist")
@patch("mjonai.data.earnings.earnings_check._get_earnings_yfinance")
def test_check_earnings_risk_bulk(mock_get_yf, mock_today):
    mock_today.return_value = date(2026, 8, 17)
    mock_get_yf.side_effect = lambda sym: date(2026, 8, 18) if sym == "RELIANCE" else date(2026, 9, 20)

    bulk = check_earnings_risk_bulk(["RELIANCE", "TCS"])
    assert len(bulk) == 2
    assert bulk["RELIANCE"].is_safe is False
    assert bulk["TCS"].is_safe is True


# ── 5. VOLATILITY & PEAD DRIFT SENTRY TESTS ──────────────────────────────────

@patch("mjonai.data.earnings.earnings_check.today_ist")
@patch("mjonai.data.earnings.earnings_check._get_earnings_yfinance")
def test_is_iv_crush_zone(mock_get_yf, mock_today):
    mock_today.return_value = date(2026, 8, 17)

    # Earnings tomorrow -> within 1 day IV crush zone
    mock_get_yf.return_value = date(2026, 8, 18)
    assert is_iv_crush_zone("RELIANCE", window_days=1) is True

    # Earnings 10 days away -> not in IV crush zone
    mock_get_yf.return_value = date(2026, 8, 30)
    assert is_iv_crush_zone("TCS", window_days=1) is False
