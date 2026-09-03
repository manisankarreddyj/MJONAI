"""
Module: knowledge/explainability.py
Purpose: Explainable AI — Generates clear, plain-English trade rationales
         and post-mortem explanations for trading decisions.
"""

from typing import Dict, Any, Optional

from knowledge.retriever import retrieve_knowledge


def generate_trade_explanation(
    signal: Dict[str, Any],
    bull_score: int = 80,
    bear_score: int = 20,
    supervisor_decision: str = "APPROVED",
    risk_checks_passed: bool = True,
) -> str:
    """
    Generate an explainable decision summary for a trade signal.
    """
    symbol = signal.get("symbol", "NIFTY")
    strategy = signal.get("strategy_id", "Strategy")
    direction = signal.get("signal_direction", signal.get("signal_type", "BUY"))
    entry = signal.get("entry_price", 0.0)
    sl = signal.get("stop_loss", 0.0)
    target = signal.get("target", 0.0)
    reasons = signal.get("reasons", [])

    # Retrieve matching wisdom
    query = f"{strategy} {direction} {' '.join(reasons)}"
    wisdom = retrieve_knowledge(query, top_k=1)
    wisdom_quote = f" — *{wisdom[0]['author']}*: \"{wisdom[0]['title']}\"" if wisdom else ""

    explanation_lines = [
        f"Trade Decision Explanation: {symbol} ({direction})",
        f"- Strategy: `{strategy}` | Decision: **{supervisor_decision}**",
        f"- Entry: Rs {entry:,.2f} | Stop Loss: Rs {sl:,.2f} | Target: Rs {target:,.2f}",
        f"- AI Consensus: Bull Conviction {bull_score}/100 vs. Bear Skeptic {bear_score}/100",
        f"- Risk Checks: {'Passed All Checks (Approved)' if risk_checks_passed else 'Vetoed by Risk Engine'}",
    ]

    if reasons:
        explanation_lines.append("- Key Technical Drivers:")
        for r in reasons[:3]:
            explanation_lines.append(f"   * {r}")

    if wisdom_quote:
        explanation_lines.append(f"- Quantitative Foundation:{wisdom_quote}")

    return "\n".join(explanation_lines)
