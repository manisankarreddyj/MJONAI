"""
Module: strategy/registry/s13_gamma_flip.py
Purpose: S13 — Dealer Gamma Flip & Zero-Gamma Acceleration Strategy.
         Exploits non-linear market maker option hedging mechanics:
           1. Positive Gamma Zone (Spot > Zero-Gamma): Dealers buy dips and sell rips -> Mean Reversion Pinning.
           2. Negative Gamma Zone (Spot < Zero-Gamma): Dealers sell into drops and buy into rallies -> Trend Acceleration.
           3. Gamma Flip Crossover: When Spot breaks from Positive to Negative Gamma, volatility explodes downward.
              When Spot breaks from Negative to Positive Gamma, market stabilizes and pins upward.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Union
import numpy as np
import pandas as pd

from strategy.registry.base import BaseStrategy, StrategySignalResult
from strategy.registry import indicators as ind

logger = logging.getLogger(__name__)


class GammaFlipStrategy(BaseStrategy):
    """
    S13: Dealer Gamma Flip & Zero-Gamma Acceleration Scalper.
    """

    name: str                        = "S13_GammaFlip"
    display_name: str                = "Dealer Gamma Flip"
    timeframe: str                   = "INTRADAY"
    asset_class: str                 = "OPTIONS"
    signal_direction: str            = "BIDIRECTIONAL"
    version: str                     = "1.0"
    is_active: bool                  = True
    allowed_asset_classes: Sequence[str] = ("OPTIONS", "INDEX", "EQUITY")
    allowed_regimes: Sequence[str]   = ("BULL", "BEAR", "NEUTRAL", "SIDEWAYS")
    min_candles_required: int        = 30
    min_holding_days: int            = 0
    max_holding_days: int            = 2

    # Parameters
    MIN_GEX_MAGNITUDE_CR: float      = 50.0     # Minimum 50 Cr GEX magnitude
    ATR_PERIOD: int                  = 14
    MIN_SCORE: int                   = 70

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

            # Zero-Gamma level from GEX engine or precomputed indicators
            zero_gamma = None
            total_gex = 0.0
            if precomputed_indicators:
                zero_gamma = precomputed_indicators.get("zero_gamma_level")
                total_gex = precomputed_indicators.get("total_gex_crores", 0.0)

            if zero_gamma is None:
                # Approximate zero gamma from recent 20-EMA
                zero_gamma = float(ind.EMA(close, timeperiod=20)[-1])

            atr_arr = ind.ATR(high, low, close, timeperiod=self.ATR_PERIOD)
            latest_atr = float(atr_arr[-1]) if len(atr_arr) > 0 else latest_close * 0.01

            # Gamma Acceleration Trigger: Spot crosses above Zero-Gamma (Bullish Pinning) or below (Bearish Acceleration)
            is_cross_above = (close[-1] > zero_gamma) and (close[-2] <= zero_gamma)
            is_cross_below = (close[-1] < zero_gamma) and (close[-2] >= zero_gamma)

            if not (is_cross_above or is_cross_below):
                return None

            direction = "LONG" if is_cross_above else "SHORT"
            sig_type = "BUY" if is_cross_above else "SELL"
            score = 80.0
            reasons = [
                f"Dealer Gamma Flip Trigger: Spot ₹{latest_close:.2f} crossed {'ABOVE' if is_cross_above else 'BELOW'} Zero-Gamma Line ₹{zero_gamma:.2f}",
                f"{'Positive Gamma Regime (Dealer Pinning & Dip Buying)' if is_cross_above else 'Negative Gamma Regime (Dealer Short Acceleration)'}"
            ]

            sl_price = round(latest_close - 1.5 * latest_atr if direction == "LONG" else latest_close + 1.5 * latest_atr, 2)

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
                    "zero_gamma_level": round(zero_gamma, 2),
                    "total_gex_crores": round(total_gex, 2),
                    "atr": round(latest_atr, 4),
                },
            )
        except Exception as e:
            logger.warning(f"[S13] {symbol} error: {e}")
            return None

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.name,
            "version": self.version,
            "min_gex_magnitude_cr": self.MIN_GEX_MAGNITUDE_CR,
            "atr_period": self.ATR_PERIOD,
            "min_score": self.MIN_SCORE,
            "timeframe": self.timeframe,
            "asset_class": self.asset_class,
        }

    def get_description(self) -> str:
        return "S13 Dealer Gamma Flip — Exploits non-linear market maker option delta hedging acceleration."
