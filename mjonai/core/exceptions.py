"""
Module: core/exceptions.py
Purpose: Domain-Specific Exception Hierarchy for MJONAI.
         Provides structured, typed error handling across Market State,
         Risk Management, Broker Execution, Data Feeds, and AI Reasoning.
"""

from typing import Optional, Dict, Any


class MJONAIError(Exception):
    """Base exception for all MJONAI domain errors."""
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        if self.context:
            return f"{self.message} | Context: {self.context}"
        return self.message


# ── MARKET & TIME EXCEPTIONS ─────────────────────────────────────────────────

class MarketClosedError(MJONAIError):
    """Raised when an action is attempted outside of market hours or on a holiday."""
    pass


class ExchangeHaltError(MJONAIError):
    """Raised during special market trading halts or emergency exchange pauses."""
    pass


# ── RISK & CAPITAL EXCEPTIONS ────────────────────────────────────────────────

class RiskLimitError(MJONAIError):
    """Base exception for all risk policy violations."""
    pass


class RiskKillLineBreachedError(RiskLimitError):
    """Raised when total lifetime portfolio drawdown exceeds the hard 15% Kill Line."""
    pass


class DailyLossLimitReachedError(RiskLimitError):
    """Raised when daily realized losses hit the daily loss limit threshold."""
    pass


class CooldownActiveError(RiskLimitError):
    """Raised when a trade is attempted during an active behavioral cooling-off window."""
    pass


class MaxOpenPositionsReachedError(RiskLimitError):
    """Raised when the portfolio is at maximum concurrent position capacity."""
    pass


# ── DATA FEED & BROKER EXCEPTIONS ────────────────────────────────────────────

class DataFeedError(MJONAIError):
    """Base exception for data feed and WebSocket failures."""
    pass


class DataFeedStaleError(DataFeedError):
    """Raised when incoming market tick data exceeds the staleness threshold."""
    pass


class TokenResolutionError(DataFeedError):
    """Raised when a trading symbol cannot be resolved to an exchange instrument token."""
    pass


class BrokerAuthError(MJONAIError):
    """Raised when broker API authentication (TOTP/JWT/API Key) fails."""
    pass


class OrderExecutionError(MJONAIError):
    """Raised when an order placement, modification, or cancellation is rejected by the broker."""
    pass


# ── REASONING & AGENT EXCEPTIONS ─────────────────────────────────────────────

class AgentReasoningError(MJONAIError):
    """Raised when an AI Committee agent fails to generate a valid structured verdict."""
    pass


class PatternMemoryError(MJONAIError):
    """Raised on pattern database corruption or quarantine state violations."""
    pass
