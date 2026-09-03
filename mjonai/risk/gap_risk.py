"""
Module: risk/gap_risk.py
Purpose: SOTA Directional GARCH Volatility & Overnight Gap Distribution Engine.
         Evaluates whether overnight price jumps could blow past stop-loss levels,
         enforcing Directional Adverse Sizing, Weekend Exposure Scaling, and
         Intraday Auto-Bypass.

The 5 Core Quantitative Capabilities:
  1. Directional Adverse Gap Analysis:
     - For LONG positions: Measures downside jump risk (Open < Prev Close).
     - For SHORT positions: Measures upside jump risk (Open > Prev Close).
  2. GARCH Volatility Clustering Proxy:
     - Compares 5-day realized volatility against 30-day baseline, scaled with India VIX.
  3. Weekend & Multi-Day Holiday Multiplier (sqrt(3) ~= 1.732x):
     - Automatically expands gap expectations on Friday evaluations to cover 65.75h exposure.
  4. Intraday (MIS) Auto-Bypass:
     - Positions exiting before 03:15 PM incur zero overnight gap penalties.
  5. Typed Immutable Result Contract (GapRiskResult).
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import logging
import math
from typing import Tuple, Dict, Any, List, Optional, Sequence, Union

from mjonai.core.time_utils import now_ist

logger = logging.getLogger(__name__)


# ── 1. TYPE-SAFE DATA CONTRACT ───────────────────────────────────────────────

@dataclass(frozen=True)
class GapRiskResult:
    """Immutable contract representing the complete results of the Overnight Gap Risk Model."""
    risk_level: str               # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    expected_gap_rs: float        # Estimated 95th percentile overnight adverse jump in rupees
    expected_gap_pct: float       # Estimated percentage gap move
    size_multiplier: float        # Position size scaler (1.0 = Full, 0.75, 0.50, 0.0 = Veto)
    is_vetoed: bool               # True if trade is rejected due to excessive gap risk
    is_weekend_scaled: bool       # True if Friday / holiday weekend scaling was applied
    is_intraday: bool             # True if trade squares off before market close
    reason: str                   # Plain-text explanation of the risk evaluation

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── 2. DEFENSIVE DATA EXTRACTORS ─────────────────────────────────────────────

def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert any value to float, converting NaN/Inf to default."""
    try:
        if val is None or isinstance(val, (list, dict, tuple)):
            return default
        f = float(val)
        return default if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return default


def _extract_ohlc_series(df: Any) -> Tuple[List[float], List[float]]:
    """
    Safely extract Close and Open price lists from Pandas DataFrame, Polars,
    numpy arrays, or lists of dictionaries.
    """
    if df is None:
        return [], []

    opens: List[float] = []
    closes: List[float] = []

    try:
        # Pandas or Polars DataFrame
        if hasattr(df, "columns"):
            # Case-insensitive column resolution
            cols = {str(c).lower(): c for c in df.columns}
            c_col = cols.get("close")
            o_col = cols.get("open")
            if c_col is not None and o_col is not None:
                closes = [_safe_float(x) for x in df[c_col].values if _safe_float(x) > 0]
                opens = [_safe_float(x) for x in df[o_col].values if _safe_float(x) > 0]
                return opens, closes

        # List of dictionaries
        elif isinstance(df, (list, tuple)) and len(df) > 0 and isinstance(df[0], dict):
            for row in df:
                c_val = _safe_float(row.get("Close") or row.get("close"))
                o_val = _safe_float(row.get("Open") or row.get("open"))
                if c_val > 0 and o_val > 0:
                    closes.append(c_val)
                    opens.append(o_val)
            return opens, closes
    except Exception as e:
        logger.warning(f"[GapRisk] Could not extract OHLC series: {e}")

    return [], []


# ── 3. CORE PUBLIC EVALUATION API ────────────────────────────────────────────

def calculate_overnight_gap_risk(
    df: Any,
    entry_price: float,
    stop_loss: float,
    direction: str = "LONG",
    is_intraday: bool = False,
    current_vix: Optional[float] = None,
    eval_time: Optional[datetime] = None,
) -> Tuple[str, float, float, str]:
    """
    Calculate dynamic overnight gap risk using historical gap distribution & volatility clustering.
    100% Backward-compatible tuple return: (risk_level, expected_gap_rs, size_multiplier, reason).
    """
    res = evaluate_gap_risk(
        df=df,
        entry_price=entry_price,
        stop_loss=stop_loss,
        direction=direction,
        is_intraday=is_intraday,
        current_vix=current_vix,
        eval_time=eval_time,
    )
    return res.risk_level, res.expected_gap_rs, res.size_multiplier, res.reason


