"""
Unit test suite for orchestration/market_session_lifecycle.py
Validates market operational windows, calendar day gates, and order entry boundaries.
"""

from datetime import datetime, time as dtime
import pytest

from orchestration.market_session_lifecycle import (
    MarketSessionState,
    get_current_session_state,
    is_order_entry_allowed,
    is_risk_monitoring_active,
    get_session_description,
)


def test_session_state_transitions_throughout_day():
    """Verify that every hour of the trading day maps to the exact institutional session state."""
    base_date = datetime(2026, 9, 3)  # Active trading day

    # 1. 08:26 IST -> PRE_MARKET
    dt_pre = base_date.replace(hour=8, minute=26)
    assert get_current_session_state(dt_pre, trading_day_override=True) == MarketSessionState.PRE_MARKET

    # 2. 09:05 IST -> AUCTION_DISCOVERY
    dt_auc = base_date.replace(hour=9, minute=5)
    assert get_current_session_state(dt_auc, trading_day_override=True) == MarketSessionState.AUCTION_DISCOVERY

    # 3. 10:30 IST -> REGULAR_MARKET
    dt_reg = base_date.replace(hour=10, minute=30)
    assert get_current_session_state(dt_reg, trading_day_override=True) == MarketSessionState.REGULAR_MARKET

    # 4. 15:20 IST -> INTRADAY_SQUARE_OFF
    dt_sq = base_date.replace(hour=15, minute=20)
    assert get_current_session_state(dt_sq, trading_day_override=True) == MarketSessionState.INTRADAY_SQUARE_OFF

    # 5. 15:45 IST -> POST_MARKET_EOD
    dt_eod = base_date.replace(hour=15, minute=45)
    assert get_current_session_state(dt_eod, trading_day_override=True) == MarketSessionState.POST_MARKET_EOD

    # 6. 22:00 IST -> OVERNIGHT_OFFLINE
    dt_night = base_date.replace(hour=22, minute=0)
    assert get_current_session_state(dt_night, trading_day_override=True) == MarketSessionState.OVERNIGHT_OFFLINE


def test_weekend_holiday_session_override():
    """Verify that weekends or holidays always resolve to OVERNIGHT_OFFLINE regardless of time."""
    midday = datetime(2026, 9, 3, 11, 30)
    # Market hours, but trading_day_override=False (holiday/weekend)
    assert get_current_session_state(midday, trading_day_override=False) == MarketSessionState.OVERNIGHT_OFFLINE


def test_order_entry_allowed_boundary():
    """Verify that fresh order entries are only permitted during REGULAR_MARKET hours."""
    assert is_order_entry_allowed(MarketSessionState.REGULAR_MARKET) is True
    assert is_order_entry_allowed(MarketSessionState.PRE_MARKET) is False
    assert is_order_entry_allowed(MarketSessionState.AUCTION_DISCOVERY) is False
    assert is_order_entry_allowed(MarketSessionState.INTRADAY_SQUARE_OFF) is False
    assert is_order_entry_allowed(MarketSessionState.POST_MARKET_EOD) is False
    assert is_order_entry_allowed(MarketSessionState.OVERNIGHT_OFFLINE) is False


def test_risk_monitoring_active_boundary():
    """Verify that risk monitors are active during regular market and intraday square-off."""
    assert is_risk_monitoring_active(MarketSessionState.REGULAR_MARKET) is True
    assert is_risk_monitoring_active(MarketSessionState.INTRADAY_SQUARE_OFF) is True
    assert is_risk_monitoring_active(MarketSessionState.OVERNIGHT_OFFLINE) is False
    assert is_risk_monitoring_active(MarketSessionState.PRE_MARKET) is False


def test_session_description_completeness():
    """Verify all session states have clear human-readable operational descriptions."""
    for state in MarketSessionState:
        desc = get_session_description(state)
        assert len(desc) > 10
        assert "Unknown" not in desc


def test_special_muhurat_trading_session():
    """Verify that a special session (e.g. Diwali Muhurat 18:15-19:15) dynamically overrides normal windows."""
    from datetime import date, time as dtime
    from orchestration.market_session_lifecycle import (
        SpecialTradingSession,
        register_special_session,
        clear_special_sessions,
    )

    muhurat_date = date(2026, 11, 8)  # Diwali Sunday
    spec = SpecialTradingSession(
        session_date=muhurat_date,
        pre_market_start=dtime(17, 45),
        auction_start=dtime(18, 0),
        regular_start=dtime(18, 15),
        square_off_start=dtime(19, 10),
        regular_end=dtime(19, 15),
        eod_end=dtime(19, 45),
        description="Diwali Muhurat Trading Session",
    )
    register_special_session(spec)

    try:
        # 1. 17:50 IST -> PRE_MARKET
        dt_pre = datetime(2026, 11, 8, 17, 50)
        assert get_current_session_state(dt_pre) == MarketSessionState.PRE_MARKET

        # 2. 18:05 IST -> AUCTION_DISCOVERY
        dt_auc = datetime(2026, 11, 8, 18, 5)
        assert get_current_session_state(dt_auc) == MarketSessionState.AUCTION_DISCOVERY

        # 3. 18:30 IST -> REGULAR_MARKET (Orders Allowed!)
        dt_reg = datetime(2026, 11, 8, 18, 30)
        assert get_current_session_state(dt_reg) == MarketSessionState.REGULAR_MARKET
        assert is_order_entry_allowed(get_current_session_state(dt_reg)) is True

        # 4. 19:12 IST -> INTRADAY_SQUARE_OFF
        dt_sq = datetime(2026, 11, 8, 19, 12)
        assert get_current_session_state(dt_sq) == MarketSessionState.INTRADAY_SQUARE_OFF

        # 5. 19:30 IST -> POST_MARKET_EOD
        dt_eod = datetime(2026, 11, 8, 19, 30)
        assert get_current_session_state(dt_eod) == MarketSessionState.POST_MARKET_EOD

        # 6. 21:00 IST -> OVERNIGHT_OFFLINE
        dt_off = datetime(2026, 11, 8, 21, 0)
        assert get_current_session_state(dt_off) == MarketSessionState.OVERNIGHT_OFFLINE
    finally:
        clear_special_sessions()

