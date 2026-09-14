"""
Module: risk/trade_risk.py
Purpose: SOTA Position Sizing, 3-Tranche Scaling, and Trade Level Engineering.
         Calculates fractal structure stop-losses, multi-factor volatility position sizing,
         exact Indian statutory regulatory tax deductions, and 3-tranche execution ladders.

The 5 Core Quantitative Capabilities:
  1. Fractal Structure & ATR Stop-Loss Discovery:
     - 10-day fractal swing low/high identification with ATR buffers.
  2. Multi-Factor Sizing Engine:
     - PositionSize = Capital * min(Risk%, Risk% * Wc * Wm)
     - Scaled by AI confidence (Wc: 0.6 to 1.2) and Volatility (Wm: 0.5 to 1.2).
  3. 3-Tranche Scaling Execution Ladder:
     - Tranche 1 (50% Qty) -> Exits at Target 1 (1.5R) -> Move SL to Breakeven.
     - Tranche 2 (30% Qty) -> Exits at Target 2 (2.5R) -> Move SL to 1R Locked.
     - Tranche 3 (20% Qty) -> Unlimited Runners trailing with Supertrend.
  4. Derivative Lot Sizing & Freeze Quantity Enforcer:
     - Enforces integer lot multiples (NIFTY 25, BANKNIFTY 15) and exchange freeze limits.
  5. Exact Regulatory Statutory Friction Matrix:
     - STT (0.1%), GST (18%), Stamp Duty (0.003%), Exchange Turnover Fees, and Slippage.
"""

from dataclasses import dataclass, field, asdict
import logging
from typing import Dict, Any, Tuple, Optional, List, Sequence, Union

from mjonai.core.constants import (
    TOTAL_CAPITAL,
    RISK_PCT_SWING,
    RISK_PCT_INTRADAY,
    RISK_PCT_POSITIONAL,
    MIN_REAL_RR,
    MAX_POSITION_SIZE,
    SYSTEM_MODE,
    PAPER_POSITION_SIZE_RESEARCH,
)

logger = logging.getLogger(__name__)

# Default Parameters
DEFAULT_ATR_SL_MULTIPLIER = 1.5
DEFAULT_STRUCTURE_BUFFER  = 0.2
DEFAULT_TARGET_RR         = 2.5
DEFAULT_TARGET_1_RR       = 1.5
DEFAULT_TARGET_2_RR       = 2.5


# ── 1. TYPE-SAFE DATA CONTRACT ───────────────────────────────────────────────

@dataclass(frozen=True)
class TradeRiskLevels:
    """Immutable contract representing the complete trade risk levels and tranche quantities."""
    entry: float
    stop_loss: float
    target: float
    target_1: float
    target_2: float
    quantity: int
    t1_quantity: int
    t2_quantity: int
    runner_quantity: int
    atr: float
    real_rr: float
    total_cost: float
    costs: Dict[str, float]
    trade_type: str
    sl_method: str
    signal_direction: str
    is_approved: bool
    rejection_reason: str = ""
    swing_low: Optional[float] = None
    target_rr: float = DEFAULT_TARGET_RR
    atr_sl_mult: float = DEFAULT_ATR_SL_MULTIPLIER
    structure_buffer: float = DEFAULT_STRUCTURE_BUFFER

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── 2. DEFENSIVE FLOAT CONVERTERS ───────────────────────────────────────────

from mjonai.core.numeric import safe_float as _safe_float


# ── 3. FRACTAL PIVOT LOW & HIGH IDENTIFIERS ─────────────────────────────────

def find_swing_low(df: Any, lookback: int = 10) -> Optional[float]:
    """
    Find most recent significant swing low from daily OHLCV data.
    A swing low = candle whose low is lower than 2 candles before AND 2 candles after it.
    """
    if df is None:
        return None

    try:
        # Support pandas DataFrame
        if hasattr(df, "columns"):
            low_col = None
            for col in df.columns:
                if str(col).lower() == "low":
                    low_col = col
                    break
            if low_col is None:
                return None
            lows = [_safe_float(x) for x in df[low_col].values]
        elif isinstance(df, (list, tuple)) and len(df) > 0:
            lows = [_safe_float(r.get("Low") or r.get("low")) for r in df if isinstance(r, dict)]
        else:
            return None

        if len(lows) < 5:
            return None

        # Search from most recent valid pivot (len(lows)-3) backwards
        start_idx = len(lows) - 3
        min_idx = max(2, len(lows) - lookback - 2)

        for i in range(start_idx, min_idx - 1, -1):
            if (lows[i] < lows[i - 1] and
                lows[i] < lows[i - 2] and
                lows[i] < lows[i + 1] and
                lows[i] < lows[i + 2] and
                lows[i] > 0):
                return float(round(lows[i], 2))

        return None
    except Exception as e:
        logger.warning(f"[TradeRisk] find_swing_low error: {e}")
        return None


