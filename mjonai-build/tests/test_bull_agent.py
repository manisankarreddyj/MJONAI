"""
Unit and Institutional Test Suite for Bull Agent (Technical Analyst Persona)
(agents/bull.py)
"""

import pytest
from unittest.mock import patch, MagicMock

from agents.bull import (
    analyse,
    _build_prompt,
    BullAgentResult,
    STRATEGY_CONTEXT_MAP,
)
from agents.llm_bridge import LLMInferenceResult


def test_strategy_context_covers_all_twelve_strategies():
    """Verify all 12 strategies S01 to S12 are registered in Bull context."""
    for i in range(1, 13):
        strat_key = f"S{i:02d}"
        matching = [k for k in STRATEGY_CONTEXT_MAP.keys() if k.startswith(strat_key)]
        assert len(matching) >= 1, f"Missing strategy {strat_key} in STRATEGY_CONTEXT_MAP"


def test_build_prompt_includes_macro_and_devil_checks():
    """Verify prompt builder formats signal, VIX, FII, and RRG."""
    signal = {
        "symbol": "TCS",
        "strategy_id": "S01_MomentumRSI",
        "entry_price": 4200.0,
        "stop_loss": 4120.0,
        "target": 4360.0,
        "risk_reward": 2.0,
        "confidence": 75,
        "volume_ratio": 1.8,
        "rsi": 62.5,
        "vix_at_signal": 13.8,
        "reasons": ["EMA aligned", "MACD bullish"],
    }
    checks = ["Liquidity Check", "Event Risk", "Gap Risk"]
    macro = {
        "fii_regime": "MEGA_BULLISH",
        "fii_long_short_ratio": 1.45,
        "sector_rrg_quadrant": "LEADING",
        "market_breadth": "AGGRESSIVE_RISK_ON",
    }

    prompt = _build_prompt(signal, checks, macro_context=macro)
    assert "TCS" in prompt
    assert "S01_MomentumRSI" in prompt
    assert "MEGA_BULLISH" in prompt
    assert "LEADING" in prompt
    assert "Liquidity Check" in prompt


def test_bull_agent_analyse_deterministic_fallback():
    """Verify Bull agent operates smoothly via deterministic fallback when offline."""
    signal = {
        "symbol": "INFY",
        "strategy_id": "S01_MomentumRSI",
        "direction": "LONG",
        "rsi": 58.0,
        "volume_ratio": 1.6,
        "sector_multiplier": 1.15,
    }
    fallback_res = LLMInferenceResult(
        success=True,
        vendor_used="deterministic_fallback",
        model="quantitative_rule_engine",
        latency_ms=0.1,
        is_fallback=True,
        parsed_payload={
            "verdict": "BUY",
            "confidence": 75,
            "key_reasons": ["Technical momentum aligned"],
            "concerns": [],
        },
    )
    with patch("agents.bull._log_agent_call"), patch("agents.bull.query_llm_fast", return_value=fallback_res):
        res = analyse(signal, devil_checks_passed=["Risk Sentry Passed"])
        assert "verdict" in res
        assert res["verdict"] in ("BUY", "STRONG_BUY")
        assert res["confidence"] > 0
        assert res["fallback_used"] is True


def test_bull_agent_analyse_with_mocked_llm():
    """Verify Bull agent properly processes LLM response and maps verdicts."""
    mock_llm_res = LLMInferenceResult(
        success=True,
        vendor_used="groq",
        model="llama-3.3-70b-versatile",
        latency_ms=180.5,
        is_fallback=False,
        parsed_payload={
            "verdict": "STRONG_BUY",
            "confidence": 92,
            "key_reasons": ["Multi-timeframe momentum alignment", "Heavy volume breakout"],
            "concerns": [],
            "regime_note": "Risk-on market rally",
            "recommendation": "Execute standard tranche size",
        },
        raw_response='{"verdict": "STRONG_BUY", "confidence": 92}',
    )

    signal = {"symbol": "RELIANCE", "strategy_id": "S03_TurtleBreakout", "direction": "LONG"}
    with patch("agents.bull.query_llm_fast", return_value=mock_llm_res), \
         patch("agents.bull._log_agent_call") as mock_log:

        res = analyse(signal)
        assert res["verdict"] == "STRONG_BUY"
        assert res["confidence"] == 92
        assert res["model_used"] == "llama-3.3-70b-versatile"
        assert res["fallback_used"] is False
        assert len(res["key_reasons"]) == 2
        mock_log.assert_called_once()
