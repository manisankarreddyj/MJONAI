"""
Module: strategy/registry/mean_reversion_short.py
Purpose: S07 — SOTA Institutional Multi-Asset Mean Reversion Short Strategy.
         Fades overbought counter-trend relief rallies ("Selling the Rip") in secularly downtrending assets.
         Combines Larry Connors' Dual-Period Overbought RSI (RSI14 & Fast RSI2), 50-EMA Resistance Retest Kiss,
         Wyckoff Upthrust Rejections, Statistical Volatility Displacement (Upper BB & ATR),
         Buying Climax Flow (RVOL & CMF), and Consecutive Up-Day Exhaustion.

Pillars of Scoring (Total: 100 Points, Minimum Gate: 70 Points):
  • HARD SENTRY 1: Price MUST be below EMA200 (Secular Macro Downtrend)
  • HARD SENTRY 2: RSI(14) MUST be in relief rally overbought territory (RSI14 >= 62.0 or Fast RSI2 >= 90.0)
  1. Multi-Period RSI Exhaustion (RSI14 >= 70 or Connors Fast RSI2 >= 90): +25 Pts
  2. Statistical Volatility Stretch (Close >= BB Upper or Stretch >= 1.8 ATR): +25 Pts
  3. Buying Climax Volume Flow (RVOL >= 1.30x or CMF Divergence):          +25 Pts
  4. Bearish Price Action Rejection (Shooting Star / Wyckoff Upthrust):   +20 Pts
  * Bonus 1 (+15 Pts): Overhead 50-EMA Resistance Retest Kiss
  * Bonus 2 (+10 Pts): Consecutive Up-Days Exhaustion (>= 3 consecutive green bars)

Inherits from BaseStrategy with full multi-asset, multi-timeframe, and precomputed indicator support.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Union
import numpy as np
import pandas as pd

from mjonai.strategy.registry.base import BaseStrategy, StrategySignalResult
from mjonai.strategy.registry import indicators as ind

logger = logging.getLogger(__name__)


class MeanReversionShort(BaseStrategy):
    """
    S07 — Mean Reversion Short Strategy.

    Research targets:
        Win rate > 55%
        Best regime: BEAR / NEUTRAL (Fading overbought relief rips into resistance)
        Worst regime: BULL market strong expansion (Short squeeze risk)
        IC target: > 0.05 (Alphalens)
    """

    name: str                        = "S07_MeanReversionShort"
    display_name: str                = "Mean Reversion Short"
    timeframe: str                   = "SWING"
    asset_class: str                 = "EQUITY"
    signal_direction: str            = "SHORT"
    version: str                     = "2.3"
    is_active: bool                  = True
    allowed_asset_classes: Sequence[str] = ("EQUITY", "INDEX", "COMMODITY", "CRYPTO", "FOREX")
    allowed_regimes: Sequence[str]   = ("BEAR", "NEUTRAL", "SIDEWAYS")
    min_candles_required: int        = 210
    min_holding_days: int            = 2
    max_holding_days: int            = 7

    # ── Parameters (Logged to MLflow / Optuna tunable) ────────────────────────
    RSI_PERIOD: int                  = 14
    RSI_FAST_PERIOD: int             = 2        # Larry Connors fast RSI
    RSI_OVERBOUGHT_DEEP: float       = 70.0     # Deep overbought threshold for RSI(14)
    RSI_OVERBOUGHT_MIN: float        = 62.0     # Relief rally overbought floor in bear market
    RSI_FAST_OVERBOUGHT: float       = 90.0     # Extreme fast exhaustion threshold for RSI(2)

    BB_PERIOD: int                   = 20       # Bollinger Band period
    BB_STD: float                    = 2.0      # Standard deviations
    EMA_SHORT: int                   = 20       # Baseline mean period
    EMA_MID: int                     = 50       # 50-day EMA resistance level
    EMA_LONG: int                    = 200      # Macro trend sentry (EMA200)

    VOLUME_PERIOD: int               = 20       # Volume average period
    VOLUME_SPIKE: float              = 1.30     # Buying climax volume surge multiplier (1.30x)
    ATR_PERIOD: int                  = 14       # ATR period for stretch and sizing
    ATR_STRETCH_MULT: float          = 1.8      # Minimum ATR stretch above 20-EMA
    CONSECUTIVE_UP_DAYS: int         = 3        # Minimum up days for exhaustion bonus

    MIN_SCORE: int                   = 70       # Minimum technical score

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
        Generate S07 Mean Reversion Short signal for given symbol and market conditions.
        """
        try:
            # 1. Validate DataFrame minimum history (adaptive if higher_tf_df or precomputed indicators available)
            min_req = min(self.min_candles_required, 30) if (higher_tf_df is not None and len(higher_tf_df) >= 100) or (precomputed_indicators and "ema_long" in precomputed_indicators) else self.min_candles_required
            is_valid, reason = self.validate_ohlcv_dataframe(df, min_candles=min_req)
            if not is_valid:
                logger.warning(f"[S07] {symbol} — {reason}")
                return None

            close  = np.asarray(df["Close"], dtype=float)
            high   = np.asarray(df["High"], dtype=float)
            low    = np.asarray(df["Low"], dtype=float)
            open_  = np.asarray(df["Open"], dtype=float)
            volume = np.asarray(df["Volume"], dtype=float) if "Volume" in df.columns else np.zeros_like(close)

            score: int = 0
            reasons: List[str] = []

            # ── 1. EMA200 Macro Trend Filter (HARD SENTRY 1) ─────────────────
            if precomputed_indicators and "ema_long" in precomputed_indicators:
                latest_ema200 = float(precomputed_indicators["ema_long"])
            elif higher_tf_df is not None and len(higher_tf_df) >= 50:
                htf_close = np.asarray(higher_tf_df["Close"], dtype=float)
                period_to_use = min(self.EMA_LONG, len(htf_close))
                ema200_arr = ind.EMA(htf_close, timeperiod=period_to_use)
                latest_ema200 = float(ema200_arr[-1]) if len(ema200_arr) > 0 else float("nan")
            else:
                ema200 = ind.EMA(close, timeperiod=self.EMA_LONG)
                latest_ema200 = float(ema200[-1]) if len(ema200) > 0 else float("nan")

            if np.isnan(latest_ema200):
                logger.warning(f"[S07] {symbol} — EMA200 is NaN")
                return None

            latest_close = float(close[-1])
            if np.isnan(latest_close) or latest_close <= 0:
                logger.warning(f"[S07] {symbol} — latest_close is NaN or non-positive")
                return None

            # HARD SENTRY: Cannot short overbought rips in stocks above 200 EMA (bull trends)
            if latest_close >= latest_ema200:
                return None

            # ── 2. Dual-Period RSI (RSI14 & Connors Fast RSI2) (HARD SENTRY 2)
            if precomputed_indicators and "rsi" in precomputed_indicators:
                latest_rsi = float(precomputed_indicators["rsi"])
            else:
                rsi14 = ind.RSI(close, timeperiod=self.RSI_PERIOD)
                latest_rsi = float(rsi14[-1]) if len(rsi14) > 0 else float("nan")

            if precomputed_indicators and "rsi_fast" in precomputed_indicators:
                latest_rsi_fast = float(precomputed_indicators["rsi_fast"])
            else:
                rsi2 = ind.RSI(close, timeperiod=self.RSI_FAST_PERIOD)
                latest_rsi_fast = float(rsi2[-1]) if len(rsi2) > 0 else float("nan")

            if np.isnan(latest_rsi):
                logger.warning(f"[S07] {symbol} — RSI is NaN")
                return None

            # HARD SENTRY: Must be within relief rally overbought territory
            if latest_rsi < self.RSI_OVERBOUGHT_MIN and (np.isnan(latest_rsi_fast) or latest_rsi_fast < self.RSI_FAST_OVERBOUGHT):
                return None

            # Score RSI exhaustion
            if latest_rsi >= self.RSI_OVERBOUGHT_DEEP or latest_rsi_fast >= self.RSI_FAST_OVERBOUGHT:
                score += 25
                reasons.append(f"Deep overbought RSI exhaustion (RSI14: {latest_rsi:.1f}, Fast RSI2: {latest_rsi_fast:.1f})")
            else:
                score += 15
                reasons.append(f"Bear market relief rally RSI (RSI14: {latest_rsi:.1f} >= {self.RSI_OVERBOUGHT_MIN:.0f})")

            # ── 3. ATR Volatility & Statistical Stretch ──────────────────────
            if precomputed_indicators and "atr" in precomputed_indicators:
                latest_atr = float(precomputed_indicators["atr"])
            else:
                atr_vals = ind.ATR(high, low, close, timeperiod=self.ATR_PERIOD)
                latest_atr = float(atr_vals[-1]) if len(atr_vals) > 0 else 0.0

            if np.isnan(latest_atr) or latest_atr <= 0:
                logger.warning(f"[S07] {symbol} — NaN or zero ATR")
                return None

            # ── 4. Bollinger Bands & ATR Distance Stretch ────────────────────
            if precomputed_indicators and all(k in precomputed_indicators for k in ("bb_upper", "bb_middle", "bb_lower")):
                latest_upper  = float(precomputed_indicators["bb_upper"])
                latest_middle = float(precomputed_indicators["bb_middle"])
                latest_lower  = float(precomputed_indicators["bb_lower"])
            else:
                upper, middle, lower = ind.BBANDS(
                    close,
                    timeperiod=self.BB_PERIOD,
                    nbdevup=self.BB_STD,
                    nbdevdn=self.BB_STD,
                )
                latest_upper  = float(upper[-1])
                latest_middle = float(middle[-1])
                latest_lower  = float(lower[-1])

            bb_range = latest_upper - latest_lower
            bb_pct = round((latest_close - latest_lower) / (bb_range + 1e-10) * 100.0, 1)

            # Measure upward distance stretch from 20-period baseline in ATR units
            mean_dist = (latest_close - latest_middle) / latest_atr

            if latest_close >= latest_upper or mean_dist >= self.ATR_STRETCH_MULT:
                score += 25
                reasons.append(f"Statistical volatility stretch confirmed (BB%: {bb_pct}%, Stretch: {mean_dist:.1f} ATR)")
            elif latest_close >= latest_middle:
                score += 12
                reasons.append(f"Price above 20-day mean (BB%: {bb_pct}%)")
            else:
                reasons.append("Price below 20-day mean")

            # ── 5. Buying Climax Volume Flow Surge ───────────────────────────
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

            # CMF < 0 is true on ~half of all bars - it cannot be the
            # sole trigger for the +25 climax pillar. Require a strongly
            # negative CMF (real distribution) instead.
            if latest_rvol >= self.VOLUME_SPIKE or latest_cmf <= -0.10:
                score += 25
                reasons.append(f"Buying climax volume surge (RVOL: {latest_rvol:.2f}x >= {self.VOLUME_SPIKE:.2f}x, CMF: {latest_cmf:.2f})")
            elif latest_rvol >= 1.0:
                score += 12
                reasons.append(f"Standard volume confirmed (RVOL: {latest_rvol:.2f}x)")
            else:
                reasons.append(f"Low volume rally (RVOL: {latest_rvol:.2f}x)")

            # ── 6. Bearish Price Action Rejection Trigger ────────────────────
            latest_open = float(open_[-1])
            latest_high = float(high[-1])
            latest_low  = float(low[-1])
            body = abs(latest_close - latest_open)
            upper_shadow = latest_high - max(latest_open, latest_close)

            shooting_star = ind.CDLSHOOTINGSTAR(open_, high, low, close)
            evening_star  = ind.CDLEVENINGSTAR(open_, high, low, close)
            engulfing     = ind.CDLENGULFING(open_, high, low, close)
            doji          = ind.CDLDOJI(open_, high, low, close)

            candle_pattern = "NONE"
            if upper_shadow >= 2.0 * (body + 1e-5) and latest_rvol >= 1.30:
                score += 25
                candle_pattern = "WYCKOFF_UPTHRUST"
                reasons.append("Wyckoff Upthrust rejection at resistance confirmed")
            elif shooting_star[-1] != 0:
                score += 20
                candle_pattern = "SHOOTING_STAR"
                reasons.append("Bearish Shooting Star rejection candle confirmed")
            elif evening_star[-1] != 0:
                score += 20
                candle_pattern = "EVENING_STAR"
                reasons.append("Bearish Evening Star reversal confirmed")
            elif engulfing[-1] < 0:
                score += 20
                candle_pattern = "BEARISH_ENGULFING"
                reasons.append("Bearish Engulfing reversal confirmed")
            elif doji[-1] != 0:
                score += 15
                candle_pattern = "DOJI"
                reasons.append("Indecision Doji candle at highs")
            # Any red bar used to earn +15 here; require real upper-wick
            # rejection evidence instead.
            elif upper_shadow >= 1.5 * (body + 1e-5):
                score += 15
                candle_pattern = "BEARISH_REJECTION"
                reasons.append("Bearish upper wick rejection confirmed")
            else:
                reasons.append("No rejection candlestick confirmation")

            # ── 7. Overhead 50-EMA Resistance Retest Kiss ────────────────────
            if precomputed_indicators and "ema_mid" in precomputed_indicators:
                latest_ema50 = float(precomputed_indicators["ema_mid"])
            else:
                ema50 = ind.EMA(close, timeperiod=self.EMA_MID)
                latest_ema50 = float(ema50[-1]) if len(ema50) > 0 else float("nan")

            if not np.isnan(latest_ema50) and (abs(latest_high - latest_ema50) <= (0.75 * latest_atr) or (latest_high >= latest_ema50 and latest_close < latest_ema50)):
                score += 15
                reasons.append(f"Overhead EMA50 resistance retest kiss confirmed (EMA50: {latest_ema50:.2f})")

            # ── 8. Consecutive Up-Days Exhaustion Bonus ──────────────────────
            consecutive_up = 0
            # Include the SIGNAL bar itself (off-by-one: the old loop
            # started one bar back and ignored today's candle).
            for i in range(len(close) - 1, max(1, len(close) - 8), -1):
                if close[i] > close[i - 1]:
                    consecutive_up += 1
                else:
                    break

            if consecutive_up >= self.CONSECUTIVE_UP_DAYS:
                score += 10
                reasons.append(f"Rally exhaustion bonus ({consecutive_up} consecutive green days)")

            # ── 9. Multi-Timeframe Filter (HTF Trend Alignment) ──────────────
            if higher_tf_df is not None and len(higher_tf_df) >= 50:
                htf_close = np.asarray(higher_tf_df["Close"], dtype=float)
                htf_ema50 = ind.EMA(htf_close, timeperiod=50)
                if htf_close[-1] > htf_ema50[-1]:
                    score = max(0, score - 15)
                    reasons.append("Higher timeframe (Daily) EMA50 bull trend penalty applied")

            # ── Score Gate Check ─────────────────────────────────────────────
            final_score = min(100.0, float(score))
            if final_score < self.MIN_SCORE:
                return None

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
                    "rsi_fast": round(latest_rsi_fast, 2) if not np.isnan(latest_rsi_fast) else 0.0,
                    "atr": round(latest_atr, 4),
                    "rvol": round(latest_rvol, 2),
                    "cmf": round(latest_cmf, 4),
                    "bb_pct": bb_pct,
                    "ema_mid": round(latest_ema50, 2) if not np.isnan(latest_ema50) else 0.0,
                    "ema_long": round(latest_ema200, 2),
                },
                extra_metadata={
                    "vix": round(float(vix), 2),
                    "market_state": market_state,
                    "mqi_level": mqi_level,
                    "consecutive_up_days": consecutive_up,
                    "min_holding_days": self.min_holding_days,
                    "max_holding_days": self.max_holding_days,
                },
            )

        except Exception as e:
            logger.warning(f"[S07] generate_signal exception for {symbol}: {e}")
            return None

    def get_parameters(self) -> Dict[str, Any]:
        """All S07 parameters for MLflow experiment tracking."""
        return {
            "strategy_id":            self.name,
            "version":                self.version,
            "rsi_period":             self.RSI_PERIOD,
            "rsi_fast_period":        self.RSI_FAST_PERIOD,
            "rsi_overbought_deep":    self.RSI_OVERBOUGHT_DEEP,
            "rsi_overbought_min":     self.RSI_OVERBOUGHT_MIN,
            "rsi_fast_overbought":    self.RSI_FAST_OVERBOUGHT,
            "bb_period":              self.BB_PERIOD,
            "bb_std":                 self.BB_STD,
            "volume_period":          self.VOLUME_PERIOD,
            "volume_spike":           self.VOLUME_SPIKE,
            "ema_mid":                self.EMA_MID,
            "ema_long":               self.EMA_LONG,
            "atr_period":             self.ATR_PERIOD,
            "atr_stretch_mult":       self.ATR_STRETCH_MULT,
            "consecutive_up_days":    self.CONSECUTIVE_UP_DAYS,
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
            f"S07 Mean Reversion Short v{self.version} — "
            f"Overbought relief rally fade in secular downtrend: Dual RSI (RSI14>={self.RSI_OVERBOUGHT_MIN:.0f} / RSI2>={self.RSI_FAST_OVERBOUGHT:.0f}), "
            f"at BB upper or >={self.ATR_STRETCH_MULT}x ATR stretch, EMA50 resistance kiss, "
            f"buying climax volume spike >={self.VOLUME_SPIKE:.2f}x, "
            f"below EMA{self.EMA_LONG}. Min score {self.MIN_SCORE}/100. Swing trades {self.min_holding_days}-{self.max_holding_days} days."
        )
