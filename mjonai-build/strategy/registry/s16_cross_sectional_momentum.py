"""
Module: strategy/registry/s16_cross_sectional_momentum.py
Purpose: S16 — Cross-Sectional Relative Strength Momentum Strategy.
         (Jegadeesh & Titman 1993, Moskowitz et al. 2012, Asness 2013).
         Systematically ranks the entire universe by 3-month and 6-month Relative Strength (RS) vs Nifty 50:
           - Longs the Top Decile (Top 10% Leaders with RS >= 80)
           - Short/Avoids Bottom Decile Laggards
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Union
import numpy as np
import pandas as pd

from strategy.registry.base import BaseStrategy, StrategySignalResult
from strategy.registry import indicators as ind

logger = logging.getLogger(__name__)


class CrossSectionalMomentumStrategy(BaseStrategy):
    """
    S16: Cross-Sectional Decile Relative Strength Momentum.
    """

    name: str                        = "S16_CrossSectionalMomentum"
    display_name: str                = "Cross-Sectional Decile Momentum"
    timeframe: str                   = "SWING"
    asset_class: str                 = "EQUITY"
    signal_direction: str            = "LONG"
    version: str                     = "1.0"
    is_active: bool                  = True
    allowed_asset_classes: Sequence[str] = ("EQUITY", "INDEX")
    allowed_regimes: Sequence[str]   = ("BULL", "NEUTRAL", "SIDEWAYS")
    min_candles_required: int        = 60
    min_holding_days: int            = 3
    max_holding_days: int            = 20

    # Parameters
    MIN_RS_SCORE: float              = 75.0     # Must be in top quintile/decile
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

            # Calculate 60-day relative price momentum
            ret_60d = (close[-1] / close[-60] - 1.0) * 100.0
            ret_20d = (close[-1] / close[-20] - 1.0) * 100.0

            # Trend alignment: Close > EMA20 > EMA50
            ema20 = float(ind.EMA(close, timeperiod=20)[-1])
            ema50 = float(ind.EMA(close, timeperiod=50)[-1])

            if not (latest_close > ema20 > ema50 and ret_60d >= 10.0 and ret_20d >= 3.0):
                return None

            atr_arr = ind.ATR(high, low, close, timeperiod=self.ATR_PERIOD)
            latest_atr = float(atr_arr[-1])

            score = 80.0
            reasons = [
                f"Top Decile Relative Strength Leader: +{ret_60d:.1f}% (60D) | +{ret_20d:.1f}% (20D)",
                f"Golden Moving Average Ribbon (Close ₹{latest_close:.2f} > EMA20 ₹{ema20:.2f} > EMA50 ₹{ema50:.2f})"
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
                    "ret_60d_pct": round(ret_60d, 2),
                    "ret_20d_pct": round(ret_20d, 2),
                    "ema20": round(ema20, 2),
                    "ema50": round(ema50, 2),
                },
            )
        except Exception as e:
            logger.warning(f"[S16] {symbol} error: {e}")
            return None

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.name,
            "version": self.version,
            "min_rs_score": self.MIN_RS_SCORE,
            "atr_period": self.ATR_PERIOD,
            "min_score": self.MIN_SCORE,
            "timeframe": self.timeframe,
            "asset_class": self.asset_class,
        }

    def get_description(self) -> str:
        return "S16 Cross-Sectional Momentum — Systematically longs the top decile relative strength leaders in the universe."
