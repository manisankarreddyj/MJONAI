"""
Module: agents/supervisor.py
Purpose: SOTA Supervisor Agent — Chief Investment Officer (CIO) & Supreme Multi-Agent Arbiter.
         Enforces deterministic mathematical decision rules in code (absolute authority),
         arbitrates Bull vs Bear adversarial debates, and generates structured transparency reports.
"""

from dataclasses import dataclass, field, asdict
import logging
import os
from typing import Dict, List, Any, Optional, Tuple, Union

from mjonai.agents.llm_bridge import query_llm_fast, LLMInferenceResult
from mjonai.core.constants import (
    SYSTEM_MODE,
    MIN_REAL_RR,
    RESEARCH_CONFIDENCE_MIN,
    LIVE_CONFIDENCE_MIN,
)

logger = logging.getLogger(__name__)

REQUIRED_DEVIL_CHECKS = 8

_SYSTEM_PROMPT = """You are the Supervisor Agent for MJONAI — an institutional-grade Indian algorithmic trading system.

Your role: Chief Investment Officer (CIO) providing a transparency report.
The deterministic rules engine has ALREADY made the final execution decision based on risk limits.
Your job is to provide an executive summary and explain the decision clearly to the trader.

Rules:
1. Respond ONLY with valid JSON — no preamble, no markdown outside JSON.
2. Be concise and crisp — this goes directly to the trader's telegram alert.
3. If approved — summarize why the trade has high statistical edge.
4. If rejected — clearly identify the primary disqualifying factor.
5. Flag any subtle data contradictions between Bull and Bear analysts.

Evidence rules (non-negotiable):
- Every fact you cite must come from the analysts' reports or the deterministic gate results given to you. You have NO tools, databases, or live feeds — never invent prices, numbers, or news.
- Report disagreements plainly, including weak evidence on both sides; your job is transparency, not advocacy.
"""


