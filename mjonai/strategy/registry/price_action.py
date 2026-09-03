"""
Module: strategy/registry/price_action.py
Purpose: S05 — SOTA Institutional Price Action & Liquidity Sweep Strategy.
         Combines high-conviction Candlestick reversal structures with
         ATR-Dynamic Support (Central Pivot Range CPR & Dynamic EMA50),
         Institutional Liquidity Sweeps (Stop Hunt Reversals), and
         Volume Flow confirmation (RVOL >= 1.25x or CMF > 0.05).

Pillars of Scoring (Total: 100 Points, Minimum Gate: 65 Points):
  1. Bullish Candlestick Pattern Trigger:           +35 Pts (MANDATORY GATEWAY)
  2. Structural Support Confluence (CPR / EMA50):    +25 Pts (Within 0.75 x ATR)
  3. Institutional Volume Flow (RVOL >= 1.25):       +20 Pts
  4. Macro Trend Alignment (Close > EMA200):        +20 Pts
  * Bonus (+10 Pts): Liquidity Sweep / Turtle Soup Reversal (Dipped below prior low & closed above)

Inherits from BaseStrategy with full multi-asset, multi-timeframe, and precomputed indicator support.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
import pandas as pd

from mjonai.strategy.registry.base import BaseStrategy, StrategySignalResult
from mjonai.strategy.registry import indicators as ind
from mjonai.core.constants import SYSTEM_MODE

logger = logging.getLogger(__name__)


class PriceActionCandles(BaseStrategy):
    """
    S05 — Price Action Candles Strategy.

    Research targets:
        Win rate > 55%
        Best regime: BULL / NEUTRAL near structural CPR support
        Worst regime: BEAR / Extreme High VIX
        IC target: > 0.05 (Alphalens)
    """

    name: str                        = "S05_PriceAction"
    display_name: str                = "Price Action Candles"
    timeframe: str                   = "SWING"
    asset_class: str                 = "EQUITY"
    version: str                     = "2.2"
    is_active: bool                  = True
    allowed_asset_classes: Sequence[str] = ("EQUITY", "INDEX", "COMMODITY", "CRYPTO", "FOREX")
    allowed_regimes: Sequence[str]   = ("BULL", "NEUTRAL", "SIDEWAYS")
    min_candles_required: int        = 50
    min_holding_days: int            = 2
    max_holding_days: int            = 7

    # ── Parameters (Logged to MLflow / Optuna tunable) ────────────────────────
    EMA_MID: int                     = 50       # Primary trend filter — mandatory
    EMA_LONG: int                    = 200      # Secondary macro trend filter
    VOLUME_PERIOD: int               = 20       # Volume average period
    VOLUME_CONFIRM: float            = 1.25     # Volume surge multiplier (1.25x)
    ATR_PERIOD: int                  = 14       # ATR volatility period
    ATR_PROXIMITY_MULT: float        = 0.75     # Distance tolerance to CPR/EMA support in ATRs
    SWING_LOOKBACK: int              = 10       # Lookback for liquidity sweep detection
    MIN_SCORE: int                   = 65       # Minimum technical score

    # ── Confirmed High-Conviction Bullish Candlestick Patterns ────────────────
    _PATTERNS: List[Tuple[str, str, int]] = [
        # Tier-1 Major Reversals (Highest statistical alpha)
        ("CDLMORNINGSTAR",      "Morning Star",         35),
        ("CDLENGULFING",        "Bullish Engulfing",    35),
        ("CDLHAMMER",           "Hammer",               35),
        ("CDL3WHITESOLDIERS",   "Three White Soldiers", 35),
        ("CDLPIERCING",         "Piercing Line",        35),
        ("CDLINVERTEDHAMMER",   "Inverted Hammer",      30),
        ("CDLDRAGONFLYDOJI",    "Dragonfly Doji",       30),
        ("CDLMARUBOZU",         "Marubozu Momentum",    30),

        # Tier-2 Continuation & Harami Patterns
        ("CDL3INSIDE",          "Three Inside Up",      25),
        ("CDL3OUTSIDE",         "Three Outside Up",     25),
        ("CDLHARAMI",           "Bullish Harami",       25),
        ("CDLHARAMICROSS",      "Harami Cross",         25),
        ("CDLKICKING",          "Kicking Bull",         25),
        ("CDLCLOSINGMARUBOZU",  "Closing Marubozu",     25),
        ("CDLBELTHOLD",         "Belt Hold Bull",       20),
        ("CDLBREAKAWAY",        "Breakaway Bull",       20),
        ("CDLSTICKSANDWICH",    "Stick Sandwich",       20),
    ]

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
        Generate S05 Price Action Candles signal for given symbol and market conditions.
        """
        try:
            # 1. Validate DataFrame minimum history
            is_valid, reason = self.validate_ohlcv_dataframe(df, min_candles=self.min_candles_required)
            if not is_valid:
                logger.warning(f"[S05] {symbol} — {reason}")
                return None

            close  = np.asarray(df["Close"], dtype=float)
            high   = np.asarray(df["High"], dtype=float)
            low    = np.asarray(df["Low"], dtype=float)
            open_  = np.asarray(df["Open"], dtype=float)
            volume = np.asarray(df["Volume"], dtype=float) if "Volume" in df.columns else np.zeros_like(close)

            score: int = 0
            reasons: List[str] = []

            # ── 1. ATR Volatility & Proximity Unit ────────────────────────────
            if precomputed_indicators and "atr" in precomputed_indicators:
                latest_atr = float(precomputed_indicators["atr"])
            else:
                atr_vals = ind.ATR(high, low, close, timeperiod=self.ATR_PERIOD)
                latest_atr = float(atr_vals[-1]) if len(atr_vals) > 0 else 0.0

            if np.isnan(latest_atr) or latest_atr <= 0:
                logger.warning(f"[S05] {symbol} — NaN or zero ATR")
                return None

            # ── 2. EMA50 Dynamic Trend Filter (HARD SENTRY) ───────────────────
            if precomputed_indicators and "ema_mid" in precomputed_indicators:
                ema50_val = float(precomputed_indicators["ema_mid"])
            else:
                ema50 = ind.EMA(close, timeperiod=self.EMA_MID)
                ema50_val = float(ema50[-1]) if len(ema50) > 0 else float("nan")

            if np.isnan(ema50_val):
                logger.warning(f"[S05] {symbol} — EMA50 is NaN")
                return None

            latest_close = float(close[-1])

            # HARD SENTRY: Price must be trading above EMA50
            if latest_close <= ema50_val:
                return None

            # ── 3. Scan Bullish Candlestick Patterns ──────────────────────────
            fired_pattern: str       = "NONE"
            fired_name: str          = "None"
            pattern_score: int       = 0
            all_fired: List[str]     = []

            if precomputed_indicators and "candle_pattern" in precomputed_indicators:
                fired_pattern = str(precomputed_indicators["candle_pattern"])
                fired_name    = fired_pattern
                pattern_score = 35
                reasons.append(f"Precomputed pattern ({fired_name}) confirmed")
            else:
                for func_name, display_name, weight in self._PATTERNS:
                    try:
                        func = getattr(ind, func_name, None)
                        if func is None:
                            func = getattr(ind, f"CDL{func_name}", None)
                        if func is None:
                            continue

                        result = func(open_, high, low, close)
                        last_val = int(result[-1]) if len(result) > 0 else 0

                        if last_val > 0:
                            if fired_pattern == "NONE":
                                fired_pattern = func_name.replace("CDL", "")
                                fired_name    = display_name
                                pattern_score = weight
                                reasons.append(f"{display_name} candle pattern confirmed")

                            all_fired.append(func_name.replace("CDL", ""))

                            # In LIVE mode, stop at first high-conviction pattern
                            if SYSTEM_MODE != "RESEARCH":
                                break

                    except Exception as e:
                        logger.debug(f"[S05] Error evaluating pattern {func_name}: {e}")
                        continue

            # HARD SENTRY: Must have at least one bullish candle pattern
            if fired_pattern == "NONE" and pattern_score == 0:
                return None

            score += pattern_score

            # ── 4. ATR-Dynamic Structural Support Confluence (CPR / EMA50) ────
            # Dynamic proximity band based on ATR: tolerance = 0.75 * ATR
            prox_tolerance = self.ATR_PROXIMITY_MULT * latest_atr

            if higher_tf_df is not None and len(higher_tf_df) >= 2:
                prev_dh = float(higher_tf_df["High"].iloc[-2])
                prev_dl = float(higher_tf_df["Low"].iloc[-2])
                prev_dc = float(higher_tf_df["Close"].iloc[-2])
                cpr = ind.cpr_pivots(prev_dh, prev_dl, prev_dc)
            elif len(high) >= 2 and len(low) >= 2 and len(close) >= 2:
                cpr = ind.cpr_pivots(high[-2], low[-2], close[-2])
            else:
                cpr = {"pivot": latest_close, "bc": latest_close, "tc": latest_close, "s1": latest_close, "r1": latest_close}
            
            cpr_p  = cpr["pivot"]
            cpr_bc = cpr["bc"]
            cpr_tc = cpr["tc"]
            cpr_s1 = cpr["s1"]

            # Check if current low or close reacted near CPR levels or EMA50
            lowest_price = float(low[-1])
            is_near_cpr = (abs(lowest_price - cpr_p) <= prox_tolerance) or \
                          (abs(lowest_price - cpr_bc) <= prox_tolerance) or \
                          (abs(lowest_price - cpr_tc) <= prox_tolerance) or \
                          (abs(lowest_price - cpr_s1) <= prox_tolerance) or \
                          (abs(latest_close - cpr_tc) <= prox_tolerance)
            is_near_ema50 = (abs(lowest_price - ema50_val) <= prox_tolerance)

            if is_near_cpr or is_near_ema50:
                score += 25
                reasons.append("Structural Support Confluence (Near CPR Pivot/EMA50 within 0.75 ATR)")
            else:
                reasons.append("Trading in open trend above support zone")

            # ── 5. Institutional Liquidity Sweep (Turtle Soup Bonus) ─────────
            # Checks if current candle swept the lowest low of the last 10 bars and closed back above
            if len(low) >= self.SWING_LOOKBACK + 2:
                prior_swing_low = float(np.min(low[-self.SWING_LOOKBACK - 1 : -1]))
                if float(low[-1]) < prior_swing_low and latest_close > prior_swing_low:
                    score += 10
                    reasons.append(f"Institutional Liquidity Sweep (Stop Hunt below {prior_swing_low:.2f} reclaimed)")

            # ── 6. Institutional Volume Flow Surge ───────────────────────────
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

            if latest_rvol >= self.VOLUME_CONFIRM or latest_cmf > 0.05:
                score += 20
                reasons.append(f"Volume confirmation (RVOL: {latest_rvol:.2f}x, CMF: {latest_cmf:.2f})")
            elif latest_rvol >= 1.0:
                score += 10
                reasons.append(f"Average volume confirmed (RVOL: {latest_rvol:.2f}x)")
            else:
                reasons.append(f"Sub-par volume (RVOL: {latest_rvol:.2f}x)")

            # ── 7. Macro Trend Alignment (Above EMA200) ──────────────────────
            if precomputed_indicators and "ema_long" in precomputed_indicators:
                ema200_val = float(precomputed_indicators["ema_long"])
            else:
                ema200 = ind.EMA(close, timeperiod=self.EMA_LONG)
                ema200_val = float(ema200[-1]) if len(ema200) > 0 else float("nan")

            if not np.isnan(ema200_val) and latest_close > ema200_val:
                score += 20
                reasons.append("Macro uptrend aligned (Price > EMA200)")
            else:
                reasons.append("Price below macro EMA200")

            # ── 8. Multi-Timeframe Check (HTF Filter) ────────────────────────
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
                candle_pattern=fired_pattern,
                indicator_values={
                    "rvol": round(latest_rvol, 2),
                    "cmf": round(latest_cmf, 4),
                    "atr": round(latest_atr, 4),
                    "ema_mid": round(ema50_val, 2),
                    "ema_long": round(ema200_val, 2) if not np.isnan(ema200_val) else 0.0,
                },
                extra_metadata={
                    "vix": round(float(vix), 2),
                    "market_state": market_state,
                    "mqi_level": mqi_level,
                    "candle_name": fired_name,
                    "all_patterns_fired": all_fired,
                    "min_holding_days": self.min_holding_days,
                    "max_holding_days": self.max_holding_days,
                },
            )

        except Exception as e:
            logger.warning(f"[S05] generate_signal exception for {symbol}: {e}")
            return None

    def get_parameters(self) -> Dict[str, Any]:
        """All S05 parameters for MLflow tracking."""
        return {
            "strategy_id":          self.name,
            "version":              self.version,
            "ema_mid":              self.EMA_MID,
            "ema_long":             self.EMA_LONG,
            "volume_period":        self.VOLUME_PERIOD,
            "volume_confirm":       self.VOLUME_CONFIRM,
            "atr_period":           self.ATR_PERIOD,
            "atr_proximity_mult":   self.ATR_PROXIMITY_MULT,
            "swing_lookback":       self.SWING_LOOKBACK,
            "min_score":            self.MIN_SCORE,
            "patterns_tested":      len(self._PATTERNS),
            "timeframe":            self.timeframe,
            "asset_class":          self.asset_class,
            "allowed_asset_classes":list(self.allowed_asset_classes),
            "allowed_regimes":      list(self.allowed_regimes),
            "min_holding_days":     self.min_holding_days,
            "max_holding_days":     self.max_holding_days,
        }

    def get_description(self) -> str:
        """Human-readable description."""
        return (
            f"S05 Price Action v{self.version} — "
            f"Tests {len(self._PATTERNS)} candlestick patterns with ATR-dynamic CPR/EMA50 support, "
            f"Liquidity Sweep detection, and volume surge >{self.VOLUME_CONFIRM:.2f}x. "
            f"Min score {self.MIN_SCORE}/100. Swing trades {self.min_holding_days}-{self.max_holding_days} days."
        )