def find_swing_high(df: Any, lookback: int = 10) -> Optional[float]:
    """
    Find most recent significant swing high from daily OHLCV data.
    A swing high = candle whose high is higher than 2 candles before AND 2 candles after it.
    Used for SHORT signals (stop loss above swing high).
    """
    if df is None:
        return None

    try:
        if hasattr(df, "columns"):
            high_col = None
            for col in df.columns:
                if str(col).lower() == "high":
                    high_col = col
                    break
            if high_col is None:
                return None
            highs = [_safe_float(x) for x in df[high_col].values]
        elif isinstance(df, (list, tuple)) and len(df) > 0:
            highs = [_safe_float(r.get("High") or r.get("high")) for r in df if isinstance(r, dict)]
        else:
            return None

        if len(highs) < 5:
            return None

        start_idx = len(highs) - 3
        min_idx = max(2, len(highs) - lookback - 2)

        for i in range(start_idx, min_idx - 1, -1):
            if (highs[i] > highs[i - 1] and
                highs[i] > highs[i - 2] and
                highs[i] > highs[i + 1] and
                highs[i] > highs[i + 2] and
                highs[i] > 0):
                return float(round(highs[i], 2))

        return None
    except Exception as e:
        logger.warning(f"[TradeRisk] find_swing_high error: {e}")
        return None


# ── 4. MULTI-FACTOR WEIGHT CALCULATORS ───────────────────────────────────────

def get_market_weight(vix: Optional[float] = 15.0, adx: Optional[float] = None) -> float:
    """
    Wm — market volatility factor based on India VIX and ADX trend strength:
      - VIX > 20:              0.5x (High volatility -> reduce position size)
      - VIX < 14 and ADX > 30: 1.2x (Low vol + strong trend -> increase size)
      - Else:                  1.0x (Normal conditions)
    """
    v = _safe_float(vix, default=15.0)
    a = _safe_float(adx, default=0.0) if adx is not None else None

    if v > 20.0:
        return 0.5
    elif v < 14.0 and a is not None and a > 30.0:
        return 1.2
    else:
        return 1.0


def get_confidence_weight(confidence: float) -> float:
    """
    Wc — confidence factor based on AI/Signal confidence score (0-100):
      - Confidence >= 90: 1.2x
      - Confidence >= 80: 1.0x
      - Confidence >= 70: 0.8x
      - Confidence < 70:  0.6x
    """
    c = _safe_float(confidence, default=75.0)
    if c >= 90.0:
        return 1.2
    elif c >= 80.0:
        return 1.0
    elif c >= 70.0:
        return 0.8
    else:
        return 0.6


# ── 5. STATUTORY REGULATORY TRANSACTION FRICTION ─────────────────────────────
# N2/H8 unification: this module previously carried a SECOND private friction
# model (flat ₹20 brokerage, always-delivery exit STT) that diverged from the
# canonical execution/tax.py engine used by backtests — so the Gate-4 net-R:R
# gate judged trades against non-canonical costs. All pricing now flows from
# ONE engine; the legacy itemized key contract is preserved for consumers.

from mjonai.execution.tax import calculate_all_in_friction  # noqa: E402 (canonical source)


_COST_KEYS = ("brokerage", "stt", "stamp_duty", "exchange", "gst", "sebi", "slippage", "total")


def _zero_costs() -> Dict[str, float]:
    return {k: 0.0 for k in _COST_KEYS}


