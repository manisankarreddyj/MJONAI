"""
Module: agents/bear.py
Purpose: SOTA Bear Agent — Fundamental & Adversarial Risk Sentry in MJONAI's Multi-Agent Consensus Room.
         Evaluates downside risks, institutional distribution traps, promoter pledging,
         macroeconomic event proximity, and market breadth divergences using the Universal Multi-LLM Bridge.
"""

from dataclasses import dataclass, field, asdict
import logging
import os
from typing import Dict, List, Any, Optional, Union

from mjonai.agents.llm_bridge import query_llm_fast, query_llm_reasoning, LLMInferenceResult

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are the Bear Agent for MJONAI — an institutional-grade Indian algorithmic trading system.

Your role: Forensic & Adversarial Risk Skeptic (Chain-of-Thought Risk Auditor).
Your job is to relentlessly challenge proposed trade setups, uncover hidden distribution traps, debt overhangs, and macro headwinds.

Your Forensic Audit Checklist:
1. Institutional FII/DII flow & Futures positioning (is smart money actively dumping or unwinding longs?).
2. Market breadth divergence (are 2-3 index heavyweights masking broad underlying distribution?).
3. Sector rotation drag (is this stock trapped in a Lagging/Weakening RRG quadrant relative to Nifty?).
4. Corporate governance & distress (promoter pledge >70%, pledged share spikes, forensic debt red flags).
5. Event risk & macro shocks (imminent RBI MPC, FOMC, or corporate earnings volatility).
4. Corporate governance & fundamental distress (high promoter pledging >70%, insider selling).
5. Macro & earnings event risk (is an RBI decision or earnings release imminent?).

Output Rules:
1. Respond ONLY with valid JSON — no preamble, no markdown outside JSON.
2. verdict must be exactly one of: VETO, CAUTION, NEUTRAL, APPROVE
3. confidence must be an integer 0 to 100 (where high confidence means high certainty of your verdict).
4. key_reasons must be a list of 2 to 4 concise strings identifying the key risks.
5. red_flags must be a list of critical dealbreaker risks (or empty list).

