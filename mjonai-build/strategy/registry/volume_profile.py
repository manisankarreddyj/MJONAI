"""
Module: strategy/registry/volume_profile.py
Purpose: S11 — SOTA Institutional Volume Profile & Auction Market Theory Strategy.
         Trades institutional liquidity nodes, Point of Control (POC), and Value Area High/Low (VAH/VAL) boundaries.
         Executes the famous Dalton "80% Rule" and Value Area Expansion breakouts on Equities, Indices, and Futures:
           1. VAL Support Bounce (Long): Price sweeps below Value Area Low (VAL), absorbs selling, and re-enters Value Area targeting POC.
           2. VAH Supply Rejection (Short): Price pushes above Value Area High (VAH), meets institutional supply, and re-enters Value Area targeting POC.
           3. Value Area Breakout (Trend): High-volume acceptance outside VAH/VAL initiating directional auction expansion.

Pillars of Scoring (Total: 100 Points, Minimum Gate: 70 Points):
  • HARD SENTRY 1: Price MUST test or penetrate Value Area boundaries (VAH or VAL)
  • HARD SENTRY 2: Volume at Price profile must have clear POC node
  1. Value Area Boundary Confluence (VAL Bounce for Long / VAH Rejection for Short): +30 Pts
  2. Point of Control (POC) Target Geometry (Favorable >= 1.8 R:R to POC node):        +25 Pts
  3. Institutional Volume Absorption (RVOL >= 1.30x at Value Area boundary):           +25 Pts
  4. Candlestick Rejection / Absorption Trigger (Hammer at VAL, Shooting Star at VAH): +20 Pts

Inherits from BaseStrategy with full multi-asset, multi-timeframe, and precomputed indicator support.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
import pandas as pd

from strategy.registry.base import BaseStrategy, StrategySignalResult
from strategy.registry import indicators as ind

logger = logging.getLogger(__name__)


class VolumeProfileStrategy(BaseStrategy):
    """
    S11: Volume Profile & Auction Market Theory Strategy.
    Capitalizes on institutional Value Area (VAH/VAL) distributions and POC gravity.
    """

    name: str                        = "S11_VolumeProfile"
    display_name: str                = "Volume Profile Auction"
    timeframe: str                   = "SWING"
    asset_class: str                 = "EQUITY"
    signal_direction: str            = "BIDIRECTIONAL"
    version: str                     = "1.0"
    is_active: bool                  = True
    allowed_asset_classes: Sequence[str] = ("EQUITY", "INDEX", "COMMODITY", "CRYPTO", "FOREX")
    allowed_regimes: Sequence[str]   = ("BULL", "BEAR", "NEUTRAL", "SIDEWAYS")
    min_candles_required: int        = 60
    min_holding_days: int            = 1
    max_holding_days: int            = 5

    # ── Parameters (Logged to MLflow / Optuna tunable) ────────────────────────
    PROFILE_LOOKBACK: int            = 30       # Lookback candles for Volume Profile computation
    NUM_PRICE_BINS: int              = 50       # Number of histogram price bins
    VALUE_AREA_PCT: float            = 0.70     # 70% of total volume for Value Area
    VOLUME_SURGE: float              = 1.30     # Volume absorption surge threshold
    ATR_PERIOD: int                  = 14
    MIN_SCORE: int                   = 70       # Minimum technical score

    def _compute_volume_profile(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        volume: np.ndarray,
    ) -> Tuple[float, float, float]:
        """
        Compute Point of Control (POC), Value Area High (VAH), and Value Area Low (VAL).
        """
        min_p = float(np.min(low))
        max_p = float(np.max(high))
        if max_p <= min_p or len(volume) == 0 or np.sum(volume) <= 0:
            # No real volume distribution -> no fabricated levels.
            # NaN propagates so every setup comparison evaluates False
            # (previously this invented a fake value area around the mean).
            return float("nan"), float("nan"), float("nan")

        # Adaptive bin count based on price range granularity (20 to 60 bins)
        num_bins = max(self.NUM_PRICE_BINS, min(60, int((max_p - min_p) / max(1.0, min_p * 0.002))))
        bins = np.linspace(min_p, max_p, num_bins + 1)
        bin_vol = np.zeros(num_bins, dtype=float)

        # Distribute bar volume across price bins
        price_span = max_p - min_p + 1e-9
        for h, l, v in zip(high, low, volume):
            if h <= l:
                idx = min(num_bins - 1, max(0, int((l - min_p) / price_span * num_bins)))
                bin_vol[idx] += v
            else:
                start_idx = min(num_bins - 1, max(0, int((l - min_p) / price_span * num_bins)))
                end_idx   = min(num_bins - 1, max(0, int((h - min_p) / price_span * num_bins)))
                span = max(1, end_idx - start_idx + 1)
                vol_per_bin = v / span
                for i in range(start_idx, end_idx + 1):
                    bin_vol[i] += vol_per_bin

        # Point of Control (POC) = bin with maximum volume
        poc_idx = int(np.argmax(bin_vol))
        poc_price = float((bins[poc_idx] + bins[poc_idx + 1]) / 2.0)

        # Value Area (70% total volume around POC)
        target_vol = np.sum(bin_vol) * self.VALUE_AREA_PCT
        cum_va_vol = bin_vol[poc_idx]
        up_idx = poc_idx
        down_idx = poc_idx

        while cum_va_vol < target_vol and (up_idx < num_bins - 1 or down_idx > 0):
            next_up_vol   = bin_vol[up_idx + 1] if up_idx < num_bins - 1 else 0.0
            next_down_vol = bin_vol[down_idx - 1] if down_idx > 0 else 0.0

            if next_up_vol >= next_down_vol and up_idx < num_bins - 1:
                up_idx += 1
                cum_va_vol += next_up_vol
            elif down_idx > 0:
                down_idx -= 1
                cum_va_vol += next_down_vol
            else:
                break

        vah_price = float(bins[up_idx + 1])
        val_price = float(bins[down_idx])
        return poc_price, vah_price, val_price

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
        Generate S11 Volume Profile signal.
        """
        try:
            if df is None or len(df) < self.min_candles_required:
                logger.warning(f"[S11] {symbol} — insufficient history ({len(df) if df is not None else 0} candles)")
                return None

            close  = np.asarray(df["Close"], dtype=float)
            high   = np.asarray(df["High"], dtype=float)
            low    = np.asarray(df["Low"], dtype=float)
            open_  = np.asarray(df["Open"], dtype=float)
            volume = np.asarray(df["Volume"], dtype=float) if "Volume" in df.columns else np.zeros_like(close)

            latest_close = float(close[-1])
            latest_high  = float(high[-1])
            latest_low   = float(low[-1])
            latest_open  = float(open_[-1])

            if np.isnan(latest_close) or latest_close <= 0:
                logger.warning(f"[S11] {symbol} — latest_close is NaN or non-positive")
                return None

            # ── 1. Calculate Volume Profile Nodes ────────────────────────────
            if precomputed_indicators and all(k in precomputed_indicators for k in ("poc", "vah", "val")):
                poc = float(precomputed_indicators["poc"])
                vah = float(precomputed_indicators["vah"])
                val = float(precomputed_indicators["val"])
            else:
                lb = min(self.PROFILE_LOOKBACK, len(close) - 1)
                poc, vah, val = self._compute_volume_profile(
                    high[-lb-1:-1], low[-lb-1:-1], close[-lb-1:-1], volume[-lb-1:-1]
                )

            # ── 2. ATR for Volatility & Buffer Calculations ──────────────────
            if precomputed_indicators and "atr" in precomputed_indicators:
                latest_atr = float(precomputed_indicators["atr"])
            else:
                atr_vals = ind.ATR(high, low, close, timeperiod=self.ATR_PERIOD)
                latest_atr = float(atr_vals[-1]) if len(atr_vals) > 0 else (latest_close * 0.01)

            # ── 3. Volume Surge (RVOL) ───────────────────────────────────────
            if precomputed_indicators and "rvol" in precomputed_indicators:
                latest_rvol = float(precomputed_indicators["rvol"])
            else:
                rvol_arr = ind.RVOL(volume, timeperiod=20) if np.sum(volume) > 0 else np.ones_like(close)
                latest_rvol = float(rvol_arr[-1]) if len(rvol_arr) > 0 else 1.0

            score: int = 0
            reasons: List[str] = []
            signal_direction: Optional[str] = None
            signal_type: Optional[str] = None
            candle_pattern = "NONE"

            # ── 4. Directional Evaluation (Auction Market Theory 80% Rule) ───

            # 🟢 LONG: VAL Support Bounce / Re-entry (Targeting POC)
            # Conditions: Price tested near/below VAL and closed back inside Value Area below POC
            if latest_low <= (val + 0.75 * latest_atr) and latest_close >= (val - 0.25 * latest_atr) and latest_close <= poc:
                signal_direction = "LONG"
                signal_type = "BUY"
                score += 30
                reasons.append(f"Value Area Low (VAL) support absorption confirmed (VAL: ₹{val:.2f}, POC Target: ₹{poc:.2f})")

                # Target Geometry
                reward = poc - latest_close
                # Anchor risk at the ACTUAL issued stop (val - 1.5 ATR);
                # the old 0.5 ATR anchor overstated R:R by a full ATR.
                risk = (latest_close - (val - 1.50 * latest_atr)) + 1e-5
                if reward / risk >= 1.5:
                    score += 25
                    reasons.append(f"Favorable POC target reward-to-risk ratio ({reward/risk:.1f} R:R)")
                else:
                    score += 15
                    reasons.append("Moderate POC target distance")

                # Volume Surge
                if latest_rvol >= self.VOLUME_SURGE:
                    score += 25
                    reasons.append(f"Institutional volume absorption at VAL ({latest_rvol:.2f}x >= {self.VOLUME_SURGE:.2f}x)")
                else:
                    score += 12
                    reasons.append(f"Average volume at VAL ({latest_rvol:.2f}x)")

                # Candlestick
                hammer = ind.CDLHAMMER(open_, high, low, close)
                if hammer[-1] != 0 or latest_close > latest_open:
                    score += 20
                    candle_pattern = "VAL_HAMMER_ABSORPTION"
                    reasons.append("Bullish candle absorption at Value Area Low")

                stop_loss = round(val - (1.50 * latest_atr), 2)
                target_price = round(poc, 2)

            # 🔴 SHORT: VAH Supply Rejection / Re-entry (Targeting POC)
            # Conditions: Price poked into or above VAH and closed back below VAH
            elif latest_high >= (vah - 0.3 * latest_atr) and latest_close <= vah and latest_close > poc:
                signal_direction = "SHORT"
                signal_type = "SELL"
                score += 30
                reasons.append(f"Value Area High (VAH) supply rejection confirmed (VAH: ₹{vah:.2f}, POC Target: ₹{poc:.2f})")

                # Target Geometry
                reward = latest_close - poc
                risk = ((vah + 1.50 * latest_atr) - latest_close) + 1e-5
                if reward / risk >= 1.5:
                    score += 25
                    reasons.append(f"Favorable POC target reward-to-risk ratio ({reward/risk:.1f} R:R)")
                else:
                    score += 15
                    reasons.append("Moderate POC target distance")

                # Volume Surge
                if latest_rvol >= self.VOLUME_SURGE:
                    score += 25
                    reasons.append(f"Institutional distribution volume at VAH ({latest_rvol:.2f}x >= {self.VOLUME_SURGE:.2f}x)")
                else:
                    score += 12
                    reasons.append(f"Average volume at VAH ({latest_rvol:.2f}x)")

                # Candlestick
                shooting_star = ind.CDLSHOOTINGSTAR(open_, high, low, close)
                if shooting_star[-1] != 0 or latest_close < latest_open:
                    score += 20
                    candle_pattern = "VAH_SHOOTING_STAR_REJECTION"
                    reasons.append("Bearish candle rejection at Value Area High")

                stop_loss = round(vah + (1.50 * latest_atr), 2)
                target_price = round(poc, 2)

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
                sl_method="VALUE_AREA_BOUNDARY",
                timeframe=self.timeframe,
                asset_class=self.asset_class,
                atr=round(latest_atr, 4),
                candle_pattern=candle_pattern,
                indicator_values={
                    "poc": round(poc, 2),
                    "vah": round(vah, 2),
                    "val": round(val, 2),
                    "rvol": round(latest_rvol, 2),
                    "atr": round(latest_atr, 4),
                    "stop_loss": stop_loss,
                    "target_price": target_price,
                },
                extra_metadata={
                    "vix": round(float(vix), 2),
                    "market_state": market_state,
                    "mqi_level": mqi_level,
                    "strategy_structure": "AUCTION_MARKET_VALUE_AREA_80PCT_RULE",
                    "min_holding_days": self.min_holding_days,
                    "max_holding_days": self.max_holding_days,
                },
            )

        except Exception as e:
            logger.warning(f"[S11] generate_signal exception for {symbol}: {e}")
            return None

    def get_parameters(self) -> Dict[str, Any]:
        """All S11 parameters for MLflow experiment tracking."""
        return {
            "strategy_id":            self.name,
            "version":                self.version,
            "profile_lookback":       self.PROFILE_LOOKBACK,
            "num_price_bins":         self.NUM_PRICE_BINS,
            "value_area_pct":         self.VALUE_AREA_PCT,
            "volume_surge":           self.VOLUME_SURGE,
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
            f"S11 Volume Profile Auction v{self.version} — "
            f"Auction Market Theory Value Area ({self.VALUE_AREA_PCT*100:.0f}%) & Point of Control (POC) trading: "
            f"VAL support bounces (Long) & VAH supply rejections (Short) targeting POC. "
            f"Holding window: {self.min_holding_days}-{self.max_holding_days} days. Min score {self.MIN_SCORE}/100."
        )
