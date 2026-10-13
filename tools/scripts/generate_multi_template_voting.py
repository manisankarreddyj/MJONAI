#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module: tools/scripts/generate_multi_template_voting.py

Purpose: Generate multi-template voting module for LLM consensus.
Clean-room reimplementation of FinGPT's multi-template voting approach.

This module provides a lightweight majority-voting layer that asks several
paraphrased prompts per security and takes the plurality vote.

NOT a LoRA fine-tuning - just prompt engineering with majority vote.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# Template configurations for multi-template voting
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

# Voting configuration
VOTING_CONFIG: Dict[str, Any] = {
    "min_templates": 3,
    "max_templates": 5,
    "consensus_threshold": 0.6,
    "unanimous_bonus": 0.1,
}


def generate_module() -> str:
    lines = [
        "# -*- coding: utf-8 -*-",
        "\"\"\"",
        "Module: mjonai/agents/multi_template_voting.py",
        "Purpose: Multi-template majority voting for LLM consensus.",
        "",
        "CONCEPT SOURCE (clean-room, no code copied): FinGPT's multi-template voting approach.",
        "Re-implemented here as a lightweight majority-voting layer over LLM prompts.",
        "NOT a LoRA fine-tuning - just prompt engineering with majority vote.",
        "License: MIT (compatible with MJONAI's personal-use posture).",
        "\"\"\"",
        "",
        "from __future__ import annotations",
        "",
        "import json",
        "from collections import Counter",
        "from typing import Any, Dict, List, Optional",
        "from dataclasses import dataclass",
        "",
        "",
        "# \u2500\u2500\u2500 Template Configurations \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
        "",
        "TEMPLATE_CONFIGS: Dict[str, Dict[str, Any]] = {",
    ]
    for key, config in TEMPLATE_CONFIGS.items():
        lines.append(f'    "{key}": {json.dumps(config)},')
    lines.append("}")
    lines.append("")

    lines.append("# \u2500\u2500\u2500 Voting Configuration \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
    lines.append("")
    lines.append("VOTING_CONFIG: Dict[str, Any] = {")
    for key, value in VOTING_CONFIG.items():
        lines.append(f'    "{key}": {json.dumps(value)},')
    lines.append("}")
    lines.append("")

    lines.append("# \u2500\u2500\u2500 Data Classes \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
    lines.append("")
    lines.append("@dataclass")
    lines.append("class TemplateResult:")
    lines.append("    template_name: str")
    lines.append("    verdict: str")
    lines.append("    confidence: int")
    lines.append("    key_reasons: List[str]")
    lines.append("    raw_response: str")
    lines.append("")

    lines.append("@dataclass")
    lines.append("class VotingResult:")
    lines.append("    consensus_verdict: str")
    lines.append("    consensus_confidence: int")
    lines.append("    vote_counts: Dict[str, int]")
    lines.append("    template_results: List[TemplateResult]")
    lines.append("    consensus_achieved: bool")
    lines.append("    notes: str")
    lines.append("")

    lines.append("# \u2500\u2500\u2500 Multi-Template Voting Engine \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
    lines.append("")
    lines.append("class MultiTemplateVoter:")
    lines.append('    """Multi-template majority voting engine for LLM consensus."""')
    lines.append("")
    lines.append("    def __init__(self, templates: Optional[List[str]] = None):")
    lines.append('        """Initialize with specific templates or use all available."""')
    lines.append("        self.templates = templates or list(TEMPLATE_CONFIGS.keys())")
    lines.append("        self.templates = self.templates[:VOTING_CONFIG[\"max_templates\"]]")
    lines.append("        if len(self.templates) < VOTING_CONFIG[\"min_templates\"]:")
    lines.append("            raise ValueError(f\"Need at least {VOTING_CONFIG['min_templates']} templates\")")
    lines.append("")
    lines.append("    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:")
    lines.append('        """Parse LLM response into structured format."""')
    lines.append("        try:")
    lines.append("            verdict = None")
    lines.append("            confidence = 50")
    lines.append("            reasons = []")
    lines.append("            for line in response.split(chr(10)):")
    lines.append("                line = line.strip()")
    lines.append("                if line.startswith(\"VERDICT:\"):")
    lines.append("                    verdict = line.split(\":\", 1)[1].strip().upper()")
    lines.append("                elif line.startswith(\"CONFIDENCE:\"):")
    lines.append("                    try:")
    lines.append("                        confidence = int(line.split(\":\", 1)[1].strip())")
    lines.append("                    except ValueError:")
    lines.append("                        pass")
    lines.append("                elif line.startswith(\"REASONS:\") or line.startswith(\"KEY_REASONS:\"):")
    lines.append("                    reasons_str = line.split(\":\", 1)[1].strip()")
    lines.append('                    reasons = [r.strip() for r in reasons_str.replace("[", "").replace("]", "").split(",") if r.strip()]')
    lines.append("            return {\"verdict\": verdict, \"confidence\": confidence, \"reasons\": reasons}")
    lines.append("        except Exception:")
    lines.append("            return None")
    lines.append("")
    lines.append("    def _run_template(self, template_key: str, symbol: str, llm_callable) -> Optional[Dict[str, Any]]:")
    lines.append('        """Run a single template against the LLM."""')
    lines.append("        config = TEMPLATE_CONFIGS.get(template_key)")
    lines.append("        if not config:")
    lines.append("            return None")
    lines.append("        prompt = config[\"prompt\"].format(symbol=symbol)")
    lines.append("        try:")
    lines.append("            response = llm_callable(prompt)")
    lines.append("            parsed = self._parse_llm_response(response)")
    lines.append("            if parsed and parsed.get(\"verdict\") in (\"BUY\", \"HOLD\", \"SELL\"):")
    lines.append("                return {")
    lines.append("                    \"template\": template_key,")
    lines.append("                    \"verdict\": parsed[\"verdict\"],")
    lines.append("                    \"confidence\": parsed.get(\"confidence\", 50),")
    lines.append("                    \"reasons\": parsed.get(\"reasons\", []),")
    lines.append("                    \"weight\": config.get(\"weight\", 1.0),")
    lines.append("                }")
    lines.append("        except Exception:")
    lines.append("            pass")
    lines.append("        return None")
    lines.append("")
    lines.append("    def vote(self, symbol: str, llm_callable) -> Dict[str, Any]:")
    lines.append('        """Run multi-template voting for a symbol."""')
    lines.append("        results = []")
    lines.append("        for template in self.templates:")
    lines.append("            result = self._run_template(template, symbol, llm_callable)")
    lines.append("            if result:")
    lines.append("                results.append(result)")
    lines.append("")
    lines.append("        if not results:")
    lines.append("            return {")
    lines.append("                \"consensus_verdict\": \"NO_CONSENSUS\",")
    lines.append("                \"consensus_confidence\": 0,")
    lines.append("                \"vote_counts\": {},")
    lines.append("                \"template_results\": [],")
    lines.append("                \"consensus_achieved\": False,")
    lines.append("                \"notes\": \"No valid template responses\",")
    lines.append("            }")
    lines.append("")
    lines.append("        # Weighted majority vote")
    lines.append("        vote_weights = Counter()")
    lines.append("        confidence_sum = Counter()")
    lines.append("        for r in results:")
    lines.append("            vote_weights[r[\"verdict\"]] += r[\"weight\"]")
    lines.append("            confidence_sum[r[\"verdict\"]] += r[\"confidence\"]")
    lines.append("")
    lines.append("        # Find majority verdict")
    lines.append("        total_weight = sum(vote_weights.values())")
    lines.append("        consensus_verdict = vote_weights.most_common(1)[0][0] if vote_weights else \"NO_CONSENSUS\"")
    lines.append("        consensus_weight = vote_weights.get(consensus_verdict, 0)")
    lines.append("        consensus_ratio = consensus_weight / total_weight if total_weight > 0 else 0")
    lines.append("")
    lines.append("        # Average confidence for consensus verdict")
    lines.append("        avg_confidence = int(confidence_sum[consensus_verdict] / vote_weights[consensus_verdict]) if vote_weights[consensus_verdict] > 0 else 0")
    lines.append("")
    lines.append("        # Check consensus threshold")
    lines.append("        consensus_achieved = consensus_ratio >= VOTING_CONFIG[\"consensus_threshold\"]")
    lines.append("")
    lines.append("        # Unanimous bonus")
    lines.append("        if consensus_achieved and consensus_ratio == 1.0:")
    lines.append("            avg_confidence = min(100, avg_confidence + int(100 * VOTING_CONFIG[\"unanimous_bonus\"]))")
    lines.append("")
    lines.append('        notes = f"{len(results)} templates voted. Consensus: {consensus_verdict} ({consensus_ratio:.0%})"')
    lines.append("        if not consensus_achieved:")
    lines.append('            notes += f" - BELOW THRESHOLD ({VOTING_CONFIG[\"consensus_threshold\"]:.0%})"')
    lines.append("")
    lines.append("        return {")
    lines.append("            \"consensus_verdict\": consensus_verdict if consensus_achieved else \"NO_CONSENSUS\",")
    lines.append("            \"consensus_confidence\": avg_confidence if consensus_achieved else 0,")
    lines.append("            \"vote_counts\": dict(vote_weights),")
    lines.append("            \"template_results\": results,")
    lines.append("            \"consensus_achieved\": consensus_achieved,")
    lines.append("            \"notes\": notes,")
    lines.append("        }")
    lines.append("")
    lines.append("")
    lines.append("# \u2500\u2500\u2500 Convenience Function \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
    lines.append("")
    lines.append("def multi_template_vote(symbol: str, llm_callable, templates: Optional[List[str]] = None) -> Dict[str, Any]:")
    lines.append('    """Convenience function for multi-template voting."""')
    lines.append("    voter = MultiTemplateVoter(templates)")
    lines.append("    return voter.vote(symbol, llm_callable)")
    lines.append("")

    return "\n".join(lines)


def main():
    code = generate_module()
    output_path = Path(__file__).resolve().parents[2] / "mjonai" / "agents" / "multi_template_voting.py"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(code, encoding="utf-8")
    print(f"Generated {output_path}")


if __name__ == "__main__":
    main()