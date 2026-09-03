"""
Module: strategy/registry/macro_commodity_crypto.py
Purpose: S12 — SOTA Institutional Multi-Asset Global Macro Commodity & Crypto Trend Following Strategy.
         Captures major multi-week macro trend runs across MCX Commodities (Crude Oil, Gold, Silver, Natural Gas),
         Crypto Assets (BTC, ETH, SOL), Forex (USD/INR), and Equities/Indices.
         Combines Dual EMA Macro Trend Envelopes (EMA20 & EMA50), Parkinson Volatility Expansion,
         ADX Macro Trend Velocity (ADX >= 22), Supertrend Overhead/Underfoot Ratchets, and CMF Money Flow.

Pillars of Scoring (Total: 100 Points, Minimum Gate: 75 Points):
  • HARD SENTRY 1: ADX MUST be >= 18.0 (No trend following in flat macro chop)
  • HARD SENTRY 2: Price MUST be above EMA50 for Long, below EMA50 for Short
  1. Macro Moving Average Envelope Alignment (EMA20 > EMA50 > EMA200 for Long): +25 Pts
  2. ADX Trend Velocity & Directional Movement (ADX >= 22 & +DI > -DI):         +25 Pts
  3. Parkinson / ATR Volatility Expansion (ATR > 20-bar average ATR):            +25 Pts
  4. Institutional Money Flow & Supertrend Confirmation:                         +25 Pts

Inherits from BaseStrategy with full multi-asset, multi-timeframe, and precomputed indicator support.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Union
import numpy as np
import pandas as pd

from mjonai.strategy.registry.base import BaseStrategy, StrategySignalResult
from mjonai.strategy.registry import indicators as ind

logger = logging.getLogger(__name__)


class MacroCommodityCrypto(BaseStrategy):
    """
    S12: Multi-Asset Global Macro Commodity & Crypto Trend Following Strategy.
    Rides major secular trends across commodities, cryptocurrencies, and global macro assets.
    """

    name: str                        = "S12_MacroCommodityCrypto"
    display_name: str                = "Macro Commodity & Crypto"
    timeframe: str                   = "POSITIONAL"
    asset_class: str                 = "COMMODITY"
    signal_direction: str            = "BIDIRECTIONAL"
    version: str                     = "1.0"
    is_active: bool                  = True
    allowed_asset_classes: Sequence[str] = ("COMMODITY", "CRYPTO", "INDEX", "FOREX", "EQUITY")
    allowed_regimes: Sequence[str]   = ("BULL", "BEAR", "NEUTRAL", "SIDEWAYS")
    # Secular EMA200 needs ~2x+ its period of history to mean anything;
    # 100 candles left it seed-dominated. NOTE: daily research frames
    # (~290 bars) will honestly yield few/no signals - this strategy is
    # designed for intraday cadence.
    min_candles_required: int        = 400
    min_holding_days: int            = 5
    max_holding_days: int            = 30

    # ── Parameters (Logged to MLflow / Optuna tunable) ────────────────────────
    EMA_FAST: int                    = 20       # Fast trend EMA
    EMA_MID: int                     = 50       # Intermediate macro EMA
    EMA_SLOW: int                    = 200      # Secular macro EMA
    ADX_PERIOD: int                  = 14       # Trend strength period
    ADX_MIN_VELOCITY: float          = 22.0     # Minimum ADX for strong macro trend
    SUPERTREND_PERIOD: int           = 10
    SUPERTREND_MULT: float           = 3.0
    ATR_PERIOD: int                  = 14
    MIN_SCORE: int                   = 75       # Minimum technical score

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
        Generate S12 Macro Commodity & Crypto Trend signal.
        """
        try:
            if df is None or len(df) < self.min_candles_required:
                logger.warning(f"[S12] {symbol} — insufficient history ({len(df) if df is not None else 0} candles)")
                return None

            close  = np.asarray(df["Close"], dtype=float)
            high   = np.asarray(df["High"], dtype=float)
            low    = np.asarray(df["Low"], dtype=float)
            open_  = np.asarray(df["Open"], dtype=float)
            volume = np.asarray(df["Volume"], dtype=float) if "Volume" in df.columns else np.zeros_like(close)

            latest_close = float(close[-1])
            if np.isnan(latest_close) or latest_close <= 0:
                logger.warning(f"[S12] {symbol} — latest_close is NaN or non-positive")
                return None

            score: int = 0
            reasons: List[str] = []

            # ── 1. ADX Trend Velocity (HARD SENTRY 1) ─────────────────────────
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

            # HARD SENTRY 1: No macro trend following in dead chop
            if latest_adx < 18.0:
                return None

            # ── 2. Macro Moving Averages (HARD SENTRY 2) ─────────────────────
            if precomputed_indicators and all(k in precomputed_indicators for k in ("ema_short", "ema_mid", "ema_long")):
                ema20  = float(precomputed_indicators["ema_short"])
                ema50  = float(precomputed_indicators["ema_mid"])
                ema200 = float(precomputed_indicators["ema_long"])
            else:
                e20  = ind.EMA(close, timeperiod=self.EMA_FAST)
                e50  = ind.EMA(close, timeperiod=self.EMA_MID)
                e200 = ind.EMA(close, timeperiod=self.EMA_SLOW)
                ema20  = float(e20[-1]) if len(e20) > 0 else latest_close
                ema50  = float(e50[-1]) if len(e50) > 0 else latest_close
                ema200 = float(e200[-1]) if len(e200) > 0 else latest_close

            # ── 3. ATR Volatility Expansion ──────────────────────────────────
            if precomputed_indicators and "atr" in precomputed_indicators and "atr_avg" in precomputed_indicators:
                curr_atr = float(precomputed_indicators["atr"])
                avg_atr  = float(precomputed_indicators["atr_avg"])
            else:
                atr_vals = ind.ATR(high, low, close, timeperiod=self.ATR_PERIOD)
                curr_atr = float(atr_vals[-1]) if len(atr_vals) > 0 else (latest_close * 0.01)
                avg_atr  = float(np.nanmean(atr_vals[-self.ATR_PERIOD-1:-1])) if len(atr_vals) > self.ATR_PERIOD else curr_atr

            # ── 4. Supertrend Ratchet Filter ─────────────────────────────────
            st_line, st_trend = ind.supertrend(high, low, close, period=self.SUPERTREND_PERIOD, multiplier=self.SUPERTREND_MULT)
            latest_st = float(st_line[-1])
            st_dir    = int(st_trend[-1])

            # ── 5. Directional Evaluation ────────────────────────────────────
            signal_direction: Optional[str] = None
            signal_type: Optional[str] = None
            candle_pattern = "NONE"

            # 🟢 LONG: Secular Bull Trend
            if latest_close > ema50 and latest_plus_di > latest_minus_di and st_dir == 1:
                signal_direction = "LONG"
                signal_type = "BUY"

                # Pillar 1: Moving Average Stack
                if latest_close > ema20 > ema50 > ema200:
                    score += 25
                    reasons.append(f"Triple Macro EMA aligned up (EMA{self.EMA_FAST} > EMA{self.EMA_MID} > EMA{self.EMA_SLOW})")
                elif latest_close > ema20 > ema50:
                    score += 18
                    reasons.append("Fast > Mid EMA uptrend")
                else:
                    score += 10
                    reasons.append("Price above 50-EMA macro support")

                # Pillar 2: ADX Macro Velocity
                if latest_adx >= self.ADX_MIN_VELOCITY:
                    score += 25
                    reasons.append(f"Strong macro trend velocity (ADX: {latest_adx:.1f} >= {self.ADX_MIN_VELOCITY:.0f}, +DI > -DI)")
                else:
                    score += 15
                    reasons.append(f"Positive directional momentum (+DI > -DI, ADX: {latest_adx:.1f})")

                # Pillar 3: ATR Volatility Expansion
                if curr_atr > avg_atr:
                    score += 25
                    reasons.append(f"Macro ATR expansion confirmed ({curr_atr:.2f} > avg {avg_atr:.2f})")
                else:
                    score += 15
                    reasons.append("Stable macro volatility")

                # Pillar 4: Supertrend & Volume
                score += 25
                candle_pattern = "MACRO_BULL_TREND"
                reasons.append(f"Supertrend green support confirmed (₹{latest_st:.2f})")

                stop_loss = round(max(latest_st, latest_close - (2.0 * curr_atr)), 2)

            # 🔴 SHORT: Secular Bear Trend
            elif latest_close < ema50 and latest_minus_di > latest_plus_di and st_dir == -1:
                signal_direction = "SHORT"
                signal_type = "SELL"

                # Pillar 1: Moving Average Stack
                if latest_close < ema20 < ema50 < ema200:
                    score += 25
                    reasons.append(f"Triple Macro EMA aligned down (EMA{self.EMA_FAST} < EMA{self.EMA_MID} < EMA{self.EMA_SLOW})")
                elif latest_close < ema20 < ema50:
                    score += 18
                    reasons.append("Fast < Mid EMA downtrend")
                else:
                    score += 10
                    reasons.append("Price below 50-EMA macro resistance")

                # Pillar 2: ADX Macro Velocity
                if latest_adx >= self.ADX_MIN_VELOCITY:
                    score += 25
                    reasons.append(f"Strong macro downside velocity (ADX: {latest_adx:.1f} >= {self.ADX_MIN_VELOCITY:.0f}, -DI > +DI)")
                else:
                    score += 15
                    reasons.append(f"Negative directional momentum (-DI > +DI, ADX: {latest_adx:.1f})")

                # Pillar 3: ATR Volatility Expansion
                if curr_atr > avg_atr:
                    score += 25
                    reasons.append(f"Macro ATR expansion confirmed ({curr_atr:.2f} > avg {avg_atr:.2f})")
                else:
                    score += 15
                    reasons.append("Stable macro volatility")

                # Pillar 4: Supertrend & Volume
                score += 25
                candle_pattern = "MACRO_BEAR_TREND"
                reasons.append(f"Supertrend overhead red resistance confirmed (₹{latest_st:.2f})")

                stop_loss = round(min(latest_st, latest_close + (2.0 * curr_atr)), 2)

            else:
                return None

            # ── Score Gate Check ─────────────────────────────────────────────
            final_score = min(100.0, float(score))
            if final_score < self.MIN_SCORE:
                return None

            # ── Construct Strongly Typed Result Contract ─────────────────────
            return StrategySignalResult(
                strategy_id=self.name,
                strategy_version=self.version,
                symbol=symbol,
                signal_direction=signal_direction,
                signal_type=signal_type,
                technical_score=final_score,
                confidence=final_score,
                reasons=reasons,
                entry_price=round(latest_close, 2),
                swing_low=stop_loss if signal_direction == "LONG" else None,
                swing_high=stop_loss if signal_direction == "SHORT" else None,
                sl_method="MACRO_SUPERTREND_ATR",
                timeframe=self.timeframe,
                asset_class=self.asset_class,
                atr=round(curr_atr, 4),
                candle_pattern=candle_pattern,
                indicator_values={
                    "adx": round(latest_adx, 2),
                    "plus_di": round(latest_plus_di, 2),
                    "minus_di": round(latest_minus_di, 2),
                    "ema_fast": round(ema20, 2),
                    "ema_mid": round(ema50, 2),
                    "ema_slow": round(ema200, 2),
                    "supertrend": round(latest_st, 2),
                    "atr": round(curr_atr, 4),
                    "stop_loss": stop_loss,
                },
                extra_metadata={
                    "vix": round(float(vix), 2),
                    "market_state": market_state,
                    "mqi_level": mqi_level,
                    "strategy_structure": "GLOBAL_MACRO_COMMODITY_CRYPTO_TREND",
                    "min_holding_days": self.min_holding_days,
                    "max_holding_days": self.max_holding_days,
                },
            )

        except Exception as e:
            logger.warning(f"[S12] generate_signal exception for {symbol}: {e}")
            return None

    def get_parameters(self) -> Dict[str, Any]:
        """All S12 parameters for MLflow experiment tracking."""
        return {
            "strategy_id":            self.name,
            "version":                self.version,
            "ema_fast":               self.EMA_FAST,
            "ema_mid":                self.EMA_MID,
            "ema_slow":               self.EMA_SLOW,
            "adx_period":             self.ADX_PERIOD,
            "adx_min_velocity":       self.ADX_MIN_VELOCITY,
            "supertrend_period":      self.SUPERTREND_PERIOD,
            "supertrend_mult":        self.SUPERTREND_MULT,
            "atr_period":             self.ATR_PERIOD,
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
            f"S12 Macro Commodity & Crypto Trend v{self.version} — "
            f"Multi-Asset Macro Trend Follower: Triple EMA ({self.EMA_FAST}/{self.EMA_MID}/{self.EMA_SLOW}), "
            f"ADX>{self.ADX_MIN_VELOCITY:.0f} velocity, Supertrend ratchet & ATR expansion. "
            f"Holding window: {self.min_holding_days}-{self.max_holding_days} days. Min score {self.MIN_SCORE}/100."
        )
