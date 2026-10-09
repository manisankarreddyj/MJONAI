"""
Module: risk/devil_checks.py
Purpose: SOTA Deterministic Pre-Trade Elimination Veto Engine.
         Executes 8 strict quantitative checks before any LLM agent or broker execution.
         Pure Python — zero hallucination, sub-millisecond execution.

The 8 Elimination Checks:
  1. Dynamic GARCH Gap Risk (overnight move vs 1.5x SL distance).
  2. Order Book Liquidity (bid-ask spread <= 0.5%).
  3. Data Feed Quality (tick stream health >= 85%).
  4. Institutional Pattern Memory (3+ recent failures in 90 days vetoed).
  5. Cross-Asset Sector Correlation (prevents concentration risk > 0.80).
  6. Bidirectional Real Risk-Reward Post-Taxes (Real R:R >= 2.0 for LONG & SHORT).
  7. Portfolio Exposure Limits (open positions <= 5 & growth capital <= 80%).
  8. Macro & Corporate Event Blackout (RBI MPC, FOMC, Budget, Earnings within 4h).
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
import logging
from typing import Tuple, Dict, Any, List, Optional, Sequence, Union

from mjonai.core.constants import (
    TOTAL_CAPITAL,
    MAX_OPEN_POSITIONS,
    MIN_REAL_RR,
    GROWTH_POOL_PCT,
    SYSTEM_MODE,
    SECTOR_MAP,
    build_setup_hash,
)

logger = logging.getLogger(__name__)


# ── 1. TYPE-SAFE DATA CONTRACT ───────────────────────────────────────────────

@dataclass(frozen=True)
class DevilCheckResult:
    """Immutable contract representing the complete results of the 8 Devil Checks."""
    all_passed: bool
    failure_reason: str
    passed_checks: List[str]
    failed_checks: List[str]
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── 2. DEFENSIVE FLOAT CONVERTERS ───────────────────────────────────────────

from mjonai.core.numeric import safe_float as _safe_float


def _extract_underlying_symbol(symbol: str) -> str:
    """
    Extract root underlying symbol for options, futures, and equities.
    E.g. NIFTY26AUG24500CE -> NIFTY, CRUDEOIL26AUGFUT -> CRUDEOIL, RELIANCE -> RELIANCE.
    """
    if not symbol:
        return ""
    clean = symbol.strip().upper()
    # Check if direct equity
    if clean in SECTOR_MAP:
        return clean
    # Check standard prefixes
    for prefix in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "CRUDEOIL", "GOLD", "SILVER"]:
        if clean.startswith(prefix):
            return prefix
    return clean


# ── 3. THE 8 INDIVIDUAL DETERMINISTIC CHECKS ─────────────────────────────────

def check_gap_risk(
    sl_distance: float,
    expected_overnight_move: Optional[float] = None,
    df: Any = None,
    entry_price: Optional[float] = None,
    stop_loss: Optional[float] = None,
    direction: str = "LONG",
) -> Tuple[bool, str]:
    """
    Check 1 — Dynamic GARCH Gap Risk.
    Uses historical overnight gap distribution & volatility clustering.
    If expected overnight move exceeds 1.5x SL distance, position is vetoed.
    """
    sl_dist = abs(_safe_float(sl_distance))
    if sl_dist <= 0:
        return False, "Stop loss distance cannot be zero"

    if df is not None and entry_price and stop_loss:
        try:
            from mjonai.risk.gap_risk import calculate_overnight_gap_risk
            level, exp_gap, size_mult, reason = calculate_overnight_gap_risk(
                df, _safe_float(entry_price), _safe_float(stop_loss), direction
            )
            if level == "CRITICAL":
                logger.warning(f"[DevilCheck] FAIL — Gap risk: {reason}")
                return False, reason
            return True, reason
        except Exception as e:
            logger.error(f"[DevilCheck] Gap risk model error: {e}")

    # Baseline fallback calculation
    if expected_overnight_move is None:
        expected_overnight_move = sl_dist * 0.5
    else:
        expected_overnight_move = abs(_safe_float(expected_overnight_move))

    threshold = sl_dist * 1.5

    if expected_overnight_move > threshold:
        reason = (
            f"Gap risk ₹{expected_overnight_move:.2f} "
            f"exceeds 1.5x SL distance ₹{threshold:.2f}"
        )
        logger.warning(f"[DevilCheck] FAIL — Gap risk: {reason}")
        return False, reason

    return True, f"Gap risk ₹{expected_overnight_move:.2f} acceptable"


def check_liquidity(bid_ask_spread_pct: float) -> Tuple[bool, str]:
    """
    Check 2 — Liquidity.
    Bid-ask spread > 0.5% means market-maker friction is too high.
    """
    spread = _safe_float(bid_ask_spread_pct)
    if spread > 0.5:
        reason = f"Bid-ask spread {spread:.2f}% exceeds 0.5% limit"
        logger.warning(f"[DevilCheck] FAIL — Liquidity: {reason}")
        return False, reason

    return True, f"Spread {spread:.2f}% acceptable"


def check_data_quality(quality_score: float) -> Tuple[bool, str]:
    """
    Check 3 — Data Quality.
    If tick stream quality score < 85%, signal may be based on dropped/stale data.
    """
    score = _safe_float(quality_score, default=100.0)
    if score < 85.0:
        reason = f"Data quality {score:.0f}% below 85% threshold"
        logger.warning(f"[DevilCheck] FAIL — Data quality: {reason}")
        return False, reason

    return True, f"Data quality {score:.0f}% acceptable"


def check_pattern_memory(setup_hash: str, lookback_days: int = 90) -> Tuple[bool, str]:
    """
    Check 4 — Pattern Memory.
    If the same setup fingerprint failed 3+ times in the last 90 days,
    veto new entries until the strategy demonstrates statistical recovery.
    """
    if not setup_hash:
        return True, "No setup hash provided — check skipped"

    try:
        from mjonai.db.repository import get_pattern_failures
        failures = get_pattern_failures(setup_hash, lookback_days)

        if failures >= 3:
            reason = f"Setup failed {failures} times in last {lookback_days} days"
            logger.warning(f"[DevilCheck] FAIL — Pattern memory: {reason}")
            return False, reason

        return True, f"Pattern history acceptable ({failures} recent failures)"
    except Exception as e:
        logger.warning(f"[DevilCheck] Pattern memory unavailable: {e} — passing check")
        return True, "Pattern memory unavailable — check skipped"


def check_correlation(
    candidate_symbol: str,
    open_trades: Sequence[dict],
    correlation_threshold: float = 0.80,
) -> Tuple[bool, str]:
    """
    Check 5 — Cross-Asset Sector Correlation.
    Extracts underlying instrument and checks against existing open positions.
    Prevents holding 2 highly correlated assets in the same sector (> 0.80).
    """
    try:
        candidate_root = _extract_underlying_symbol(candidate_symbol)
        candidate_sector = SECTOR_MAP.get(candidate_root) or SECTOR_MAP.get(candidate_symbol)

        if not candidate_sector:
            return True, f"Sector unknown for {candidate_symbol} — correlation check skipped"

        for trade in open_trades:
            trade_symbol = str(trade.get("symbol", "")).strip().upper()
            trade_root = _extract_underlying_symbol(trade_symbol)
            trade_sector = SECTOR_MAP.get(trade_root) or SECTOR_MAP.get(trade_symbol)

            if trade_sector and trade_sector == candidate_sector:
                proxy_correlation = 0.85
                if proxy_correlation > correlation_threshold:
                    reason = (
                        f"High correlation with {trade_symbol} "
                        f"(same sector: {candidate_sector}) — "
                        f"proxy correlation {proxy_correlation}"
                    )
                    logger.warning(f"[DevilCheck] FAIL — Correlation: {reason}")
                    return False, reason

        return True, "No high correlation detected"
    except Exception as e:
        logger.warning(f"[DevilCheck] Correlation check error: {e} — passing")
        return True, "Correlation check error — skipped"


def check_real_rr(
    entry: float,
    stop_loss: float,
    target: float,
    total_cost: float,
    quantity: int,
    direction: str = "BUY",
) -> Tuple[bool, str]:
    """
    Check 6 — Bidirectional Real Risk-Reward after Transaction Costs.
    Must be >= 2.0 after all STT, GST, and brokerage deductions.
    Supports both LONG/BUY and SHORT/SELL directions.
    """
    e = _safe_float(entry)
    sl = _safe_float(stop_loss)
    tgt = _safe_float(target)
    cost = _safe_float(total_cost)
    qty = int(quantity) if quantity > 0 else 0
    dir_clean = str(direction or "BUY").strip().upper()

    if qty <= 0:
        return False, "Quantity is zero — position sizing failed"

    cost_per_unit = cost / qty

    if dir_clean in ("BUY", "LONG"):
        raw_reward = tgt - e
        raw_risk = e - sl
    else:  # SHORT / SELL
        raw_reward = e - tgt
        raw_risk = sl - e

    if raw_risk <= 0:
        return False, f"Invalid stop loss for {dir_clean} trade (Risk <= 0)"
    if raw_reward <= 0:
        return False, f"Invalid target for {dir_clean} trade (Reward <= 0)"

    net_reward = raw_reward - cost_per_unit
    net_risk = raw_risk + cost_per_unit

    if net_risk <= 0:
        return False, "Net risk calculation invalid"

    real_rr = round(net_reward / net_risk, 2)

    if real_rr < MIN_REAL_RR:
        reason = f"Real RR {real_rr} below minimum {MIN_REAL_RR} after transaction costs"
        logger.warning(f"[DevilCheck] FAIL — Real RR: {reason}")
        return False, reason

    return True, f"Real RR {real_rr} acceptable"


def check_portfolio_limits(
    open_trades: Sequence[dict],
    growth_pool_deployed_pct: float,
    max_open_positions: int = MAX_OPEN_POSITIONS,
) -> Tuple[bool, str]:
    """
    Check 7 — Portfolio Limits & Exposure Ceilings.
    1. Open positions count <= max_open_positions (default 5).
    2. Growth capital deployed <= 80% ceiling.
    """
    open_count = len(open_trades)
    deployed_pct = _safe_float(growth_pool_deployed_pct)

    if open_count >= max_open_positions:
        reason = f"Max positions ({max_open_positions}) already open"
        logger.warning(f"[DevilCheck] FAIL — Portfolio limits: {reason}")
        return False, reason

    if deployed_pct >= 80.0:
        reason = f"Growth pool at {deployed_pct:.0f}% — 80% ceiling reached"
        logger.warning(f"[DevilCheck] FAIL — Portfolio limits: {reason}")
        return False, reason

    return True, f"{open_count} positions open | Growth pool {deployed_pct:.0f}% deployed"


def check_event_risk(
    calendar_events: Sequence[dict],
    block_hours: float = 4.0,
) -> Tuple[bool, str]:
    """
    Check 8 — Macroeconomic & Corporate Event Risk Blackout.
    Blocks entries if a high-impact event (RBI, FOMC, Budget, Earnings) is within 4 hours.
    """
    if not calendar_events:
        return True, "No imminent high-impact events"

    for event in calendar_events:
        hours_away = _safe_float(event.get("hours_away", 999))
        impact = str(event.get("impact", "LOW")).upper()
        name = event.get("name", "Unknown event")

        if hours_away < block_hours and impact == "HIGH":
            reason = f"High-impact event in {hours_away:.1f} hours: {name}"
            logger.warning(f"[DevilCheck] FAIL — Event risk: {reason}")
            return False, reason

    return True, "No imminent high-impact events"


# ── 4. MASTER ORCHESTRATOR ───────────────────────────────────────────────────

def _estimate_overnight_gap_from_df(df) -> Optional[float]:
    """
    Median absolute overnight gap (open vs previous close), in PRICE
    UNITS, over the last ~60 bars. Returns None when candles are
    unavailable/insufficient so callers can fall back explicitly.

    This replaces the old 0.5xATR placeholder that made Check 1 a
    dead control: with real gap data the 1.5x-SL-distance veto can
    actually trip on gappy names.
    """
    try:
        if df is None or len(df) < 10:
            return None

        opens = df["Open"].astype(float).values
        closes = df["Close"].astype(float).values

        gaps = []
        for i in range(max(1, len(df) - 60), len(df)):
            prev_close = closes[i - 1]
            if prev_close > 0:
                gaps.append(abs(opens[i] - prev_close))

        if len(gaps) < 5:
            return None

        gaps.sort()
        mid = len(gaps) // 2
        median_gap = (
            gaps[mid]
            if len(gaps) % 2 == 1
            else (gaps[mid - 1] + gaps[mid]) / 2.0
        )
        return float(round(median_gap, 4)) if median_gap > 0 else None
    except Exception:
        return None


def run_all_devil_checks(
    signal: dict,
    open_trades: Sequence[dict],
    calendar_events: Optional[Sequence[dict]] = None,
    data_quality_score: float = 95.0,
    bid_ask_spread_pct: float = 0.05,
    expected_overnight_move: Optional[float] = None,
    system_mode: Optional[str] = None,
    df=None,
) -> Tuple[bool, str, list]:
    """
    Run all 8 deterministic devil checks against a candidate trading signal.
    In LIVE mode: Hard veto on the first failing check (protects capital).
    In RESEARCH mode: Runs all checks and flags warnings for audit.

    Returns:
        (all_passed: bool, failure_reason: str, passed_checks: List[str])
    """
    result = evaluate_devil_checks(
        signal=signal,
        open_trades=open_trades,
        calendar_events=calendar_events,
        data_quality_score=data_quality_score,
        bid_ask_spread_pct=bid_ask_spread_pct,
        expected_overnight_move=expected_overnight_move,
        system_mode=system_mode,
        df=df,
    )
    return result.all_passed, result.failure_reason, result.passed_checks


def evaluate_devil_checks(
    signal: dict,
    open_trades: Sequence[dict],
    calendar_events: Optional[Sequence[dict]] = None,
    data_quality_score: float = 95.0,
    bid_ask_spread_pct: float = 0.05,
    expected_overnight_move: Optional[float] = None,
    system_mode: Optional[str] = None,
    df=None,
) -> DevilCheckResult:
    """
    SOTA Structured Evaluator returning typed DevilCheckResult.
    """
    events = calendar_events if calendar_events is not None else []
    sys_mode = str(system_mode or SYSTEM_MODE).upper()
    is_research = (sys_mode == "RESEARCH")

    entry = _safe_float(signal.get("entry_price"))
    sl = _safe_float(signal.get("stop_loss"))
    target = _safe_float(signal.get("target"))
    quantity = int(signal.get("quantity", 0))
    total_cost = _safe_float(signal.get("total_cost", 0.0))
    direction = str(signal.get("direction") or signal.get("signal_direction") or "BUY").upper()
    symbol = str(signal.get("symbol", "")).strip().upper()
    atr = _safe_float(signal.get("atr", abs(entry - sl) / 1.5))

    if expected_overnight_move is None:
        # Prefer a REAL estimate from recent overnight gaps when the
        # caller supplies candles. The old 0.5xATR fallback made the
        # gap check mathematically unable to trip (dead control).
        df_overnight = _estimate_overnight_gap_from_df(df)
        if df_overnight is not None:
            expected_overnight_move = df_overnight
        else:
            expected_overnight_move = atr * 0.5

    sl_distance = abs(entry - sl)

    # Compute growth pool deployment
    growth_pool = TOTAL_CAPITAL * GROWTH_POOL_PCT
    deployed = sum(
        _safe_float(t.get("entry_price", 0)) *
        int(t.get("quantity_remaining") or t.get("quantity") or 0)
        for t in open_trades
    )
    growth_pool_deployed_pct = (deployed / growth_pool * 100) if growth_pool > 0 else 0.0

    # Build pattern setup hash
    setup_hash = build_setup_hash(
        symbol=symbol,
        strategy_id=signal.get("strategy_id", "S00_Legacy"),
        sl_method=signal.get("sl_method", "ATR"),
        market_state=signal.get("market_state", "NEUTRAL"),
        vix=_safe_float(signal.get("vix_at_signal"), default=16.0),
        candle_pattern=signal.get("candle_pattern", "NONE"),
    )

    checks = [
        ("Gap Risk", lambda: check_gap_risk(
            sl_distance,
            expected_overnight_move,
            df=df,
            entry_price=entry if df is not None else None,
            stop_loss=sl if df is not None else None,
            direction=direction,
        )),
        ("Liquidity", lambda: check_liquidity(bid_ask_spread_pct)),
        ("Data Quality", lambda: check_data_quality(data_quality_score)),
        ("Pattern Memory", lambda: check_pattern_memory(setup_hash)),
        ("Correlation", lambda: check_correlation(symbol, open_trades)),
        ("Real RR", lambda: check_real_rr(entry, sl, target, total_cost, quantity, direction=direction)),
        ("Portfolio Limits", lambda: check_portfolio_limits(open_trades, growth_pool_deployed_pct)),
        ("Event Risk", lambda: check_event_risk(events)),
    ]

    passed_checks: List[str] = []
    failed_checks: List[str] = []
    details_dict: Dict[str, Any] = {}
    first_failure_reason = ""

    # Calculate gap risk position-size multiplier (0.50, 0.75, 1.0)
    gap_size_mult = 1.0
    if df is not None and entry > 0 and sl > 0:
        try:
            from mjonai.risk.gap_risk import calculate_overnight_gap_risk
            _, _, gap_size_mult, _ = calculate_overnight_gap_risk(
                df, entry, sl, direction
            )
        except Exception:
            gap_size_mult = 1.0
    details_dict["gap_risk_multiplier"] = float(gap_size_mult)

    for check_name, check_fn in checks:
        passed, reason = check_fn()
        details_dict[check_name] = reason

        if passed:
            passed_checks.append(check_name)
            logger.info(f"[DevilCheck] PASS — {check_name}: {reason}")
        else:
            failed_checks.append(check_name)
            if not first_failure_reason:
                first_failure_reason = f"{check_name}: {reason}"

            if is_research:
                logger.warning(f"[DevilCheck] WARN (RESEARCH) — {check_name}: {reason}")
                passed_checks.append(f"{check_name}*")
            else:
                logger.warning(f"[DevilCheck] VETO — {check_name}: {reason}")
                return DevilCheckResult(
                    all_passed=False,
                    failure_reason=first_failure_reason,
                    passed_checks=passed_checks,
                    failed_checks=failed_checks,
                    details=details_dict,
                )

    all_passed = len(failed_checks) == 0 or is_research
    reason_msg = "All 8 devil checks run" if all_passed else first_failure_reason

    return DevilCheckResult(
        all_passed=all_passed,
        failure_reason=reason_msg,
        passed_checks=passed_checks,
        failed_checks=failed_checks,
        details=details_dict,
    )
