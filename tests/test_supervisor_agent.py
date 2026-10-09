"""
Unit and Institutional Test Suite for Supervisor Agent (CIO Consensus Arbiter)
(agents/supervisor.py)
"""

import pytest
from unittest.mock import patch, MagicMock

from mjonai.agents.supervisor import (
    evaluate,
    _apply_decision_rules,
    _build_prompt,
    SupervisorEvaluationResult,
)
from mjonai.agents.llm_bridge import LLMInferenceResult


def test_apply_decision_rules_approve_case():
    """Verify deterministic approval when all risk criteria and Bull analyst agree."""
    signal = {"symbol": "TCS", "risk_reward": 2.25}
    bull = {"verdict": "STRONG_BUY", "confidence": 76}
    checks = [f"Check {i}" for i in range(8)]

    decision, reason = _apply_decision_rules(signal, bull, checks)
    assert decision == "APPROVE"
    assert reason == ""


def test_apply_decision_rules_short_path_direction_aware():
    """SHORT fix: a bearish Bull verdict (SELL) confirms a SHORT; a BUY on a SHORT is a
    directional disagreement and is rejected. LONG behavior unchanged."""
    checks_8 = [f"Check {i}" for i in range(8)]
    short_sig = {"symbol": "INFY", "risk_reward": 2.5, "signal_direction": "SHORT"}
    # SHORT + bearish confirm -> APPROVE
    dec, rsn = _apply_decision_rules(short_sig, {"verdict": "SELL", "confidence": 70}, checks_8)
    assert dec == "APPROVE", rsn
    # SHORT + opposite-direction BUY -> REJECT
    dec2, rsn2 = _apply_decision_rules(short_sig, {"verdict": "BUY", "confidence": 80}, checks_8)
    assert dec2 == "REJECT"
    assert "insufficient conviction" in rsn2
    # SHORT + VETO -> REJECT
    dec3, _r = _apply_decision_rules(short_sig, {"verdict": "VETO", "confidence": 90}, checks_8)
    assert dec3 == "REJECT"
    # LONG guards: BUY approves, SELL rejected
    long_sig = {"symbol": "TCS", "risk_reward": 2.5}
    dec4, _r4 = _apply_decision_rules(long_sig, {"verdict": "BUY", "confidence": 70}, checks_8)
    assert dec4 == "APPROVE", _r4
    dec5, _r5 = _apply_decision_rules(long_sig, {"verdict": "SELL", "confidence": 70}, checks_8)
    assert dec5 == "REJECT"


def test_apply_decision_rules_reject_cases():
    """Verify deterministic rejections on failed thresholds."""
    signal = {"symbol": "INFY", "risk_reward": 2.2}
    bull_neutral = {"verdict": "NEUTRAL", "confidence": 55}
    checks_8 = [f"Check {i}" for i in range(8)]

    # 1. Bull Neutral
    dec, rsn = _apply_decision_rules(signal, bull_neutral, checks_8)
    assert dec == "REJECT"
    assert "insufficient conviction" in rsn

    # 2. Insufficient Risk Reward
    signal_low_rr = {"symbol": "INFY", "risk_reward": 1.6}
    bull_buy = {"verdict": "BUY", "confidence": 70}
    dec, rsn = _apply_decision_rules(signal_low_rr, bull_buy, checks_8)
    assert dec == "REJECT"
    assert "Real RR" in rsn

    # 3. Insufficient Devil Checks (in LIVE mode)
    checks_5 = [f"Check {i}" for i in range(5)]
    with patch("mjonai.agents.supervisor.SYSTEM_MODE", "LIVE"):
        dec, rsn = _apply_decision_rules(signal, bull_buy, checks_5)
        assert dec == "REJECT"
        assert "devil checks passed" in rsn


def test_apply_decision_rules_bear_veto_arbitration():
    """Verify Bear agent red flag halts approval unless super-majority high confidence."""
    signal = {"symbol": "ADANIENT", "risk_reward": 2.5}
    bull = {"verdict": "BUY", "confidence": 72}
    checks_8 = [f"Check {i}" for i in range(8)]
    bear_veto = {
        "verdict": "VETO",
        "red_flags": ["Promoter pledge 78% (Distress Alert)"],
    }

    dec, rsn = _apply_decision_rules(signal, bull, checks_8, bear_result=bear_veto)
    assert dec == "REJECT"
    assert "Bear Agent Critical Red Flag Veto" in rsn


def test_supervisor_evaluate_approved_generates_cio_report():
    """Verify Supervisor generates CIO report when signal is approved."""
    mock_llm_res = LLMInferenceResult(
        success=True,
        vendor_used="groq",
        model="llama-3.3-70b-versatile",
        latency_ms=145.0,
        is_fallback=False,
        parsed_payload={
            "summary": "TCS trade cleared for entry based on strong momentum.",
            "deciding_factor": "Multi-timeframe momentum alignment",
            "top_reasons": ["RSI 62 in momentum corridor", "All 8 risk sentry checks passed"],
            "risk_note": "Monitor IT sector breadth",
            "confidence_assessment": "High confidence setup",
        },
        raw_response='{"summary": "TCS trade cleared..."}',
    )

    signal = {"symbol": "TCS", "risk_reward": 2.4, "strategy_id": "S01_MomentumRSI"}
    bull = {"verdict": "STRONG_BUY", "confidence": 80, "key_reasons": ["Momentum breakout"]}
    checks = [f"Check {i}" for i in range(8)]

    with patch("mjonai.agents.supervisor.query_llm_fast", return_value=mock_llm_res), \
         patch("mjonai.agents.supervisor._log_agent_call"):

        res = evaluate(signal, bull, devil_checks_passed=checks)
        assert res["approved"] is True
        assert res["final_decision"] == "APPROVE"
        assert res["model_used"] == "llama-3.3-70b-versatile"
        assert len(res["top_reasons"]) >= 1


def test_supervisor_evaluate_rejected_skips_llm():
    """Verify Supervisor skips LLM inference on REJECT to save API quota."""
    signal = {"symbol": "TCS", "risk_reward": 1.5}  # Low RR
    bull = {"verdict": "NEUTRAL", "confidence": 40}

    with patch("mjonai.agents.supervisor.query_llm_fast") as mock_query, \
         patch("mjonai.agents.supervisor._log_agent_call"):

        res = evaluate(signal, bull)
        assert res["approved"] is False
        assert res["final_decision"] == "REJECT"
        assert res["model_used"] == "RULES_ONLY"
        assert res["latency_ms"] == 0.0
        mock_query.assert_not_called()
