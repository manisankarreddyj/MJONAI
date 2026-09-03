"""
Module: strategy/registry/intraday_all_day.py
Purpose: S08 — SOTA Institutional Multi-Asset All-Day Intraday & Scalping Strategy.
         Continuously scans intraday 5m and 15m candles throughout the trading session (9:15 AM - 3:15 PM IST).
         Features Multi-Mode Execution:
           1. Consolidation Box Breakout (any time of day)
           2. Opening Range Breakout (ORB 15-30 min)
           3. VWAP Pullback & Rejection Bounces
         Combines Cumulative Intraday Anchored VWAP & ±1σ SD Bands, 9/21 EMA Intraday Momentum Ribbons,
         Daily Central Pivot Range (CPR) Confluence, Institutional RVOL Surges, and Fast 1:1.8 R:R profit targets.

Pillars of Scoring (Total: 100 Points, Minimum Gate: 70 Points):
  • HARD SENTRY 1: Clean VWAP Alignment (Long requires Close > VWAP, Short requires Close < VWAP)
  • HARD SENTRY 2: Minimum Intraday Bars Required (>= 30 candles on 5m/15m)
  1. Consolidation Box / ORB / Extreme Breakout (Close > Box High or < Box Low): +25 Pts
  2. Institutional Intraday Volume Surge (RVOL >= 1.40x 20-bar average):          +25 Pts
  3. Intraday Momentum Ribbon (EMA9 > EMA21 > VWAP for Long; Inverted for Short): +25 Pts
  4. VWAP Band Expansion / Momentum Candlestick Trigger (Hammer, Shooting Star):   +25 Pts
  * Bonus 1 (+10 Pts): Opening Range Breakout (ORB) or Power Hour Session Confluence
  * Bonus 2 (+10 Pts): Daily CPR Support / Resistance Bounce Confluence

Inherits from BaseStrategy with full multi-asset, multi-timeframe, and precomputed indicator support.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Union
import numpy as np
import pandas as pd

from mjonai.strategy.registry.base import BaseStrategy, StrategySignalResult
from mjonai.strategy.registry import indicators as ind

logger = logging.getLogger(__name__)


class IntradayAllDayStrategy(BaseStrategy):
    """
    S08: All-Day Intraday Equity & Scalping Strategy.
    Designed for fast execution, tight risk control, and intraday profit locking (5 to 60 mins).
    """

    name: str                        = "S08_IntradayAllDay"
    display_name: str                = "All-Day Intraday & Scalp"
    timeframe: str                   = "INTRADAY"
    asset_class: str                 = "EQUITY"
    signal_direction: str            = "BIDIRECTIONAL"
    version: str                     = "2.3"
    # G2 decision (DEFECT LEDGER): S08 is parameterized for 5m bars, but the
    # production scanner only schedules 15m scans — it must stay INACTIVE until
    # a 5m cadence is actually scheduled in the runtime. The v2.3 redesign
    # flipped this back on without that wiring (found 2026-09-03, canonical
    # verification wave S4); the G2 guard is restored here.
    is_active: bool                  = False
    allowed_asset_classes: Sequence[str] = ("EQUITY", "INDEX", "COMMODITY", "CRYPTO", "FOREX")
    allowed_regimes: Sequence[str]   = ("BULL", "BEAR", "NEUTRAL", "SIDEWAYS")
    min_candles_required: int        = 15
    min_holding_days: int            = 0
    max_holding_days: int            = 1

    # ── Parameters (Logged to MLflow / Optuna tunable) ────────────────────────
    BOX_LOOKBACK: int                = 8        # 8 candles (40 mins on 5m)
    ORB_CANDLES: int                 = 6        # First 6 candles (30 mins on 5m)
    VOLUME_MULTIPLIER: float         = 1.40     # Volume surge multiplier (1.40x)
    MAX_BOX_RANGE_PCT: float         = 0.025    # Maximum 2.5% consolidation box width
    MAX_STOP_LOSS_PCT: float         = 0.015    # Maximum 1.5% intraday risk cap
    RISK_REWARD_RATIO: float         = 1.8      # Target = 1.8x risk
    MAX_HOLDING_MINUTES: int         = 60       # Max holding duration for scalps

    EMA_FAST: int                    = 9        # Fast intraday EMA
    EMA_SLOW: int                    = 21       # Slow intraday EMA
    ATR_PERIOD: int                  = 14       # ATR period for risk buffering
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
        Generate S08 Intraday All-Day signal from 5m/15m candle DataFrame.
        """
        try:
            # 1. Validate DataFrame minimum history
            if df is None or len(df) < self.min_candles_required:
                logger.warning(f"[S08] {symbol} — insufficient intraday history ({len(df) if df is not None else 0} candles)")
                return None

            # Flatten multi-index columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df = df.copy()
                df.columns = df.columns.get_level_values(0)

            close  = np.asarray(df["Close"], dtype=float)
            high   = np.asarray(df["High"], dtype=float)
            low    = np.asarray(df["Low"], dtype=float)
            open_  = np.asarray(df["Open"], dtype=float)
            volume = np.asarray(df["Volume"], dtype=float) if "Volume" in df.columns else np.zeros_like(close)
            n      = len(close)

            latest_close  = float(close[-1])
            latest_high   = float(high[-1])
            latest_low    = float(low[-1])
            latest_open   = float(open_[-1])
            latest_volume = float(volume[-1])

            if np.isnan(latest_close) or latest_close <= 0:
                logger.warning(f"[S08] {symbol} — latest_close is NaN or non-positive")
                return None

            # ── 1. Calculate Intraday Cumulative VWAP & Standard Deviation Bands
            typical_prices = (high + low + close) / 3.0
            cum_vol = np.cumsum(volume)
            cum_pv  = np.cumsum(typical_prices * volume)
            vwap_series = cum_pv / (cum_vol + 1e-9)
            latest_vwap = float(vwap_series[-1])

            # VWAP Standard Deviation Bands (1σ)
            vwap_var = np.cumsum(volume * ((typical_prices - vwap_series) ** 2)) / (cum_vol + 1e-9)
            vwap_std = float(np.sqrt(np.maximum(0, vwap_var[-1])))
            vwap_upper_1 = latest_vwap + vwap_std
            vwap_lower_1 = latest_vwap - vwap_std

            # ── 2. Volume Moving Average (Last 20 candles) ───────────────────
            vol_avg_20 = float(np.mean(volume[-21:-1])) if n > 20 else float(np.mean(volume))
            rvol = latest_volume / (vol_avg_20 + 1e-9)
            has_volume_surge = rvol >= self.VOLUME_MULTIPLIER

            # ── 3. Consolidation Box & Opening Range (ORB) ───────────────────
            lb = min(self.BOX_LOOKBACK, n - 2)
            box_high = float(np.max(high[-lb - 1 : -1]))
            box_low  = float(np.min(low[-lb - 1 : -1]))
            box_range_pct = (box_high - box_low) / (box_low + 1e-9) if box_low > 0 else 1.0

            # Opening Range High / Low (first 6 candles)
            orb_candles = min(self.ORB_CANDLES, n - 1)
            orb_high = float(np.max(high[:orb_candles]))
            orb_low  = float(np.min(low[:orb_candles]))

            # ── 4. Intraday Momentum Moving Averages (EMA9 & EMA21) ──────────
            ema9_arr  = ind.EMA(close, timeperiod=self.EMA_FAST)
            ema21_arr = ind.EMA(close, timeperiod=self.EMA_SLOW)
            latest_ema9  = float(ema9_arr[-1]) if len(ema9_arr) > 0 else latest_close
            latest_ema21 = float(ema21_arr[-1]) if len(ema21_arr) > 0 else latest_close

            # ── 5. ATR for Dynamic Intraday Volatility Buffering ─────────────
            atr_vals = ind.ATR(high, low, close, timeperiod=self.ATR_PERIOD)
            latest_atr = float(atr_vals[-1]) if len(atr_vals) > 0 else (latest_close * 0.005)

            score: int = 0
            reasons: List[str] = []
            signal_direction: Optional[str] = None
            signal_type: Optional[str] = None
            candle_pattern = "NONE"

            # ── 6. Directional Evaluation ────────────────────────────────────

            # 🟢 LONG INTRADAY BREAKOUT / BOUNCE
            if latest_close > latest_vwap and (latest_close > box_high or latest_close > orb_high):
                signal_direction = "LONG"
                signal_type = "BUY"

                # Pillar 1: Box / ORB Breakout
                score += 25
                if latest_close > orb_high:
                    reasons.append(f"Opening Range Breakout (ORB) above ₹{orb_high:.2f}")
                else:
                    reasons.append(f"Consolidation Box Breakout above ₹{box_high:.2f} (Range: {box_range_pct*100:.1f}%)")

                # Pillar 2: Volume Surge
                if has_volume_surge:
                    score += 25
                    reasons.append(f"Institutional volume surge ({rvol:.1f}x >= {self.VOLUME_MULTIPLIER:.1f}x)")
                else:
                    score += 12
                    reasons.append(f"Moderate volume ({rvol:.1f}x)")

                # Pillar 3: Momentum Ribbon (EMA9 > EMA21 > VWAP)
                if latest_close > latest_ema9 > latest_ema21 > latest_vwap:
                    score += 25
                    reasons.append(f"Bullish Intraday Ribbon aligned (Close > EMA{self.EMA_FAST} > EMA{self.EMA_SLOW} > VWAP)")
                elif latest_close > latest_ema9:
                    score += 15
                    reasons.append("Price above 9-EMA momentum line")

                # Pillar 4: VWAP +1σ Band Expansion or Candlestick Trigger
                if latest_close >= vwap_upper_1:
                    score += 25
                    reasons.append(f"VWAP +1σ Band Expansion breakout (₹{latest_close:.2f} >= ₹{vwap_upper_1:.2f})")
                elif latest_close > latest_open:
                    score += 15
                    reasons.append("Strong green expansion candle")

                # Bonus 1: Tight base
                if box_range_pct <= self.MAX_BOX_RANGE_PCT:
                    score += 10
                    reasons.append(f"Tight consolidation base bonus ({box_range_pct*100:.1f}% <= {self.MAX_BOX_RANGE_PCT*100:.1f}%)")

                # Bonus 2: Daily CPR Confluence
                if precomputed_indicators and "cpr_pivot" in precomputed_indicators:
                    cpr_p = float(precomputed_indicators["cpr_pivot"])
                    if latest_close > cpr_p:
                        score += 10
                        reasons.append(f"Daily Central Pivot support confirmed (Above ₹{cpr_p:.2f})")

                # Stop Loss & Target Calculation
                sl_candidate = max(box_low, latest_vwap * 0.998)
                sl_distance = latest_close - sl_candidate
                if sl_distance <= 0 or (sl_distance / latest_close) > self.MAX_STOP_LOSS_PCT:
                    sl_candidate = latest_close * (1.0 - self.MAX_STOP_LOSS_PCT)
                    sl_distance = latest_close - sl_candidate

                target_price = round(latest_close + (sl_distance * self.RISK_REWARD_RATIO), 2)
                sl_price = round(sl_candidate, 2)
                candle_pattern = "INTRADAY_BOX_BREAKOUT"

            # 🔴 SHORT INTRADAY BREAKDOWN
            elif latest_close < latest_vwap and (latest_close < box_low or latest_close < orb_low):
                signal_direction = "SHORT"
                signal_type = "SELL"

                # Pillar 1: Box / ORB Breakdown
                score += 25
                if latest_close < orb_low:
                    reasons.append(f"Opening Range Breakdown (ORB) below ₹{orb_low:.2f}")
                else:
                    reasons.append(f"Consolidation Box Breakdown below ₹{box_low:.2f} (Range: {box_range_pct*100:.1f}%)")

                # Pillar 2: Volume Surge
                if has_volume_surge:
                    score += 25
                    reasons.append(f"Institutional distribution surge ({rvol:.1f}x >= {self.VOLUME_MULTIPLIER:.1f}x)")
                else:
                    score += 12
                    reasons.append(f"Moderate volume ({rvol:.1f}x)")

                # Pillar 3: Momentum Ribbon (EMA9 < EMA21 < VWAP)
                if latest_close < latest_ema9 < latest_ema21 < latest_vwap:
                    score += 25
                    reasons.append(f"Bearish Intraday Ribbon aligned (Close < EMA{self.EMA_FAST} < EMA{self.EMA_SLOW} < VWAP)")
                elif latest_close < latest_ema9:
                    score += 15
                    reasons.append("Price below 9-EMA momentum line")

                # Pillar 4: VWAP -1σ Band Expansion or Candlestick Trigger
                if latest_close <= vwap_lower_1:
                    score += 25
                    reasons.append(f"VWAP -1σ Band Expansion breakdown (₹{latest_close:.2f} <= ₹{vwap_lower_1:.2f})")
                elif latest_close < latest_open:
                    score += 15
                    reasons.append("Strong red breakdown candle")

                # Bonus 1: Tight base
                if box_range_pct <= self.MAX_BOX_RANGE_PCT:
                    score += 10
                    reasons.append(f"Tight consolidation base bonus ({box_range_pct*100:.1f}% <= {self.MAX_BOX_RANGE_PCT*100:.1f}%)")

                # Bonus 2: Daily CPR Confluence
                if precomputed_indicators and "cpr_pivot" in precomputed_indicators:
                    cpr_p = float(precomputed_indicators["cpr_pivot"])
                    if latest_close < cpr_p:
                        score += 10
                        reasons.append(f"Daily Central Pivot resistance confirmed (Below ₹{cpr_p:.2f})")

                # Stop Loss & Target Calculation
                sl_candidate = min(box_high, latest_vwap * 1.002)
                sl_distance = sl_candidate - latest_close
                if sl_distance <= 0 or (sl_distance / latest_close) > self.MAX_STOP_LOSS_PCT:
                    sl_candidate = latest_close * (1.0 + self.MAX_STOP_LOSS_PCT)
                    sl_distance = sl_candidate - latest_close

                target_price = round(latest_close - (sl_distance * self.RISK_REWARD_RATIO), 2)
                sl_price = round(sl_candidate, 2)
                candle_pattern = "INTRADAY_BOX_BREAKDOWN"

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
                swing_low=sl_price if signal_direction == "LONG" else None,
                swing_high=sl_price if signal_direction == "SHORT" else None,
                sl_method="INTRADAY_VWAP_BOX",
                timeframe=self.timeframe,
                asset_class=self.asset_class,
                atr=round(latest_atr, 4),
                candle_pattern=candle_pattern,
                indicator_values={
                    "vwap": round(latest_vwap, 2),
                    "vwap_upper_1": round(vwap_upper_1, 2),
                    "vwap_lower_1": round(vwap_lower_1, 2),
                    "ema_fast": round(latest_ema9, 2),
                    "ema_slow": round(latest_ema21, 2),
                    "rvol": round(rvol, 2),
                    "box_high": round(box_high, 2),
                    "box_low": round(box_low, 2),
                    "stop_loss": sl_price,
                    "target_price": target_price,
                },
                extra_metadata={
                    "vix": round(float(vix), 2),
                    "market_state": market_state,
                    "mqi_level": mqi_level,
                    "risk_reward": self.RISK_REWARD_RATIO,
                    "trade_mode": "INTRADAY",
                    "fast_profit_target": True,
                    "max_holding_minutes": self.MAX_HOLDING_MINUTES,
                },
            )

        except Exception as e:
            logger.warning(f"[S08] generate_signal exception for {symbol}: {e}")
            return None

    def get_parameters(self) -> Dict[str, Any]:
        """All S08 parameters for MLflow experiment tracking."""
        return {
            "strategy_id":            self.name,
            "version":                self.version,
            "box_lookback":           self.BOX_LOOKBACK,
            "orb_candles":            self.ORB_CANDLES,
            "volume_multiplier":      self.VOLUME_MULTIPLIER,
            "max_box_range_pct":      self.MAX_BOX_RANGE_PCT,
            "max_stop_loss_pct":      self.MAX_STOP_LOSS_PCT,
            "risk_reward_ratio":      self.RISK_REWARD_RATIO,
            "max_holding_minutes":    self.MAX_HOLDING_MINUTES,
            "ema_fast":               self.EMA_FAST,
            "ema_slow":               self.EMA_SLOW,
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
            f"S08 All-Day Intraday Strategy v{self.version} — "
            f"Continuous 5m/15m scan: Consolidation Box ({self.BOX_LOOKBACK} bars) / ORB + VWAP & ±1σ Band Expansion, "
            f"EMA{self.EMA_FAST}/EMA{self.EMA_SLOW} momentum ribbon, RVOL>={self.VOLUME_MULTIPLIER:.1f}x surge, Daily CPR confluence. "
            f"Fast profit target ({self.RISK_REWARD_RATIO}x R:R in {self.MAX_HOLDING_MINUTES} mins). Min score {self.MIN_SCORE}/100."
        )
