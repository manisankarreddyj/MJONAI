"""
Module: orchestration/market_session_lifecycle.py
Purpose: SOTA Market Session Lifecycle State Machine for Indian Equity Markets (NSE/BSE).
         Formalizes market operational windows: Pre-market, Opening Auction,
         Regular Hours, MIS Square-off, EOD Reconciliation, Overnight Maintenance,
         and Special Sessions (Diwali Muhurat Trading & Disaster Recovery Mock Drills).
"""

from dataclasses import dataclass
from datetime import datetime, date, time as dtime
from enum import Enum
import logging
from typing import Optional, Dict, Any, List

from mjonai.core.time_utils import now_ist, is_trading_day

logger = logging.getLogger(__name__)


class MarketSessionState(str, Enum):
    """Formal states of the Indian equity market operating day."""
    OVERNIGHT_OFFLINE = "OVERNIGHT_OFFLINE"       # 16:30 - 08:25 IST, Weekends & Exchange Holidays
    PRE_MARKET = "PRE_MARKET"                     # 08:25 - 09:00 IST (Token sync, risk reset, TOTP login)
    AUCTION_DISCOVERY = "AUCTION_DISCOVERY"       # 09:00 - 09:15 IST (Pre-open opening auction)
    REGULAR_MARKET = "REGULAR_MARKET"             # 09:15 - 15:15 IST (Active algorithmic trading)
    INTRADAY_SQUARE_OFF = "INTRADAY_SQUARE_OFF"   # 15:15 - 15:30 IST (MIS auto square-off & liquidation)
    POST_MARKET_EOD = "POST_MARKET_EOD"           # 15:30 - 16:30 IST (3-way reconciliation & feedback learning)


@dataclass(frozen=True)
class SpecialTradingSession:
    """Contract for non-standard exchange sessions (e.g. Muhurat Trading or Saturday Live Mock Drills)."""
    session_date: date
    pre_market_start: dtime
    auction_start: dtime
    regular_start: dtime
    square_off_start: dtime
    regular_end: dtime
    eod_end: dtime
    description: str


# Global Registry for Special Exchange Sessions
_SPECIAL_SESSIONS: Dict[date, SpecialTradingSession] = {}


def register_special_session(session: SpecialTradingSession) -> None:
    """Register a special exchange session (e.g. Diwali Muhurat or Saturday DR Drill)."""
    _SPECIAL_SESSIONS[session.session_date] = session
    logger.info(f"[MarketLifecycle] Registered special session for {session.session_date}: {session.description}")


def clear_special_sessions() -> None:
    """Clear registered special sessions (useful for tests and resets)."""
    _SPECIAL_SESSIONS.clear()


def get_current_session_state(
    current_time: Optional[datetime] = None,
    trading_day_override: Optional[bool] = None,
) -> MarketSessionState:
    """
    Determine the current market session state based on IST clock and calendar rules.
    Respects special sessions (Muhurat), weekends, and NSE/BSE holidays.
    """
    now = current_time or now_ist()
    d = now.date()
    t = now.time()

    # 1. Check for registered Special Trading Session on this date
    if d in _SPECIAL_SESSIONS:
        spec = _SPECIAL_SESSIONS[d]
        if spec.pre_market_start <= t < spec.auction_start:
            return MarketSessionState.PRE_MARKET
        elif spec.auction_start <= t < spec.regular_start:
            return MarketSessionState.AUCTION_DISCOVERY
        elif spec.regular_start <= t < spec.square_off_start:
            return MarketSessionState.REGULAR_MARKET
        elif spec.square_off_start <= t < spec.regular_end:
            return MarketSessionState.INTRADAY_SQUARE_OFF
        elif spec.regular_end <= t < spec.eod_end:
            return MarketSessionState.POST_MARKET_EOD
        else:
            return MarketSessionState.OVERNIGHT_OFFLINE

    # 2. Check standard trading day calendar rules
    is_active_day = is_trading_day(d) if trading_day_override is None else trading_day_override
    if not is_active_day:
        return MarketSessionState.OVERNIGHT_OFFLINE

    # 3. Standard NSE/BSE time-of-day intervals (IST)
    if dtime(8, 25) <= t < dtime(9, 0):
        return MarketSessionState.PRE_MARKET
    elif dtime(9, 0) <= t < dtime(9, 15):
        return MarketSessionState.AUCTION_DISCOVERY
    elif dtime(9, 15) <= t < dtime(15, 15):
        return MarketSessionState.REGULAR_MARKET
    elif dtime(15, 15) <= t < dtime(15, 30):
        return MarketSessionState.INTRADAY_SQUARE_OFF
    elif dtime(15, 30) <= t < dtime(16, 30):
        return MarketSessionState.POST_MARKET_EOD
    else:
        return MarketSessionState.OVERNIGHT_OFFLINE


def get_session_description(state: MarketSessionState) -> str:
    """Provide a human-readable operational description for each state."""
    descriptions = {
        MarketSessionState.OVERNIGHT_OFFLINE: "Exchange Closed — Overnight Maintenance, Data Sync & Factor Research",
        MarketSessionState.PRE_MARKET: "Pre-Market Preparation — Daily State Reset, Token Map Sync & Broker Authentication",
        MarketSessionState.AUCTION_DISCOVERY: "NSE Pre-Open Auction — Discovery Orders, Indicative Equilibrium & Gap Analysis",
        MarketSessionState.REGULAR_MARKET: "Regular Market Hours — Multi-Strategy Scanning, AI Consensus & Fast SL Monitoring",
        MarketSessionState.INTRADAY_SQUARE_OFF: "MIS Square-off Window — Mandatory Intraday Liquidation & Stop-Loss Exits",
        MarketSessionState.POST_MARKET_EOD: "Post-Market EOD — 3-Way Reconciliation, Institutional Metrics & Model Feedback",
    }
    return descriptions.get(state, "Unknown Market Session")
