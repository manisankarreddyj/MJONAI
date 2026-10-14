"""
Module: agents/bull.py
Purpose: SOTA Bull Agent — Technical Analyst Persona in MJONAI's Multi-Agent Consensus Room.
         Evaluates trade setups across all 12 Strategies (S01-S12) with Macro Intelligence,
         Sector RRG, and FII Flow Confirmation using the Universal Multi-LLM Bridge.
"""

from dataclasses import dataclass, field, asdict
import logging
import os
from typing import Dict, List, Any, Optional, Union

from mjonai.agents.llm_bridge import query_llm_fast, LLMInferenceResult

logger = logging.getLogger(__name__)

REQUIRED_DEVIL_CHECKS = 8

STRATEGY_CONTEXT_MAP: Dict[str, str] = {
    "S01_MomentumRSI": "Momentum Breakout — Bullish RSI (55-70) & Volume expansion",
    "S02_MeanReversion": "Mean Reversion Long — Oversold RSI (<30) bouncing off lower band",
    "S03_TurtleBreakout": "Donchian Turtle Breakout — 20-day / 55-day channel breakout",
    "S04_BollingerSqueeze": "Bollinger Squeeze — Volatility expansion out of tight bandwidth",
    "S05_PriceAction": "Institutional Price Action — Multi-timeframe candlestick confirmation",
    "S06_MomentumShort": "Momentum Breakdown — Bearish RSI (30-45) breakdown",
    "S07_MeanReversionShort": "Mean Reversion Short — Overbought RSI (>70) rejecting resistance",
    "S08_VolumeProfile": "Volume Profile — Point of Control (POC) & Value Area (VAL/VAH) bounce",
    "S09_OptionsThetaDecay": "Options Theta Harvest — Delta-neutral Strangles & Iron Condors",
    "S10_PairsTrading": "Statistical Arbitrage — Cointegrated pair mean-reversion spread",
    "S11_SectorMomentum": "Sector Rotation Leader — Outperforming stock in Leading RRG sector",
    "S12_MultiTimeframeBreakout": "Multi-Timeframe Alignment — Daily trend + 15m structural breakout",
}

_SYSTEM_PROMPT = """You are the Bull Agent for MJONAI — an institutional-grade Indian algorithmic trading system.

Your role: Technical Analyst & Momentum Evaluator. You evaluate trade setups on NSE/MCX assets.

Your personality:
- Rigorous, quantitative, and data-driven.
- You look for GENUINE institutional momentum and liquidity sponsorship.
- You reject weak, low-volume setups or exhausted late-stage trends.
- You think like a veteran proprietary desk trader with 10+ years of Indian market experience.

Output Rules:
1. Respond ONLY with valid JSON — no preamble, no markdown outside JSON.
2. For LONG signals, verdict must be one of: STRONG_BUY, BUY, NEUTRAL, VETO.
   For SHORT signals, verdict must be one of: STRONG_SELL, SELL, NEUTRAL, VETO.
3. confidence must be an integer 0 to 100.
4. key_reasons must be a list of 2 to 4 concise strings.
5. concerns must be a list of potential failure points (or empty list).

Evidence rules (non-negotiable):
- Evaluate ONLY the signal data in this prompt. You have NO tools, databases, or live feeds — never invent prices, volumes, news, fundamentals, or flows that are not provided above.
- Do not defer to the direction implied by the strategy that raised this signal. Form an independent read from the evidence and flag disagreement plainly.
- NEUTRAL is an abstention, not a mild veto: use it when the evidence is insufficient, paired with a low confidence.
- NO tools, NO external data, NO memory of company-specific history. If the prompt withholds ticker/industry/date (blind mode), do NOT infer them.
"""


