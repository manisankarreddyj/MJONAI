"""
Module: agents/debate_room.py
Purpose: SOTA Adversarial Multi-Agent Debate Coordinator for MJONAI.
         Orchestrates multi-round deliberations between the Bull Technical Analyst
         and the Bear Risk Sentry before passing the final debate transcript to the Supervisor CIO.
"""

from dataclasses import dataclass, field, asdict
import logging
from typing import Dict, List, Any, Optional, Union

from mjonai.agents.bull import analyse as analyse_bull, BullAgentResult
from mjonai.agents.bear import analyse as analyse_bear, BearAgentResult
from mjonai.agents.macro_specialist import analyse_macro_flow, MacroSpecialistResult
from mjonai.agents.supervisor import evaluate as evaluate_supervisor, SupervisorEvaluationResult
from mjonai.agents.llm_bridge import query_llm_fast, LLMInferenceResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DebateTranscript:
    """Immutable record of the multi-round deliberation between Bull, Bear, and Macro specialists."""
    bull_initial_verdict: str
    bull_confidence: int
    bull_reasons: List[str]
    bear_initial_verdict: str
    bear_confidence: int
    bear_risks: List[str]
    bear_red_flags: List[str]
    macro_verdict: str = "NEUTRAL"
    macro_conviction: int = 50
    macro_drivers: List[str] = field(default_factory=list)
    bull_rebuttal: Optional[str] = None
    consensus_verdict: str = "NEUTRAL"
    consensus_score: int = 50
    rounds_conducted: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DebateConsensusResult:
    """Immutable contract representing the final synthesized debate room outcome."""
    approved: bool
    final_decision: str  # APPROVE, REJECT
    rejection_reason: str
    consensus_score: int
    summary: str
    deciding_factor: str
    transcript: DebateTranscript
    supervisor_report: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _conduct_bull_rebuttal(
    signal: Dict[str, Any],
    bull_result: Dict[str, Any],
    bear_result: Dict[str, Any],
    macro_context: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Round 2: Ask Bull Analyst to evaluate if technical momentum overcomes the Bear's specific risk flags.
    """
    red_flags = bear_result.get("red_flags", [])
    concerns = bear_result.get("key_reasons", [])
    primary_risk = red_flags[0] if red_flags else (concerns[0] if concerns else "Downside volatility")

    prompt = f"""Round 2 Adversarial Counter-Evaluation for {signal.get('symbol', 'UNKNOWN')}:

BULL INITIAL CASE:
- Verdict: {bull_result.get('verdict')} ({bull_result.get('confidence')}% confidence)
- Reasons: {', '.join(bull_result.get('key_reasons', []))}

BEAR OBJECTION:
- Primary Risk Flagged: "{primary_risk}"
- Bear Confidence: {bear_result.get('confidence')}%

YOUR TASK:
Does the price structure, volume, and sector relative strength overcome this Bear risk?
Respond in 1-2 concise sentences as JSON:
{{
  "overcomes_risk": true/false,
  "rebuttal_argument": "1-2 sentence counter-thesis or concession"
}}"""

    llm_res: LLMInferenceResult = query_llm_fast(
        prompt=prompt,
        system_prompt="You are the Bull Technical Analyst defending or conceding your trade thesis. Respond with strict JSON.",
        signal=signal,
        macro_context=macro_context,
    )

    payload = llm_res.parsed_payload or {}
    return str(payload.get("rebuttal_argument") or f"Bull acknowledges {primary_risk} but technical structure remains intact.")


def conduct_adversarial_debate(
    signal: Dict[str, Any],
    devil_checks_passed: Optional[List[str]] = None,
    macro_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Conduct multi-round adversarial debate between Bull and Bear personas.
      Round 1: Parallel Bull Technical Analysis + Bear Risk Sentry Evaluation.
      Round 2: If disagreement exists, Bull provides a counter-argument to Bear's top risk.
      Final Arbiter: Supervisor CIO applies deterministic code rules and synthesizes consensus.

    Args:
        signal: Trade signal dictionary
        devil_checks_passed: List of passed risk sentry checks
        macro_context: FII flows, Market Breadth, Sector RRG context

    Returns:
        Dictionary contract containing final decision, consensus score, and transcript.
    """
    symbol = str(signal.get("symbol", "UNKNOWN"))
    checks = devil_checks_passed or ["Risk Sentry Passed"]

    # ── Round 1: Independent Bull, Bear & Macro Flow Evaluation ──
    logger.info(f"[DebateRoom] Initiating Round 1 deliberation for {symbol}...")
    bull_res = analyse_bull(signal, devil_checks_passed=checks, macro_context=macro_context)
    bear_res = analyse_bear(signal, macro_context=macro_context)
    macro_res = analyse_macro_flow(signal, macro_context=macro_context)

    bull_verdict = str(bull_res.get("verdict", "NEUTRAL")).upper()
    bear_verdict = str(bear_res.get("verdict", "NEUTRAL")).upper()
    macro_verdict = str(macro_res.get("verdict", "NEUTRAL")).upper()

    bull_conf = int(bull_res.get("confidence", 50))
    bear_conf = int(bear_res.get("confidence", 50))
    macro_conf = int(macro_res.get("conviction_score", 50))

    rebuttal_text = None
    rounds = 1

    # ── Round 2: Adversarial Rebuttal (Triggered if Bull is Buy but Bear flags risks) ──
    if bull_verdict in ("BUY", "STRONG_BUY") and bear_verdict in ("VETO", "CAUTION"):
        logger.info(f"[DebateRoom] Round 2 triggered: Bull ({bull_verdict}) vs Bear ({bear_verdict}) for {symbol}")
        rebuttal_text = _conduct_bull_rebuttal(signal, bull_res, bear_res, macro_context=macro_context)
        rounds = 2

    # Calculate net consensus conviction score (0-100 across 3 specialist personas)
    if bear_verdict in ("APPROVE", "PASS", "CLEAR"):
        bear_trade_support = bear_conf
    else:
        bear_trade_support = 100 - bear_conf

    net_score = max(0, min(100, int((bull_conf * 0.40) + (bear_trade_support * 0.30) + (macro_conf * 0.30))))

    # ── Final Arbiter: Supervisor CIO Evaluation ──
    supervisor_res = evaluate_supervisor(
        signal=signal,
        bull_result=bull_res,
        devil_checks_passed=checks,
        bear_result=bear_res,
        macro_context=macro_context,
    )

    transcript = DebateTranscript(
        bull_initial_verdict=bull_verdict,
        bull_confidence=bull_conf,
        bull_reasons=list(bull_res.get("key_reasons") or []),
        bear_initial_verdict=bear_verdict,
        bear_confidence=bear_conf,
        bear_risks=list(bear_res.get("key_reasons") or []),
        bear_red_flags=list(bear_res.get("red_flags") or []),
        macro_verdict=macro_verdict,
        macro_conviction=macro_conf,
        macro_drivers=list(macro_res.get("key_drivers") or []),
        bull_rebuttal=rebuttal_text,
        consensus_verdict=supervisor_res.get("final_decision", "REJECT"),
        consensus_score=net_score,
        rounds_conducted=rounds,
    )

    result = DebateConsensusResult(
        approved=supervisor_res.get("approved", False),
        final_decision=supervisor_res.get("final_decision", "REJECT"),
        rejection_reason=supervisor_res.get("rejection_reason", ""),
        consensus_score=net_score,
        summary=supervisor_res.get("summary", ""),
        deciding_factor=supervisor_res.get("deciding_factor", ""),
        transcript=transcript,
        supervisor_report=supervisor_res,
    )

    logger.info(f"[DebateRoom] Deliberation complete for {symbol} → {result.final_decision} (Consensus Score: {net_score}/100 | {rounds} rounds)")
    return result.to_dict()