Evidence rules (non-negotiable):
- Evaluate ONLY the data in this prompt. You have NO tools, databases, or live feeds — never invent promoter-pledge, insider, FII, earnings, or news facts that are not provided above. Absent evidence means UNKNOWN, never a red flag.
- Do not manufacture risk to justify the skeptic role. A red flag must trace to a specific number or fact in this prompt; if the provided evidence shows no material downside, return NEUTRAL or APPROVE.
- NEUTRAL is an abstention, not a mild veto — it carries no penalty and is never a substitute for citing evidence.
"""


@dataclass(frozen=True)
class BearAgentResult:
    """Immutable contract representing the Bear Agent's risk & fundamental evaluation."""
    verdict: str  # VETO, CAUTION, NEUTRAL, APPROVE
    confidence: int
    key_reasons: List[str] = field(default_factory=list)
    red_flags: List[str] = field(default_factory=list)
    fii_sentiment: str = "NEUTRAL"
    insider_activity: str = "Unknown"
    risk_summary: str = ""
    model_used: str = "UNKNOWN"
    fallback_used: bool = False
    latency_ms: float = 0.0
    raw_response: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _fetch_market_context(provided_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Fetch fundamental and macro context with fallbacks."""
    context = {
        "fii_net_cr": None,
        "fii_regime": "NEUTRAL",
        "market_state": "NEUTRAL",
        "vix": 15.0,
        "pcr": 1.0,
        "promoter_pledge": 0.0,
        "insider_activity": "None known",
        "market_breadth": "BALANCED",
        "sector_rrg": "BALANCED",
        "macro_event_risk": "NONE",
    }

    if isinstance(provided_context, dict):
        context.update({k: v for k, v in provided_context.items() if v is not None})
        return context

    try:
        from mjonai.db.repository import get_latest_market_state
        state = get_latest_market_state()
        if state:
            context["fii_net_cr"] = state.get("fii_net_cr")
            context["market_state"] = str(state.get("market_state") or "NEUTRAL")
            context["vix"] = float(state.get("vix") or 15.0)
    except Exception as e:
        logger.debug(f"[Bear] Market context DB notice: {e}")

    return context


def _build_prompt(
    signal: Dict[str, Any],
    context: Dict[str, Any],
) -> str:
    """Construct adversarial risk analysis prompt for Bear Analyst."""
    fii_str = f"₹{context['fii_net_cr']:+.0f} Cr" if context.get("fii_net_cr") is not None else "Normal"
    pledge_str = f"{context.get('promoter_pledge', 0.0):.1f}%"
    news_flags = ", ".join(context.get("news_red_flags", [])) or "None detected"

    return f"""Evaluate the DOWNSIDE RISKS for this proposed trade on {signal.get('symbol', 'UNKNOWN')}:

SIGNAL DETAILS:
  Symbol:          {signal.get('symbol', 'UNKNOWN')}
  Strategy:        {signal.get('strategy_id', 'Quantitative Strategy')}
  Direction:       {signal.get('direction', signal.get('signal_direction', 'LONG'))}
  Entry Price:     ₹{signal.get('entry_price', 0):.2f}
  Stop Loss:       ₹{signal.get('stop_loss', 0):.2f}
  Target Price:    ₹{signal.get('target', 0):.2f}
  Risk-Reward:     {signal.get('risk_reward', 0):.2f}
  RSI (14):        {signal.get('rsi', 50.0):.1f}
  India VIX:       {context.get('vix', 15.0):.1f}

MACRO, SECTOR & FUNDAMENTAL RISKS:
  FII Net Flow:    {fii_str} ({context.get('fii_regime', 'NEUTRAL')})
  Market Breadth:  {context.get('market_breadth', 'BALANCED')}
  Sector RRG:      {context.get('sector_rrg', 'BALANCED')}
  Option PCR:      {context.get('pcr', 1.0):.2f}
  Promoter Pledge: {pledge_str}
  Insider Action:  {context.get('insider_activity', 'None known')}
  Macro Event:     {context.get('macro_event_risk', 'NONE')}
  News Red Flags:  {news_flags}

YOUR TASK AS THE ADVERSARIAL SKEPTIC:
  - If FII selling > ₹500 Cr or Severe Drain: Flag liquidity risk.
  - If VIX > 20 or Macro Event today: Flag elevated volatility shock risk.
  - If Sector is LAGGING: Flag sectoral drag on stock.
  - If Promoter Pledge > 70%: Emit CRITICAL RED FLAG.
  - If News Red Flags mention auditor resignation, SEBI action, raid, or fraud: Emit hard VETO.

Respond with strict JSON only:
{{
  "verdict": "VETO|CAUTION|NEUTRAL|APPROVE",
  "confidence": <integer 0-100>,
  "key_reasons": ["risk reason 1", "risk reason 2"],
  "red_flags": ["critical dealbreaker"] or [],
  "insider_activity": "None known|Buying|Selling|Unknown",
  "fii_sentiment": "BUYING|SELLING|NEUTRAL|UNKNOWN",
  "risk_summary": "one sentence summary of primary downside risk"
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
            "agent_name": "BEAR",
            "agent_model": result.get("model_used", "UNKNOWN"),
            "fallback_used": result.get("fallback_used", False),
            "system_mode": SYSTEM_MODE,
            "prompt_tokens": 0,
            "response_tokens": 0,
            "latency_ms": result.get("latency_ms", 0.0),
            "raw_verdict": result.get("verdict"),
            "confidence_given": result.get("confidence"),
            "key_reasons": result.get("key_reasons", []),
            "concerns": result.get("red_flags", []),
            "full_response": raw_response[:5000] if raw_response else "",
        })
    except Exception as e:
        logger.debug(f"[Bear] Audit log notice (non-critical): {e}")


def analyse(
    signal: Dict[str, Any],
    devil_checks_passed: Optional[List[str]] = None,
    macro_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Main Bear Agent entrypoint.
    Queries the multi-vendor LLM bridge with automatic deterministic risk evaluation.

    Args:
        signal: Trade signal dictionary
        devil_checks_passed: Optional list of passed devil risk checks
        macro_context: Optional FII flow, Market Breadth, Sector RRG, and Macro Event context

    Returns:
        Dictionary contract containing risk verdict, red flags, confidence, and telemetry.
    """
    context = _fetch_market_context(provided_context=macro_context)
    prompt = _build_prompt(signal, context)
    symbol = str(signal.get("symbol", "UNKNOWN"))

    # Query universal dispatcher with deep reasoning enabled
    llm_res: LLMInferenceResult = query_llm_fast(
        prompt=prompt,
        system_prompt=_SYSTEM_PROMPT,
        signal=signal,
        macro_context=macro_context,
        is_reasoning=True,
    )

    payload = llm_res.parsed_payload or {}
    raw_verdict = str(payload.get("verdict", "NEUTRAL")).upper().strip()
    confidence = payload.get("confidence", 50)

    # Standardize Bear verdict vocabulary:
    # VETO = High risk dealbreaker, CAUTION = Moderate risk, APPROVE = Low risk (clear skies)
    if "VETO" in raw_verdict or "REJECT" in raw_verdict or "SELL" in raw_verdict:
        final_verdict = "VETO"
    elif "CAUTION" in raw_verdict or "BEARISH" in raw_verdict:
        final_verdict = "CAUTION"
    elif "APPROVE" in raw_verdict or "BULLISH" in raw_verdict:
        final_verdict = "APPROVE"
    else:
        final_verdict = "NEUTRAL"

    # Type-safe lists
    raw_reasons = payload.get("key_reasons") or payload.get("reasons")
    key_reasons_list: List[str] = [str(r) for r in raw_reasons] if isinstance(raw_reasons, list) else ["No critical fundamental block detected"]

    raw_flags = payload.get("red_flags")
    red_flags_list: List[str] = [str(f) for f in raw_flags] if isinstance(raw_flags, list) else []

    result = BearAgentResult(
        verdict=final_verdict,
        confidence=int(confidence),
        key_reasons=key_reasons_list,
        red_flags=red_flags_list,
        fii_sentiment=str(payload.get("fii_sentiment") or context.get("fii_regime", "NEUTRAL")),
        insider_activity=str(payload.get("insider_activity") or context.get("insider_activity", "Unknown")),
        risk_summary=str(payload.get("risk_summary") or f"Bear risk assessment complete for {symbol}"),
        model_used=llm_res.model,
        fallback_used=llm_res.is_fallback,
        latency_ms=llm_res.latency_ms,
        raw_response=llm_res.raw_response,
    )

    # Log audit trail
    _log_agent_call(signal, result.to_dict(), llm_res.raw_response)

    logger.info(f"[Bear] {symbol} → {result.verdict} ({result.confidence}% confidence | {result.latency_ms:.1f}ms via {result.model_used})")
    return result.to_dict()