def evaluate_gap_risk(
    df: Any,
    entry_price: float,
    stop_loss: float,
    direction: str = "LONG",
    is_intraday: bool = False,
    current_vix: Optional[float] = None,
    eval_time: Optional[datetime] = None,
) -> GapRiskResult:
    """
    SOTA Structured Gap Risk Evaluator returning typed GapRiskResult.
    """
    e = _safe_float(entry_price)
    sl = _safe_float(stop_loss)
    sl_distance = abs(e - sl)
    dir_clean = str(direction or "LONG").strip().upper()
    is_long = dir_clean in ("LONG", "BUY")
    now = eval_time or now_ist()

    # 1. Intraday Auto-Bypass (MIS day trades never hold overnight)
    if is_intraday:
        return GapRiskResult(
            risk_level="LOW",
            expected_gap_rs=0.0,
            expected_gap_pct=0.0,
            size_multiplier=1.0,
            is_vetoed=False,
            is_weekend_scaled=False,
            is_intraday=True,
            reason="Intraday position — squares off at 03:15 PM (zero overnight gap risk)",
        )

    if sl_distance <= 0 or e <= 0:
        return GapRiskResult(
            risk_level="CRITICAL",
            expected_gap_rs=0.0,
            expected_gap_pct=0.0,
            size_multiplier=0.0,
            is_vetoed=True,
            is_weekend_scaled=False,
            is_intraday=False,
            reason="Invalid entry or stop loss price (SL distance <= 0)",
        )

    opens, closes = _extract_ohlc_series(df)

    # 2. Insufficient History Fallback — FAIL TIGHT, not open.
    # The old path returned LOW/full-size, giving the thinnest-history
    # stocks zero gap scrutiny. Unknown risk is treated as elevated.
    if len(closes) < 30 or len(opens) < 30:
        fallback_gap_rs = round(sl_distance * 0.5, 2)
        fallback_gap_pct = (fallback_gap_rs / e) if e > 0 else 0.005
        return GapRiskResult(
            risk_level="MEDIUM",
            expected_gap_rs=fallback_gap_rs,
            expected_gap_pct=round(fallback_gap_pct, 4),
            size_multiplier=0.5,
            is_vetoed=False,
            is_weekend_scaled=False,
            is_intraday=False,
            reason="Insufficient history (<30 bars) — gap risk treated as MEDIUM, size halved",
        )

    try:
        # 3. Directional Adverse Gap Distribution Calculation
        adverse_gaps: List[float] = []
        n = min(len(opens), len(closes))

        for i in range(1, n):
            prev_close = closes[i - 1]
            curr_open = opens[i]
            if prev_close <= 0:
                continue

            # Directional adverse gap
            if is_long:
                # For LONG: Only Gap-Down is adverse
                if curr_open < prev_close:
                    gap_pct = (prev_close - curr_open) / prev_close
                    adverse_gaps.append(gap_pct)
            else:
                # For SHORT: Only Gap-Up is adverse
                if curr_open > prev_close:
                    gap_pct = (curr_open - prev_close) / prev_close
                    adverse_gaps.append(gap_pct)

        # Fallback if stock had very few adverse gap days
        if not adverse_gaps:
            adverse_gaps = [
                abs(opens[i] - closes[i - 1]) / closes[i - 1]
                for i in range(1, n)
                if closes[i - 1] > 0
            ]

        if not adverse_gaps:
            fallback_gap_rs = round(sl_distance * 0.5, 2)
            return GapRiskResult(
                risk_level="LOW",
                expected_gap_rs=fallback_gap_rs,
                expected_gap_pct=round(fallback_gap_rs / e, 4),
                size_multiplier=1.0,
                is_vetoed=False,
                is_weekend_scaled=False,
                is_intraday=False,
                reason="No gap data available — using baseline",
            )

        adverse_gaps.sort()
        n_gaps = len(adverse_gaps)
        p95_idx = min(n_gaps - 1, int(n_gaps * 0.95))
        p95_gap_pct = adverse_gaps[p95_idx]

        # 4. Volatility Clustering (GARCH proxy: 5-day realized vol / 30-day realized vol)
        recent_returns = [
            abs(closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(max(1, len(closes) - 5), len(closes))
            if closes[i - 1] > 0
        ]
        baseline_returns = [
            abs(closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(max(1, len(closes) - 30), len(closes))
            if closes[i - 1] > 0
        ]

        recent_vol = sum(recent_returns) / len(recent_returns) if recent_returns else 0.01
        base_vol = sum(baseline_returns) / len(baseline_returns) if baseline_returns else 0.01

        vol_clustering_multiplier = min(2.0, max(0.8, recent_vol / (base_vol + 1e-9)))

        # Incorporate Live India VIX if elevated
        vix_val = _safe_float(current_vix)
        if vix_val > 18.0:
            vix_factor = 1.0 + min(0.5, (vix_val - 18.0) / 20.0)
            vol_clustering_multiplier = min(2.0, vol_clustering_multiplier * vix_factor)

        # 5. Weekend & Long Holiday Multiplier (Friday = 4)
        is_friday = now.weekday() == 4
        weekend_mult = math.sqrt(3.0) if is_friday else 1.0  # sqrt(3) ~= 1.732

        # 6. Adjusted Expected 95th-Percentile Overnight Gap
        adjusted_gap_pct = p95_gap_pct * vol_clustering_multiplier * weekend_mult
        expected_gap_rs = round(e * adjusted_gap_pct, 2)

        # 7. Sizing & Risk Evaluation Ladder
        if expected_gap_rs > (sl_distance * 1.5):
            return GapRiskResult(
                risk_level="CRITICAL",
                expected_gap_rs=expected_gap_rs,
                expected_gap_pct=round(adjusted_gap_pct, 4),
                size_multiplier=0.0,
                is_vetoed=True,
                is_weekend_scaled=is_friday,
                is_intraday=False,
                reason=(
                    f"Critical Gap Risk: Expected overnight move ₹{expected_gap_rs:.2f} "
                    f"exceeds 1.5x SL distance (₹{sl_distance:.2f})"
                    + (" [Weekend Scaled]" if is_friday else "")
                ),
            )
        elif expected_gap_rs > (sl_distance * 1.0):
            return GapRiskResult(
                risk_level="HIGH",
                expected_gap_rs=expected_gap_rs,
                expected_gap_pct=round(adjusted_gap_pct, 4),
                size_multiplier=0.5,
                is_vetoed=False,
                is_weekend_scaled=is_friday,
                is_intraday=False,
                reason=(
                    f"High Gap Risk: Expected overnight move ₹{expected_gap_rs:.2f} "
                    f"matches SL distance (₹{sl_distance:.2f}) — reducing position to 50%"
                    + (" [Weekend Scaled]" if is_friday else "")
                ),
            )
        elif expected_gap_rs > (sl_distance * 0.7):
            return GapRiskResult(
                risk_level="MEDIUM",
                expected_gap_rs=expected_gap_rs,
                expected_gap_pct=round(adjusted_gap_pct, 4),
                size_multiplier=0.75,
                is_vetoed=False,
                is_weekend_scaled=is_friday,
                is_intraday=False,
                reason=(
                    f"Moderate Gap Risk: Expected overnight move ₹{expected_gap_rs:.2f} "
                    f"— scaling size to 75%"
                    + (" [Weekend Scaled]" if is_friday else "")
                ),
            )
        else:
            return GapRiskResult(
                risk_level="LOW",
                expected_gap_rs=expected_gap_rs,
                expected_gap_pct=round(adjusted_gap_pct, 4),
                size_multiplier=1.0,
                is_vetoed=False,
                is_weekend_scaled=is_friday,
                is_intraday=False,
                reason=(
                    f"Low Gap Risk: Expected overnight move ₹{expected_gap_rs:.2f} "
                    f"is well within SL distance (₹{sl_distance:.2f})"
                ),
            )

    except Exception as err:
        logger.error(f"[GapRisk] Failed to compute gap risk: {err}")
        fallback_gap_rs = round(sl_distance * 0.5, 2)
        entry_val = _safe_float(entry_price)
        fallback_pct = round(fallback_gap_rs / entry_val, 4) if entry_val > 0 else 0.005
        # FAIL TIGHT: a broken model must not hand out full size.
        return GapRiskResult(
            risk_level="MEDIUM",
            expected_gap_rs=fallback_gap_rs,
            expected_gap_pct=fallback_pct,
            size_multiplier=0.5,
            is_vetoed=False,
            is_weekend_scaled=False,
            is_intraday=False,
            reason=f"Gap risk calculation error (treated as MEDIUM): {err}",
        )
