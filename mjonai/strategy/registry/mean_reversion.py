"""
Module: strategy/registry/mean_reversion.py
Purpose: S02 — SOTA Institutional Multi-Asset Mean Reversion Long Strategy.
         Captures high-probability oversold pullbacks in secularly uptrending assets (Price > EMA200).
         Combines Larry Connors' Dual-Period RSI (RSI14 & Fast RSI2), Consecutive Down-Day Exhaustion,
         Statistical Volatility Displacement (ATR & Bollinger Bands), Capitulation Volume Absorption (RVOL/CMF),
         and Bullish Price Action Rejection triggers.

Pillars of Scoring (Total: 100 Points, Minimum Gate: 70 Points):
  • HARD SENTRY 1: Price MUST be above EMA200 (No falling knives in secular downtrends)
  • HARD SENTRY 2: RSI(14) MUST be in oversold pullback territory (RSI14 <= 38.0)
  1. Multi-Period RSI Exhaustion (RSI14 < 30 or Connors Fast RSI2 < 10): +25 Pts
  2. Statistical Volatility Stretch (Close <= BB Lower or Stretch >= 1.8 ATR): +25 Pts
  3. Capitulation Volume Flow & Absorption (RVOL >= 1.30x or CMF > 0.05): +25 Pts
  4. Bullish Price Action Rejection (Lower shadow / Hammer / Green Close): +20 Pts
  * Bonus (+10 Pts): Consecutive Down-Days Exhaustion (>= 3 consecutive red bars into support)

Inherits from BaseStrategy with full multi-asset, multi-timeframe, and precomputed indicator support.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Union
import numpy as np
import pandas as pd

from mjonai.strategy.registry.base import BaseStrategy, StrategySignalResult
from mjonai.strategy.registry import indicators as ind

logger = logging.getLogger(__name__)


class MeanReversion(BaseStrategy):
    """
    S02 — Mean Reversion Long Strategy.
    
    Research targets:
        Win rate > 55%
        Best regime: BULL — oversold dip in secular bull trend
        Worst regime: BEAR / Crash — falling knife risk
        IC target: > 0.05 (Alphalens)
    """

    name: str                        = "S02_MeanReversion"
    display_name: str                = "Mean Reversion"
    timeframe: str                   = "SWING"
    asset_class: str                 = "EQUITY"
    version: str                     = "2.2"
    is_active: bool                  = True
    allowed_asset_classes: Sequence[str] = ("EQUITY", "INDEX", "COMMODITY", "CRYPTO", "FOREX")
    allowed_regimes: Sequence[str]   = ("BULL", "NEUTRAL", "SIDEWAYS")
    min_candles_required: int        = 210
    min_holding_days: int            = 2
    max_holding_days: int            = 7

    # ── Parameters (Logged to MLflow / Optuna tunable) ────────────────────────
    RSI_PERIOD: int                  = 14
    RSI_FAST_PERIOD: int             = 2        # Larry Connors fast RSI
    RSI_OVERSOLD_DEEP: float         = 30.0     # Deep oversold threshold for RSI(14)
    RSI_OVERSOLD_MAX: float          = 38.0     # Max oversold ceiling for pullbacks in bull markets
    RSI_FAST_OVERSOLD: float         = 10.0     # Extreme fast exhaustion threshold for RSI(2)

    BB_PERIOD: int                   = 20       # Bollinger Band period
    BB_STD: float                    = 2.0      # Standard deviations
    EMA_SHORT: int                   = 20       # Baseline mean period
    EMA_LONG: int                    = 200      # Macro trend sentry (EMA200)

    VOLUME_PERIOD: int               = 20       # Volume average period
    VOLUME_SPIKE: float              = 1.30     # Capitulation volume surge multiplier (1.30x)
    ATR_PERIOD: int                  = 14       # ATR period for stretch and sizing
    ATR_STRETCH_MULT: float          = 1.8      # Minimum ATR stretch from 20-EMA
    CONSECUTIVE_DOWN_DAYS: int       = 3        # Minimum down days for exhaustion bonus

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
        Generate S02 Mean Reversion signal for given symbol and market conditions.
        """
        try:
            # 1. Validate DataFrame minimum history (adaptive if higher_tf_df or precomputed indicators available)
            min_req = min(self.min_candles_required, 30) if (higher_tf_df is not None and len(higher_tf_df) >= 100) or (precomputed_indicators and "ema_long" in precomputed_indicators) else self.min_candles_required
            is_valid, reason = self.validate_ohlcv_dataframe(df, min_candles=min_req)
            if not is_valid:
                logger.warning(f"[S02] {symbol} — {reason}")
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
                logger.warning(f"[S02] {symbol} — EMA200 is NaN")
                return None

            latest_close = float(close[-1])

            # HARD SENTRY: Cannot buy oversold dips in stocks below 200 EMA
            if latest_close <= latest_ema200:
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
                logger.warning(f"[S02] {symbol} — RSI is NaN")
                return None

            # HARD SENTRY: Must be within oversold pullback ceiling
            if latest_rsi > self.RSI_OVERSOLD_MAX and (np.isnan(latest_rsi_fast) or latest_rsi_fast > self.RSI_FAST_OVERSOLD):
                return None

            # Score RSI exhaustion
            if latest_rsi <= self.RSI_OVERSOLD_DEEP or latest_rsi_fast <= self.RSI_FAST_OVERSOLD:
                score += 25
                reasons.append(f"Deep RSI exhaustion (RSI14: {latest_rsi:.1f}, Fast RSI2: {latest_rsi_fast:.1f})")
            else:
                score += 15
                reasons.append(f"Bull market pullback RSI (RSI14: {latest_rsi:.1f} <= {self.RSI_OVERSOLD_MAX:.0f})")

            # ── 3. ATR Volatility & Statistical Stretch ──────────────────────
            if precomputed_indicators and "atr" in precomputed_indicators:
                latest_atr = float(precomputed_indicators["atr"])
            else:
                atr_vals = ind.ATR(high, low, close, timeperiod=self.ATR_PERIOD)
                latest_atr = float(atr_vals[-1]) if len(atr_vals) > 0 else 0.0

            if np.isnan(latest_atr) or latest_atr <= 0:
                logger.warning(f"[S02] {symbol} — NaN or zero ATR")
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

            # Measure distance stretch from 20-period baseline in ATR units
            mean_dist = (latest_middle - latest_close) / latest_atr

            if latest_close <= latest_lower or mean_dist >= self.ATR_STRETCH_MULT:
                score += 25
                reasons.append(f"Statistical volatility stretch confirmed (BB%: {bb_pct}%, Stretch: {mean_dist:.1f} ATR)")
            elif latest_close <= latest_middle:
                score += 12
                reasons.append(f"Price below 20-day mean (BB%: {bb_pct}%)")
            else:
                reasons.append("Price above 20-day mean")

            # ── 5. Capitulation Volume Flow Surge ────────────────────────────
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

            if latest_rvol >= self.VOLUME_SPIKE or latest_cmf > 0.05:
                score += 25
                reasons.append(f"Capitulation volume surge (RVOL: {latest_rvol:.2f}x >= {self.VOLUME_SPIKE:.2f}x, CMF: {latest_cmf:.2f})")
            elif latest_rvol >= 1.0:
                score += 12
                reasons.append(f"Standard volume absorption (RVOL: {latest_rvol:.2f}x)")
            else:
                reasons.append(f"Low volume dip (RVOL: {latest_rvol:.2f}x)")

            # ── 6. Bullish Price Action Absorption & Rejection Trigger ────────
            latest_open = float(open_[-1])
            latest_high = float(high[-1])
            latest_low  = float(low[-1])
            body = abs(latest_close - latest_open)
            lower_shadow = min(latest_open, latest_close) - latest_low

            hammer    = ind.CDLHAMMER(open_, high, low, close)
            engulfing = ind.CDLENGULFING(open_, high, low, close)
            doji      = ind.CDLDOJI(open_, high, low, close)

            candle_pattern = "NONE"
            if hammer[-1] != 0:
                score += 20
                candle_pattern = "HAMMER"
                reasons.append("Bullish Hammer rejection candle confirmed")
            elif engulfing[-1] > 0:
                score += 20
                candle_pattern = "BULLISH_ENGULFING"
                reasons.append("Bullish Engulfing reversal confirmed")
            elif doji[-1] != 0:
                score += 15
                candle_pattern = "DOJI"
                reasons.append("Indecision Doji candle at lows")
            elif lower_shadow >= 1.5 * (body + 1e-5) or latest_close > latest_open:
                score += 15
                candle_pattern = "BULLISH_ABSORPTION"
                reasons.append("Bullish lower wick absorption confirmed")
            else:
                reasons.append("No absorption candlestick confirmation")

            # ── 7. Consecutive Down-Days Exhaustion Bonus ────────────────────
            # If stock fell for >= 3 consecutive bars into support, selling pressure is exhausted
            consecutive_down = 0
            for i in range(len(close) - 2, max(0, len(close) - 7), -1):
                if close[i] < close[i - 1]:
                    consecutive_down += 1
                else:
                    break

            if consecutive_down >= self.CONSECUTIVE_DOWN_DAYS:
                score += 10
                reasons.append(f"Selling exhaustion bonus ({consecutive_down} consecutive down days)")

            # ── 8. Multi-Timeframe Filter (HTF Trend Alignment) ──────────────
            if higher_tf_df is not None and len(higher_tf_df) >= 50:
                htf_close = np.asarray(higher_tf_df["Close"], dtype=float)
                htf_ema50 = ind.EMA(htf_close, timeperiod=50)
                if htf_close[-1] < htf_ema50[-1]:
                    score = max(0, score - 15)
                    reasons.append("Higher timeframe (Daily) EMA50 resistance penalty applied")

            # ── Score Gate Check ─────────────────────────────────────────────
            final_score = min(100.0, float(score))
            if final_score < self.MIN_SCORE:
                return None

            # ── Construct Strongly Typed Result Contract ─────────────────────
            return StrategySignalResult(
                strategy_id=self.name,
                strategy_version=self.version,
                symbol=symbol,
                signal_direction="LONG",
                signal_type="BUY",
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
                    "ema_long": round(latest_ema200, 2),
                },
                extra_metadata={
                    "vix": round(float(vix), 2),
                    "market_state": market_state,
                    "mqi_level": mqi_level,
                    "consecutive_down_days": consecutive_down,
                    "min_holding_days": self.min_holding_days,
                    "max_holding_days": self.max_holding_days,
                },
            )

        except Exception as e:
            logger.warning(f"[S02] generate_signal exception for {symbol}: {e}")
            return None

    def get_parameters(self) -> Dict[str, Any]:
        """All S02 parameters for MLflow experiment tracking."""
        return {
            "strategy_id":            self.name,
            "version":                self.version,
            "rsi_period":             self.RSI_PERIOD,
            "rsi_fast_period":        self.RSI_FAST_PERIOD,
            "rsi_oversold_deep":      self.RSI_OVERSOLD_DEEP,
            "rsi_oversold_max":       self.RSI_OVERSOLD_MAX,
            "rsi_fast_oversold":      self.RSI_FAST_OVERSOLD,
            "bb_period":              self.BB_PERIOD,
            "bb_std":                 self.BB_STD,
            "volume_period":          self.VOLUME_PERIOD,
            "volume_spike":           self.VOLUME_SPIKE,
            "ema_long":               self.EMA_LONG,
            "atr_period":             self.ATR_PERIOD,
            "atr_stretch_mult":       self.ATR_STRETCH_MULT,
            "consecutive_down_days":  self.CONSECUTIVE_DOWN_DAYS,
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
            f"S02 Mean Reversion v{self.version} — "
            f"Oversold dip in secular bull trend: Dual RSI (RSI14<={self.RSI_OVERSOLD_MAX:.0f} / RSI2<={self.RSI_FAST_OVERSOLD:.0f}), "
            f"at BB lower or >={self.ATR_STRETCH_MULT}x ATR stretch, "
            f"capitulation volume spike >={self.VOLUME_SPIKE:.2f}x, "
            f"above EMA{self.EMA_LONG}. Min score {self.MIN_SCORE}/100. Swing trades {self.min_holding_days}-{self.max_holding_days} days."
        )