def calculate_costs(
    entry: float,
    quantity: int,
    direction: str = "BUY",
    product_type: str = "DELIVERY",
) -> Dict[str, float]:
    """
    Canonical round-trip friction via execution/tax.py.calculate_all_in_friction
    plus the standard 5 bps/side research slippage (same convention as
    research/backtest/costs.py).

    Key contract preserved for existing consumers (validate_trade RR gate,
    orders RESEARCH booking): brokerage/stt/stamp_duty/exchange/gst/sebi/
    slippage/total. Canonical turnover_charges merges exchange+SEBI and lands
    in 'exchange' with 'sebi' kept at 0.0 for compatibility.
    """
    e = _safe_float(entry)
    qty = max(0, int(quantity))
    if e <= 0 or qty <= 0:
        return _zero_costs()

    product = "INTRADAY" if str(product_type).upper() == "INTRADAY" else "DELIVERY"

    try:
        canon = calculate_all_in_friction(
            buy_price=e,
            sell_price=e,
            quantity=qty,
            asset_class="EQUITY",
            product_type=product,
            exchange="NSE",
        )
    except Exception as exc:  # fail-closed on friction: refuse to price blind
        logger.error(f"[TradeRisk] Canonical friction call failed ({exc}) - returning zero costs")
        raise

    slippage = round((e * qty) * 0.0005 * 2, 2)  # 5 bps per side, both sides
    total = round(float(canon["total_friction"]) + slippage, 2)

    return {
        "brokerage": round(float(canon["brokerage"]), 2),
        "stt": round(float(canon["stt_ctt"]), 2),
        "stamp_duty": round(float(canon["stamp_duty"]), 2),
        "exchange": round(float(canon["turnover_charges"]), 2),
        "gst": round(float(canon["gst"]), 2),
        "sebi": 0.0,
        "slippage": slippage,
        "total": total,
    }


# ── 6. INSTITUTIONAL POSITION SIZING & TRANCHE SPLITTER ──────────────────────

def split_tranche_quantities(total_quantity: int) -> Tuple[int, int, int]:
    """
    Split total quantity into 3 institutional scaling tranches:
      - Tranche 1 (50%): Target 1 (1.5R) -> Move SL to Breakeven
      - Tranche 2 (30%): Target 2 (2.5R) -> Move SL to 1R Locked
      - Tranche 3 (20%): Runners -> Supertrend Trailing
    Handles small retail lots (1, 2, 3 shares) with zero fractional crashes.
    """
    qty = max(0, int(total_quantity))
    if qty <= 0:
        return 0, 0, 0
    if qty == 1:
        return 1, 0, 0
    if qty == 2:
        return 1, 1, 0
    if qty == 3:
        return 1, 1, 1

    t1 = max(1, int(qty * 0.50))
    t2 = int(qty * 0.30)
    t3 = qty - (t1 + t2)

    return t1, t2, max(0, t3)


