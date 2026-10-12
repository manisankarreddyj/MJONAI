"""
Unit and Institutional Test Suite for Adversarial Debate Room Coordinator
(agents/debate_room.py)
"""

import pytest
from unittest.mock import patch, MagicMock

from mjonai.agents.debate_room import (
    conduct_adversarial_debate,
    DebateTranscript,
    DebateConsensusResult,
)


@pytest.mark.flaky
def test_conduct_adversarial_debate_unanimous_approval():
    """Verify Round 1 debate when Bull is strongly bullish and Bear has no veto."""
    mock_bull = {
        "verdict": "STRONG_BUY",
        "confidence": 85,
        "key_reasons": ["Breakout momentum confirmed"],
    }
    mock_bear = {
        "verdict": "APPROVE",
        "confidence": 75,
        "key_reasons": ["FII inflows supportive"],
        "red_flags": [],
    }
    mock_sup = {
        "approved": True,
        "final_decision": "APPROVE",
        "rejection_reason": "",
        "summary": "Trade approved by consensus",
        "deciding_factor": "Strong momentum",
    }

    signal = {"symbol": "RELIANCE", "strategy_id": "S01_MomentumRSI", "risk_reward": 2.4}

    with patch("mjonai.agents.debate_room.analyse_bull", return_value=mock_bull), \
         patch("mjonai.agents.debate_room.analyse_bear", return_value=mock_bear), \
         patch("mjonai.agents.debate_room.evaluate_supervisor", return_value=mock_sup):

        res = conduct_adversarial_debate(signal)
        assert res["approved"] is True
        assert res["final_decision"] == "APPROVE"
        assert res["consensus_score"] > 70
        assert res["transcript"]["rounds_conducted"] == 1


def test_conduct_adversarial_debate_two_rounds_with_rebuttal():
    """Verify Round 2 adversarial rebuttal triggers when Bear flags concerns."""
    mock_bull = {
        "verdict": "BUY",
        "confidence": 78,
        "key_reasons": ["Technical breakout"],
    }
    mock_bear = {
        "verdict": "CAUTION",
        "confidence": 65,
        "key_reasons": ["FII cash selling ₹600 Cr"],
        "red_flags": [],
    }
    mock_sup = {
        "approved": True,
        "final_decision": "APPROVE",
        "rejection_reason": "",
        "summary": "Approved with tight stop",
        "deciding_factor": "Momentum overrides mild FII selling",
    }

    signal = {"symbol": "INFY", "strategy_id": "S01_MomentumRSI", "risk_reward": 2.2}

    with patch("mjonai.agents.debate_room.analyse_bull", return_value=mock_bull), \
         patch("mjonai.agents.debate_room.analyse_bear", return_value=mock_bear), \
         patch("mjonai.agents.debate_room._conduct_bull_rebuttal", return_value="Sector RRG is Leading which decouples from broad selling"), \
         patch("mjonai.agents.debate_room.evaluate_supervisor", return_value=mock_sup):

        res = conduct_adversarial_debate(signal)
        assert res["approved"] is True
        assert res["transcript"]["rounds_conducted"] == 2
        assert res["transcript"]["bull_rebuttal"] is not None
        assert "Sector RRG is Leading" in res["transcript"]["bull_rebuttal"]


# ── Abstention contract (clean-room adoption of the ai-hedge-fund pattern) ──

_DETERMINISTIC_SUP = {
    "approved": True,
    "final_decision": "APPROVE",
    "rejection_reason": "",
    "summary": "Approved with tight stop",
    "deciding_factor": "Momentum overrides mild FII selling",
}


def _run_debate_with_bear(bear_verdict, bear_conf):
    """Hermetic debate runner: Bull 80 / Macro 60 fixed, only the Bear varies."""
    signal = {"symbol": "HDFCBANK", "strategy_id": "S01_MomentumRSI", "risk_reward": 2.5}
    mock_bull = {"verdict": "BUY", "confidence": 80, "key_reasons": ["Breakout"]}
    mock_bear = {"verdict": bear_verdict, "confidence": bear_conf, "key_reasons": [], "red_flags": []}
    mock_macro = {"verdict": "NEUTRAL", "conviction_score": 60, "key_drivers": []}

    with patch("mjonai.agents.debate_room.analyse_bull", return_value=mock_bull), \
         patch("mjonai.agents.debate_room.analyse_bear", return_value=mock_bear), \
         patch("mjonai.agents.debate_room.analyse_macro_flow", return_value=mock_macro), \
         patch("mjonai.agents.debate_room._conduct_bull_rebuttal", return_value="Structure intact"), \
         patch("mjonai.agents.debate_room.evaluate_supervisor", return_value=_DETERMINISTIC_SUP):
        return conduct_adversarial_debate(signal)


def test_bear_neutral_abstains_from_consensus_score():
    """A NEUTRAL Bear is an abstention: it must not move the consensus score.

    Regression pin for the abstention contract. The previous arithmetic folded
    NEUTRAL into `100 - confidence`, so an evidence-starved Bear (confidence 10)
    scored 90 while a confidently-NEUTRAL one (confidence 90) scored 10 — the less
    the Bear knew, the more it pushed the consensus. Abstention carries no weight
    either way; the remaining Bull/Macro weights renormalize.
    """
    scores = [_run_debate_with_bear("NEUTRAL", conf)["consensus_score"] for conf in (10, 50, 90)]

    # Renormalized Bull/Macro blend is independent of the abstaining Bear's confidence:
    # (80*0.40 + 60*0.30) / 0.70 = 71.43 -> 71
    assert scores == [71, 71, 71]
    # The old arithmetic produced 77 for the evidence-starved Bear — abstention must never vote.
    assert 77 not in scores


def test_bear_veto_still_lowers_consensus_score():
    """A directional Bear verdict must still count; only NEUTRAL is exempt."""
    res = _run_debate_with_bear("VETO", 90)

    # bear_trade_support = 100-90 = 10, weights unchanged: 80*0.4 + 10*0.3 + 60*0.3 = 53
    assert res["consensus_score"] == 53
    assert res["transcript"]["bear_initial_verdict"] == "VETO"


def test_agent_prompts_carry_evidence_boundary_and_abstention_rule():
    """Prompt-hygiene pin (clean-room adoption of the TradingAgents pattern).

    Every persona's system prompt must deny external tools/data, forbid inventing
    facts, and (for the voting advisors) define NEUTRAL as an abstention.
    """
    from mjonai.agents import bull, bear, supervisor

    for prompt in (bull._SYSTEM_PROMPT, bear._SYSTEM_PROMPT, supervisor._SYSTEM_PROMPT):
        assert "NO tools" in prompt
        assert "never invent" in prompt
    for prompt in (bull._SYSTEM_PROMPT, bear._SYSTEM_PROMPT):
        assert "abstention" in prompt
