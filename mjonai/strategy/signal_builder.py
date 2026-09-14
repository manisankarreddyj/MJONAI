"""
Module: strategy/signal_builder.py
Purpose: SOTA Signal Intelligence Schema, Flight Recorder, and Multi-Asset Record Builder.
         Standardizes signals across all 10 alpha dimensions, 3-tranche execution ladders,
         derivative metadata, Bayesian pattern hashes, and AI debate telemetry.

The 10 Core Quantitative Capabilities:
  1. Structured Indicator Scores & Raw Numerical Values Snapshot (Zero string checkmark parsing).
  2. Complete 3-Tranche Scaling Execution Geometry (Target 1, Target 2, T1/T2/Runner quantities).
  3. Directional SL & Target Distance Arithmetic (Correct for both LONG and SHORT).
  4. Deterministic Pattern Hash Auto-Generation (Links directly to db.patterns memory).
  5. Multi-Asset Derivative Metadata (Asset class, underlying, strike, option type, expiry, lot size).
  6. 10-Factor Confidence Scoring Breakdown Unpacking.
  7. 8 Deterministic Devil Checks Telemetry Matrix.
  8. AI Multi-Agent Audit Telemetry (Bull, Bear, Supervisor verdicts & token costs).
  9. Defensive Float Sanitization Against NaN/Inf.
 10. Immutable Typed Contract (SignalIntelligencePayload).
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
import logging
from typing import Dict, Any, Tuple, Optional, List, Sequence, Union

from mjonai.core.time_utils import now_ist, week_of_month, market_open_minutes
from mjonai.core.constants import (
    SYSTEM_MODE,
    SECTOR_MAP,
    get_time_bucket,
)
from mjonai.strategy.config import extract_underlying_symbol

logger = logging.getLogger(__name__)


# ── 1. DEFENSIVE FLOAT CONVERTER ─────────────────────────────────────────────

from functools import partial as _partial
from mjonai.core.numeric import safe_float as _safe_float

_safe_float = _partial(_safe_float, default=None)


# ── 2. TYPED DATA CONTRACT ───────────────────────────────────────────────────

@dataclass(frozen=True)
class SignalIntelligencePayload:
    """Immutable typed contract representing a complete Signal Intelligence log record."""
    symbol: str
    signal_type: str
    strategy_id: str
    strategy_version: str
    system_mode: str
    market_state: str
    mqi_level: str
    generated_at: str
    market_open_minutes: int
    time_of_day_bucket: str
    day_of_week: str
    week_of_month: int
    sector: Optional[str] = None
    vix_at_signal: Optional[float] = None
    technical_score: Optional[float] = None
    final_confidence: Optional[float] = None
    setup_hash: Optional[str] = None
    signal_direction: str = "LONG"
    asset_class: str = "EQUITY"
    underlying_symbol: Optional[str] = None
    strike: Optional[float] = None
    option_type: Optional[str] = None
    expiry_date: Optional[str] = None
    lot_size: int = 1
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    target_1: Optional[float] = None
    target_2: Optional[float] = None
    sl_distance_pct: Optional[float] = None
    target_distance_pct: Optional[float] = None
    sl_method: Optional[str] = None
    swing_low_used: Optional[float] = None
    atr_at_signal: Optional[float] = None
    planned_rr: Optional[float] = None
    planned_quantity: int = 0
    t1_quantity: int = 0
    t2_quantity: int = 0
    runner_quantity: int = 0
    planned_capital: float = 0.0
    indicator_scores: Dict[str, float] = field(default_factory=dict)
    indicator_values: Dict[str, float] = field(default_factory=dict)
    confidence_breakdown: Dict[str, float] = field(default_factory=dict)
    devil_all_passed: Optional[bool] = None
    devil_failure_reason: Optional[str] = None
    devil_gap_risk: Optional[bool] = None
    devil_liquidity: Optional[bool] = None
    devil_data_quality: Optional[bool] = None
    devil_pattern_memory: Optional[bool] = None
    devil_correlation: Optional[bool] = None
    devil_real_rr: Optional[bool] = None
    devil_portfolio_limits: Optional[bool] = None
    devil_event_risk: Optional[bool] = None
    earnings_safe: Optional[bool] = None
    earnings_days_away: Optional[int] = None
    sector_cap_ok: Optional[bool] = None
    bull_verdict: Optional[str] = None
    bull_confidence: Optional[float] = None
    bull_key_reasons: List[str] = field(default_factory=list)
    bull_concerns: List[str] = field(default_factory=list)
    bear_verdict: Optional[str] = None
    bear_confidence: Optional[float] = None
    bear_key_reasons: List[str] = field(default_factory=list)
    bear_red_flags: List[str] = field(default_factory=list)
    bear_fii_sentiment: Optional[str] = None
    bear_risk_summary: Optional[str] = None
    supervisor_decision: Optional[str] = None
    supervisor_reason: Optional[str] = None
    supervisor_deciding_factor: Optional[str] = None
    rejection_reason: Optional[str] = None
    extra_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert contract to serializable dict with flattened extra fields."""
        d = asdict(self)
        extra = d.pop("extra_metadata", {})
        if extra and isinstance(extra, dict):
            d.update(extra)
        return d


