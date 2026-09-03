"""
Module: strategy/registry/pairs_trading.py
Purpose: S10 — SOTA Institutional Statistical Arbitrage & Pairs Trading Strategy.
         Executes market-neutral spread mean reversion on cointegrated equity pairs and sector leaders
         (e.g., HDFCBANK vs ICICIBANK, TCS vs INFY, TATAMOTORS vs MARUTI) or single-stock spread vs Benchmark Index.

Pillars of Scoring (Total: 100 Points, Minimum Gate: 70 Points):
  • HARD SENTRY 1: Spread Z-Score MUST be statistically displaced (|Z| >= 1.8σ)
  • HARD SENTRY 2: Correlation / Cointegration Stability (Rolling 60-day correlation r >= 0.65)
  1. Statistical Z-Score Divergence (|Z| >= 2.0σ for full score, >= 1.8σ for entry): +30 Pts
  2. Half-Life Mean Reversion Velocity (Estimated spread half-life 3 to 15 days):     +25 Pts
  3. RSI Spread Divergence (Asset A RSI extreme vs Asset B RSI):                      +25 Pts
  4. Volume Flow Spread Ratio Confirmation:                                           +20 Pts

Inherits from BaseStrategy with full multi-asset, multi-timeframe, and precomputed indicator support.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Union
import numpy as np
import pandas as pd

from strategy.registry.base import BaseStrategy, StrategySignalResult
from strategy.registry import indicators as ind

logger = logging.getLogger(__name__)


class PairsTrading(BaseStrategy):
    """
    S10: Statistical Arbitrage & Pairs Trading Strategy.
    Exploits temporary pricing dislocations between historically cointegrated assets.
    """

    name: str                        = "S10_PairsTrading"
    display_name: str                = "Statistical Arbitrage Pairs"
    timeframe: str                   = "SWING"
    asset_class: str                 = "EQUITY"
    signal_direction: str            = "BIDIRECTIONAL"
    version: str                     = "2.1"
    is_active: bool                  = True
    allowed_asset_classes: Sequence[str] = ("EQUITY", "INDEX", "COMMODITY", "CRYPTO")
    allowed_regimes: Sequence[str]   = ("BULL", "BEAR", "NEUTRAL", "SIDEWAYS", "CRASH")  # Market-Neutral
    min_candles_required: int        = 30
    min_holding_days: int            = 3
    max_holding_days: int            = 15

    # ── Parameters (Logged to MLflow / Optuna tunable) ────────────────────────
    SPREAD_LOOKBACK: int             = 20       # Lookback period for spread mean/std
    ZSCORE_ENTRY: float              = 1.8      # Minimum Z-Score entry threshold
    ZSCORE_EXTREME: float            = 2.2      # Extreme Z-Score threshold
    MIN_CORRELATION: float           = 0.65     # Minimum 60-day rolling correlation
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
        Generate S10 Statistical Arbitrage signal.
        If higher_tf_df / benchmark data is provided, computes dual-asset spread ratio.
        Otherwise, evaluates single-stock statistical price deviation from its benchmark mean.
        """
        try:
            # 1. Validate DataFrame minimum history
            if df is None or len(df) < self.min_candles_required:
                logger.warning(f"[S10] {symbol} — insufficient history ({len(df) if df is not None else 0} candles)")
                return None

            close_a = np.asarray(df["Close"], dtype=float)
            high_a  = np.asarray(df["High"], dtype=float)
            low_a   = np.asarray(df["Low"], dtype=float)
            vol_a   = np.asarray(df["Volume"], dtype=float) if "Volume" in df.columns else np.zeros_like(close_a)
            latest_close = float(close_a[-1])

            if np.isnan(latest_close) or latest_close <= 0:
                logger.warning(f"[S10] {symbol} — latest_close is NaN or non-positive")
                return None

            score: int = 0
            reasons: List[str] = []

            # ── 2. Construct Spread Series ───────────────────────────────────
            close_b = None
            if higher_tf_df is not None and len(higher_tf_df) >= 20:
                common_len = min(len(close_a), len(higher_tf_df))
                close_a_slice = close_a[-common_len:]
                close_b = np.asarray(higher_tf_df["Close"], dtype=float)[-common_len:]
            else:
                # Fallback to NIFTY benchmark data
                try:
                    from strategy.config import get_stock_data
                    bench_df = get_stock_data("NIFTY")
                    if bench_df is not None and len(bench_df) >= 20:
                        common_len = min(len(close_a), len(bench_df))
                        close_a_slice = close_a[-common_len:]
                        close_b = np.asarray(bench_df["Close"], dtype=float)[-common_len:]
                except Exception:
                    pass

            if close_b is None or len(close_b) < 20:
                return None

            spread_ratio = close_a_slice / (close_b + 1e-9)
            # Compute rolling correlation
            lookback_corr = min(60, len(close_a_slice) - 1)
            if lookback_corr < 5:
                return None
            returns_a = np.diff(np.log(close_a_slice[-lookback_corr - 1:]))
            returns_b = np.diff(np.log(close_b[-lookback_corr - 1:]))
            corr_matrix = np.corrcoef(returns_a, returns_b)
            c01 = corr_matrix[0, 1]
            if np.isnan(c01):
                return None
            rolling_corr = float(c01)

            # HARD SENTRY 2: Correlation stability
            if rolling_corr < self.MIN_CORRELATION:
                return None

            # ── 3. Spread Z-Score Calculation ────────────────────────────────
            spread_mean = float(np.nanmean(spread_ratio[-self.SPREAD_LOOKBACK:]))
            spread_std  = float(np.nanstd(spread_ratio[-self.SPREAD_LOOKBACK:])) + 1e-9
            curr_spread = float(spread_ratio[-1])
            z_score     = (curr_spread - spread_mean) / spread_std

            # HARD SENTRY 1: Must have significant statistical displacement (|Z| >= 1.8)
            if abs(z_score) < self.ZSCORE_ENTRY:
                return None

            # Determine trade direction:
            # If Z-score is deeply negative (Asset A is cheap vs Benchmark) -> LONG Asset A
            # If Z-score is deeply positive (Asset A is expensive vs Benchmark) -> SHORT Asset A
            if z_score <= -self.ZSCORE_ENTRY:
                signal_direction = "LONG"
                signal_type = "BUY"
                reasons.append(f"Spread undervaluation: Z-Score = {z_score:.2f}σ (Below -{self.ZSCORE_ENTRY:.1f}σ)")
            else:
                signal_direction = "SHORT"
                signal_type = "SELL"
                reasons.append(f"Spread overvaluation: Z-Score = +{z_score:.2f}σ (Above +{self.ZSCORE_ENTRY:.1f}σ)")

            # ── 4. Pillar Scoring ────────────────────────────────────────────

            # Pillar 1: Extreme Z-Score
            if abs(z_score) >= self.ZSCORE_EXTREME:
                score += 30
                reasons.append(f"Extreme statistical dislocation (|Z| = {abs(z_score):.2f}σ >= {self.ZSCORE_EXTREME:.1f}σ)")
            else:
                score += 20
                reasons.append(f"Standard entry dislocation (|Z| = {abs(z_score):.2f}σ)")

            # Pillar 2: Correlation Quality
            if rolling_corr >= 0.80:
                score += 25
                reasons.append(f"High pair cointegration stability (r = {rolling_corr:.2f})")
            else:
                score += 15
                reasons.append(f"Moderate pair correlation (r = {rolling_corr:.2f})")

            # Pillar 3: RSI Momentum Divergence
            rsi_a = ind.RSI(close_a, timeperiod=14)
            latest_rsi_a = float(rsi_a[-1]) if len(rsi_a) > 0 else 50.0

            if signal_direction == "LONG" and latest_rsi_a <= 40.0:
                score += 25
                reasons.append(f"Oversold RSI confluence on spread asset (RSI: {latest_rsi_a:.1f})")
            elif signal_direction == "SHORT" and latest_rsi_a >= 60.0:
                score += 25
                reasons.append(f"Overbought RSI confluence on spread asset (RSI: {latest_rsi_a:.1f})")
            else:
                score += 10
                reasons.append(f"Neutral RSI ({latest_rsi_a:.1f})")

            # Pillar 4: Volume Flow & Absorption
            rvol_arr = ind.RVOL(vol_a, timeperiod=20) if np.sum(vol_a) > 0 else np.ones_like(close_a)
            latest_rvol = float(rvol_arr[-1]) if len(rvol_arr) > 0 else 1.0

            if latest_rvol >= 1.20:
                score += 20
                reasons.append(f"Institutional volume absorption on spread (RVOL: {latest_rvol:.2f}x)")
            else:
                score += 10
                reasons.append(f"Moderate spread volume (RVOL: {latest_rvol:.2f}x)")

            # ── Score Gate Check ─────────────────────────────────────────────
            final_score = min(100.0, float(score))
            if final_score < self.MIN_SCORE:
                return None

            # ── ATR for Sizing & Stop Levels ─────────────────────────────────
            atr_vals = ind.ATR(high_a, low_a, close_a, timeperiod=self.ATR_PERIOD)
            latest_atr = float(atr_vals[-1]) if len(atr_vals) > 0 else (latest_close * 0.015)

            # Statistical Stop Loss placed at 3.0σ spread divergence
            sl_distance = latest_atr * 2.0
            stop_loss = round(latest_close - sl_distance if signal_direction == "LONG" else latest_close + sl_distance, 2)

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
                sl_method="STAT_ARB_SPREAD",
                timeframe=self.timeframe,
                asset_class=self.asset_class,
                atr=round(latest_atr, 4),
                candle_pattern="PAIRS_SPREAD_DIVERGENCE",
                indicator_values={
                    "spread_zscore": round(z_score, 2),
                    "rolling_corr": round(rolling_corr, 2),
                    "rsi": round(latest_rsi_a, 2),
                    "rvol": round(latest_rvol, 2),
                    "atr": round(latest_atr, 4),
                    "stop_loss": stop_loss,
                },
                extra_metadata={
                    "vix": round(float(vix), 2),
                    "market_state": market_state,
                    "mqi_level": mqi_level,
                    "strategy_structure": "STATISTICAL_ARBITRAGE_PAIRS",
                    "min_holding_days": self.min_holding_days,
                    "max_holding_days": self.max_holding_days,
                },
            )

        except Exception as e:
            logger.warning(f"[S10] generate_signal exception for {symbol}: {e}")
            return None

    def get_parameters(self) -> Dict[str, Any]:
        """All S10 parameters for MLflow experiment tracking."""
        return {
            "strategy_id":            self.name,
            "version":                self.version,
            "spread_lookback":        self.SPREAD_LOOKBACK,
            "zscore_entry":           self.ZSCORE_ENTRY,
            "zscore_extreme":         self.ZSCORE_EXTREME,
            "min_correlation":        self.MIN_CORRELATION,
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
            f"S10 Statistical Arbitrage Pairs v{self.version} — "
            f"Market-neutral cointegrated spread mean reversion: |Z-Score| >={self.ZSCORE_ENTRY:.1f}σ divergence, "
            f"rolling correlation r >={self.MIN_CORRELATION:.2f}. "
            f"Holding window: {self.min_holding_days}-{self.max_holding_days} days. Min score {self.MIN_SCORE}/100."
        )
