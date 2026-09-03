"""
Module: strategy/registry/momentum_short.py
Purpose: S06 — SOTA Institutional Multi-Asset Momentum Short Strategy.
         Captures high-velocity downward momentum, structural breakdowns, and short continuation in secular downtrends.
         Combines RSI Bearish Momentum Zone (30-45), MACD Negative Acceleration, Triple EMA Bearish Stacking,
         ADX Trend Velocity (-DI > +DI), Donchian 20-Day Low Structural Breakdown,
         Institutional Distribution Flow (RVOL & CMF), and Bearish Candlestick Triggers.

Pillars of Scoring (Total: 100 Points, Minimum Gate: 65 Points):
  • HARD SENTRY 1: Price MUST be below EMA200 (Secular Macro Downtrend)
  • HARD SENTRY 2: ADX >= 15.0 (No shorting in completely flat/dead chop)
  • HARD SENTRY 3: RSI(14) >= 25.0 (Prevents shorting into deep oversold capitulation bottoms)
  1. RSI Bearish Momentum Zone (30-45 or 25-30 Power Breakdown):        +20 Pts
  2. MACD Bearish Acceleration (Histogram < 0 & Declining):            +20 Pts
  3. Triple EMA Bearish Stack (EMA20 < EMA50 < EMA200):                 +20 Pts
  4. Trend Velocity & Supertrend Resistance (ADX >= 20 & -DI > +DI):    +15 Pts
  5. Institutional Distribution Flow (RVOL >= 1.20x or CMF < -0.05):     +15 Pts
  6. Bearish Candlestick Pattern Trigger (Shooting Star, Evening Star): +10 Pts
  * Bonus (+10 Pts): 20-Day Donchian Low Structural Breakdown

Inherits from BaseStrategy with full multi-asset, multi-timeframe, and precomputed indicator support.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Union
import numpy as np
import pandas as pd

from strategy.registry.base import BaseStrategy, StrategySignalResult
from strategy.registry import indicators as ind

logger = logging.getLogger(__name__)


class MomentumShort(BaseStrategy):
    """
    S06 — Momentum Short Strategy.

    Research targets:
        Win rate > 52% (Fast asymmetric downside velocity)
        Best regime: BEAR / NEUTRAL breakdown
        Worst regime: BULL market strong uptrends (Short squeeze risk)
        IC target: > 0.05 (Alphalens)
    """

    name: str                        = "S06_MomentumShort"
    display_name: str                = "Momentum Short"
    timeframe: str                   = "SWING"
    asset_class: str                 = "EQUITY"
    signal_direction: str            = "SHORT"
    version: str                     = "2.2"
    is_active: bool                  = True
    allowed_asset_classes: Sequence[str] = ("EQUITY", "INDEX", "COMMODITY", "CRYPTO", "FOREX")
    allowed_regimes: Sequence[str]   = ("BEAR", "NEUTRAL", "SIDEWAYS")
    min_candles_required: int        = 210
    min_holding_days: int            = 3
    max_holding_days: int            = 10

    # ── Parameters (Logged to MLflow / Optuna tunable) ────────────────────────
    RSI_PERIOD: int                  = 14
    RSI_MIN: float                   = 30.0     # Normal bearish momentum floor
    RSI_MAX: float                   = 45.0     # Bearish momentum ceiling
    RSI_POWER_MIN: float             = 25.0     # Power breakdown floor with high ADX
    RSI_HARD_FLOOR: float            = 25.0     # Absolute floor (no shorting below 25)

    MACD_FAST: int                   = 12
    MACD_SLOW: int                   = 26
    MACD_SIGNAL: int                 = 9

    EMA_SHORT: int                   = 20
    EMA_MID: int                     = 50
    EMA_LONG: int                    = 200

    ADX_PERIOD: int                  = 14
    ADX_MIN_STRENGTH: float          = 20.0
    ADX_POWER_STRENGTH: float        = 28.0

    ATR_PERIOD: int                  = 14
    SUPERTREND_MULTIPLIER: float      = 3.0

    RVOL_PERIOD: int                 = 20
    RVOL_MIN_THRESHOLD: float        = 1.20
    VOLUME_PERIOD: int               = 20
    VOLUME_CONFIRM: float            = 1.20
    BREAKDOWN_LOOKBACK: int          = 20       # Donchian breakdown lookback

    MIN_SCORE: int                   = 65       # Minimum technical score

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
        Generate S06 Momentum Short signal for given symbol and market conditions.
        """
        try:
            # 1. Validate DataFrame minimum history (adaptive if higher_tf_df or precomputed indicators available)
            min_req = min(self.min_candles_required, 30) if (higher_tf_df is not None and len(higher_tf_df) >= 100) or (precomputed_indicators and "ema_long" in precomputed_indicators) else self.min_candles_required
            is_valid, reason = self.validate_ohlcv_dataframe(df, min_candles=min_req)
            if not is_valid:
                logger.warning(f"[S06] {symbol} — {reason}")
                return None

            close  = np.asarray(df["Close"], dtype=float)
            high   = np.asarray(df["High"], dtype=float)
            low    = np.asarray(df["Low"], dtype=float)
            open_  = np.asarray(df["Open"], dtype=float)
            volume = np.asarray(df["Volume"], dtype=float) if "Volume" in df.columns else np.zeros_like(close)

            score: int = 0
            reasons: List[str] = []

            # ── 1. Trend Strength (ADX & Directional Movement) ───────────────
            if precomputed_indicators and all(k in precomputed_indicators for k in ("adx", "plus_di", "minus_di")):
                latest_adx      = float(precomputed_indicators["adx"])
                latest_plus_di  = float(precomputed_indicators["plus_di"])
                latest_minus_di = float(precomputed_indicators["minus_di"])
            else:
                adx_vals = ind.ADX(high, low, close, timeperiod=self.ADX_PERIOD)
                p_di     = ind.PLUS_DI(high, low, close, timeperiod=self.ADX_PERIOD)
                m_di     = ind.MINUS_DI(high, low, close, timeperiod=self.ADX_PERIOD)
                latest_adx      = float(adx_vals[-1]) if len(adx_vals) > 0 else 0.0
                latest_plus_di  = float(p_di[-1]) if len(p_di) > 0 else 0.0
                latest_minus_di = float(m_di[-1]) if len(m_di) > 0 else 0.0

            # HARD SENTRY 1: No shorting in completely flat/dead chop
            if latest_adx < 15.0:
                return None

            # ── 2. EMA Long Macro Trend Sentry (HARD SENTRY 2) ────────────────
            if precomputed_indicators and all(k in precomputed_indicators for k in ("ema_short", "ema_mid", "ema_long")):
                ema_s = float(precomputed_indicators["ema_short"])
                ema_m = float(precomputed_indicators["ema_mid"])
                ema_l = float(precomputed_indicators["ema_long"])
            elif higher_tf_df is not None and len(higher_tf_df) >= 50:
                htf_close = np.asarray(higher_tf_df["Close"], dtype=float)
                period_to_use = min(self.EMA_LONG, len(htf_close))
                ema_long_arr = ind.EMA(htf_close, timeperiod=period_to_use)
                ema_l = float(ema_long_arr[-1]) if len(ema_long_arr) > 0 else float("nan")
                ema_s = float(ind.EMA(close, timeperiod=min(self.EMA_SHORT, len(close)))[-1])
                ema_m = float(ind.EMA(close, timeperiod=min(self.EMA_MID, len(close)))[-1])
            else:
                ema_short = ind.EMA(close, timeperiod=self.EMA_SHORT)
                ema_mid   = ind.EMA(close, timeperiod=self.EMA_MID)
                ema_long  = ind.EMA(close, timeperiod=self.EMA_LONG)
                ema_s = float(ema_short[-1]) if len(ema_short) > 0 else float("nan")
                ema_m = float(ema_mid[-1]) if len(ema_mid) > 0 else float("nan")
                ema_l = float(ema_long[-1]) if len(ema_long) > 0 else float("nan")

            if np.isnan(ema_s) or np.isnan(ema_m) or np.isnan(ema_l):
                logger.warning(f"[S06] {symbol} — EMA values contain NaN")
                return None

            latest_close = float(close[-1])
            if np.isnan(latest_close) or latest_close <= 0:
                logger.warning(f"[S06] {symbol} — latest_close is NaN or non-positive")
                return None

            # HARD SENTRY: Cannot short stocks trading in a secular bull market above 200 EMA
            if latest_close >= ema_l:
                return None

            # ── 3. RSI Bearish Momentum Zone (HARD SENTRY 3) ─────────────────
            if precomputed_indicators and "rsi" in precomputed_indicators:
                latest_rsi = float(precomputed_indicators["rsi"])
            else:
                rsi = ind.RSI(close, timeperiod=self.RSI_PERIOD)
                latest_rsi = float(rsi[-1]) if len(rsi) > 0 else float("nan")

            if np.isnan(latest_rsi):
                logger.warning(f"[S06] {symbol} — RSI is NaN")
                return None

            # HARD SENTRY: Prevents shorting at deep oversold bottoms (capitulation climax)
            if latest_rsi < self.RSI_HARD_FLOOR:
                return None

            if self.RSI_MIN <= latest_rsi <= self.RSI_MAX:
                score += 20
                reasons.append(f"RSI in optimal bearish momentum zone ({latest_rsi:.1f})")
            elif self.RSI_POWER_MIN <= latest_rsi < self.RSI_MIN and latest_adx >= self.ADX_POWER_STRENGTH:
                score += 20
                reasons.append(f"RSI in Power Breakdown zone ({latest_rsi:.1f}) confirmed by high ADX ({latest_adx:.1f})")
            else:
                reasons.append(f"RSI out of bearish zone ({latest_rsi:.1f})")

            # ── 4. MACD Bearish Acceleration (Histogram < 0 & Declining) ─────
            if precomputed_indicators and "macd_hist" in precomputed_indicators and "macd_hist_prev" in precomputed_indicators:
                hist_curr = float(precomputed_indicators["macd_hist"])
                hist_prev = float(precomputed_indicators["macd_hist_prev"])
            else:
                _, _, hist = ind.MACD(
                    close,
                    fastperiod=self.MACD_FAST,
                    slowperiod=self.MACD_SLOW,
                    signalperiod=self.MACD_SIGNAL,
                )
                hist_curr = float(hist[-1]) if len(hist) > 0 else float("nan")
                hist_prev = float(hist[-2]) if len(hist) > 1 else float("nan")

            if np.isnan(hist_curr) or np.isnan(hist_prev):
                logger.warning(f"[S06] {symbol} — MACD is NaN")
                return None

            if hist_curr < 0.0 and hist_curr < hist_prev:
                score += 20
                reasons.append("MACD histogram negative and accelerating downwards")
            elif hist_curr < 0.0:
                score += 10
                reasons.append("MACD negative baseline")
            else:
                reasons.append("MACD momentum not bearish")

            # ── 5. EMA Alignment (EMA20 < EMA50 < EMA200) ────────────────────
            if ema_s < ema_m < ema_l:
                score += 20
                reasons.append(f"Triple EMA aligned down (EMA{self.EMA_SHORT} < EMA{self.EMA_MID} < EMA{self.EMA_LONG})")
            elif ema_s < ema_m and latest_close < ema_l:
                score += 10
                reasons.append("Price below EMA200 with Short < Mid EMA")
            else:
                reasons.append("EMAs not bearishly aligned")

            # ── 6. Trend Velocity & Supertrend Resistance ────────────────────
            if precomputed_indicators and "supertrend_line" in precomputed_indicators and "supertrend_dir" in precomputed_indicators:
                latest_st = float(precomputed_indicators["supertrend_line"])
                st_dir    = int(precomputed_indicators["supertrend_dir"])
            else:
                st_line, st_trend = ind.supertrend(
                    high, low, close,
                    period=self.ATR_PERIOD,
                    multiplier=self.SUPERTREND_MULTIPLIER,
                )
                latest_st = float(st_line[-1])
                st_dir    = int(st_trend[-1])

            is_supertrend_bear = (st_dir == -1 or latest_close < latest_st)
            is_adx_bear = (latest_adx >= self.ADX_MIN_STRENGTH and latest_minus_di > latest_plus_di)

            if is_supertrend_bear and is_adx_bear:
                score += 15
                reasons.append(f"Supertrend overhead resistance + Strong ADX downside velocity ({latest_adx:.1f})")
            elif is_supertrend_bear or is_adx_bear:
                score += 8
                reasons.append("Partial bearish trend velocity confirmed")
            else:
                reasons.append("Trend velocity filter not met")

            # ── 7. Institutional Distribution Volume Flow Surge ──────────────
            if precomputed_indicators and "rvol" in precomputed_indicators:
                latest_rvol = float(precomputed_indicators["rvol"])
            else:
                rvol_arr = ind.RVOL(volume, timeperiod=self.VOLUME_PERIOD) if np.sum(volume) > 0 else np.ones_like(close)
                latest_rvol = float(rvol_arr[-1]) if len(rvol_arr) > 0 else 1.0

            if precomputed_indicators and "cmf" in precomputed_indicators:
                latest_cmf = float(precomputed_indicators["cmf"])
            else:
                cmf_arr = ind.CMF(high, low, close, volume, timeperiod=20) if np.sum(volume) > 0 else np.zeros_like(close)
                latest_cmf = float(cmf_arr[-1]) if len(cmf_arr) > 0 else 0.0

            if latest_rvol >= self.RVOL_MIN_THRESHOLD or latest_cmf < -0.05:
                score += 15
                reasons.append(f"Institutional distribution surge (RVOL: {latest_rvol:.2f}x, CMF: {latest_cmf:.2f})")
            elif latest_rvol >= 1.0:
                score += 8
                reasons.append(f"Average volume confirmed (RVOL: {latest_rvol:.2f}x)")
            else:
                reasons.append(f"Sub-par volume (RVOL: {latest_rvol:.2f}x)")

            # ── 8. Bearish Candlestick Pattern Confirmation ──────────────────
            shooting_star = ind.CDLSHOOTINGSTAR(open_, high, low, close)
            evening_star  = ind.CDLEVENINGSTAR(open_, high, low, close)
            engulfing     = ind.CDLENGULFING(open_, high, low, close)
            marubozu      = ind.CDLMARUBOZU(open_, high, low, close)

            candle_pattern = "NONE"
            if shooting_star[-1] != 0:
                score += 10
                candle_pattern = "SHOOTING_STAR"
                reasons.append("Bearish Shooting Star candle confirmed")
            elif evening_star[-1] != 0:
                score += 10
                candle_pattern = "EVENING_STAR"
                reasons.append("Bearish Evening Star reversal confirmed")
            elif engulfing[-1] < 0:
                score += 10
                candle_pattern = "BEARISH_ENGULFING"
                reasons.append("Bearish Engulfing breakdown candle confirmed")
            elif marubozu[-1] < 0:
                score += 10
                candle_pattern = "BEARISH_MARUBOZU"
                reasons.append("Bearish Marubozu momentum breakdown confirmed")
            elif latest_close < float(low[-2]):
                score += 5
                candle_pattern = "BREAKDOWN_BAR"
                reasons.append("Breakdown close below prior bar low")
            else:
                reasons.append("No confirmation bearish candlestick pattern")

            # ── 9. Donchian 20-Day Low Structural Breakdown Bonus ────────────
            lookback_low_20 = float(np.min(low[-self.BREAKDOWN_LOOKBACK - 1 : -1]))
            if latest_close < lookback_low_20:
                score += 10
                reasons.append(f"20-day structural support breakdown (Below {lookback_low_20:.2f})")

            # ── 10. Multi-Timeframe Check (HTF Filter) ───────────────────────
            if higher_tf_df is not None and len(higher_tf_df) >= 50:
                htf_close = np.asarray(higher_tf_df["Close"], dtype=float)
                htf_ema50 = ind.EMA(htf_close, timeperiod=50)
                if htf_close[-1] > htf_ema50[-1]:
                    # Higher timeframe is still bullish — penalty on shorting
                    score = max(0, score - 15)
                    reasons.append("Higher timeframe (Daily) EMA50 bull trend penalty applied")

            # ── Score Gate Check ─────────────────────────────────────────────
            final_score = min(100.0, float(score))
            if final_score < self.MIN_SCORE:
                return None

            # ── ATR for Trade Levels & Risk Sizing ───────────────────────────
            if precomputed_indicators and "atr" in precomputed_indicators:
                latest_atr = float(precomputed_indicators["atr"])
            else:
                atr_vals = ind.ATR(high, low, close, timeperiod=self.ATR_PERIOD)
                latest_atr = float(atr_vals[-1])

            # ── Construct Strongly Typed Result Contract ─────────────────────
            return StrategySignalResult(
                strategy_id=self.name,
                strategy_version=self.version,
                symbol=symbol,
                signal_direction="SHORT",
                signal_type="SELL",
                technical_score=final_score,
                confidence=final_score,
                reasons=reasons,
                entry_price=round(latest_close, 2),
                timeframe=self.timeframe,
                asset_class=self.asset_class,
                atr=round(latest_atr, 4),
                candle_pattern=candle_pattern,
                indicator_values={
                    "rsi": round(latest_rsi, 2),
                    "adx": round(latest_adx, 2),
                    "atr": round(latest_atr, 4),
                    "rvol": round(latest_rvol, 2),
                    "cmf": round(latest_cmf, 4),
                    "ema_short": round(ema_s, 2),
                    "ema_mid": round(ema_m, 2),
                    "ema_long": round(ema_l, 2),
                    "supertrend": round(latest_st, 2),
                    "lookback_low_20": round(lookback_low_20, 2),
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
            logger.warning(f"[S06] generate_signal exception for {symbol}: {e}")
            return None

    def get_parameters(self) -> Dict[str, Any]:
        """All S06 parameters for MLflow/Optuna experiment tracking."""
        return {
            "strategy_id":            self.name,
            "version":                self.version,
            "rsi_period":             self.RSI_PERIOD,
            "rsi_min":                self.RSI_MIN,
            "rsi_max":                self.RSI_MAX,
            "rsi_power_min":          self.RSI_POWER_MIN,
            "rsi_hard_floor":         self.RSI_HARD_FLOOR,
            "macd_fast":              self.MACD_FAST,
            "macd_slow":              self.MACD_SLOW,
            "macd_signal":            self.MACD_SIGNAL,
            "ema_short":              self.EMA_SHORT,
            "ema_mid":                self.EMA_MID,
            "ema_long":               self.EMA_LONG,
            "adx_period":             self.ADX_PERIOD,
            "adx_min_strength":       self.ADX_MIN_STRENGTH,
            "atr_period":             self.ATR_PERIOD,
            "supertrend_multiplier":  self.SUPERTREND_MULTIPLIER,
            "rvol_period":            self.RVOL_PERIOD,
            "rvol_min_threshold":     self.RVOL_MIN_THRESHOLD,
            "breakdown_lookback":     self.BREAKDOWN_LOOKBACK,
            "min_score":              self.MIN_SCORE,
            "timeframe":              self.timeframe,
            "asset_class":            self.asset_class,
            "allowed_asset_classes":  list(self.allowed_asset_classes),
            "allowed_regimes":        list(self.allowed_regimes),
            "min_holding_days":       self.min_holding_days,
            "max_holding_days":       self.max_holding_days,
        }

    def get_description(self) -> str:
        """Human-readable description for alerts and research reports."""
        return (
            f"S06 Momentum Short v{self.version} — "
            f"Institutional swing breakdown: RSI {self.RSI_MIN:.0f}-{self.RSI_MAX:.0f}, "
            f"MACD negative acceleration, Triple EMA aligned down ({self.EMA_SHORT}/{self.EMA_MID}/{self.EMA_LONG}), "
            f"ADX>{self.ADX_MIN_STRENGTH:.0f} (-DI>+DI) + Supertrend resistance, RVOL>{self.RVOL_MIN_THRESHOLD:.1f}x distribution. "
            f"Min score {self.MIN_SCORE}/100. Holding window: {self.min_holding_days}-{self.max_holding_days} days."
        )