# ── 3. MASTER SIGNAL INTELLIGENCE BUILDER ────────────────────────────────────

def build_signal_record(
    symbol: str,
    signal_type: str,
    market_state: str,
    mqi_level: str,
    vix: Optional[float] = None,
    tech_score: Optional[float] = None,
    reasons: Optional[List[str]] = None,
    confidence: Optional[float] = None,
    levels: Optional[Dict[str, Any]] = None,
    bull_result: Optional[Dict[str, Any]] = None,
    bear_result: Optional[Dict[str, Any]] = None,
    supervisor_result: Optional[Dict[str, Any]] = None,
    devil_checks: Optional[List[str]] = None,
    devil_passed: Optional[bool] = None,
    devil_reason: Optional[str] = None,
    earnings_safe: Optional[bool] = None,
    earnings_days: Optional[int] = None,
    sector_ok: Optional[bool] = None,
    rejection_reason: Optional[str] = None,
    strategy_id: str = "S00_Legacy",
    strategy_version: str = "1.0",
    signal_direction: str = "LONG",
    asset_class: str = "EQUITY",
    underlying_symbol: Optional[str] = None,
    indicator_scores: Optional[Dict[str, float]] = None,
    indicator_values: Optional[Dict[str, float]] = None,
    confidence_breakdown: Optional[Dict[str, float]] = None,
    system_mode: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a complete signal_intelligence record dict for DB insertion.
    100% Backward-compatible signature.
    """
    payload = evaluate_signal_payload(
        symbol=symbol,
        signal_type=signal_type,
        market_state=market_state,
        mqi_level=mqi_level,
        vix=vix,
        tech_score=tech_score,
        reasons=reasons,
        confidence=confidence,
        levels=levels,
        bull_result=bull_result,
        bear_result=bear_result,
        supervisor_result=supervisor_result,
        devil_checks=devil_checks,
        devil_passed=devil_passed,
        devil_reason=devil_reason,
        earnings_safe=earnings_safe,
        earnings_days=earnings_days,
        sector_ok=sector_ok,
        rejection_reason=rejection_reason,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        signal_direction=signal_direction,
        asset_class=asset_class,
        underlying_symbol=underlying_symbol,
        indicator_scores=indicator_scores,
        indicator_values=indicator_values,
        confidence_breakdown=confidence_breakdown,
        system_mode=system_mode,
        extra=extra,
    )
    return payload.to_dict()


def _build_signal_record(*args, **kwargs) -> Dict[str, Any]:
    """Legacy internal alias for build_signal_record."""
    return build_signal_record(*args, **kwargs)


def evaluate_signal_payload(
    symbol: str,
    signal_type: str,
    market_state: str,
    mqi_level: str,
    vix: Optional[float] = None,
    tech_score: Optional[float] = None,
    reasons: Optional[List[str]] = None,
    confidence: Optional[float] = None,
    levels: Optional[Dict[str, Any]] = None,
    bull_result: Optional[Dict[str, Any]] = None,
    bear_result: Optional[Dict[str, Any]] = None,
    supervisor_result: Optional[Dict[str, Any]] = None,
    devil_checks: Optional[List[str]] = None,
    devil_passed: Optional[bool] = None,
    devil_reason: Optional[str] = None,
    earnings_safe: Optional[bool] = None,
    earnings_days: Optional[int] = None,
    sector_ok: Optional[bool] = None,
    rejection_reason: Optional[str] = None,
    strategy_id: str = "S00_Legacy",
    strategy_version: str = "1.0",
    signal_direction: str = "LONG",
    asset_class: str = "EQUITY",
    underlying_symbol: Optional[str] = None,
    indicator_scores: Optional[Dict[str, float]] = None,
    indicator_values: Optional[Dict[str, float]] = None,
    confidence_breakdown: Optional[Dict[str, float]] = None,
    system_mode: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> SignalIntelligencePayload:
    """
    SOTA Evaluator constructing typed SignalIntelligencePayload.
    """
    now = now_ist()
    time_bucket = get_time_bucket(now.hour, now.minute)
    clean_sym = str(symbol or "UNKNOWN").strip().upper()
    root_sym = extract_underlying_symbol(clean_sym)
    sector = SECTOR_MAP.get(root_sym) or SECTOR_MAP.get(clean_sym)
    sys_mode = str(system_mode or SYSTEM_MODE).upper()
    dir_clean = str(signal_direction or "LONG").strip().upper()

    # 1. Deterministic Pattern Hash Generation
    strat_id = str(extra.get("strategy_id") if extra and "strategy_id" in extra else strategy_id)
    try:
        from mjonai.db.patterns import generate_setup_hash
        setup_hash = generate_setup_hash(strat_id, market_state, time_bucket)
    except Exception:
        setup_hash = f"{strat_id}_{market_state}_{time_bucket}".replace(" ", "_")

    # 2. Indicator Scores & Values Snapshot
    ind_scores = dict(indicator_scores or {})
    ind_values = dict(indicator_values or {})

    # Backward-compatible checkmark parser fallback if indicator_scores is empty
    if not ind_scores and reasons:
        for r in reasons:
            r_str = str(r)
            if "RSI" in r_str and "✓" in r_str:
                ind_scores["rsi_score"] = 20.0
            elif "RSI" in r_str:
                ind_scores["rsi_score"] = 0.0
            if "MACD" in r_str and "✓" in r_str:
                ind_scores["macd_score"] = 20.0
            elif "MACD" in r_str:
                ind_scores["macd_score"] = 0.0
            if "EMA" in r_str and "✓" in r_str:
                ind_scores["ema_score"] = 20.0
            elif "EMA" in r_str:
                ind_scores["ema_score"] = 0.0
            if "Supertrend" in r_str and "✓" in r_str:
                ind_scores["supertrend_score"] = 20.0
            elif "Supertrend" in r_str:
                ind_scores["supertrend_score"] = 0.0
            if "Candle" in r_str and "✓" in r_str:
                ind_scores["candle_score"] = 20.0
            elif "Candle" in r_str:
                ind_scores["candle_score"] = 0.0

    # 3. Trade Level & 3-Tranche Execution Geometry
    entry_p = None
    sl_p = None
    tgt_p = None
    tgt_1_p = None
    tgt_2_p = None
    sl_dist_pct = None
    tgt_dist_pct = None
    sl_method = None
    swing_low_used = None
    atr_val = None
    planned_rr = None
    qty = 0
    t1_qty = 0
    t2_qty = 0
    runner_qty = 0
    planned_cap = 0.0

    if levels:
        entry_p = _safe_float(levels.get("entry") or levels.get("entry_price"))
        sl_p = _safe_float(levels.get("stop_loss"))
        tgt_p = _safe_float(levels.get("target"))
        tgt_1_p = _safe_float(levels.get("target_1"))
        tgt_2_p = _safe_float(levels.get("target_2"))
        sl_method = str(levels.get("sl_method") or "")
        swing_low_used = _safe_float(levels.get("swing_low"))
        atr_val = _safe_float(levels.get("atr"))
        planned_rr = _safe_float(levels.get("real_rr") or levels.get("planned_rr"))
        qty = max(0, int(levels.get("quantity") or levels.get("planned_quantity") or 0))
        t1_qty = max(0, int(levels.get("t1_quantity") or 0))
        t2_qty = max(0, int(levels.get("t2_quantity") or 0))
        runner_qty = max(0, int(levels.get("runner_quantity") or 0))

        if qty > 0 and (t1_qty + t2_qty + runner_qty == 0):
            from mjonai.risk.trade_risk import split_tranche_quantities
            t1_qty, t2_qty, runner_qty = split_tranche_quantities(qty)

        if entry_p and entry_p > 0:
            planned_cap = round(entry_p * qty, 2)
            if sl_p and sl_p > 0:
                sl_dist_pct = round(abs(entry_p - sl_p) / entry_p * 100.0, 4)
            if tgt_p and tgt_p > 0:
                tgt_dist_pct = round(abs(tgt_p - entry_p) / entry_p * 100.0, 4)

    # 4. 8 Deterministic Devil Checks Telemetry
    devil_flags: Dict[str, Optional[bool]] = {}
    if devil_checks is not None:
        check_names = set(devil_checks)
        devil_flags = {
            "devil_gap_risk": "Gap Risk" in check_names,
            "devil_liquidity": "Liquidity" in check_names,
            "devil_data_quality": "Data Quality" in check_names,
            "devil_pattern_memory": "Pattern Memory" in check_names,
            "devil_correlation": "Correlation" in check_names,
            "devil_real_rr": "Real RR" in check_names,
            "devil_portfolio_limits": "Portfolio Limits" in check_names,
            "devil_event_risk": "Event Risk" in check_names,
        }

    # 5. Multi-Agent AI Audit Unpacking
    b_verd = bull_result.get("verdict") if bull_result else None
    b_conf = _safe_float(bull_result.get("confidence")) if bull_result else None
    b_reasons = bull_result.get("key_reasons", []) if bull_result else []
    b_concerns = bull_result.get("concerns", []) if bull_result else []

    be_verd = bear_result.get("verdict") if bear_result else None
    be_conf = _safe_float(bear_result.get("confidence")) if bear_result else None
    be_reasons = bear_result.get("key_reasons", []) if bear_result else []
    be_flags = bear_result.get("red_flags", []) if bear_result else []
    be_fii = bear_result.get("fii_sentiment") if bear_result else None
    be_summary = bear_result.get("risk_summary") if bear_result else None

    s_dec = supervisor_result.get("final_decision") if supervisor_result else None
    s_reason = supervisor_result.get("rejection_reason") if supervisor_result else None
    s_factor = supervisor_result.get("deciding_factor") if supervisor_result else None

    # Merge Extra
    extra_dict = dict(extra or {})

    return SignalIntelligencePayload(
        symbol=clean_sym,
        signal_type=signal_type,
        strategy_id=strat_id,
        strategy_version=strategy_version,
        system_mode=sys_mode,
        market_state=market_state,
        mqi_level=mqi_level,
        generated_at=now.isoformat(),
        market_open_minutes=market_open_minutes(now),
        time_of_day_bucket=time_bucket,
        day_of_week=now.strftime("%A"),
        week_of_month=week_of_month(now),
        sector=sector,
        vix_at_signal=_safe_float(vix),
        technical_score=_safe_float(tech_score),
        final_confidence=_safe_float(confidence),
        setup_hash=setup_hash,
        signal_direction=dir_clean,
        asset_class=asset_class,
        underlying_symbol=root_sym,
        entry_price=entry_p,
        stop_loss=sl_p,
        target=tgt_p,
        target_1=tgt_1_p,
        target_2=tgt_2_p,
        sl_distance_pct=sl_dist_pct,
        target_distance_pct=tgt_dist_pct,
        sl_method=sl_method,
        swing_low_used=swing_low_used,
        atr_at_signal=atr_val,
        planned_rr=planned_rr,
        planned_quantity=qty,
        t1_quantity=t1_qty,
        t2_quantity=t2_qty,
        runner_quantity=runner_qty,
        planned_capital=planned_cap,
        indicator_scores=ind_scores,
        indicator_values=ind_values,
        confidence_breakdown=dict(confidence_breakdown or {}),
        devil_all_passed=devil_passed,
        devil_failure_reason=devil_reason,
        devil_gap_risk=devil_flags.get("devil_gap_risk"),
        devil_liquidity=devil_flags.get("devil_liquidity"),
        devil_data_quality=devil_flags.get("devil_data_quality"),
        devil_pattern_memory=devil_flags.get("devil_pattern_memory"),
        devil_correlation=devil_flags.get("devil_correlation"),
        devil_real_rr=devil_flags.get("devil_real_rr"),
        devil_portfolio_limits=devil_flags.get("devil_portfolio_limits"),
        devil_event_risk=devil_flags.get("devil_event_risk"),
        earnings_safe=earnings_safe,
        earnings_days_away=earnings_days,
        sector_cap_ok=sector_ok,
        bull_verdict=b_verd,
        bull_confidence=b_conf,
        bull_key_reasons=b_reasons,
        bull_concerns=b_concerns,
        bear_verdict=be_verd,
        bear_confidence=be_conf,
        bear_key_reasons=be_reasons,
        bear_red_flags=be_flags,
        bear_fii_sentiment=be_fii,
        bear_risk_summary=be_summary,
        supervisor_decision=s_dec,
        supervisor_reason=s_reason,
        supervisor_deciding_factor=s_factor,
        rejection_reason=rejection_reason,
        extra_metadata=extra_dict,
    )
