# -*- coding: utf-8 -*-
"""
Module: mjonai/agents/multi_template_voting.py
Purpose: Multi-template majority voting for LLM consensus.

CONCEPT SOURCE (clean-room, no code copied): FinGPT's multi-template voting approach.
Re-implemented here as a lightweight majority-voting layer over LLM prompts.
NOT a LoRA fine-tuning - just prompt engineering with majority vote.
License: MIT (compatible with MJONAI's personal-use posture).
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

# ─── Template Configurations ───────────────────────────────────────────────────

TEMPLATE_CONFIGS: Dict[str, Dict[str, Any]] = {
    "bullish_bias": {
        "name": "Bullish Bias Template",
        "prompt": "Analyze {symbol} from a bullish perspective. Focus on positive catalysts, growth drivers, and upside potential. Return: VERDICT (BUY/HOLD/SELL), CONFIDENCE (0-100), KEY_REASONS (bullet points).",
        "weight": 1.0,
    },
    "bearish_bias": {
        "name": "Bearish Bias Template",
        "prompt": "Analyze {symbol} from a bearish perspective. Focus on risks, downside catalysts, and valuation concerns. Return: VERDICT (BUY/HOLD/SELL), CONFIDENCE (0-100), KEY_REASONS (bullet points).",
        "weight": 1.0,
    },
    "neutral_analysis": {
        "name": "Neutral Analysis Template",
        "prompt": "Provide a balanced analysis of {symbol}. Weigh both bullish and bearish factors equally. Return: VERDICT (BUY/HOLD/SELL), CONFIDENCE (0-100), KEY_REASONS (bullet points).",
        "weight": 1.0,
    },
    "risk_focused": {
        "name": "Risk-Focused Template",
        "prompt": "Analyze {symbol} with emphasis on downside risk, drawdown potential, and risk-adjusted returns. Return: VERDICT (BUY/HOLD/SELL), CONFIDENCE (0-100), KEY_REASONS (bullet points).",
        "weight": 1.0,
    },
    "valuation_focused": {
        "name": "Valuation-Focused Template",
        "prompt": "Analyze {symbol} from a valuation perspective. Focus on P/E, P/B, DCF, and relative valuation vs peers. Return: VERDICT (BUY/HOLD/SELL), CONFIDENCE (0-100), KEY_REASONS (bullet points).",
        "weight": 1.0,
    },
    "momentum_focused": {
        "name": "Momentum-Focused Template",
        "prompt": "Analyze {symbol} from a technical momentum perspective. Focus on trend, RSI, MACD, volume, and price action. Return: VERDICT (BUY/HOLD/SELL), CONFIDENCE (0-100), KEY_REASONS (bullet points).",
        "weight": 1.0,
    },
}

# Voting Configuration
VOTING_CONFIG: Dict[str, Any] = {
    "min_templates": 3,
    "max_templates": 5,
    "consensus_threshold": 0.6,
    "unanimous_bonus": 0.1,
}


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class TemplateResult:
    template_name: str
    verdict: str  # BUY/HOLD/SELL
    confidence: int  # 0-100
    key_reasons: List[str]
    raw_response: str


@dataclass
class VotingResult:
    consensus_verdict: str  # BUY/HOLD/SELL/NO_CONSENSUS
    consensus_confidence: int  # 0-100
    vote_counts: Dict[str, int]  # BUY: 3, HOLD: 1, etc.
    template_results: List[TemplateResult]
    consensus_achieved: bool
    notes: str


# ─── Multi-Template Voting Engine ───────────────────────────────────────────

class MultiTemplateVoter:
    """Multi-template majority voting engine for LLM consensus."""

    def __init__(self, templates: Optional[List[str]] = None):
        """Initialize with specific templates or use all available."""
        self.templates = templates or list(TEMPLATE_CONFIGS.keys())
        self.templates = self.templates[:VOTING_CONFIG["max_templates"]]
        if len(self.templates) < VOTING_CONFIG["min_templates"]:
            raise ValueError(f"Need at least {VOTING_CONFIG['min_templates']} templates")

    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response into structured format."""
        try:
            verdict = None
            confidence = 50
            reasons = []
            for line in response.split(chr(10)):
                line = line.strip()
                if line.startswith("VERDICT:"):
                    verdict = line.split(":", 1)[1].strip().upper()
                elif line.startswith("CONFIDENCE:"):
                    try:
                        confidence = int(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass
                elif line.startswith("REASONS:") or line.startswith("KEY_REASONS:"):
                    reasons_str = line.split(":", 1)[1].strip()
                    reasons = [r.strip() for r in reasons_str.replace("[", "").replace("]", "").split(",") if r.strip()]
            return {"verdict": verdict, "confidence": confidence, "reasons": reasons}
        except Exception:
            return None

    def _run_template(self, template_key: str, symbol: str, llm_callable) -> Optional[Dict[str, Any]]:
        """Run a single template against the LLM."""
        config = TEMPLATE_CONFIGS.get(template_key)
        if not config:
            return None
        prompt = config["prompt"].format(symbol=symbol)
        try:
            response = llm_callable(prompt)
            parsed = self._parse_llm_response(response)
            if parsed and parsed.get("verdict") in ("BUY", "HOLD", "SELL"):
                return {
                    "template": template_key,
                    "verdict": parsed["verdict"],
                    "confidence": parsed.get("confidence", 50),
                    "reasons": parsed.get("reasons", []),
                    "weight": config.get("weight", 1.0),
                }
        except Exception:
            pass
        return None

    def vote(self, symbol: str, llm_callable) -> Dict[str, Any]:
        """Run multi-template voting for a symbol."""
        results = []
        for template in self.templates:
            result = self._run_template(template, symbol, llm_callable)
            if result:
                results.append(result)

        if not results:
            return {
                "consensus_verdict": "NO_CONSENSUS",
                "consensus_confidence": 0,
                "vote_counts": {},
                "template_results": [],
                "consensus_achieved": False,
                "notes": "No valid template responses",
            }

        # Weighted majority vote
        vote_weights = Counter()
        confidence_sum = Counter()
        for r in results:
            vote_weights[r["verdict"]] += r["weight"]
            confidence_sum[r["verdict"]] += r["confidence"]

        # Find majority verdict
        total_weight = sum(vote_weights.values())
        consensus_verdict = vote_weights.most_common(1)[0][0] if vote_weights else "NO_CONSENSUS"
        consensus_weight = vote_weights.get(consensus_verdict, 0)
        consensus_ratio = consensus_weight / total_weight if total_weight > 0 else 0

        # Average confidence for consensus verdict
        avg_confidence = int(confidence_sum[consensus_verdict] / vote_weights[consensus_verdict]) if vote_weights[consensus_verdict] > 0 else 0

        # Check consensus threshold
        consensus_achieved = consensus_ratio >= VOTING_CONFIG["consensus_threshold"]

        # Unanimous bonus
        if consensus_achieved and consensus_ratio == 1.0:
            avg_confidence = min(100, avg_confidence + int(100 * VOTING_CONFIG["unanimous_bonus"]))

        notes = f"{len(results)} templates voted. Consensus: {consensus_verdict} ({consensus_ratio:.0%})"
        if not consensus_achieved:
            notes += f" - BELOW THRESHOLD ({VOTING_CONFIG['consensus_threshold']:.0%})"

        return {
            "consensus_verdict": consensus_verdict if consensus_achieved else "NO_CONSENSUS",
            "consensus_confidence": avg_confidence if consensus_achieved else 0,
            "vote_counts": dict(vote_weights),
            "template_results": results,
            "consensus_achieved": consensus_achieved,
            "notes": notes,
        }


# ─── Convenience Function ───────────────────────────────────────────────────

def multi_template_vote(symbol: str, llm_callable, templates: Optional[List[str]] = None) -> Dict[str, Any]:
    """Convenience function for multi-template voting."""
    voter = MultiTemplateVoter(templates)
    return voter.vote(symbol, llm_callable)