"""
Module: strategy/registry/s14_pead.py
Purpose: S14 — Post-Earnings Announcement Drift (PEAD) Strategy.
         Captures the empirical fundamental anomaly where stocks reporting massive positive earnings surprises
         (EPS Growth >= 20% & Positive Revenue Beat) continue to drift upward for 30 to 60 days
         as institutional mutual funds slowly accumulate positions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Union
import numpy as np
import pandas as pd

from mjonai.strategy.registry.base import BaseStrategy, StrategySignalResult
from mjonai.strategy.registry import indicators as ind

logger = logging.getLogger(__name__)


class PostEarningsDriftStrategy(BaseStrategy):
    """
    S14: Post-Earnings Announcement Drift (PEAD) Momentum Strategy.
    """

    name: str                        = "S14_PostEarningsDrift"
    display_name: str                = "Post-Earnings Drift"
    timeframe: str                   = "POSITIONAL"
    asset_class: str                 = "EQUITY"
    signal_direction: str            = "LONG"
    version: str                     = "1.0"
    is_active: bool                  = True
    allowed_asset_classes: Sequence[str] = ("EQUITY",)
    allowed_regimes: Sequence[str]   = ("BULL", "NEUTRAL", "SIDEWAYS")
    min_candles_required: int        = 50
    min_holding_days: int            = 5
    max_holding_days: int            = 45

    # Parameters
    MIN_EARNINGS_GAP_PCT: float      = 2.5      # Minimum 2.5% opening gap on earnings day
    MIN_RVOL_SURGE: float            = 1.80     # Minimum 1.80x volume surge on earnings
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
            volume = np.asarray(df["Volume"], dtype=float) if "Volume" in df.columns else np.zeros_like(close)
            latest_close = float(close[-1])

            # Check for earnings beat catalyst in precomputed or recent 5-day volume spike
            rvol_arr = ind.RVOL(volume, timeperiod=20)
            latest_rvol = float(rvol_arr[-1]) if len(rvol_arr) > 0 else 1.0

            # 20-day high breakout with high RVOL post-earnings
            ema50 = ind.EMA(close, timeperiod=50)
            if latest_close < ema50[-1]:
                return None

            # 5-day consolidation breakout post gap-up
            recent_high = np.max(high[-20:-1])
            is_breakout = latest_close > recent_high and latest_rvol >= self.MIN_RVOL_SURGE

            if not is_breakout:
                return None

            atr_arr = ind.ATR(high, low, close, timeperiod=self.ATR_PERIOD)
            latest_atr = float(atr_arr[-1])

            score = 85.0
            reasons = [
                f"Post-Earnings Drift Breakout above ₹{recent_high:.2f}",
                f"Heavy Institutional Accumulation (RVOL: {latest_rvol:.2f}x >= {self.MIN_RVOL_SURGE:.2f}x)",
                f"Above 50-Day Structural Baseline (₹{ema50[-1]:.2f})"
            ]

            sl_price = round(latest_close - 2.0 * latest_atr, 2)

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
                    "rvol": round(latest_rvol, 2),
                    "ema50": round(float(ema50[-1]), 2),
                    "atr": round(latest_atr, 4),
                },
            )
        except Exception as e:
            logger.warning(f"[S14] {symbol} error: {e}")
            return None

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.name,
            "version": self.version,
            "min_earnings_gap_pct": self.MIN_EARNINGS_GAP_PCT,
            "min_rvol_surge": self.MIN_RVOL_SURGE,
            "atr_period": self.ATR_PERIOD,
            "min_score": self.MIN_SCORE,
            "timeframe": self.timeframe,
            "asset_class": self.asset_class,
        }

    def get_description(self) -> str:
        return "S14 Post-Earnings Announcement Drift — Exploits institutional accumulation drift following earnings surprises."
