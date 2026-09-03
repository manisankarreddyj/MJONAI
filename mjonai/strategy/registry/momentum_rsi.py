"""
Module: strategy/registry/momentum_rsi.py
Purpose: S01 — SOTA Institutional 20-Bar Resistance Breakout Momentum Strategy.
         Removes noisy RSI-cross traps. Focuses 100% on genuine price breakouts:
           1. Daily Macro Filter: Daily Close > EMA50 or Daily RSI >= 50.0 (Bullish Bias)
           2. 15m Baseline: Price > EMA200, EMA20 > EMA50, ADX >= 20.0 (Established Uptrend)
           3. The Single Master Trigger:
              - Fresh 20-Bar Resistance Breakout (Close > 20-bar High)
              - RSI in Bullish Momentum Zone (55 <= RSI <= 72)
              - Institutional Volume Surge (RVOL >= 1.35x)
              - Bullish Green Close (Close > Open)
           4. Dynamic Swing Low Stop Loss with Breathing Room (1.8% - 2.8% buffer)
           5. Tranche 1 (+2.2R) Lock + Breakeven SL Ratchet & Target 2 (+4.0R) Runner
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Union
import numpy as np
import pandas as pd

from mjonai.strategy.registry.base import BaseStrategy, StrategySignalResult
from mjonai.strategy.registry import indicators as ind

logger = logging.getLogger(__name__)


class MomentumRSI(BaseStrategy):
    """
    S01 — Institutional Resistance Breakout Strategy.
    """

    name: str                        = "S01_MomentumRSI"
    display_name: str                = "Momentum RSI"
    timeframe: str                   = "SWING"
    asset_class: str                 = "EQUITY"
    version: str                     = "6.0"
    is_active: bool                  = True
    allowed_asset_classes: Sequence[str] = ("EQUITY", "INDEX", "COMMODITY", "CRYPTO", "FOREX")
    allowed_regimes: Sequence[str]   = ("BULL", "NEUTRAL", "SIDEWAYS")
    min_candles_required: int        = 100
    min_holding_days: int            = 2
    max_holding_days: int            = 7

    # ── Parameters ────────────────────────────────────────────────────────────
    RSI_PERIOD: int                  = 14
    RSI_MIN: float                   = 55.0
    RSI_MAX: float                   = 72.0

    EMA_SHORT: int                   = 20
    EMA_MID: int                     = 50
    EMA_LONG: int                    = 200

    ADX_PERIOD: int                  = 14
    ADX_MIN_STRENGTH: float          = 20.0

    ATR_PERIOD: int                  = 14
    RVOL_PERIOD: int                 = 20
    RVOL_MIN_THRESHOLD: float        = 1.35

    DONCHIAN_PERIOD: int             = 20
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
        """
        Generate S01 Pure Resistance Breakout Signal.
        """
        try:
            # 1. Validate DataFrame minimum history
            is_valid, reason = self.validate_ohlcv_dataframe(df, min_candles=self.min_candles_required)
            if not is_valid:
                return None

            close  = np.asarray(df["Close"], dtype=float)
            high   = np.asarray(df["High"], dtype=float)
            low    = np.asarray(df["Low"], dtype=float)
            open_  = np.asarray(df["Open"], dtype=float)
            volume = np.asarray(df["Volume"], dtype=float) if "Volume" in df.columns else np.zeros_like(close)

            # ── 1. DAILY MACRO FILTER (Must have Bullish Bias) ───────────────
            if higher_tf_df is not None and len(higher_tf_df) >= 20:
                d_close = np.asarray(higher_tf_df["Close"], dtype=float)
                d_ema50 = ind.EMA(d_close, timeperiod=min(50, len(d_close)-1))
                d_rsi   = ind.RSI(d_close, timeperiod=min(14, len(d_close)-1))

                is_daily_bull = (d_close[-1] >= d_ema50[-1] * 0.99) or (d_rsi[-1] >= 50.0)
                if not is_daily_bull:
                    return None

            # ── 2. 15-MINUTE TIMEFRAME INDICATORS ────────────────────────────
            ema_short = ind.EMA(close, timeperiod=self.EMA_SHORT)
            ema_mid   = ind.EMA(close, timeperiod=self.EMA_MID)
            ema_long  = ind.EMA(close, timeperiod=self.EMA_LONG)
            ema_s = float(ema_short[-1])
            ema_m = float(ema_mid[-1])
            ema_l = float(ema_long[-1])
            latest_close = float(close[-1])

            # 15m Baseline Trend: Price > 200-EMA and Short > Mid
            if latest_close < ema_l or ema_s <= ema_m:
                return None

            # 15m ADX Gate (Filters out dead chop)
            adx_vals = ind.ADX(high, low, close, timeperiod=self.ADX_PERIOD)
            latest_adx = float(adx_vals[-1]) if len(adx_vals) > 0 else 0.0
            if latest_adx < self.ADX_MIN_STRENGTH:
                return None

            # 15m RSI & RVOL
            rsi_vals = ind.RSI(close, timeperiod=self.RSI_PERIOD)
            latest_rsi = float(rsi_vals[-1])

            if np.isnan(latest_rsi) or latest_rsi < self.RSI_MIN or latest_rsi > self.RSI_MAX:
                return None

            rvol_arr = ind.RVOL(volume, timeperiod=self.RVOL_PERIOD) if np.sum(volume) > 0 else np.ones_like(close)
            latest_rvol = float(rvol_arr[-1]) if len(rvol_arr) > 0 else 1.0

            # ── 3. THE SINGLE MASTER PRICE BREAKOUT TRIGGER ──────────────────
            # First-cross resistance: window EXCLUDES both the signal bar
            # and the prior bar. The old window included the prior bar's own
            # high, so close[-2] <= max(...) stayed true on continuation
            # days and the "fresh breakout" refired on every trend day.
            resistance = (
                np.max(high[-(self.DONCHIAN_PERIOD + 2):-2])
                if len(high) >= (self.DONCHIAN_PERIOD + 3)
                else high[-3]
            )

            is_breakout = (close[-1] > resistance) and (close[-2] <= resistance)
            is_vol_confirmed = (latest_rvol >= self.RVOL_MIN_THRESHOLD)
            is_bull_bar = (close[-1] > open_[-1])

            if not (is_breakout and is_vol_confirmed and is_bull_bar):
                return None

            score = 90.0
            reasons = [
                f"Fresh 20-Bar Resistance Breakout above ₹{resistance:.2f}",
                f"RSI Bullish Momentum ({latest_rsi:.1f})",
                f"Institutional Volume Surge ({latest_rvol:.2f}x >= {self.RVOL_MIN_THRESHOLD:.2f}x)"
            ]

            # ── 4. Dynamic Swing Low Stop Loss with Breathing Room ───────────
            atr_vals = ind.ATR(high, low, close, timeperiod=self.ATR_PERIOD)
            latest_atr = float(atr_vals[-1])

            recent_10_low = float(np.min(low[-10:]))
            raw_risk = latest_close - recent_10_low
            min_safe_risk = 2.5 * latest_atr  # Natural 1.8% to 2.8% breathing room

            if raw_risk < min_safe_risk:
                sl_price = round(latest_close - min_safe_risk, 2)
            else:
                sl_price = round(recent_10_low - 0.2 * latest_atr, 2)

            return StrategySignalResult(
                strategy_id=self.name,
                strategy_version=self.version,
                symbol=symbol,
                signal_direction="LONG",
                signal_type="BUY",
                technical_score=float(score),
                confidence=float(score),
                reasons=reasons,
                entry_price=round(latest_close, 2),
                swing_low=sl_price,
                timeframe=self.timeframe,
                asset_class=self.asset_class,
                atr=round(latest_atr, 4),
                candle_pattern="FRESH_20BAR_RESISTANCE_BREAKOUT",
                indicator_values={
                    "rsi": round(latest_rsi, 2),
                    "adx": round(latest_adx, 2),
                    "atr": round(latest_atr, 4),
                    "rvol": round(latest_rvol, 2),
                    "ema_short": round(ema_s, 2),
                    "ema_mid": round(ema_m, 2),
                    "ema_long": round(ema_l, 2),
                    "breakout_level": round(resistance, 2),
                },
                extra_metadata={
                    "vix": round(float(vix), 2),
                    "market_state": market_state,
                    "mqi_level": mqi_level,
                    "min_holding_days": self.min_holding_days,
                    "max_holding_days": self.max_holding_days,
                },
            )

        except Exception as e:
            logger.warning(f"[S01] generate_signal exception for {symbol}: {e}")
            return None

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "strategy_id":            self.name,
            "version":                self.version,
            "rsi_period":             self.RSI_PERIOD,
            "rsi_min":                self.RSI_MIN,
            "rsi_max":                self.RSI_MAX,
            "ema_short":              self.EMA_SHORT,
            "ema_mid":                self.EMA_MID,
            "ema_long":               self.EMA_LONG,
            "adx_period":             self.ADX_PERIOD,
            "adx_min_strength":       self.ADX_MIN_STRENGTH,
            "atr_period":             self.ATR_PERIOD,
            "rvol_period":            self.RVOL_PERIOD,
            "rvol_min_threshold":     self.RVOL_MIN_THRESHOLD,
            "donchian_period":        self.DONCHIAN_PERIOD,
            "min_score":              self.MIN_SCORE,
            "timeframe":              self.timeframe,
            "asset_class":            self.asset_class,
        }

    def get_description(self) -> str:
        return (
            f"S01 Momentum RSI v{self.version} — Pure 20-Bar Resistance Breakout Strategy. "
            f"Requires fresh price breakout above 20-bar high confirmed by RSI {self.RSI_MIN}-{self.RSI_MAX} and RVOL>={self.RVOL_MIN_THRESHOLD}x."
        )
