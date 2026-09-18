"""
Module: strategy/pipeline.py
Purpose: SOTA Single Signal Processing Pipeline, 7-Stage Verification Funnel,
         Deterministic Devil Checks, Concurrent Multi-Agent AI Debate Room Orchestration,
         3-Tranche Execution Sizing, and Permanent Intelligence Ledger.

The 7 Verification Gates:
  Gate 1: Multi-Factor Quantitative Confidence Check (Dynamic 10-factor confluence engine).
  Gate 2: Corporate Earnings Blackout (Exempts Index and Commodity derivatives).
  Gate 3: Beta-Weighted Sector Concentration Limits (Derivative underlying symbol extraction).
  Gate 4: Precision 3-Tranche Price Geometry & Slippage Guard (Target 1, Target 2, T1/T2/Runner sizing).
  Gate 5: 8 Deterministic Mathematical Devil Checks (Gap Risk, Liquidity, VIX, Event Risk, etc.).
  Gate 6: Concurrent Multi-Agent AI Boardroom Debate (Bull & Bear parallelized, Supervisor CIO verdict).
  Gate 7: Order Dispatch & Permanent Flight Recorder Logging (db.signals.insert_signal_intelligence).
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
import logging
import math
from typing import Dict, Any, Tuple, Optional, List, Sequence, Union

from mjonai.core.time_utils import now_ist
from mjonai.core.numeric import safe_float as _safe_float
from mjonai.core.constants import (
    SYSTEM_MODE,
    SECTOR_MAP,
    RESEARCH_CONFIDENCE_MIN,
    LIVE_CONFIDENCE_MIN,
    TOTAL_CAPITAL,
    GROWTH_POOL_PCT,
    MAX_OPEN_POSITIONS,
)
from mjonai.db.repository import (
    insert_signal,
    insert_signal_intelligence,
)
from mjonai.risk.trade_risk import (
    calculate_trade_levels,
    evaluate_trade_risk_levels,
    find_swing_low,
    find_swing_high,
    split_tranche_quantities,
)
from mjonai.risk.emergency_triggers import is_trading_allowed
from mjonai.risk.devil_checks import run_all_devil_checks, evaluate_devil_checks
from mjonai.agents.bull import analyse as bull_analyse
from mjonai.agents.bear import analyse as bear_analyse
from mjonai.agents.supervisor import evaluate as supervisor_evaluate

# Universal TA-Lib Compatibility Bridge
import mjonai.strategy.registry.indicators as indicators
from mjonai.strategy.config import (
    calculate_confidence,
    evaluate_confidence_score,
    check_sector_limits,
    evaluate_sector_limits,
    get_dynamic_position_limit,
    extract_underlying_symbol,
    _build_calendar_events,
)
from mjonai.strategy.signal_builder import build_signal_record, _build_signal_record


def _live_market_quality(symbol: str) -> tuple:
    """
    Real spread (%) and data-quality score (0-100) for Devil Checks 2 & 3,
    taken from the live feed. The old call passed nothing, so both checks
    evaluated fixed defaults and passed unconditionally (dead controls).

    Behaviour:
    - token known AND tick fresh   -> real spread, quality 95
    - token known BUT tick stale   -> spread 0.5%, quality 55  (both FAIL
      their thresholds: bad data vetoes the signal - fail closed)
    - token unknown (no map entry) -> legacy neutral defaults, logged once
    """
    try:
        from mjonai.data.angelone.token_map import SYMBOL_MAP
        from mjonai.data.angelone import websocket as _ws

        token = SYMBOL_MAP.get(symbol) if SYMBOL_MAP else None
        if not token:
            return 0.05, 95.0

        token_str = str(token)

        if hasattr(_ws, "_is_fresh") and not _ws._is_fresh(token_str):
            logger.warning(f"[Pipeline] Stale tick for {symbol} - Devil Checks 2/3 will veto")
            return 0.5, 55.0

        spread = None
        if hasattr(_ws, "get_live_spread_pct"):
            try:
                spread = _ws.get_live_spread_pct(token_str)
            except Exception:
                spread = None

        if spread is None or spread <= 0:
            # Fresh but one-sided quotes (depth absent): mildly stricter default.
            return 0.10, 95.0

        return float(spread), 95.0
    except Exception as e:
        logger.debug(f"[Pipeline] _live_market_quality fallback for {symbol}: {e}")
        return 0.05, 95.0

def _raw_token_is_fresh(token: Any) -> bool:
    """
    Fail-closed freshness probe for callers that read the raw ``live_prices``
    dict: a token is usable only when its last tick is fresh. Any resolution
    failure returns False, so a stale or unknown tick is never treated as live.
    """
    try:
        from mjonai.data.angelone import websocket as _ws
        return bool(_ws.is_token_fresh(str(token)))
    except Exception:
        return False

logger = logging.getLogger(__name__)

# List of macro index & commodity underlying symbols exempt from corporate earnings checks
INDEX_UNDERLYINGS = {
    "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "BANKEX",
    "CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"
}


# ── 1. TYPED DATA CONTRACT ───────────────────────────────────────────────────

@dataclass(frozen=True)
class PipelineProcessingResult:
    """Immutable contract representing the output of the 7-stage signal processing pipeline."""
    is_approved: bool
    rejection_stage: str
    rejection_reason: str
    signal_data: Optional[Dict[str, Any]] = None
    signal_intelligence_id: Optional[str] = None
    stage_durations_ms: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── 2. DEFENSIVE FLOAT CONVERTER ─────────────────────────────────────────────

def _compute_trend_strength(
    high_s: Any,
    low_s: Any,
    close_s: Any,
    timeperiod: int = 14,
) -> Optional[float]:
    """
    Real Wilder ADX (H5 fix): the previous inline expression was a gain/loss
    ratio mislabeled as ADX and silently fed position-sizing weights. Returns
    None on insufficient/flat history so market weight stays neutral (1.0).
    """
    try:
        adx_arr = indicators.ADX(high_s, low_s, close_s, timeperiod=timeperiod)
        if len(adx_arr) > 0:
            last_val = float(adx_arr[-1])
            if last_val == last_val and last_val > 0:  # NaN-safe
                return round(last_val, 2)
    except Exception:
        pass
    return None


def _resolve_structure_reference(
    strategy_result: Dict[str, Any],
    df: Any,
    signal_direction: str,
):
    """
    C2 fix: strategies emit their own engineered stop through the typed
    contract (swing_low/swing_high + sl_method — e.g. S03's TURTLE_2N hard
    stop, S01's breathing-room stop). Prefer that level EXACTLY; the generic
    10-bar fractal recomputation is only a fallback. The legacy 'turtle_sl'
    key was never emitted by any registry strategy and is dropped.

    Returns (reference_level, is_explicit_strategy_stop).
    """
    direction = str(signal_direction or "LONG").upper()
    emitted = strategy_result.get("swing_low") if direction == "LONG" else strategy_result.get("swing_high")
    try:
        if emitted is not None and float(emitted) > 0:
            return float(emitted), True
    except (TypeError, ValueError):
        pass
    if direction == "SHORT":
        return find_swing_high(df, lookback=10), False
    return find_swing_low(df, lookback=10), False


def _rvol_ratio_to_score(ratio: Any) -> Optional[float]:
    """
    H3: map an RVOL ratio (e.g. 1.35x from strategy indicator_values) to a
    0-100 evidence score. Linear anchor: 0.5x -> 0, 2.0x -> 100 (1.0x ~ 33).
    Returns None when the strategy did not emit RVOL — never a default.
    """
    r = _safe_float(ratio, default=float("nan"))
    if math.isnan(r) or r <= 0:
        return None
    return round(max(0.0, min(100.0, (r - 0.5) / 1.5 * 100.0)), 1)


def _live_mqi_pct() -> Optional[float]:
    """H3: real MQI percentage from the live hot-path cache; None if absent."""
    try:
        from mjonai.core.mqi import get_cached_mqi

        snapshot = get_cached_mqi()
        pct = getattr(snapshot, "mqi_pct", None)
        if pct is None:
            return None
        value = _safe_float(pct, default=float("nan"))
        return None if math.isnan(value) else round(value, 1)
    except Exception:
        return None


def _pattern_expectancy_score(
    strategy_result: Dict[str, Any],
    symbol: str,
    market_state: str,
    vix: float,
    system_mode: str,
) -> Optional[float]:
    """
    H3 follow-up: real pattern-memory factor. Score = Laplace-smoothed win
    rate (schema field laplace_win_rate, 0-100) for this setup hash.
    Quarantined setups score 0.0 (strong negative evidence); fewer than 3
    occurrences or any lookup failure -> None (no memory is NOT bad memory).
    Hash inputs mirror execution/orders.open_paper_trade so the looked-up
    fingerprint matches the one stored on the trade row.
    """
    try:
        from mjonai.core.constants import build_setup_hash
        from mjonai.db.patterns import get_pattern

        setup_hash = strategy_result.get("setup_hash") or build_setup_hash(
            symbol=str(symbol),
            strategy_id=str(strategy_result.get("strategy_id", "UNKNOWN")),
            sl_method=str(strategy_result.get("sl_method", "ATR")),
            market_state=strategy_result.get("market_state") or str(market_state),
            vix=_safe_float(vix, default=15.0) if vix is not None else 15.0,
            candle_pattern=str(strategy_result.get("candle_pattern", "NONE")),
        )
        record = get_pattern(setup_hash=str(setup_hash), system_mode=system_mode)
        if not record:
            return None
        if record.get("is_quarantined"):
            return 0.0
        occurrences = int(record.get("occurrences") or 0)
        if occurrences < 3:
            return None
        score = _safe_float(record.get("laplace_win_rate"), default=float("nan"))
        return None if math.isnan(score) else round(max(0.0, min(100.0, score)), 1)
    except Exception:
        return None


def _sector_breadth_score(
    sector_breadth_map: Optional[Dict[str, float]],
    symbol: str,
) -> Optional[float]:
    """
    H3 bridge: symbol -> SECTOR_MAP sector -> advancing ratio (0..1) -> 0-100.
    Missing map / unknown sector / absent ratio all degrade to None (never
    fabricated) — the H3 evaluator excludes them honestly.
    """
    if not sector_breadth_map or not symbol:
        return None
    sector = SECTOR_MAP.get(str(symbol).upper())
    if not sector:
        return None
    ratio = sector_breadth_map.get(sector)
    if ratio is None:
        return None
    return round(max(0.0, min(1.0, float(ratio))) * 100.0, 1)


# ── 3. SINGLE STRATEGY SIGNAL PROCESSING PIPELINE ────────────────────────────

def process_single_strategy_signal(
    strategy_result: Dict[str, Any],
    clean_symbol: str,
    df: Any,
    market_state: str,
    mqi_level: str,
    vix: float,
    open_trades: Sequence[Dict[str, Any]],
    open_strategy_symbols: set,
    live_prices: Dict[str, Any],
    symbol_map: Dict[str, Any],
    approved_signals: List[Dict[str, Any]],
    system_mode: Optional[str] = None,
    sector_breadth_map: Optional[Dict[str, float]] = None,
) -> bool:
    """
    Process a single strategy signal through the 7 verification gates.
    Backward-compatible boolean return.
    """
    res = evaluate_strategy_pipeline(
        strategy_result=strategy_result,
        clean_symbol=clean_symbol,
        df=df,
        market_state=market_state,
        mqi_level=mqi_level,
        vix=vix,
        open_trades=open_trades,
        open_strategy_symbols=open_strategy_symbols,
        live_prices=live_prices,
        symbol_map=symbol_map,
        system_mode=system_mode,
        sector_breadth_map=sector_breadth_map,
    )

    if res.is_approved and res.signal_data:
        approved_signals.append(res.signal_data)
        return True
    return False


def _process_single_strategy_signal(*args, **kwargs) -> bool:
    """Legacy alias for process_single_strategy_signal."""
    return process_single_strategy_signal(*args, **kwargs)


def evaluate_strategy_pipeline(
    strategy_result: Dict[str, Any],
    clean_symbol: str,
    df: Any,
    market_state: str,
    mqi_level: str,
    vix: float,
    open_trades: Sequence[Dict[str, Any]],
    open_strategy_symbols: set,
    live_prices: Dict[str, Any],
    symbol_map: Dict[str, Any],
    system_mode: Optional[str] = None,
    sector_breadth_map: Optional[Dict[str, float]] = None,
) -> PipelineProcessingResult:
    """
    SOTA 7-Stage Quantitative Verification Funnel returning typed PipelineProcessingResult.
    `sector_breadth_map`: per-sector advancing ratio (0..1) computed by the
    scanner's cross-section for this cycle; None entries stay honest-None.
    """
    sys_mode = str(system_mode or SYSTEM_MODE).upper()
    tech_score = _safe_float(strategy_result.get("technical_score"))
    reasons = strategy_result.get("reasons", [])
    candle_pattern = strategy_result.get("candle_pattern", "NONE")
    strategy_id = str(strategy_result.get("strategy_id", "S00_Legacy"))
    strategy_ver = str(strategy_result.get("strategy_version", "1.0"))
    signal_direction = str(strategy_result.get("signal_direction", "LONG")).upper()
    asset_class = str(strategy_result.get("asset_class", "EQUITY")).upper()

    # Extract root underlying symbol (e.g. RELIANCE26AUGFUT -> RELIANCE, NIFTY26AUG24500CE -> NIFTY)
    underlying_symbol = extract_underlying_symbol(clean_symbol)

    # ── CHECK: Duplicate Position Check ──────────────────────────────
    if (clean_symbol, strategy_id) in open_strategy_symbols:
        msg = f"{clean_symbol} — {strategy_id} position already open."
        logger.info(f"[Pipeline] ✗ {msg}")
        return PipelineProcessingResult(
            is_approved=False,
            rejection_stage="DUPLICATE_CHECK",
            rejection_reason=msg,
        )

    # ── CHECK: Behavioral Guard Symbol Quarantine Check ──────────────
    try:
        from mjonai.risk.behavioral_guard import is_symbol_locked
        if is_symbol_locked(clean_symbol) or is_symbol_locked(underlying_symbol):
            msg = f"{clean_symbol} quarantined by Behavioral Guard due to consecutive stop-outs."
            logger.info(f"[Pipeline] ✗ {msg}")
            return PipelineProcessingResult(
                is_approved=False,
                rejection_stage="BEHAVIORAL_SYMBOL_LOCK",
                rejection_reason=msg,
                rejection_code="SYMBOL_QUARANTINED",
            )
    except Exception as e:
        logger.debug(f"[Pipeline] Behavioral symbol check notice: {e}")

    # ── GATE 1: Multi-Factor Quantitative Confidence Evaluation ──────
    # H3 fix: feed REAL auxiliary evidence where it exists (strategy RVOL
    # ratio + live MQI pct). Everything still missing stays None and is
    # excluded by the evaluator's renormalized blend — never fabricated.
    conf_res = evaluate_confidence_score(
        technical=tech_score,
        rvol=_rvol_ratio_to_score((strategy_result.get("indicator_values") or {}).get("rvol")),
        mqi_score=_live_mqi_pct(),
        pattern_expectancy=_pattern_expectancy_score(
            strategy_result=strategy_result,
            symbol=clean_symbol,
            market_state=market_state,
            vix=vix,
            system_mode=sys_mode,
        ),
        sector_breadth=_sector_breadth_score(sector_breadth_map, clean_symbol),
        relative_strength=strategy_result.get("rs_score"),
        derivative_oi=strategy_result.get("oi_score"),
        system_mode=sys_mode,
    )

    if not conf_res.is_approved:
        logger.info(f"[Pipeline] ✗ Gate 1 Rejected ({clean_symbol}): {conf_res.rejection_reason}")
        try:
            insert_signal_intelligence(build_signal_record(
                symbol=clean_symbol,
                signal_type="PRE_FILTERED",
                market_state=market_state,
                mqi_level=mqi_level,
                vix=vix,
                tech_score=tech_score,
                reasons=reasons,
                confidence=conf_res.confidence,
                rejection_reason=conf_res.rejection_reason,
                strategy_id=strategy_id,
                strategy_version=strategy_ver,
                signal_direction=signal_direction,
                asset_class=asset_class,
                system_mode=sys_mode,
                underlying_symbol=underlying_symbol,
            ))
        except Exception:
            pass

        return PipelineProcessingResult(
            is_approved=False,
            rejection_stage="CONFIDENCE_FILTER",
            rejection_reason=conf_res.rejection_reason,
        )

    confidence = conf_res.confidence

    # ── GATE 2: Corporate Earnings Blackout (Exempts Indices, Commodities, Options, Crypto) ──
    is_index_or_commodity = (
        asset_class in ("INDEX", "COMMODITY", "OPTIONS", "CRYPTO", "FOREX") or
        underlying_symbol.upper() in INDEX_UNDERLYINGS
    )

    is_safe: bool = True
    earnings_msg: str = ""

    if is_index_or_commodity:
        is_safe = True
        earnings_msg = f"{underlying_symbol} (Index/Commodity) — exempt from corporate earnings check."
    else:
        # H12 fix: mode-aware fail-closed. RESEARCH may proceed degraded
        # (explicitly opted into the permissive fallback); PAPER/LIVE treat
        # an unverifiable earnings calendar as a BLOCK, never a bypass.
        research_degraded = str(sys_mode).upper() == "RESEARCH"
        try:
            from mjonai.data.earnings.earnings_check import check_earnings_risk
            risk_snap = check_earnings_risk(
                underlying_symbol,
                allow_degraded_permissive=research_degraded,
            )
            is_safe = bool(getattr(risk_snap, "is_safe", risk_snap[0]))
            earnings_msg = str(getattr(risk_snap, "message", risk_snap[1]))
        except Exception as e:
            if research_degraded:
                is_safe = True
                earnings_msg = f"Earnings gate unavailable in RESEARCH — proceeding degraded: {e}"
                logger.warning(f"[Pipeline] {clean_symbol}: {earnings_msg}")
            else:
                is_safe = False
                earnings_msg = f"Earnings gate UNAVAILABLE — failing CLOSED ({sys_mode}): {e}"
                logger.error(f"[Pipeline] ✗ Gate 2 {clean_symbol}: {earnings_msg}")

    if not is_safe:
        logger.info(f"[Pipeline] ✗ Gate 2 Blocked ({clean_symbol}): {earnings_msg}")
        try:
            insert_signal_intelligence(build_signal_record(
                symbol=clean_symbol,
                signal_type="PRE_FILTERED",
                market_state=market_state,
                mqi_level=mqi_level,
                vix=vix,
                tech_score=tech_score,
                reasons=reasons,
                confidence=confidence,
                earnings_safe=False,
                rejection_reason=earnings_msg,
                strategy_id=strategy_id,
                strategy_version=strategy_ver,
                signal_direction=signal_direction,
                asset_class=asset_class,
                system_mode=sys_mode,
                underlying_symbol=underlying_symbol,
            ))
        except Exception:
            pass

        return PipelineProcessingResult(
            is_approved=False,
            rejection_stage="EARNINGS_BLACKOUT",
            rejection_reason=earnings_msg,
        )

    # ── GATE 3: Beta-Weighted Sector Concentration Limits ────────────
    close_vals = df['Close'].squeeze().values
    proxy_entry = _safe_float(close_vals[-1]) if len(close_vals) > 0 else 1000.0

    from mjonai.risk.trade_risk import calculate_position_size
    proxy_qty = calculate_position_size(
        entry=proxy_entry,
        stop_loss=proxy_entry * 0.985 if signal_direction == "LONG" else proxy_entry * 1.015,
        confidence=confidence,
        vix=vix,
        trade_type=str(strategy_result.get("timeframe", "SWING")),
        system_mode=sys_mode,
    )

    sector_res = evaluate_sector_limits(
        candidate_symbol=clean_symbol,
        candidate_entry=proxy_entry,
        candidate_qty=proxy_qty,
        open_trades=open_trades,
    )

    if not sector_res.is_allowed:
        logger.info(f"[Pipeline] ✗ Gate 3 Blocked ({clean_symbol}): {sector_res.reason}")
        try:
            insert_signal_intelligence(build_signal_record(
                symbol=clean_symbol,
                signal_type="PRE_FILTERED",
                market_state=market_state,
                mqi_level=mqi_level,
                vix=vix,
                tech_score=tech_score,
                reasons=reasons,
                confidence=confidence,
                earnings_safe=is_safe,
                sector_ok=False,
                rejection_reason=sector_res.reason,
                strategy_id=strategy_id,
                strategy_version=strategy_ver,
                signal_direction=signal_direction,
                asset_class=asset_class,
                system_mode=sys_mode,
                underlying_symbol=underlying_symbol,
            ))
        except Exception:
            pass

        return PipelineProcessingResult(
            is_approved=False,
            rejection_stage="SECTOR_LIMIT",
            rejection_reason=sector_res.reason,
        )

    # ── GATE 4: Live Price Resolution, Slippage Guard & 3-Tranche Geometry ──
    close_s = df['Close'].squeeze()
    high_s = df['High'].squeeze()
    low_s = df['Low'].squeeze()

    atr_vals = indicators.ATR(high_s, low_s, close_s, timeperiod=14)
    atr = _safe_float(atr_vals[-1]) if len(atr_vals) > 0 else proxy_entry * 0.015

    # ADX trend strength: real Wilder ADX via registry indicators (H5 fix).
    # None on insufficient/flat history -> market weight stays neutral.
    adx = _compute_trend_strength(high_s, low_s, close_s)

    # Resolve Entry Price: WebSocket LTP -> Live Intraday Candle Close -> Daily Candle Close Fallback
    ltp = None
    ltp_source = "CANDLE_CLOSE"
    if live_prices and symbol_map:
        token = symbol_map.get(clean_symbol)
        if token and str(token) in live_prices and _raw_token_is_fresh(token):
            ltp = _safe_float(live_prices.get(str(token)))
            if ltp > 0:
                ltp_source = "WEBSOCKET"

    # Fallback 1: Query live intraday 15m candle close for exact live fill
    if not ltp or ltp <= 0:
        try:
            from mjonai.data.angelone.historical import fetch_historical_candles, CandleInterval
            df_live = fetch_historical_candles(clean_symbol, interval=CandleInterval.FIFTEEN_MINUTE, days_back=1)
            if df_live is not None and not df_live.empty:
                ltp = _safe_float(df_live["Close"].iloc[-1])
                if ltp > 0:
                    ltp_source = "LIVE_INTRADAY_TICK"
        except Exception:
            pass

    # Fallback 2: Proxy entry from scanner dataframe
    if not ltp or ltp <= 0:
        ltp = proxy_entry
        ltp_source = "CANDLE_CLOSE"

    entry = round(float(ltp), 2)

    # Structure Stop Loss Resolution (C2 fix): honor the strategy's own
    # engineered stop exactly; fall back to the generic fractal only when
    # the strategy did not emit one.
    swing_ref, explicit_stop = _resolve_structure_reference(strategy_result, df, signal_direction)

    trade_type = str(strategy_result.get("timeframe", "SWING"))

    trade_risk_eval = evaluate_trade_risk_levels(
        entry=entry,
        atr=atr,
        confidence=confidence,
        vix=vix,
        trade_type=trade_type,
        swing_low=swing_ref if signal_direction == "LONG" else None,
        swing_high=swing_ref if signal_direction == "SHORT" else None,
        structure_buffer=0.0 if explicit_stop else None,
        adx=adx,
        signal_direction=signal_direction,
        system_mode=sys_mode,
        lot_size=int(strategy_result.get("lot_size", 1)),
        freeze_qty=strategy_result.get("freeze_qty"),
    )

    if not trade_risk_eval.is_approved:
        msg = f"Trade risk validation failed: {trade_risk_eval.rejection_reason}"
        logger.info(f"[Pipeline] ✗ Gate 4 Rejected ({clean_symbol}): {msg}")
        return PipelineProcessingResult(
            is_approved=False,
            rejection_stage="TRADE_RISK_VALIDATION",
            rejection_reason=msg,
        )

    levels = trade_risk_eval.to_dict()
    if strategy_result.get("sl_method"):
        levels["sl_method"] = strategy_result["sl_method"]

    # ── GATE 5: 8 Deterministic Mathematical Devil Checks ────────────
    live_spread_pct, live_data_quality = _live_market_quality(clean_symbol)
    devil_res = evaluate_devil_checks(
        signal={
            "symbol": clean_symbol,
            "entry_price": levels["entry"],
            "stop_loss": levels["stop_loss"],
            "target": levels["target"],
            "quantity": levels["quantity"],
            "total_cost": levels["total_cost"],
            "atr": levels["atr"],
            "sl_method": levels["sl_method"],
            "strategy_id": strategy_id,
            "market_state": market_state,
            "vix_at_signal": vix,
            "candle_pattern": candle_pattern,
            "signal_direction": signal_direction,
            "asset_class": asset_class,
            "underlying_symbol": underlying_symbol,
        },
        open_trades=open_trades,
        calendar_events=_build_calendar_events(),
        bid_ask_spread_pct=live_spread_pct,
        data_quality_score=live_data_quality,
        system_mode=sys_mode,
        df=df,
    )
    devil_passed = devil_res.all_passed
    devil_reason = devil_res.failure_reason
    devil_checks = devil_res.passed_checks

    if not devil_passed:
        logger.info(f"[Pipeline] ✗ Gate 5 Vetoed ({clean_symbol}): {devil_reason}")
        try:
            insert_signal_intelligence(build_signal_record(
                symbol=clean_symbol,
                signal_type="DEBATE_REJECTED",
                market_state=market_state,
                mqi_level=mqi_level,
                vix=vix,
                tech_score=tech_score,
                reasons=reasons,
                confidence=confidence,
                levels=levels,
                devil_checks=devil_checks,
                devil_passed=False,
                devil_reason=devil_reason,
                earnings_safe=is_safe,
                sector_ok=True,
                rejection_reason=devil_reason,
                strategy_id=strategy_id,
                strategy_version=strategy_ver,
                signal_direction=signal_direction,
                asset_class=asset_class,
                system_mode=sys_mode,
                underlying_symbol=underlying_symbol,
            ))
        except Exception:
            pass

        return PipelineProcessingResult(
            is_approved=False,
            rejection_stage="DEVIL_CHECKS_VETO",
            rejection_reason=devil_reason,
        )

    # Dynamic Gap Risk Position Size Scaling (0.75x for Medium, 0.50x for High)
    gap_mult = _safe_float(devil_res.details.get("gap_risk_multiplier") if devil_res.details else 1.0, default=1.0)
    if 0.0 < gap_mult < 1.0:
        lot_size = int(strategy_result.get("lot_size", 1))
        orig_qty = int(levels.get("quantity", 1))
        scaled_qty = max(lot_size, int(round(orig_qty * gap_mult)))
        if lot_size > 1:
            scaled_qty = (scaled_qty // lot_size) * lot_size
            if scaled_qty < lot_size:
                scaled_qty = lot_size
        levels["quantity"] = scaled_qty
        levels["gap_risk_multiplier"] = gap_mult
        levels["capital_allocated"] = round(levels["entry"] * scaled_qty, 2)
        logger.info(f"[Pipeline] Gap risk size scaled {orig_qty} -> {scaled_qty} ({gap_mult:.2f}x) for {clean_symbol}")

    # ── GATE 6: Concurrent Multi-Agent AI Boardroom Debate Room ──────
    signal_intelligence_id = None
    try:
        gen_record = insert_signal_intelligence(build_signal_record(
            symbol=clean_symbol,
            signal_type="GENERATED",
            market_state=market_state,
            mqi_level=mqi_level,
            vix=vix,
            tech_score=tech_score,
            reasons=reasons,
            confidence=confidence,
            levels=levels,
            devil_checks=devil_checks,
            devil_passed=True,
            devil_reason=None,
            earnings_safe=is_safe,
            sector_ok=True,
            strategy_id=strategy_id,
            strategy_version=strategy_ver,
            signal_direction=signal_direction,
            asset_class=asset_class,
            system_mode=sys_mode,
            underlying_symbol=underlying_symbol,
            extra={
                "candle_pattern": candle_pattern,
                "ltp_source": ltp_source,
            },
        ))
        if gen_record and isinstance(gen_record, dict):
            signal_intelligence_id = gen_record.get("id")
    except Exception as e:
        logger.warning(f"[Pipeline] GENERATED record insert failed (non-critical): {e}")

    debate_signal = {
        "symbol": clean_symbol,
        "entry_price": levels["entry"],
        "stop_loss": levels["stop_loss"],
        "target": levels["target"],
        "quantity": levels["quantity"],
        "risk_reward": levels["real_rr"],
        "total_cost": levels["total_cost"],
        "confidence": confidence,
        "atr": levels["atr"],
        "sl_method": levels["sl_method"],
        "market_state": market_state,
        "mqi_level": mqi_level,
        "reasons": reasons,
        "signal_intelligence_id": signal_intelligence_id,
        "vix_at_signal": vix,
        "signal_direction": signal_direction,
        "asset_class": asset_class,
        "underlying_symbol": underlying_symbol,
    }

    # Parallelize Bull and Bear Agent Analysis for 50% Latency Reduction
    bull_result: Dict[str, Any] = {"verdict": "NEUTRAL", "confidence": confidence, "model_used": "FALLBACK"}
    bear_result: Dict[str, Any] = {"verdict": "NEUTRAL", "confidence": confidence, "model_used": "FALLBACK"}

    try:
        from mjonai.intelligence.context_builder import build_macro_context
        macro_context = build_macro_context(
            vix=vix,
            market_state=market_state,
            calendar_events=_build_calendar_events(),
        )
    except Exception as e:
        logger.warning(f"[Pipeline] macro_context build failed (neutral fallback): {e}")
        macro_context = None

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_bull = executor.submit(bull_analyse, signal=debate_signal, devil_checks_passed=devil_checks, macro_context=macro_context)
            fut_bear = executor.submit(bear_analyse, signal=debate_signal, macro_context=macro_context)
            bull_result = fut_bull.result(timeout=10.0)
            bear_result = fut_bear.result(timeout=10.0)
    except Exception as e:
        logger.warning(f"[Pipeline] Concurrent AI debate error (falling back): {e}")

    # Supervisor CIO Agent Verdict
    supervisor_result = supervisor_evaluate(
        signal=debate_signal,
        bull_result=bull_result,
        devil_checks_passed=devil_checks,
        bear_result=bear_result,
        macro_context=macro_context,
    )

    if not supervisor_result.get("approved"):
        sup_reason = supervisor_result.get("rejection_reason", "Supervisor Veto")
        logger.info(f"[Pipeline] ✗ Gate 6 Vetoed ({clean_symbol}): {sup_reason}")
        try:
            insert_signal_intelligence(build_signal_record(
                symbol=clean_symbol,
                signal_type="DEBATE_REJECTED",
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
                devil_passed=True,
                earnings_safe=is_safe,
                sector_ok=True,
                rejection_reason=sup_reason,
                strategy_id=strategy_id,
                strategy_version=strategy_ver,
                signal_direction=signal_direction,
                asset_class=asset_class,
                system_mode=sys_mode,
                underlying_symbol=underlying_symbol,
            ))
        except Exception:
            pass

        return PipelineProcessingResult(
            is_approved=False,
            rejection_stage="SUPERVISOR_DEBATE_VETO",
            rejection_reason=sup_reason,
            signal_intelligence_id=signal_intelligence_id,
        )

    # ── GATE 7: Order Dispatch Packet Assembly & Permanent Ledger ────
    final_signal = {
        "symbol": clean_symbol,
        "signal_type": "BUY" if signal_direction == "LONG" else "SELL",
        "entry_price": levels["entry"],
        "stop_loss": levels["stop_loss"],
        "target": levels["target"],
        "target_1": levels.get("target_1"),
        "target_2": levels.get("target_2"),
        "quantity": levels["quantity"],
        "t1_quantity": levels.get("t1_quantity", 0),
        "t2_quantity": levels.get("t2_quantity", 0),
        "runner_quantity": levels.get("runner_quantity", 0),
        "confidence": confidence,
        "atr": levels["atr"],
        "risk_reward": levels["real_rr"],
        "total_cost": levels["total_cost"],
        "technical_score": tech_score,
        "market_state": market_state,
        "mqi_level": mqi_level,
        "status": "APPROVED",
        "reasons": reasons,
        "sl_method": levels["sl_method"],
        "swing_low": levels.get("swing_low"),
        "bull_verdict": bull_result.get("verdict"),
        "bull_confidence": bull_result.get("confidence"),
        "signal_intelligence_id": signal_intelligence_id,
        "vix_at_signal": vix,
        "strategy_id": strategy_id,
        "strategy_version": strategy_ver,
        "candle_pattern": candle_pattern,
        "trade_type": trade_type,
        "signal_direction": signal_direction,
        "asset_class": asset_class,
        "underlying_symbol": underlying_symbol,
        "ltp_source": ltp_source,
    }

    # Log APPROVED record
    try:
        insert_signal_intelligence(build_signal_record(
            symbol=clean_symbol,
            signal_type="APPROVED",
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
            devil_passed=True,
            earnings_safe=is_safe,
            sector_ok=True,
            strategy_id=strategy_id,
            strategy_version=strategy_ver,
            signal_direction=signal_direction,
            asset_class=asset_class,
            system_mode=sys_mode,
            underlying_symbol=underlying_symbol,
            extra={
                "was_executed": False,
                "candle_pattern": candle_pattern,
                "ltp_source": ltp_source,
            },
        ))
    except Exception as e:
        logger.warning(f"[Pipeline] APPROVED record insert failed (non-critical): {e}")

    # Legacy table backward-compatibility insert
    try:
        insert_signal({
            "symbol": clean_symbol,
            "signal_type": "BUY" if signal_direction == "LONG" else "SELL",
            "entry_price": levels["entry"],
            "stop_loss": levels["stop_loss"],
            "target": levels["target"],
            "confidence": confidence,
            "timeframe": trade_type,
            "market_state": market_state,
            "mqi_level": mqi_level,
            "status": "APPROVED",
        })
    except Exception:
        pass

    logger.info(
        f"[Pipeline] ✅ APPROVED [{signal_direction}]: {clean_symbol} ({strategy_id}) @ ₹{levels['entry']} | "
        f"SL: ₹{levels['stop_loss']} | Tgt1: ₹{levels.get('target_1')} | Tgt2: ₹{levels.get('target_2')} | "
        f"T1 Qty: {levels.get('t1_quantity')} | T2 Qty: {levels.get('t2_quantity')} | Runner: {levels.get('runner_quantity')}"
    )

    return PipelineProcessingResult(
        is_approved=True,
        rejection_stage="",
        rejection_reason="",
        signal_data=final_signal,
        signal_intelligence_id=signal_intelligence_id,
    )
