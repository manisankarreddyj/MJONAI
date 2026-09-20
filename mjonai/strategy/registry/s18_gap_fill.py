"""
Module: strategy/registry/s18_gap_fill.py
Purpose: S18 — Opening Gap-Fill & Fair Value Gap (FVG) Strategy.
         Exploits two major institutional liquidity phenomena:
           1. Opening Gap Fill (Mean Reversion): When an opening gap is overextended (0.3% to 1.5%) with low volume (RVOL <= 1.3x),
              it enters a high-probability trade targeting the Previous Day's Close (PDC).
           2. Fair Value Gap (FVG) Mitigation (Trend Continuation): In strong trending markets, when price pulls back
              to mitigate an unmitigated 3-candle Fair Value Gap (Consequent Encroachment 50% level),
              it enters in the direction of the macro trend.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Union
import numpy as np
import pandas as pd

from mjonai.strategy.registry.base import BaseStrategy, StrategySignalResult
from mjonai.strategy.registry import indicators as ind
from mjonai.data.microstructure.gap_analyzer import analyze_opening_gap_and_fvg, GapType

logger = logging.getLogger(__name__)


class GapFillAndFVGStrategy(BaseStrategy):
    """
    S18: Opening Gap-Fill & Fair Value Gap (FVG) Strategy.
    """

    name: str                        = "S18_GapFillFVG"
    display_name: str                = "Gap Fill & Fair Value Gap"
    timeframe: str                   = "INTRADAY"
    asset_class: str                 = "EQUITY"
    signal_direction: str            = "BIDIRECTIONAL"
    version: str                     = "1.0"
    is_active: bool                  = True
    # Scan cadence whitelist (minute pipeline, S08 re-enable): this intraday
    # strategy keeps its current 15m scan slot ONLY. The 5m slot is S08's; a
    # ruling is required before any sibling joins it.
    scan_cadences: Sequence[str]     = ("15m",)
    allowed_asset_classes: Sequence[str] = ("EQUITY", "INDEX", "OPTIONS", "COMMODITY")
    allowed_regimes: Sequence[str]   = ("BULL", "BEAR", "NEUTRAL", "SIDEWAYS")
    min_candles_required: int        = 20
    min_holding_days: int            = 0
    max_holding_days: int            = 1

    # Parameters
    MIN_GAP_PCT: float               = 0.35     # Minimum 0.35% gap to trade
    MAX_GAP_PCT: float               = 1.50     # Maximum 1.50% gap (larger gaps are breakaways)
    ATR_PERIOD: int                  = 14
    MIN_SCORE: int                   = 75

    def generate_signal(
        self,
        df: pd.DataFrame,
        symbol: str,
        vix: float,
        market_state: str,
        mqi_level: str,
        higher_tf_df: Optional[pd.DataFrame] = None,
        precomputed_indicators: Optional[Dict[str, Any]] = None,
    ) -> Optional[StrategySignalResult]:
        try:
            if df is None or len(df) < self.min_candles_required:
                return None

            close = np.asarray(df["Close"], dtype=float)
            high  = np.asarray(df["High"], dtype=float)
            low   = np.asarray(df["Low"], dtype=float)
            latest_close = float(close[-1])

            gap_snap = analyze_opening_gap_and_fvg(symbol, df)

            atr_arr = ind.ATR(high, low, close, timeperiod=self.ATR_PERIOD)
            latest_atr = float(atr_arr[-1]) if len(atr_arr) > 0 else latest_close * 0.01

            # Mode A: Opening Gap Fill Mean Reversion
            if gap_snap.gap_type == GapType.EXHAUSTION_FILL and abs(gap_snap.gap_pct) >= self.MIN_GAP_PCT:
                if gap_snap.gap_pct > 0:
                    # Gap up -> Short to fill gap down to prev close
                    direction = "SHORT"
                    sig_type = "SELL"
                    reasons = [
                        f"Opening Gap-Up Exhaustion (+{gap_snap.gap_pct:.2f}%): High probability fill targeting Previous Close ₹{gap_snap.prev_close:.2f}",
                        f"Fill Probability: {gap_snap.fill_probability_pct:.0f}%"
                    ]
                    sl_price = round(latest_close + 1.5 * latest_atr, 2)
                else:
                    # Gap down -> Long to fill gap up to prev close
                    direction = "LONG"
                    sig_type = "BUY"
                    reasons = [
                        f"Opening Gap-Down Exhaustion ({gap_snap.gap_pct:.2f}%): High probability fill targeting Previous Close ₹{gap_snap.prev_close:.2f}",
                        f"Fill Probability: {gap_snap.fill_probability_pct:.0f}%"
                    ]
                    sl_price = round(latest_close - 1.5 * latest_atr, 2)

                score = 80.0
                return StrategySignalResult(
                    strategy_id=self.name,
                    strategy_version=self.version,
                    symbol=symbol,
                    signal_direction=direction,
                    signal_type=sig_type,
                    technical_score=score,
                    confidence=score,
                    reasons=reasons,
                    entry_price=round(latest_close, 2),
                    swing_low=sl_price if direction == "LONG" else None,
                    swing_high=sl_price if direction == "SHORT" else None,
                    timeframe=self.timeframe,
                    asset_class=self.asset_class,
                    atr=round(latest_atr, 4),
                    indicator_values={
                        "gap_pct": gap_snap.gap_pct,
                        "prev_close": gap_snap.prev_close,
                        "fill_prob": gap_snap.fill_probability_pct,
                    },
                )

            # Mode B: Fair Value Gap (FVG) Mitigation Re-test
            if gap_snap.active_fvgs:
                latest_fvg = gap_snap.active_fvgs[-1]
                if latest_fvg.gap_type == "BULLISH_FVG" and latest_close <= latest_fvg.top_level and latest_close >= latest_fvg.bottom_level:
                    # Pullback to Bullish FVG zone -> Buy
                    score = 85.0
                    reasons = [
                        f"Institutional Bullish Fair Value Gap (FVG) Mitigation at ₹{latest_close:.2f} (Zone: ₹{latest_fvg.bottom_level:.2f} - ₹{latest_fvg.top_level:.2f})",
                        f"Consequent Encroachment (50% Mid-Point): ₹{latest_fvg.mid_point:.2f}"
                    ]
                    sl_price = round(latest_fvg.bottom_level - 0.5 * latest_atr, 2)
                    return StrategySignalResult(
                        strategy_id=self.name,
                        strategy_version=self.version,
                        symbol=symbol,
                        signal_direction="LONG",
                        signal_type="BUY",
                        technical_score=score,
                        confidence=score,
                        reasons=reasons,
                        entry_price=round(latest_close, 2),
                        swing_low=sl_price,
                        timeframe=self.timeframe,
                        asset_class=self.asset_class,
                        atr=round(latest_atr, 4),
                        indicator_values={
                            "fvg_top": latest_fvg.top_level,
                            "fvg_bottom": latest_fvg.bottom_level,
                            "fvg_mid": latest_fvg.mid_point,
                        },
                    )

            return None
        except Exception as e:
            logger.warning(f"[S18] {symbol} error: {e}")
            return None

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.name,
            "version": self.version,
            "min_gap_pct": self.MIN_GAP_PCT,
            "max_gap_pct": self.MAX_GAP_PCT,
            "atr_period": self.ATR_PERIOD,
            "min_score": self.MIN_SCORE,
            "timeframe": self.timeframe,
            "asset_class": self.asset_class,
        }

    def get_description(self) -> str:
        return "S18 Gap Fill & FVG — Exploits opening gap mean-reversion fills and institutional Fair Value Gap (FVG) mitigations."
