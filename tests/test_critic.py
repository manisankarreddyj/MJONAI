"""
Unit and Institutional Test Suite for Post-Trade Critic & Reflection Agent
(agents/critic.py)
"""

import pytest
from unittest.mock import patch, MagicMock

from mjonai.agents.critic import (
    reflect_on_closed_trade,
    TradeReflectionResult,
)
from mjonai.agents.llm_bridge import LLMInferenceResult


def test_reflect_on_closed_trade_good_win():
    """Verify Good Win classification on clean profitable trades."""
    trade = {
        "id": "101",
        "symbol": "TCS",
        "strategy_id": "S01_MomentumRSI",
        "entry_price": 4150.0,
        "exit_price": 4310.0,
        "realized_pnl": 4000.0,
        "pnl_pct": 3.85,
        "exit_reason": "TARGET_TP1_HIT",
        "mae_pct": -0.45,
        "mfe_pct": 4.10,
        "holding_days": 3,
    }

    mock_llm_res = LLMInferenceResult(
        success=True,
        vendor_used="groq",
        model="llama-3.3-70b-versatile",
        latency_ms=120.0,
        is_fallback=False,
        parsed_payload={
            "execution_quality": "GOOD_WIN",
            "learning_insight": "Clean trend following execution with low drawdown.",
            "strategy_recommendation": "Parameters performing well in current regime.",
            "holding_efficiency": "HIGH",
        },
    )

    with patch("mjonai.agents.critic.query_llm_fast", return_value=mock_llm_res):
        res = reflect_on_closed_trade(trade)
        assert res["execution_quality"] == "GOOD_WIN"
        assert res["realized_pnl"] == 4000.0
        assert "Clean trend following" in res["learning_insight"]


def test_reflect_on_closed_trade_good_loss():
    """Verify Good Loss classification on disciplined stop loss exits."""
    trade = {
        "id": "102",
        "symbol": "SBIN",
        "strategy_id": "S03_TurtleBreakout",
        "entry_price": 820.0,
        "exit_price": 804.0,
        "realized_pnl": -1600.0,
        "pnl_pct": -1.95,
        "exit_reason": "TRAILING_STOP_LOSS",
        "mae_pct": -2.0,
        "mfe_pct": 0.5,
        "holding_days": 2,
    }

    with patch("mjonai.agents.critic.query_llm_fast", return_value=LLMInferenceResult(
        success=True, vendor_used="deterministic", model="rule_engine", latency_ms=1.0, is_fallback=True, parsed_payload={}
    )):
        res = reflect_on_closed_trade(trade)
        assert res["execution_quality"] == "GOOD_LOSS"
        assert res["realized_pnl"] == -1600.0
        assert "Controlled loss" in res["learning_insight"]
