"""
Module: agents/critic.py
Purpose: SOTA Post-Trade Reflection & Continuous Learning Critic Agent for MJONAI.
         Evaluates closed trades, analyzes Max Adverse Excursion (MAE), Max Favorable Excursion (MFE),
         classifies execution quality (GOOD_WIN, GOOD_LOSS, BAD_WIN_LUCKY, BAD_LOSS_MISTAKE),
         and generates strategy calibration feedback for continuous improvement.
"""

from dataclasses import dataclass, field, asdict
import html
import logging
from typing import Dict, List, Any, Optional, Union, Tuple

from agents.llm_bridge import query_llm_fast, query_llm_reasoning, LLMInferenceResult

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are the Trade Critic & Learning Agent for MJONAI — an institutional algorithmic trading system.

Your role: Post-Mortem Quantitative Analyst.
You review closed trades to extract actionable insights, detect execution inefficiencies, and improve future strategy performance.

Evaluation Criteria:
1. GOOD_WIN: Clean trend capture with favorable risk-reward and low drawdown.
2. GOOD_LOSS: Disciplined stop-loss hit with minimal slippage; followed quantitative plan.
3. BAD_WIN_LUCKY: Profitable trade that suffered excessive adverse drawdown (>1.5x SL) before recovering.
4. BAD_LOSS_MISTAKE: Severe loss from holding past stop-loss, late breakout entry, or fighting market drag.

Output Rules:
1. Respond ONLY with valid JSON — no preamble, no markdown outside JSON.
2. execution_quality must be exactly one of: GOOD_WIN, GOOD_LOSS, BAD_WIN_LUCKY, BAD_LOSS_MISTAKE
3. learning_insight must be 1-2 concise actionable sentences.
4. strategy_recommendation must suggest a specific parameter adjustment (e.g., tighten trail SL, adjust entry threshold, wider target).
"""


@dataclass(frozen=True)
class TradeReflectionResult:
    """Immutable contract representing post-trade audit and learning reflection."""
    trade_id: Optional[str]
    symbol: str
    execution_quality: str  # GOOD_WIN, GOOD_LOSS, BAD_WIN_LUCKY, BAD_LOSS_MISTAKE
    realized_pnl: float
    pnl_pct: float
    learning_insight: str
    strategy_recommendation: str
    holding_efficiency: str
    mae_pct: float
    mfe_pct: float
    model_used: str = "DETERMINISTIC"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _classify_execution_deterministic(
    pnl: float,
    pnl_pct: float,
    mae_pct: float,
    mfe_pct: float,
    exit_reason: str,
) -> Tuple[str, str, str]:
    """Pure mathematical execution classifier."""
    if pnl > 0:
        if mae_pct < -3.5:
            quality = "BAD_WIN_LUCKY"
            insight = "Trade became profitable but suffered deep drawdown during holding period."
            rec = "Consider tighter initial stop or waiting for pullback before entry."
        else:
            quality = "GOOD_WIN"
            insight = "Clean trade execution with minimal adverse drawdown and high trend capture."
            rec = "Strategy parameters aligned with current market regime."
    else:
        if "STOP_LOSS" in exit_reason or "TRAILING_SL" in exit_reason:
            quality = "GOOD_LOSS"
            insight = "Controlled loss executed strictly at planned risk levels. Statistical variance."
            rec = "Maintain disciplined risk limits."
        else:
            quality = "BAD_LOSS_MISTAKE"
            insight = "Loss occurred with suboptimal exit execution or holding against adverse trend."
            rec = "Enforce stricter automated trailing stop without manual intervention."

    return quality, insight, rec


def reflect_on_closed_trade(
    trade: Dict[str, Any],
    macro_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Perform post-mortem reflection on a closed trade.

    Args:
        trade: Closed trade record dictionary from database/ledger
        macro_context: Optional macro market context at exit

    Returns:
        Dictionary contract containing execution quality, learning insights, and recommendations.
    """
    symbol = str(trade.get("symbol", "UNKNOWN"))
    trade_id = str(trade.get("id", trade.get("trade_id", "")))
    strategy_id = str(trade.get("strategy_id", "Quantitative Strategy"))
    exit_reason = str(trade.get("exit_reason", "NORMAL_EXIT")).upper()

    entry = float(trade.get("entry_price") or 0.0)
    exit_p = float(trade.get("exit_price") or entry)
    pnl = float(trade.get("net_pnl") or trade.get("realized_pnl") or trade.get("pnl") or 0.0)
    pnl_pct = float(trade.get("pnl_pct") or 0.0)
    holding_days = int(trade.get("holding_days") or 1)

    mae_pct = float(trade.get("mae_pct") or (min(0.0, pnl_pct)))
    mfe_pct = float(trade.get("mfe_pct") or (max(0.0, pnl_pct)))

    # 1. Deterministic baseline
    det_quality, det_insight, det_rec = _classify_execution_deterministic(
        pnl=pnl,
        pnl_pct=pnl_pct,
        mae_pct=mae_pct,
        mfe_pct=mfe_pct,
        exit_reason=exit_reason,
    )

    # 2. LLM deep reflection
    prompt = f"""Conduct post-mortem review for closed trade #{trade_id} on {symbol}:

TRADE METRICS:
- Asset: {symbol} ({strategy_id})
- Entry Price: ₹{entry:.2f} | Exit Price: ₹{exit_p:.2f}
- Realized Net P&L: ₹{pnl:+,.2f} ({pnl_pct:+.2f}%)
- Holding Duration: {holding_days} days
- Exit Trigger: {exit_reason}
- Max Adverse Excursion (MAE): {mae_pct:.2f}%
- Max Favorable Excursion (MFE): {mfe_pct:.2f}%

Respond with strict JSON only:
{{
  "execution_quality": "GOOD_WIN|GOOD_LOSS|BAD_WIN_LUCKY|BAD_LOSS_MISTAKE",
  "learning_insight": "1-2 sentence core takeaway",
  "strategy_recommendation": "1 actionable parameter optimization suggestion",
  "holding_efficiency": "HIGH|OPTIMAL|LOW"
}}"""

    llm_res: LLMInferenceResult = query_llm_fast(
        prompt=prompt,
        system_prompt=_SYSTEM_PROMPT,
        signal=trade,
        macro_context=macro_context,
        is_reasoning=True,
    )

    payload = llm_res.parsed_payload or {}
    raw_qual = str(payload.get("execution_quality") or det_quality).upper()

    final_quality = raw_qual if raw_qual in ("GOOD_WIN", "GOOD_LOSS", "BAD_WIN_LUCKY", "BAD_LOSS_MISTAKE") else det_quality
    learning_insight = str(payload.get("learning_insight") or det_insight)
    strategy_rec = str(payload.get("strategy_recommendation") or det_rec)
    holding_eff = str(payload.get("holding_efficiency") or ("HIGH" if pnl > 0 else "LOW"))

    result = TradeReflectionResult(
        trade_id=trade_id or None,
        symbol=symbol,
        execution_quality=final_quality,
        realized_pnl=pnl,
        pnl_pct=pnl_pct,
        learning_insight=learning_insight,
        strategy_recommendation=strategy_rec,
        holding_efficiency=holding_eff,
        mae_pct=mae_pct,
        mfe_pct=mfe_pct,
        model_used=llm_res.model,
    )

    logger.info(f"[Critic] Post-mortem for #{trade_id} {symbol}: {result.execution_quality} (Net P&L: ₹{pnl:+,.2f})")
    return result.to_dict()
