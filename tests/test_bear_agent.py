"""
Unit and Institutional Test Suite for Bear Agent (Adversarial Risk Sentry)
(agents/bear.py)
"""

import pytest
from unittest.mock import patch, MagicMock

from mjonai.agents.bear import (
    analyse,
    _build_prompt,
    _fetch_market_context,
    BearAgentResult,
)
from mjonai.agents.llm_bridge import LLMInferenceResult


def test_build_prompt_includes_adversarial_threat_factors():
    """Verify prompt builder embeds promoter pledging, FII selling, and VIX spikes."""
    signal = {
        "symbol": "ADANIENT",
        "strategy_id": "S01_MomentumRSI",
        "direction": "LONG",
        "entry_price": 3100.0,
        "stop_loss": 2980.0,
        "target": 3300.0,
        "risk_reward": 1.67,
        "rsi": 78.5,
    }
    context = {
        "fii_net_cr": -1450.0,
        "fii_regime": "SEVERE_DRAIN",
        "vix": 22.4,
        "promoter_pledge": 72.5,
        "insider_activity": "Promoter selling",
        "market_breadth": "DEFENSIVE_ROTATION_RISK_OFF",
        "sector_rrg": "LAGGING",
        "macro_event_risk": "RBI_MPC_RATE_DECISION",
    }

    prompt = _build_prompt(signal, context)
    assert "ADANIENT" in prompt
    assert "-1450" in prompt
    assert "SEVERE_DRAIN" in prompt
    assert "72.5%" in prompt
    assert "RBI_MPC_RATE_DECISION" in prompt
    assert "LAGGING" in prompt


def test_bear_agent_analyse_deterministic_fallback():
    """Verify Bear agent operates smoothly via deterministic fallback when offline."""
    signal = {
        "symbol": "SBIN",
        "strategy_id": "S01_MomentumRSI",
        "direction": "LONG",
        "rsi": 56.0,
        "volume_ratio": 1.4,
    }
    fallback_res = LLMInferenceResult(
        success=False,
        vendor_used="fallback",
        model="RULES_ONLY",
        latency_ms=0.1,
        is_fallback=True,
        parsed_payload=None,
    )
    with patch("mjonai.agents.bear._log_agent_call"), patch("mjonai.agents.bear.query_llm_fast", return_value=fallback_res):
        res = analyse(signal)
        assert "verdict" in res
        assert res["verdict"] in ("APPROVE", "CAUTION", "NEUTRAL", "VETO")
        assert res["fallback_used"] is True
        assert "risk_summary" in res


def test_bear_agent_analyse_with_mocked_llm_veto():
    """Verify Bear agent properly emits VETO when high-risk red flags are detected."""
    mock_llm_res = LLMInferenceResult(
        success=True,
        vendor_used="gemini",
        model="gemini-2.5-flash",
        latency_ms=210.0,
        is_fallback=False,
        parsed_payload={
            "verdict": "VETO",
            "confidence": 95,
            "key_reasons": ["Severe FII institutional cash drain", "High promoter pledging >70%"],
            "red_flags": ["Distress promoter pledge 72.5%"],
            "insider_activity": "Promoter selling",
            "fii_sentiment": "SEVERE_DRAIN",
            "risk_summary": "High risk of institutional selloff and promoter distress.",
        },
        raw_response='{"verdict": "VETO", "confidence": 95}',
    )

    signal = {"symbol": "ADANIENT", "direction": "LONG"}
    with patch("mjonai.agents.bear.query_llm_fast", return_value=mock_llm_res), \
         patch("mjonai.agents.bear._log_agent_call") as mock_log:

        res = analyse(signal)
        assert res["verdict"] == "VETO"
        assert res["confidence"] == 95
        assert res["model_used"] == "gemini-2.5-flash"
        assert res["fallback_used"] is False
        assert len(res["red_flags"]) == 1
        assert "Distress promoter pledge" in res["red_flags"][0]
        mock_log.assert_called_once()
