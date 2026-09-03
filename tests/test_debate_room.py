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