@dataclass(frozen=True)
class SupervisorEvaluationResult:
    """Immutable contract representing the CIO's final consensus decision and report."""
    approved: bool
    final_decision: str  # APPROVE, REJECT
    rejection_reason: str
    summary: str
    deciding_factor: str
    top_reasons: List[str] = field(default_factory=list)
    risk_note: str = ""
    confidence_assessment: str = ""
    bull_verdict: str = "NEUTRAL"
    bull_confidence: int = 0
    bear_verdict: Optional[str] = None
    model_used: str = "RULES_ONLY"
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _apply_decision_rules(
    signal: Dict[str, Any],
    bull_result: Dict[str, Any],
    devil_checks_passed: List[str],
    bear_result: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """
    Apply deterministic decision rules in Python code (Absolute Authority).
    LLM cannot override these rules under any circumstances.
    """
    bull_verdict = str(bull_result.get("verdict", "NEUTRAL")).upper().strip()

    # 1. Safe float conversions
    try:
        bull_confidence = float(bull_result.get("confidence", 0))
    except (TypeError, ValueError):
        bull_confidence = 0.0

    try:
        real_rr = float(signal.get("risk_reward", 0))
    except (TypeError, ValueError):
        real_rr = 0.0

    checks_count = len(devil_checks_passed)

    # Rule 1 — Technical Analyst must confirm the trade direction (direction-aware).
    # A bullish read confirms a LONG; a bearish read confirms a SHORT. VETO/REJECT block either;
    # the opposite-direction read (e.g. a BUY verdict on a SHORT setup) is a disagreement -> REJECT.
    # APPROVE is a direction-agnostic confirm emitted by the deterministic fallback (valid for both).
    direction = str(signal.get("direction", signal.get("signal_direction", "LONG"))).upper()
    if bull_verdict in ("VETO", "REJECT"):
        return "REJECT", f"Technical Analyst verdict {bull_verdict} — insufficient conviction for {direction} setup"
    if direction in ("LONG", "BUY"):
        if bull_verdict not in ("BUY", "STRONG_BUY", "APPROVE"):
            return "REJECT", f"Technical Analyst verdict {bull_verdict} — insufficient conviction for {direction} setup"
    else:
        if bull_verdict not in ("SELL", "STRONG_SELL", "APPROVE"):
            return "REJECT", f"Technical Analyst verdict {bull_verdict} — insufficient conviction for {direction} setup"

    # Rule 2 — Devil Risk Sentry Checks
    if SYSTEM_MODE != "RESEARCH" and checks_count < REQUIRED_DEVIL_CHECKS:
        return "REJECT", f"Only {checks_count}/{REQUIRED_DEVIL_CHECKS} devil checks passed"

    # Rule 3 — Confidence Threshold
    min_confidence = RESEARCH_CONFIDENCE_MIN if SYSTEM_MODE == "RESEARCH" else LIVE_CONFIDENCE_MIN
    if bull_confidence < min_confidence:
        return "REJECT", f"Bull confidence {bull_confidence:.0f}% below {min_confidence}% threshold"

    # Rule 4 — Real Risk:Reward post-friction >= 2.0
    if real_rr < MIN_REAL_RR:
        return "REJECT", f"Real RR {real_rr:.2f} below institutional minimum {MIN_REAL_RR:.2f}"

    # Rule 5 — Adversarial Bear Veto Arbitration
    if bear_result:
        bear_verdict = str(bear_result.get("verdict", "NEUTRAL")).upper().strip()
        red_flags = bear_result.get("red_flags", [])

        if red_flags and len(red_flags) > 0:
            # Critical red flag (e.g. promoter pledge >70% or severe distribution)
            if bull_confidence < 85 or checks_count < REQUIRED_DEVIL_CHECKS:
                return "REJECT", f"Bear Agent Critical Red Flag Veto: {red_flags[0]}"

        if bear_verdict == "VETO" and bull_confidence < 80:
            return "REJECT", f"Bear Agent Veto — excessive downside risk"

    return "APPROVE", ""


def _build_prompt(
    signal: Dict[str, Any],
    bull_result: Dict[str, Any],
    devil_checks_passed: List[str],
    final_decision: str,
    rejection_reason: str,
    bear_result: Optional[Dict[str, Any]] = None,
) -> str:
    """Build prompt for CIO transparency report."""
    bull_reasons = "\n".join(f"  - {r}" for r in bull_result.get("key_reasons", []))
    bull_concerns = "\n".join(f"  - {c}" for c in bull_result.get("concerns", []))
    checks_str = ", ".join(devil_checks_passed)

    bear_section = ""
    if bear_result:
        bear_reasons = "\n".join(f"  - {r}" for r in bear_result.get("key_reasons", []))
        bear_flags = "\n".join(f"  - {f}" for f in bear_result.get("red_flags", []))
        bear_section = f"""
BEAR AGENT EVALUATION:
  Verdict:       {bear_result.get('verdict', 'UNKNOWN')} ({bear_result.get('confidence', 0)}% confidence)
  FII Sentiment: {bear_result.get('fii_sentiment', 'UNKNOWN')}
  Risk Summary:  {bear_result.get('risk_summary', 'N/A')}
  Key Risks:
{bear_reasons or '  - None flagged'}
  Red Flags:
{bear_flags or '  - None'}"""

    return f"""Review this trading decision for {signal.get('symbol', 'UNKNOWN')}:

SIGNAL DATA:
  Symbol:        {signal.get('symbol', 'UNKNOWN')}
  Strategy:      {signal.get('strategy_id', 'Quantitative Strategy')}
  Entry Price:   ₹{signal.get('entry_price', 0):.2f}
  Stop Loss:     ₹{signal.get('stop_loss', 0):.2f}
  Target Price:  ₹{signal.get('target', 0):.2f}
  Real RR:       {signal.get('risk_reward', 0):.2f} (post-friction)
  Direction:     {signal.get('direction', signal.get('signal_direction', 'LONG'))}

BULL AGENT EVALUATION:
  Verdict:       {bull_result.get('verdict', 'UNKNOWN')} ({bull_result.get('confidence', 0)}% confidence)
  Reasons:
{bull_reasons or '  - Technical breakout aligned'}
  Concerns:
{bull_concerns or '  - None'}
{bear_section}

DEVIL CHECKS PASSED: {len(devil_checks_passed)}/{REQUIRED_DEVIL_CHECKS}
  Passed: {checks_str}

FINAL CODE DECISION: {final_decision}
REJECTION REASON (if any): {rejection_reason or 'None (All criteria met)'}

Provide your CIO transparency report as JSON:
{{
  "summary": "2-3 sentence plain English executive summary",
  "deciding_factor": "the single most important factor for this decision",
  "top_reasons": ["reason 1", "reason 2", "reason 3"],
  "risk_note": "main risk to monitor during this trade",
  "confidence_assessment": "brief assessment of trade quality",
  "approved": {str(final_decision == "APPROVE").lower()}
}}"""


def _log_agent_call(signal: Dict[str, Any], result: Dict[str, Any], raw_response: str) -> None:
    """Non-blocking audit log to agent_logs repository."""
    try:
        from mjonai.db.repository import insert_agent_log
        from mjonai.core.constants import SYSTEM_MODE

        signal_id = signal.get("signal_intelligence_id") or signal.get("id")
        insert_agent_log({
            "signal_id": signal_id,
            "trade_id": None,
            "agent_name": "SUPERVISOR",
            "agent_model": result.get("model_used", "RULES_ONLY"),
            "fallback_used": False,
            "system_mode": SYSTEM_MODE,
            "prompt_tokens": 0,
            "response_tokens": 0,
            "latency_ms": result.get("latency_ms", 0.0),
            "raw_verdict": result.get("final_decision"),
            # Magnitude = the technical case strength (Bull's confidence); the
            # DIRECTION comes from final_decision, so the calibration loop scores
            # an APPROVE as P(win)=conf and a REJECT as P(win)=1-conf. Not a
            # raw echo of Bull — the verdict carries the supervisor's own call.
            "confidence_given": result.get("bull_confidence"),
            "key_reasons": result.get("top_reasons", []),
            "concerns": [result.get("rejection_reason")] if result.get("rejection_reason") else [],
            "full_response": raw_response[:5000] if raw_response else "",
        })
    except Exception as e:
        logger.debug(f"[Supervisor] Audit log notice (non-critical): {e}")


def evaluate(
    signal: Dict[str, Any],
    bull_result: Dict[str, Any],
    devil_checks_passed: Optional[List[str]] = None,
    bear_result: Optional[Dict[str, Any]] = None,
    macro_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Main Supervisor Agent entrypoint.
    1. Executes deterministic mathematical rules in code (Code decides, not LLM).
    2. If approved, queries the universal LLM bridge to generate plain-English CIO transparency report.
    3. If rejected, skips LLM inference to save API quota and returns instant rule-based explanation.

    Args:
        signal: Trade signal dictionary
        bull_result: Bull Analyst result dictionary
        devil_checks_passed: List of passed devil checks
        bear_result: Optional Bear Adversarial Analyst result dictionary
        macro_context: Optional macro and market breadth context

    Returns:
        Dictionary contract containing approved boolean, final_decision, and executive report.
    """
    checks = devil_checks_passed or ["Risk Sentry Passed"]
    symbol = str(signal.get("symbol", "UNKNOWN"))

    # ── Step 1: Deterministic code decision (Absolute Authority) ──
    final_decision, rejection_reason = _apply_decision_rules(
        signal=signal,
        bull_result=bull_result,
        devil_checks_passed=checks,
        bear_result=bear_result,
    )

    logger.info(f"[Supervisor] {symbol} → {final_decision} | Bull: {bull_result.get('verdict')} | Checks: {len(checks)}/{REQUIRED_DEVIL_CHECKS}")

    raw_response = ""
    latency_ms = 0.0
    model_used = "RULES_ONLY"

    # ── Step 2: CIO Transparency Report ──
    if final_decision == "APPROVE":
        prompt = _build_prompt(
            signal=signal,
            bull_result=bull_result,
            devil_checks_passed=checks,
            final_decision=final_decision,
            rejection_reason=rejection_reason,
            bear_result=bear_result,
        )

        llm_res: LLMInferenceResult = query_llm_fast(
            prompt=prompt,
            system_prompt=_SYSTEM_PROMPT,
            signal=signal,
            macro_context=macro_context,
        )

        payload = llm_res.parsed_payload or {}
        latency_ms = llm_res.latency_ms
        model_used = llm_res.model
        raw_response = llm_res.raw_response

        raw_reasons = payload.get("top_reasons") or bull_result.get("key_reasons") or ["Technical momentum and risk limits verified"]
        top_reasons_list: List[str] = [str(r) for r in raw_reasons] if isinstance(raw_reasons, list) else ["High statistical edge confirmed"]

        report = {
            "summary": str(payload.get("summary") or f"{symbol} trade approved by institutional consensus."),
            "deciding_factor": str(payload.get("deciding_factor") or "Strong technical momentum and risk clearance"),
            "top_reasons": top_reasons_list,
            "risk_note": str(payload.get("risk_note") or "Standard swing trade trailing stop applies"),
            "confidence_assessment": str(payload.get("confidence_assessment") or f"Bull confidence: {bull_result.get('confidence')}%"),
        }
    else:
        # Instant zero-quota rule explanation on rejection
        report = {
            "summary": f"{symbol} trade rejected: {rejection_reason}",
            "deciding_factor": rejection_reason,
            "top_reasons": [rejection_reason],
            "risk_note": "Setup failed quantitative criteria",
            "confidence_assessment": f"Bull confidence: {bull_result.get('confidence', 0)}%",
        }

    summary_str: str = str(report.get("summary") or "")
    deciding_factor_str: str = str(report.get("deciding_factor") or "")
    raw_top_reasons = report.get("top_reasons")
    top_reasons_list: List[str] = [str(r) for r in raw_top_reasons] if isinstance(raw_top_reasons, list) else [deciding_factor_str]
    risk_note_str: str = str(report.get("risk_note") or "")
    conf_assessment_str: str = str(report.get("confidence_assessment") or "")

    result = SupervisorEvaluationResult(
        approved=final_decision == "APPROVE",
        final_decision=final_decision,
        rejection_reason=rejection_reason,
        summary=summary_str,
        deciding_factor=deciding_factor_str,
        top_reasons=top_reasons_list,
        risk_note=risk_note_str,
        confidence_assessment=conf_assessment_str,
        bull_verdict=str(bull_result.get("verdict", "NEUTRAL")),
        bull_confidence=int(float(bull_result.get("confidence", 0))),
        bear_verdict=str(bear_result.get("verdict")) if bear_result and bear_result.get("verdict") is not None else None,
        model_used=model_used,
        latency_ms=latency_ms,
    )

    # Log audit trail
    _log_agent_call(signal, result.to_dict(), raw_response)

    return result.to_dict()
