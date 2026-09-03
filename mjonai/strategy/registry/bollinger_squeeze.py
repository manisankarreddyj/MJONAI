"""
Module: strategy/registry/bollinger_squeeze.py
Purpose: S04 — SOTA Institutional Bollinger Squeeze & TTM Compression Strategy.
         Detects true volatility compression (Bollinger Bands contracting inside Keltner Channels
         or Bandwidth < 75% of 20-day average) followed by explosive directional expansion
         with institutional volume surge (RVOL >= 1.25) and MACD momentum confirmation.

Pillars of Scoring (Total: 100 Points, Minimum Gate: 70 Points):
  1. Volatility Compression (TTM Squeeze / Bandwidth < Threshold): +30 Pts (MANDATORY GATEWAY)
  2. Volatility Expansion (Bandwidth Expanding & Upper Band Test): +25 Pts
  3. Institutional Volume Surge (RVOL >= 1.25 or CMF > 0):         +20 Pts
  4. MACD Bullish Momentum (Histogram > 0 & Rising):               +15 Pts
  5. RSI Momentum Baseline (> 50):                                 +10 Pts

Inherits from BaseStrategy with full multi-asset, multi-timeframe, and precomputed indicator support.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Union
import numpy as np
import pandas as pd

from mjonai.strategy.registry.base import BaseStrategy, StrategySignalResult
from mjonai.strategy.registry import indicators as ind

logger = logging.getLogger(__name__)


class BollingerSqueeze(BaseStrategy):
    """
    S04 — Bollinger Squeeze & TTM Compression Strategy.
    
    Research targets:
        Win rate > 55%
        Best: Low/Normal VIX environment + pre-breakout compression
        Worst: Extreme VIX (Bands naturally wide — no squeeze)
        IC target: > 0.05 (Alphalens)
    """

    name: str                        = "S04_BollingerSqueeze"
    display_name: str                = "Bollinger Squeeze"
    timeframe: str                   = "SWING"
    asset_class: str                 = "EQUITY"
    version: str                     = "2.1"
    is_active: bool                  = True
    allowed_asset_classes: Sequence[str] = ("EQUITY", "INDEX", "COMMODITY", "CRYPTO", "FOREX")
    allowed_regimes: Sequence[str]   = ("BULL", "NEUTRAL", "SIDEWAYS")
    min_candles_required: int        = 50
    min_holding_days: int            = 3
    max_holding_days: int            = 10

    # ── Parameters (Logged to MLflow / Optuna tunable) ────────────────────────
    BB_PERIOD: int                   = 20       # Bollinger Band period
    BB_STD: float                    = 2.0      # Standard deviations
    KELTNER_EMA: int                 = 20       # Keltner Channel EMA period
    KELTNER_ATR: int                 = 20       # Keltner ATR period (TTM squeeze standard: 20/20/1.5)
    KELTNER_MULT: float              = 1.5      # Keltner Channel multiplier (TTM standard is 1.5)

    SQUEEZE_LOOKBACK: int            = 20       # Days to calculate avg BB width
    BASE_SQUEEZE_THRESHOLD: float    = 0.75     # Base threshold: BB width < 75% of avg

    MACD_FAST: int                   = 12
    MACD_SLOW: int                   = 26
    MACD_SIGNAL: int                 = 9

    RSI_PERIOD: int                  = 14
    RSI_CONFIRM: float               = 50.0     # RSI must be above 50 for bullish confirmation

    ATR_PERIOD: int                  = 14
    RVOL_PERIOD: int                 = 20
    RVOL_MIN_THRESHOLD: float        = 1.20

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
        Generate S04 Bollinger Squeeze signal for given symbol and market conditions.
        """
        try:
            # 1. Validate DataFrame minimum history
            is_valid, reason = self.validate_ohlcv_dataframe(df, min_candles=self.min_candles_required)
            if not is_valid:
                logger.warning(f"[S04] {symbol} — {reason}")
                return None

            close  = np.asarray(df["Close"], dtype=float)
            high   = np.asarray(df["High"], dtype=float)
            low    = np.asarray(df["Low"], dtype=float)
            open_  = np.asarray(df["Open"], dtype=float)
            volume = np.asarray(df["Volume"], dtype=float) if "Volume" in df.columns else np.zeros_like(close)

            score: int = 0
            reasons: List[str] = []

            # ── 1. Bollinger Bands & Keltner Channels (TTM Squeeze) ──────────
            if precomputed_indicators and all(k in precomputed_indicators for k in ("bb_upper", "bb_middle", "bb_lower", "kelt_upper", "kelt_lower", "bb_width_curr", "bb_width_prev", "bb_width_avg", "recent_min_width")):
                bb_up        = float(precomputed_indicators["bb_upper"])
                bb_mid       = float(precomputed_indicators["bb_middle"])
                bb_dn        = float(precomputed_indicators["bb_lower"])
                kelt_up      = float(precomputed_indicators["kelt_upper"])
                kelt_dn      = float(precomputed_indicators["kelt_lower"])
                curr_width   = float(precomputed_indicators["bb_width_curr"])
                prev_width   = float(precomputed_indicators["bb_width_prev"])
                avg_width    = float(precomputed_indicators["bb_width_avg"])
                recent_min_w = float(precomputed_indicators["recent_min_width"])
                is_ttm_squeezed = bool(precomputed_indicators.get("is_ttm_squeezed", False))
            else:
                bb_upper_arr, bb_middle_arr, bb_lower_arr = ind.BBANDS(
                    close,
                    timeperiod=self.BB_PERIOD,
                    nbdevup=self.BB_STD,
                    nbdevdn=self.BB_STD,
                )
                kelt_upper_arr, _, kelt_lower_arr = ind.keltner_channels(
                    high, low, close,
                    ema_period=self.KELTNER_EMA,
                    atr_period=self.KELTNER_ATR,
                    multiplier=self.KELTNER_MULT,
                )
                bb_up   = float(bb_upper_arr[-1])
                bb_mid  = float(bb_middle_arr[-1])
                bb_dn   = float(bb_lower_arr[-1])
                kelt_up = float(kelt_upper_arr[-1])
                kelt_dn = float(kelt_lower_arr[-1])

                # BB width array for bandwidth analysis
                bb_width_arr = (bb_upper_arr - bb_lower_arr) / (bb_middle_arr + 1e-10)
                curr_width   = float(bb_width_arr[-1])
                prev_width   = float(bb_width_arr[-2])
                avg_width    = float(np.nanmean(bb_width_arr[-self.SQUEEZE_LOOKBACK - 1 : -1]))
                # Check minimum bandwidth in the recent setup window (past 15 bars)
                lookback_window = min(15, len(bb_width_arr) - 2)
                recent_min_w = float(np.nanmin(bb_width_arr[-lookback_window - 1 : -1]))

                # Check if TTM squeeze (BB inside Keltner) was active in the setup window
                ttm_squeezed_arr = (bb_upper_arr <= kelt_upper_arr) & (bb_lower_arr >= kelt_lower_arr)
                is_ttm_squeezed = bool(np.any(ttm_squeezed_arr[-lookback_window - 1 : -1]))

            if np.isnan(curr_width) or np.isnan(prev_width) or np.isnan(avg_width) or avg_width == 0.0:
                logger.warning(f"[S04] {symbol} — NaN in BB calculations")
                return None

            # ── 2. Volatility Compression Check (TTM & VIX-Adaptive Squeeze) ──
            vix_scale = 1.0 + max(0.0, (vix - 15.0) / 100.0)
            adaptive_threshold = self.BASE_SQUEEZE_THRESHOLD * vix_scale
            is_bw_squeezed = recent_min_w < (avg_width * adaptive_threshold)

            was_squeezed = is_ttm_squeezed or is_bw_squeezed
            if not was_squeezed:
                # HARD SENTRY: No squeeze = no compression = no explosive setup
                return None

            score += 30
            squeeze_pct = round(recent_min_w / (avg_width + 1e-10) * 100.0, 1)
            reasons.append(f"Volatility Squeeze confirmed (TTM inside Keltner: {is_ttm_squeezed}, Bandwidth: {squeeze_pct}% of avg)")

            # ── 3. Expansion Beginning & Upper Band Breakout ─────────────────
            latest_close = float(close[-1])
            is_expanding = (prev_width > 0.0 and curr_width > prev_width)
            # Expansion credit requires an UPPER-BAND breakout. The old
            # 'or close > yesterday high' arm awarded the full explosive
            # bonus (+25) to any green tick.
            is_upper_breakout = latest_close >= (bb_up * 0.99)

            if is_expanding and is_upper_breakout:
                score += 25
                expansion_pct = round((curr_width - prev_width) / prev_width * 100.0, 2)
                reasons.append(f"Explosive expansion triggered (+{expansion_pct}% band expansion + Upper Band breakout)")
            elif is_expanding:
                score += 15
                reasons.append("Band expansion beginning without full upper breakout")
            else:
                reasons.append("Bands still in compression phase")

            # ── 4. Institutional Volume Flow Surge ───────────────────────────
            if precomputed_indicators and "rvol" in precomputed_indicators:
                latest_rvol = float(precomputed_indicators["rvol"])
            else:
                rvol_arr = ind.RVOL(volume, timeperiod=self.RVOL_PERIOD) if np.sum(volume) > 0 else np.ones_like(close)
                latest_rvol = float(rvol_arr[-1]) if len(rvol_arr) > 0 else 1.0

            if precomputed_indicators and "cmf" in precomputed_indicators:
                latest_cmf = float(precomputed_indicators["cmf"])
            else:
                cmf_arr = ind.CMF(high, low, close, volume, timeperiod=20) if np.sum(volume) > 0 else np.zeros_like(close)
                latest_cmf = float(cmf_arr[-1]) if len(cmf_arr) > 0 else 0.0

            if latest_rvol >= self.RVOL_MIN_THRESHOLD or latest_cmf > 0.05:
                score += 20
                reasons.append(f"Institutional volume surge (RVOL: {latest_rvol:.2f}x, CMF: {latest_cmf:.2f})")
            elif latest_rvol >= 1.0:
                score += 10
                reasons.append(f"Standard volume confirmed (RVOL: {latest_rvol:.2f}x)")
            else:
                reasons.append(f"Sub-par breakout volume (RVOL: {latest_rvol:.2f}x)")

            # ── 5. MACD Direction Confirmation ───────────────────────────────
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
                logger.warning(f"[S04] {symbol} — NaN in MACD histogram")
                return None

            if hist_curr > 0.0 and hist_curr > hist_prev:
                score += 15
                reasons.append("MACD bullish momentum accelerating")
            elif hist_curr > 0.0:
                score += 8
                reasons.append("MACD positive baseline")
            else:
                reasons.append("MACD momentum not bullish")

            # ── 6. RSI Momentum Baseline (> 50) ──────────────────────────────
            if precomputed_indicators and "rsi" in precomputed_indicators:
                latest_rsi = float(precomputed_indicators["rsi"])
            else:
                rsi = ind.RSI(close, timeperiod=self.RSI_PERIOD)
                latest_rsi = float(rsi[-1]) if len(rsi) > 0 else float("nan")

            if np.isnan(latest_rsi):
                logger.warning(f"[S04] {symbol} — NaN in RSI")
                return None

            if latest_rsi > self.RSI_CONFIRM:
                score += 10
                reasons.append(f"RSI confirms upward velocity ({latest_rsi:.1f} > {self.RSI_CONFIRM:.0f})")
            else:
                reasons.append(f"RSI below baseline ({latest_rsi:.1f} <= {self.RSI_CONFIRM:.0f})")

            # ── 7. Multi-Timeframe Check (HTF Filter) ────────────────────────
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

            # ── ATR for Trade Levels & Risk Sizing ───────────────────────────
            if precomputed_indicators and "atr" in precomputed_indicators:
                latest_atr = float(precomputed_indicators["atr"])
            else:
                atr_vals = ind.ATR(high, low, close, timeperiod=self.ATR_PERIOD)
                latest_atr = float(atr_vals[-1])

            if np.isnan(latest_atr):
                logger.warning(f"[S04] {symbol} — NaN in ATR")
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
                candle_pattern="SQUEEZE_EXPANSION",
                indicator_values={
                    "rsi": round(latest_rsi, 2),
                    "atr": round(latest_atr, 4),
                    "rvol": round(latest_rvol, 2),
                    "cmf": round(latest_cmf, 4),
                    "bb_width_curr": round(curr_width, 6),
                    "bb_width_avg": round(avg_width, 6),
                    "squeeze_pct": squeeze_pct,
                },
                extra_metadata={
                    "vix": round(float(vix), 2),
                    "market_state": market_state,
                    "mqi_level": mqi_level,
                    "is_ttm_squeezed": is_ttm_squeezed,
                    "min_holding_days": self.min_holding_days,
                    "max_holding_days": self.max_holding_days,
                },
            )

        except Exception as e:
            logger.warning(f"[S04] generate_signal exception for {symbol}: {e}")
            return None

    def get_parameters(self) -> Dict[str, Any]:
        """All S04 parameters for MLflow/Optuna experiment tracking."""
        return {
            "strategy_id":            self.name,
            "version":                self.version,
            "bb_period":              self.BB_PERIOD,
            "bb_std":                 self.BB_STD,
            "keltner_ema":            self.KELTNER_EMA,
            "keltner_atr":            self.KELTNER_ATR,
            "keltner_mult":           self.KELTNER_MULT,
            "squeeze_lookback":       self.SQUEEZE_LOOKBACK,
            "base_squeeze_threshold": self.BASE_SQUEEZE_THRESHOLD,
            "macd_fast":              self.MACD_FAST,
            "macd_slow":              self.MACD_SLOW,
            "macd_signal":            self.MACD_SIGNAL,
            "rsi_period":             self.RSI_PERIOD,
            "rsi_confirm":            self.RSI_CONFIRM,
            "atr_period":             self.ATR_PERIOD,
            "rvol_period":            self.RVOL_PERIOD,
            "rvol_min_threshold":     self.RVOL_MIN_THRESHOLD,
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
            f"S04 Bollinger Squeeze & TTM Compression v{self.version} — "
            f"TTM Squeeze (BB inside Keltner / Bandwidth < {int(self.BASE_SQUEEZE_THRESHOLD * 100)}% avg) "
            f"→ Expansion surge (RVOL > {self.RVOL_MIN_THRESHOLD:.2f}x) → MACD momentum + RSI > {self.RSI_CONFIRM:.0f}. "
            f"Min score {self.MIN_SCORE}/100. Holding window: {self.min_holding_days}-{self.max_holding_days} days."
        )
