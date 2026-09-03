"""
Unit test suite for core/exceptions.py
Verifies typed exception hierarchies and context propagation.
"""

import pytest
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from mjonai.core.exceptions import (
    MJONAIError,
    MarketClosedError,
    ExchangeHaltError,
    RiskLimitError,
    RiskKillLineBreachedError,
    DailyLossLimitReachedError,
    CooldownActiveError,
    MaxOpenPositionsReachedError,
    DataFeedError,
    DataFeedStaleError,
    TokenResolutionError,
    BrokerAuthError,
    OrderExecutionError,
    AgentReasoningError,
    PatternMemoryError,
)


def test_base_mjonai_error_with_context():
    """Verify base exception stores and formats message and context."""
    err = MJONAIError("Test error occurred", context={"symbol": "RELIANCE", "price": 2500.0})
    assert err.message == "Test error occurred"
    assert err.context["symbol"] == "RELIANCE"
    assert "Context:" in str(err)


def test_exception_hierarchies():
    """Verify inheritance hierarchies for risk and data feed exceptions."""
    assert issubclass(RiskKillLineBreachedError, RiskLimitError)
    assert issubclass(DailyLossLimitReachedError, RiskLimitError)
    assert issubclass(CooldownActiveError, RiskLimitError)
    assert issubclass(RiskLimitError, MJONAIError)

    assert issubclass(DataFeedStaleError, DataFeedError)
    assert issubclass(TokenResolutionError, DataFeedError)
    assert issubclass(DataFeedError, MJONAIError)

    assert issubclass(MarketClosedError, MJONAIError)
    assert issubclass(BrokerAuthError, MJONAIError)
    assert issubclass(OrderExecutionError, MJONAIError)
