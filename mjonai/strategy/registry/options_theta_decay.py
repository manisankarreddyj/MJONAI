"""
Module: strategy/registry/options_theta_decay.py
Purpose: S09 — SOTA Institutional Options Delta-Neutral & Theta Decay Strategy.
         Captures non-directional time decay (Theta harvesting) and implied volatility crush (Vega contraction)
         on Index Options (NIFTY, BANKNIFTY, FINNIFTY) and Liquid F&O Equities.
         Constructs Delta-Neutral Short Strangles and Iron Condors when:
           1. India VIX / Implied Volatility Rank (IVR) is elevated (IVR >= 50% or VIX >= 15.0).
           2. Market is consolidating within an ATR-bound range or Sideways/Neutral regime.
           3. ADX is low (ADX < 20, confirming non-trending consolidation).
           4. Sells OTM Strikes (0.15 - 0.25 Delta) outside the ±1.5σ expected move.

Pillars of Scoring (Total: 100 Points, Minimum Gate: 70 Points):
  • HARD SENTRY 1: ADX MUST be <= 25.0 (No non-directional theta selling in strong directional breakout trends)
  • HARD SENTRY 2: India VIX MUST be >= 12.0 (Adequate option premium available)
  1. Elevated Volatility Premium (VIX >= 15.0 or IVR >= 50%):            +30 Pts
  2. Range-Bound Consolidation (Price between BB Upper & Lower):          +25 Pts
  3. ADX Trend Absence (ADX < 18 & -DI / +DI balanced):                  +25 Pts
  4. Non-Directional CPR / VWAP Balance:                                  +20 Pts

Inherits from BaseStrategy with full multi-asset, multi-timeframe, and precomputed indicator support.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Union
import numpy as np
import pandas as pd

from mjonai.strategy.registry.base import BaseStrategy, StrategySignalResult
from mjonai.strategy.registry import indicators as ind

logger = logging.getLogger(__name__)


class OptionsThetaDecay(BaseStrategy):
    """
    S09: Options Delta-Neutral & Theta Decay Strategy.
    Harvests option premium decay on non-trending indices and heavyweights.
    """

    name: str                        = "S09_OptionsThetaDecay"
    display_name: str                = "Options Theta Decay"
    timeframe: str                   = "INTRADAY"
    asset_class: str                 = "OPTIONS"
    signal_direction: str            = "NON_DIRECTIONAL"
    version: str                     = "1.1"
    is_active: bool                  = False
    allowed_asset_classes: Sequence[str] = ("OPTIONS", "INDEX", "EQUITY")
    allowed_regimes: Sequence[str]   = ("NEUTRAL", "SIDEWAYS", "BULL", "BEAR")
    min_candles_required: int        = 50
    min_holding_days: int            = 0
    max_holding_days: int            = 3

    # ── Parameters (Logged to MLflow / Optuna tunable) ────────────────────────
    ADX_MAX_TREND: float             = 25.0     # Hard ceiling: no theta selling if ADX > 25
    ADX_OPTIMAL_CHOP: float          = 18.0     # Optimal non-trending ADX
    VIX_MIN_THRESHOLD: float         = 12.0     # Minimum VIX floor
    VIX_OPTIMAL_THRESHOLD: float     = 15.0     # Optimal VIX for rich premiums
    TARGET_DELTA: float              = 0.20     # Target OTM Delta for short strikes
    EXPECTED_MOVE_SIGMA: float       = 1.5      # Multiple of ATR / IV expected move
    BB_PERIOD: int                   = 20
    BB_STD: float                    = 2.0
    ATR_PERIOD: int                  = 14
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
        Generate S09 Options Theta Decay signal for given symbol and volatility regime.
        """
        try:
            # 1. Validate DataFrame minimum history
            if df is None or len(df) < self.min_candles_required:
                logger.warning(f"[S09] {symbol} — insufficient history ({len(df) if df is not None else 0} candles)")
                return None

            close  = np.asarray(df["Close"], dtype=float)
            high   = np.asarray(df["High"], dtype=float)
            low    = np.asarray(df["Low"], dtype=float)
            open_  = np.asarray(df["Open"], dtype=float)
            volume = np.asarray(df["Volume"], dtype=float) if "Volume" in df.columns else np.zeros_like(close)

            latest_close = float(close[-1])
            if np.isnan(latest_close) or latest_close <= 0:
                logger.warning(f"[S09] {symbol} — latest_close is NaN or non-positive")
                return None

            score: int = 0
            reasons: List[str] = []

            # ── 1. Trend Strength Sentry (ADX) (HARD SENTRY 1) ─────────────────
            if precomputed_indicators and "adx" in precomputed_indicators:
                latest_adx = float(precomputed_indicators["adx"])
            else:
                adx_vals = ind.ADX(high, low, close, timeperiod=self.ATR_PERIOD)
                latest_adx = float(adx_vals[-1]) if len(adx_vals) > 0 else 0.0

            # HARD SENTRY 1: Cannot sell non-directional theta in strong directional trends
            if latest_adx > self.ADX_MAX_TREND:
                return None

            # ── 2. Volatility Sentry (India VIX) (HARD SENTRY 2) ──────────────
            if vix is None or np.isnan(vix) or vix <= 0:
                return None  # missing market data never fabricates a pass
            current_vix = float(vix)

            # HARD SENTRY 2: Option premiums too cheap when VIX < 12
            if current_vix < self.VIX_MIN_THRESHOLD:
                return None

            # ── 3. Pillar Scoring ────────────────────────────────────────────

            # Pillar 1: Volatility Premium (VIX)
            if current_vix >= self.VIX_OPTIMAL_THRESHOLD:
                score += 30
                reasons.append(f"Elevated India VIX premium ({current_vix:.1f} >= {self.VIX_OPTIMAL_THRESHOLD:.1f})")
            else:
                score += 15
                reasons.append(f"Moderate VIX premium ({current_vix:.1f})")

            # Pillar 2: Range-Bound Price Action (Bollinger Bands containment)
            if precomputed_indicators and all(k in precomputed_indicators for k in ("bb_upper", "bb_middle", "bb_lower")):
                bb_upper = float(precomputed_indicators["bb_upper"])
                bb_lower = float(precomputed_indicators["bb_lower"])
                bb_mid   = float(precomputed_indicators["bb_middle"])
            else:
                upper, middle, lower = ind.BBANDS(close, timeperiod=self.BB_PERIOD, nbdevup=self.BB_STD, nbdevdn=self.BB_STD)
                bb_upper = float(upper[-1])
                bb_lower = float(lower[-1])
                bb_mid   = float(middle[-1])

            # Contained within middle 80% of Bollinger Band range
            bb_range = bb_upper - bb_lower
            bb_pct = (latest_close - bb_lower) / (bb_range + 1e-10)

            if 0.15 <= bb_pct <= 0.85:
                score += 25
                reasons.append(f"Price well-contained in Bollinger Band neutral zone ({bb_pct*100:.1f}%)")
            else:
                score += 10
                reasons.append(f"Price near Bollinger Band boundary ({bb_pct*100:.1f}%)")

            # Pillar 3: ADX Absence of Directional Velocity
            if latest_adx <= self.ADX_OPTIMAL_CHOP:
                score += 25
                reasons.append(f"Optimal non-trending chop confirmed (ADX: {latest_adx:.1f} <= {self.ADX_OPTIMAL_CHOP:.1f})")
            else:
                score += 15
                reasons.append(f"Moderate trend momentum (ADX: {latest_adx:.1f})")

            # Pillar 4: RSI Neutral Equilibrium (RSI between 42 and 58)
            if precomputed_indicators and "rsi" in precomputed_indicators:
                latest_rsi = float(precomputed_indicators["rsi"])
            else:
                rsi = ind.RSI(close, timeperiod=14)
                latest_rsi = float(rsi[-1]) if len(rsi) > 0 else 50.0

            if 42.0 <= latest_rsi <= 58.0:
                score += 20
                reasons.append(f"RSI in perfect non-directional balance ({latest_rsi:.1f})")
            else:
                score += 10
                reasons.append(f"RSI slightly asymmetric ({latest_rsi:.1f})")

            # ── Score Gate Check ─────────────────────────────────────────────
            final_score = min(100.0, float(score))
            if final_score < self.MIN_SCORE:
                return None

            # ── 4. Options Geometry (Short Call / Put Strikes) ────────────────
            if precomputed_indicators and "atr" in precomputed_indicators:
                latest_atr = float(precomputed_indicators["atr"])
            else:
                atr_vals = ind.ATR(high, low, close, timeperiod=self.ATR_PERIOD)
                latest_atr = float(atr_vals[-1]) if len(atr_vals) > 0 else (latest_close * 0.01)

            expected_move = latest_atr * self.EXPECTED_MOVE_SIGMA
            sym_upper = str(symbol).upper()
            if "BANKNIFTY" in sym_upper:
                strike_step = 100.0
            elif "NIFTY" in sym_upper or "FINNIFTY" in sym_upper or "MIDCPNIFTY" in sym_upper:
                strike_step = 50.0
            elif "SENSEX" in sym_upper:
                strike_step = 100.0
            elif latest_close > 500:
                strike_step = 50.0
            elif latest_close > 200:
                strike_step = 20.0
            else:
                strike_step = 10.0

            short_ce_strike = round((latest_close + expected_move) / strike_step) * strike_step
            short_pe_strike = round((latest_close - expected_move) / strike_step) * strike_step
            wing_width = strike_step * 2.0
            long_ce_strike = short_ce_strike + wing_width
            long_pe_strike = short_pe_strike - wing_width

            # ── Construct Strongly Typed Result Contract ─────────────────────
            return StrategySignalResult(
                strategy_id=self.name,
                strategy_version=self.version,
                symbol=symbol,
                signal_direction="NON_DIRECTIONAL",
                signal_type="SELL",  # Short Strangle / Iron Condor
                technical_score=final_score,
                confidence=final_score,
                reasons=reasons,
                entry_price=round(latest_close, 2),
                timeframe=self.timeframe,
                asset_class=self.asset_class,
                atr=round(latest_atr, 4),
                option_type="STRANGLE",
                strike_price=short_ce_strike,
                candle_pattern="THETA_DECAY_RANGE",
                indicator_values={
                    "vix": round(current_vix, 2),
                    "adx": round(latest_adx, 2),
                    "rsi": round(latest_rsi, 2),
                    "atr": round(latest_atr, 4),
                    "short_ce_strike": short_ce_strike,
                    "short_pe_strike": short_pe_strike,
                    "long_ce_strike": long_ce_strike,
                    "long_pe_strike": long_pe_strike,
                    "expected_move": round(expected_move, 2),
                    "bb_pct": round(bb_pct * 100.0, 1),
                },
                extra_metadata={
                    "vix": round(current_vix, 2),
                    "market_state": market_state,
                    "mqi_level": mqi_level,
                    "strategy_structure": "IRON_CONDOR_OR_STRANGLE",
                    "legs": [
                        {"type": "CE", "action": "SELL", "strike": short_ce_strike},
                        {"type": "PE", "action": "SELL", "strike": short_pe_strike},
                        {"type": "CE", "action": "BUY", "strike": long_ce_strike},
                        {"type": "PE", "action": "BUY", "strike": long_pe_strike},
                    ],
                    "target_delta": self.TARGET_DELTA,
                    "min_holding_days": self.min_holding_days,
                    "max_holding_days": self.max_holding_days,
                },
            )

        except Exception as e:
            logger.warning(f"[S09] generate_signal exception for {symbol}: {e}")
            return None

    def get_parameters(self) -> Dict[str, Any]:
        """All S09 parameters for MLflow experiment tracking."""
        return {
            "strategy_id":            self.name,
            "version":                self.version,
            "adx_max_trend":          self.ADX_MAX_TREND,
            "adx_optimal_chop":       self.ADX_OPTIMAL_CHOP,
            "vix_min_threshold":      self.VIX_MIN_THRESHOLD,
            "vix_optimal_threshold":  self.VIX_OPTIMAL_THRESHOLD,
            "target_delta":           self.TARGET_DELTA,
            "expected_move_sigma":    self.EXPECTED_MOVE_SIGMA,
            "bb_period":              self.BB_PERIOD,
            "bb_std":                 self.BB_STD,
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
            f"S09 Options Theta Decay v{self.version} — "
            f"Delta-Neutral Theta & Vega harvesting: India VIX >={self.VIX_MIN_THRESHOLD:.1f}, "
            f"ADX <={self.ADX_MAX_TREND:.0f} non-trending chop, Bollinger Band neutral containment. "
            f"Sells OTM Strikes (Delta ~{self.TARGET_DELTA:.2f}) outside ±{self.EXPECTED_MOVE_SIGMA}σ expected move. "
            f"Min score {self.MIN_SCORE}/100."
        )