@dataclass(frozen=True)
class BullAgentResult:
    """Immutable contract representing the Bull Agent's technical evaluation."""
    verdict: str  # BUY/STRONG_BUY (LONG), SELL/STRONG_SELL (SHORT), NEUTRAL, VETO
    confidence: int
    key_reasons: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)
    regime_note: str = ""
    recommendation: str = ""
    model_used: str = "UNKNOWN"
    fallback_used: bool = False
    latency_ms: float = 0.0
    raw_response: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _build_prompt(
    signal: Dict[str, Any],
    devil_checks_passed: List[str],
    macro_context: Optional[Dict[str, Any]] = None,
    blind: bool = False,
) -> str:
    """Construct comprehensive quantitative prompt for Bull Analyst.

    Args:
        signal: Trade signal dictionary
        devil_checks_passed: List of passing devil risk checks
        macro_context: Optional FII flow, Gift Nifty, and Sector RRG context
        blind: If True, withholds ticker/industry/date for research validity (prevents LLM memorization)

    Returns:
        Formatted prompt string
    """
    reasons_str = "\n".join(f"  - {r}" for r in signal.get("reasons", []))
    checks_str = "\n".join(f"  - {c}" for c in devil_checks_passed)

    strategy_id = str(signal.get("strategy_id", "UNKNOWN"))
    strat_desc = STRATEGY_CONTEXT_MAP.get(strategy_id, "Quantitative Strategy")

    vix = float(signal.get("vix_at_signal", 15.0))
    vix_state = "LOW (Calm)" if vix < 14 else ("HIGH (Elevated Risk)" if vix > 20 else "NORMAL")

    macro = macro_context or {}
    fii_regime = macro.get("fii_regime", "NEUTRAL")
    fii_ls_ratio = macro.get("fii_long_short_ratio", 1.0)
    sector_rrg = macro.get("sector_rrg_quadrant", "BALANCED")
    market_breadth = macro.get("market_breadth", "BALANCED")

    if blind:
        # Blind backtest mode: withhold ticker, industry, calendar date — prevents LLM memorization
        symbol_display = "ANONYMIZED"
        strategy_display = f"{strategy_id} (blind)"
    else:
        symbol_display = signal.get('symbol', 'UNKNOWN')
        strategy_display = f"{strategy_id} — {strat_desc}"

    return f"""Evaluate this trade signal for {symbol_display}:

SIGNAL DATA:
  Symbol:          {symbol_display}
  Strategy:        {strategy_display}
  Direction:       {signal.get('direction', signal.get('signal_direction', 'LONG'))}
  Entry Price:     ₹{signal.get('entry_price', 0):.2f}
  Stop Loss:       ₹{signal.get('stop_loss', 0):.2f}
  Target Price:    ₹{signal.get('target', 0):.2f}
  Risk-Reward:     {signal.get('risk_reward', 0):.2f} (post-friction)
  Technical Score: {signal.get('confidence', 0)}/100
  Volume Ratio:    {signal.get('volume_ratio', 1.0):.2f}x 20-day avg
  RSI (14):        {signal.get('rsi', 50.0):.1f}
  India VIX:       {vix:.1f} ({vix_state})

MACRO & SECTOR CONTEXT:
  Sector RRG:      {sector_rrg}
  Market Breadth:  {market_breadth}
  FII Flow Regime: {fii_regime} (FII Futures L/S: {fii_ls_ratio:.2f})

TECHNICAL EVIDENCE:
{reasons_str or '  - Algorithmic technical confirmation'}

DEVIL CHECKS PASSED ({len(devil_checks_passed)}/{REQUIRED_DEVIL_CHECKS}):
{checks_str}

Provide your structured verdict as JSON:
{{
  "verdict": "STRONG_BUY|BUY|NEUTRAL|VETO",
  "confidence": <0-100>,
  "key_reasons": ["reason 1", "reason 2"],
  "concerns": ["concern 1"],
  "regime_note": "market regime assessment",
  "recommendation": "one sentence conclusion"
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
            "agent_name": "BULL",
            "agent_model": result.get("model_used", "UNKNOWN"),
            "fallback_used": result.get("fallback_used", False),
            "system_mode": SYSTEM_MODE,
            "prompt_tokens": 0,
            "response_tokens": 0,
            "latency_ms": result.get("latency_ms", 0.0),
            "raw_verdict": result.get("verdict"),
            "confidence_given": result.get("confidence"),
            "key_reasons": result.get("key_reasons", []),
            "concerns": result.get("concerns", []),
            "full_response": raw_response[:5000] if raw_response else "",
        })
    except Exception as e:
        logger.debug(f"[Bull] Audit log notice (non-critical): {e}")


def analyse(
    signal: Dict[str, Any],
    devil_checks_passed: Optional[List[str]] = None,
    macro_context: Optional[Dict[str, Any]] = None,
    blind: bool = False,
) -> Dict[str, Any]:
    """
    Main Bull Agent entrypoint.
    Queries the multi-vendor LLM bridge with automatic deterministic fallback.

    Args:
        signal: Trade signal dictionary
        devil_checks_passed: List of passing devil risk checks
        macro_context: Optional FII flow, Gift Nifty, and Sector RRG context
        blind: If True, withholds ticker/industry/date for research validity (prevents LLM memorization)

    Returns:
        Dictionary contract containing verdict, confidence, reasons, and telemetry.
    """
    checks = devil_checks_passed or ["Risk Checks Verified"]
    prompt = _build_prompt(signal, checks, macro_context=macro_context, blind=blind)
    symbol = str(signal.get("symbol", "UNKNOWN"))

    # Query universal low-latency dispatcher
    llm_res: LLMInferenceResult = query_llm_fast(
        prompt=prompt,
        system_prompt=_SYSTEM_PROMPT,
        signal=signal,
        macro_context=macro_context,
        # Bull's directional vocabulary survives the bridge verbatim: SELL /
        # STRONG_SELL confirm SHORT setups (supervisor Rule 1) instead of
        # collapsing into VETO at the shared layer.
        allowed_verdicts=("STRONG_BUY", "BUY", "APPROVE", "STRONG_SELL",
                          "SELL", "VETO", "REJECT", "CAUTION", "NEUTRAL"),
    )

    payload = llm_res.parsed_payload or {}
    verdict = payload.get("verdict", "NEUTRAL")
    confidence = payload.get("confidence", 50)

    # Standardize verdict vocabulary. SELL/STRONG_SELL are kept as a distinct directional
    # (bearish) verdict — NOT a veto — so a correct bearish read can confirm a SHORT setup.
    if verdict in ("STRONG_BUY", "BUY", "APPROVE"):
        final_verdict = "BUY" if confidence < 80 else "STRONG_BUY"
    elif verdict in ("STRONG_SELL", "SELL"):
        final_verdict = "SELL" if confidence < 80 else "STRONG_SELL"
    elif verdict in ("VETO", "REJECT"):
        final_verdict = "VETO"
    else:
        final_verdict = "NEUTRAL"

    # Cap fallback confidence at 80
    if llm_res.is_fallback and confidence > 80:
        confidence = 80

    raw_reasons = payload.get("key_reasons") or payload.get("reasons")
    key_reasons_list: List[str] = [str(r) for r in raw_reasons] if isinstance(raw_reasons, list) else ["Technical breakout momentum confirmed"]

    raw_concerns = payload.get("concerns")
    concerns_list: List[str] = [str(c) for c in raw_concerns] if isinstance(raw_concerns, list) else []

    result = BullAgentResult(
        verdict=final_verdict,
        confidence=int(confidence),
        key_reasons=key_reasons_list,
        concerns=concerns_list,
        regime_note=str(payload.get("regime_note") or "Market trend aligned"),
        recommendation=str(payload.get("recommendation") or f"Bull Analyst approves {symbol} setup"),
        model_used=llm_res.model,
        fallback_used=llm_res.is_fallback,
        latency_ms=llm_res.latency_ms,
        raw_response=llm_res.raw_response,
    )

    # Log audit trail
    _log_agent_call(signal, result.to_dict(), llm_res.raw_response)

    logger.info(f"[Bull] {symbol} → {result.verdict} ({result.confidence}% confidence | {result.latency_ms:.1f}ms via {result.model_used})")
    return result.to_dict()
