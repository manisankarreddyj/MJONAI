"""
Module: agents/macro_specialist.py
Purpose: SOTA Macroeconomic & Institutional Liquidity Specialist Agent for MJONAI.
         Specializes in assessing FII/DII Net Flow regimes, FII Index Futures Long/Short
         ratios, and Sector Relative Rotation (RRG) leading/lagging quadrants to provide
         the 3rd institutional perspective in the Investment Committee Debate Room.
"""

from dataclasses import dataclass, field, asdict
import json
import logging
import os
import time
from typing import Dict, List, Any, Optional, Union

from mjonai.agents.llm_bridge import query_llm_fast, LLMInferenceResult

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are the Macro & Institutional Liquidity Specialist for MJONAI — an institutional Indian quantitative trading system.

Your Role: Macro Strategist & Liquidity Flow Specialist.
Your job is to evaluate whether macro liquidity, institutional positioning (FII/DII), and sector rotation support the proposed trade.

Key Evaluation Criteria:
1. FII/DII Net Cash Flow & 5-Day Velocity (is smart money supporting or dumping this market?).
2. FII Index Futures Long/Short positioning (extreme crowding >75% long = squeeze risk, <20% long = capitulation bottom).
3. Sector Relative Rotation (RRG) phase space:
   - LEADING quadrant: Strong tailwind (+conviction).
   - IMPROVING quadrant: Early accumulation (+conviction).
   - WEAKENING quadrant: Momentum exhaustion (neutral/caution).
   - LAGGING quadrant: Structural drag (-conviction).

Output Rules:
1. Respond ONLY with valid JSON.
2. verdict must be exactly one of: STRONG_TAILWIND, MODERATE_SUPPORT, NEUTRAL, LIQUIDITY_HEADWIND
3. conviction_score must be an integer between 0 and 100.
4. key_drivers must be a list of 2-3 concise rationale points.
"""


@dataclass(frozen=True)
class MacroSpecialistResult:
    """Immutable contract representing the Macro Specialist's evaluation."""
    verdict: str  # STRONG_TAILWIND, MODERATE_SUPPORT, NEUTRAL, LIQUIDITY_HEADWIND
    conviction_score: int  # 0 to 100
    sector_alignment: str  # LEADING, IMPROVING, WEAKENING, LAGGING, NEUTRAL
    fii_regime: str
    key_drivers: List[str]
    model_used: str
    fallback_used: bool
    latency_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _get_deterministic_macro_fallback(
    macro_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Deterministic fallback for macro flow evaluation."""
    ctx = macro_context or {}
    fii = ctx.get("fii_net_cr") or 0.0
    sector_rrg = str(ctx.get("sector_rrg") or "BALANCED").upper()

    if fii > 500 and "LEAD" in sector_rrg:
        verdict = "STRONG_TAILWIND"
        conviction = 80
        drivers = ["Robust FII institutional inflow >₹500 Cr", "Stock belongs to Leading RRG sector"]
    elif fii < -1000 or "LAG" in sector_rrg:
        verdict = "LIQUIDITY_HEADWIND"
        conviction = 30
        drivers = ["Institutional cash drain or sector in Lagging RRG quadrant"]
    else:
        verdict = "MODERATE_SUPPORT"
        conviction = 60
        drivers = ["Macro liquidity and sector rotation within normal parameters"]

    return {
        "verdict": verdict,
        "conviction_score": conviction,
        "sector_alignment": sector_rrg,
        "fii_regime": str(ctx.get("fii_regime") or "BALANCED"),
        "key_drivers": drivers,
    }


def analyse_macro_flow(
    signal: Dict[str, Any],
    macro_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Execute Macro & Institutional Flow analysis for trade deliberation.
    """
    ctx = macro_context or {}
    symbol = str(signal.get("symbol", "UNKNOWN"))
    fii_flow_str = f"₹{ctx.get('fii_net_cr', 0.0):+.0f} Cr" if ctx.get("fii_net_cr") is not None else "Normal"

    prompt = f"""Evaluate the MACRO LIQUIDITY & SECTOR TAILWIND for {symbol}:

TRADE CONTEXT:
  Symbol:          {symbol}
  Direction:       {signal.get('direction', 'LONG')}
  Sector:          {ctx.get('sector', 'Nifty Broad Market')}

INSTITUTIONAL & SECTOR METRICS:
  FII Net Cash:    {fii_flow_str} ({ctx.get('fii_regime', 'BALANCED')})
  DII Net Cash:    ₹{ctx.get('dii_net_cr', 0.0):+.0f} Cr
  Sector RRG:      {ctx.get('sector_rrg', 'BALANCED')}
  Market Breadth:  {ctx.get('market_breadth', 'BALANCED')}
  India VIX:       {ctx.get('vix', 15.0):.1f}

Respond with strict JSON:
{{
  "verdict": "STRONG_TAILWIND|MODERATE_SUPPORT|NEUTRAL|LIQUIDITY_HEADWIND",
  "conviction_score": 0-100,
  "sector_alignment": "LEADING|IMPROVING|WEAKENING|LAGGING",
  "key_drivers": ["driver 1", "driver 2"]
}}"""

    llm_res: LLMInferenceResult = query_llm_fast(
        prompt=prompt,
        system_prompt=_SYSTEM_PROMPT,
        signal=signal,
        macro_context=macro_context,
    )

    det_fallback = _get_deterministic_macro_fallback(macro_context)
    payload = llm_res.parsed_payload or det_fallback

    verdict = str(payload.get("verdict") or det_fallback["verdict"]).upper()
    conviction = int(payload.get("conviction_score") or det_fallback["conviction_score"])
    drivers = list(payload.get("key_drivers") or det_fallback["key_drivers"])
    sector_align = str(payload.get("sector_alignment") or det_fallback["sector_alignment"])

    res = MacroSpecialistResult(
        verdict=verdict,
        conviction_score=conviction,
        sector_alignment=sector_align,
        fii_regime=str(ctx.get("fii_regime") or "BALANCED"),
        key_drivers=drivers,
        model_used=llm_res.model,
        fallback_used=llm_res.is_fallback,
        latency_ms=llm_res.latency_ms,
    )

    logger.info(f"[MacroSpecialist] {symbol} → {res.verdict} ({res.conviction_score}% conviction via {res.model_used})")
    return res.to_dict()
