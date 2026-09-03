"""
Module: strategy/registry/s15_fii_short_squeeze.py
Purpose: S15 — FII Index Futures Short-Squeeze Sentry Strategy.
         Exploits extreme institutional derivative positioning imbalances:
           - When Foreign Institutional Investors (FIIs) hold extreme net short positions (Long Ratio <= 15%),
             the market becomes heavily asymmetric to the upside.
           - Any minor positive catalyst or gap-up forces aggressive short-covering, triggering explosive 500-1000 point rallies.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Union
import numpy as np
import pandas as pd

from strategy.registry.base import BaseStrategy, StrategySignalResult
from strategy.registry import indicators as ind
from data.derivatives.participant_oi import fetch_live_nse_participant_oi, InstitutionalPositioningZone

logger = logging.getLogger(__name__)


class FIIShortSqueezeStrategy(BaseStrategy):
    """
    S15: FII Index Futures Short-Squeeze Sentry.
    """

    name: str                        = "S15_FIIShortSqueeze"
    display_name: str                = "FII Short Squeeze Sentry"
    timeframe: str                   = "SWING"
    asset_class: str                 = "INDEX"
    signal_direction: str            = "LONG"
    version: str                     = "1.0"
    is_active: bool                  = True
    allowed_asset_classes: Sequence[str] = ("INDEX", "OPTIONS", "EQUITY")
    allowed_regimes: Sequence[str]   = ("BULL", "NEUTRAL", "BEAR", "SIDEWAYS")
    min_candles_required: int        = 20
    min_holding_days: int            = 1
    max_holding_days: int            = 7

    # Parameters
    EXTREME_SHORT_THRESHOLD: float   = 0.15     # FII Futures Long Ratio <= 15%
    ATR_PERIOD: int                  = 14
    MIN_SCORE: int                   = 80

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

            # Get FII positioning data
            fii_ratio = 0.20
            p_snap = fetch_live_nse_participant_oi()
            if p_snap:
                fii_ratio = p_snap.fii_index_fut_ratio

            if precomputed_indicators and "fii_index_fut_ratio" in precomputed_indicators:
                fii_ratio = float(precomputed_indicators["fii_index_fut_ratio"])

            # Squeeze condition: FIIs heavily trapped short (<= 15%) + Intraday reversal green close
            is_fii_trapped = (fii_ratio <= self.EXTREME_SHORT_THRESHOLD)
            is_green_reversal = (close[-1] > close[-2]) and (close[-1] > float(ind.EMA(close, timeperiod=9)[-1]))

            if not (is_fii_trapped and is_green_reversal):
                return None

            atr_arr = ind.ATR(high, low, close, timeperiod=self.ATR_PERIOD)
            latest_atr = float(atr_arr[-1])

            score = 90.0
            reasons = [
                f"FII Short Squeeze Trap Active: FII Futures Long Ratio at extreme low {fii_ratio*100:.1f}% (<= {self.EXTREME_SHORT_THRESHOLD*100:.1f}%)",
                f"Intraday Bullish Reversal Confirmation (Close ₹{latest_close:.2f} > 9-EMA)"
            ]

            sl_price = round(latest_close - 1.8 * latest_atr, 2)

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
                    "fii_futures_long_ratio": round(fii_ratio, 3),
                    "atr": round(latest_atr, 4),
                },
            )
        except Exception as e:
            logger.warning(f"[S15] {symbol} error: {e}")
            return None

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.name,
            "version": self.version,
            "extreme_short_threshold": self.EXTREME_SHORT_THRESHOLD,
            "atr_period": self.ATR_PERIOD,
            "min_score": self.MIN_SCORE,
            "timeframe": self.timeframe,
            "asset_class": self.asset_class,
        }

    def get_description(self) -> str:
        return "S15 FII Short Squeeze — Exploits asymmetric short squeeze explosions when FIIs are trapped short."