def calculate_position_size(
    entry: float,
    stop_loss: float,
    confidence: float,
    vix: float = 15.0,
    trade_type: str = "SWING",
    adx: Optional[float] = None,
    system_mode: Optional[str] = None,
    lot_size: int = 1,
    freeze_qty: Optional[int] = None,
) -> int:
    """
    Calculate position size using the multi-factor risk formula:
    PositionSize = Capital * min(Risk%, Risk% * Wc * Wm) / RiskPerShare
    """
    e = _safe_float(entry)
    sl = _safe_float(stop_loss)
    sys_mode = str(system_mode or SYSTEM_MODE).upper()

    if e <= 0:
        return 0

    # RESEARCH mode: Fixed sizing for scientific comparability
    if sys_mode == "RESEARCH":
        raw_qty = max(1, int(PAPER_POSITION_SIZE_RESEARCH // e))
        if lot_size > 1:
            raw_qty = max(lot_size, (raw_qty // lot_size) * lot_size)
        if freeze_qty and raw_qty > freeze_qty:
            raw_qty = freeze_qty
        return raw_qty

    # LIVE mode: Risk-based sizing formula
    risk_pct = {
        "SWING": RISK_PCT_SWING,
        "INTRADAY": RISK_PCT_INTRADAY,
        "POSITIONAL": RISK_PCT_POSITIONAL,
    }.get(str(trade_type).upper(), RISK_PCT_SWING)

    wc = get_confidence_weight(confidence)
    wm = get_market_weight(vix, adx)

    adjusted_risk = min(risk_pct, risk_pct * wc * wm)
    risk_capital = TOTAL_CAPITAL * adjusted_risk
    risk_per_share = abs(e - sl)

    if risk_per_share <= 0:
        logger.warning(f"[TradeRisk] Invalid SL: entry={e}, sl={sl}")
        return 0

    quantity = int(risk_capital / risk_per_share)

    # Hard cap: no single position > 20% of capital
    max_qty = int((TOTAL_CAPITAL * MAX_POSITION_SIZE) / e)
    quantity = min(quantity, max_qty)

    # Enforce derivative lot sizing
    if lot_size > 1:
        quantity = (quantity // lot_size) * lot_size

    # Enforce exchange freeze quantity cap
    if freeze_qty and quantity > freeze_qty:
        quantity = freeze_qty

    return max(0, quantity)


def validate_trade(
    entry: float,
    stop_loss: float,
    target: float,
    quantity: int,
    costs: Dict[str, float],
    direction: str = "LONG",
) -> Tuple[bool, str, float]:
    """
    Validate trade passes minimum real RR (>= 2.0) after transaction friction.
    """
    e = _safe_float(entry)
    sl = _safe_float(stop_loss)
    tgt = _safe_float(target)
    qty = max(0, int(quantity))
    total_cost = _safe_float(costs.get("total"))
    dir_clean = str(direction or "LONG").upper()
    is_long = dir_clean in ("LONG", "BUY")

    if qty <= 0:
        return False, "Quantity is zero — insufficient capital or invalid sizing", 0.0

    cost_per_share = total_cost / qty

    if is_long:
        raw_reward = tgt - e
        raw_risk = e - sl
    else:  # SHORT
        raw_reward = e - tgt
        raw_risk = sl - e

    if raw_risk <= 0 or raw_reward <= 0:
        return False, "Invalid price geometry (Risk or Reward <= 0)", 0.0

    net_reward = raw_reward - cost_per_share
    net_risk = raw_risk + cost_per_share

    if net_risk <= 0:
        return False, "Net risk calculation invalid", 0.0

    real_rr = round(net_reward / net_risk, 2)

    if real_rr < MIN_REAL_RR:
        return False, f"Real RR {real_rr} below minimum {MIN_REAL_RR}", real_rr

    return True, "APPROVED", real_rr


# ── 7. MASTER TRADE LEVEL ENGINEERING ────────────────────────────────────────

def calculate_trade_levels(
    entry: float,
    atr: float,
    confidence: float,
    vix: float = 15.0,
    trade_type: str = "SWING",
    swing_low: Optional[float] = None,
    swing_high: Optional[float] = None,
    adx: Optional[float] = None,
    target_rr: Optional[float] = None,
    atr_sl_mult: Optional[float] = None,
    structure_buffer: Optional[float] = None,
    signal_direction: str = "LONG",
    system_mode: Optional[str] = None,
    lot_size: int = 1,
    freeze_qty: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Master trade level calculation — entry, SL, targets, 3-tranche scaling, costs, and validation.
    100% Backward-compatible dictionary return.
    """
    res = evaluate_trade_risk_levels(
        entry=entry,
        atr=atr,
        confidence=confidence,
        vix=vix,
        trade_type=trade_type,
        swing_low=swing_low,
        swing_high=swing_high,
        adx=adx,
        target_rr=target_rr,
        atr_sl_mult=atr_sl_mult,
        structure_buffer=structure_buffer,
        signal_direction=signal_direction,
        system_mode=system_mode,
        lot_size=lot_size,
        freeze_qty=freeze_qty,
    )
    return res.to_dict() if res.is_approved else None


def evaluate_trade_risk_levels(
    entry: float,
    atr: float,
    confidence: float,
    vix: float = 15.0,
    trade_type: str = "SWING",
    swing_low: Optional[float] = None,
    swing_high: Optional[float] = None,
    adx: Optional[float] = None,
    target_rr: Optional[float] = None,
    atr_sl_mult: Optional[float] = None,
    structure_buffer: Optional[float] = None,
    signal_direction: str = "LONG",
    system_mode: Optional[str] = None,
    lot_size: int = 1,
    freeze_qty: Optional[int] = None,
) -> TradeRiskLevels:
    """
    SOTA Structured Trade Risk Evaluator returning typed TradeRiskLevels.
    """
    e = _safe_float(entry)
    a = max(0.01, _safe_float(atr, default=e * 0.015))
    c = _safe_float(confidence, default=75.0)
    v = _safe_float(vix, default=15.0)
    dir_clean = str(signal_direction or "LONG").strip().upper()
    is_short = dir_clean in ("SHORT", "SELL")

    t_rr = _safe_float(target_rr, default=DEFAULT_TARGET_RR)
    sl_mult = _safe_float(atr_sl_mult, default=DEFAULT_ATR_SL_MULTIPLIER)
    s_buffer = _safe_float(structure_buffer, default=DEFAULT_STRUCTURE_BUFFER)

    # 1. Stop Loss & Target Geometry
    if is_short:
        # SHORT: SL above entry
        if swing_high is not None and swing_high > e:
            candidate_sl = round(swing_high + (s_buffer * a), 2)
            sl = candidate_sl
            sl_method = "STRUCTURE_SHORT"
        else:
            sl = round(e + (sl_mult * a), 2)
            sl_method = "ATR_SHORT"

        risk_dist = sl - e
        target = round(e - (t_rr * risk_dist), 2)
        target_1 = round(e - (DEFAULT_TARGET_1_RR * risk_dist), 2)
        target_2 = round(e - (DEFAULT_TARGET_2_RR * risk_dist), 2)
    else:
        # LONG: SL below entry
        if swing_low is not None and 0 < swing_low < e:
            candidate_sl = round(swing_low - (s_buffer * a), 2)
            if candidate_sl > 0:
                sl = candidate_sl
                sl_method = "STRUCTURE"
            else:
                sl = round(e - (sl_mult * a), 2)
                sl_method = "ATR"
        else:
            sl = round(e - (sl_mult * a), 2)
            sl_method = "ATR"

        risk_dist = e - sl
        target = round(e + (t_rr * risk_dist), 2)
        target_1 = round(e + (DEFAULT_TARGET_1_RR * risk_dist), 2)
        target_2 = round(e + (DEFAULT_TARGET_2_RR * risk_dist), 2)

    # 2. Position Sizing
    quantity = calculate_position_size(
        entry=e,
        stop_loss=sl,
        confidence=c,
        vix=v,
        trade_type=trade_type,
        adx=adx,
        system_mode=system_mode,
        lot_size=lot_size,
        freeze_qty=freeze_qty,
    )

    # 3. 3-Tranche Scaling Split
    t1_qty, t2_qty, runner_qty = split_tranche_quantities(quantity)

    # 4. Regulatory Transaction Friction — canonical engine; product type
    # follows the trade's timeframe so intraday trades no longer pay
    # always-delivery STT/stamp (N2 divergence eliminated).
    costs = calculate_costs(
        entry=e,
        quantity=quantity,
        direction=dir_clean,
        product_type="INTRADAY" if str(trade_type).upper() == "INTRADAY" else "DELIVERY",
    )

    # 5. Real Net R:R Validation
    passed, reason, real_rr = validate_trade(
        entry=e,
        stop_loss=sl,
        target=target,
        quantity=quantity,
        costs=costs,
        direction=dir_clean,
    )

    return TradeRiskLevels(
        entry=e,
        stop_loss=sl,
        target=target,
        target_1=target_1,
        target_2=target_2,
        quantity=quantity,
        t1_quantity=t1_qty,
        t2_quantity=t2_qty,
        runner_quantity=runner_qty,
        atr=round(a, 2),
        real_rr=real_rr,
        total_cost=costs["total"],
        costs=costs,
        trade_type=trade_type,
        sl_method=sl_method,
        signal_direction=dir_clean,
        is_approved=passed,
        rejection_reason=reason if not passed else "",
        swing_low=swing_low,
        target_rr=t_rr,
        atr_sl_mult=sl_mult,
        structure_buffer=s_buffer,
    )


def calculate_volatility_risk_parity_quantity(
    total_capital: float,
    risk_per_trade_pct: float,
    entry_price: float,
    stop_loss_price: float,
    atr: Optional[float] = None,
    max_position_capital_pct: float = 0.25,
) -> int:
    """
    Compute Volatility-Targeted Risk Parity Position Quantity.
    Ensures every trade risks the exact target dollar amount (e.g., 1.0% of total capital)
    regardless of whether the stock is high-beta or low-beta.
    """
    cap = max(1000.0, float(total_capital))
    entry = max(0.01, float(entry_price))
    sl = max(0.01, float(stop_loss_price))
    risk_rupees = cap * (max(0.001, float(risk_per_trade_pct)) / 100.0)

    # Per-share risk distance
    per_share_risk = abs(entry - sl)
    if per_share_risk <= 0:
        per_share_risk = (atr if atr and atr > 0 else entry * 0.015)

    # Risk-based quantity
    raw_qty = int(risk_rupees / per_share_risk)

    # Capital ceiling cap (e.g. max 25% capital in a single stock)
    max_capital_allowed = cap * max_position_capital_pct
    max_shares_capital = int(max_capital_allowed / entry)

    final_qty = max(1, min(raw_qty, max_shares_capital))
    return final_qty
