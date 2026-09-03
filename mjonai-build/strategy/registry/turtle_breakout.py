"""
Module: strategy/registry/turtle_breakout.py
Purpose: S03 — Turtle Breakout (v3.0), rebuilt to the ORIGINAL
         Richard Dennis / William Eckhardt Turtle rules after the
         2026-08-23 audit found v2.2's stops denominated in BARS
         (~hours on intraday charts) contradicting its positional
         holding promise.

Original-rule fidelity (see OriginalTurtleRules.pdf / TradingBlox):
  • Entry   : close breaks above the prior 20-day Donchian high
  • N       : ATR over 20 periods (the Turtle volatility unit)
  • Risk    : initial stop = entry - 2N  (~2% account risk at 1-unit sizing)
  • Exit    : trail the 10-day low (no profit target, no time stop;
              a max-holding cap remains as a practical disaster brake)
  • Filter  : price above EMA200 (macro regime gate)

QUALIFICATION PILLARS (scored on top of the hard rules, gate 75/100):
  1. Clean breakout close near candle high .................. +25
  2. Major 55-day Donchian breakout / ATR expansion ......... +25
  3. Institutional volume surge (RVOL or CMF) ............... +25
  4. Trend velocity (ADX >= 20 & +DI > -DI) ................. +25
  Bonus: tight pre-breakout consolidation base .............. +10
  HTF (weekly/daily EMA50) resistance penalty ............... -15

RUNTIME REQUIREMENT: this strategy MUST run on DAILY bars. Every
period below (20/55/10-day) is denominated in DAYS. A runtime guard
rejects sub-daily candle frames outright so the v2.2 unit-mismatch
bug can never recur silently.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Union
import numpy as np
import pandas as pd

from strategy.registry.base import BaseStrategy, StrategySignalResult
from strategy.registry import indicators as ind

logger = logging.getLogger(__name__)


class TurtleBreakout(BaseStrategy):
    """
    S03 — Turtle Breakout Positional Strategy (original-rules faithful).

    Research targets:
        Win rate ~35-45% (classic trend-following payoff distribution)
        RR target: open-ended — exits come from the 10-day-low trail,
        not from a fixed profit target
        Best regime: BULL trending market
        Worst regime: SIDEWAYS / tight chop
    """

    name: str                        = "S03_TurtleBreakout"
    display_name: str                = "Turtle Breakout"
    timeframe: str                   = "POSITIONAL"
    asset_class: str                 = "EQUITY"
    version: str                     = "3.0"
    is_active: bool                  = True
    allowed_asset_classes: Sequence[str] = ("EQUITY", "INDEX", "COMMODITY", "CRYPTO", "FOREX")
    allowed_regimes: Sequence[str]   = ("BULL", "NEUTRAL", "SIDEWAYS")
    # EMA200 needs real history; 240 keeps daily research frames viable
    # while avoiding the worst of the ewm seed bias.
    min_candles_required: int        = 240
    min_holding_days: int            = 5
    max_holding_days: int            = 45   # disaster cap only — the real
                                            # exit is the 10-day-low trail

    # ── Parameters (Logged to MLflow / Optuna tunable) ────────────────────────
    BREAKOUT_PERIOD_S1: int          = 20       # System 1 Donchian High Period
    BREAKOUT_PERIOD_S2: int          = 55       # System 2 Major Donchian High Period
    N_ATR_PERIOD: int                = 20       # Turtle N = ATR(20)  [was ATR_PERIOD=14]
    SL_PERIOD: int                   = 10       # Days for the trailing EXIT low
    RISK_MULTIPLE_N: float           = 2.0      # Initial stop = entry - 2N (Turtle standard)

    VOLUME_PERIOD: int               = 20       # Volume average period
    VOLUME_CONFIRM: float            = 1.30     # Volume surge multiplier (1.30x)

    EMA_LONG: int                    = 200      # Macro trend filter (EMA200)
    ADX_PERIOD: int                  = 14       # Trend strength period
    ADX_MIN_STRENGTH: float          = 20.0     # Minimum ADX for trend velocity

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
        Generate S03 Turtle Breakout signal for given symbol and market conditions.
        """
        try:
            # 0. TIMEFRAME GUARD: all periods are in DAYS. Sub-daily
            # candle frames turn the 20/55/10-day rules into hour-scale
            # noise — reject instead of trading a corrupted system.
            try:
                idx = df.index
                if len(idx) >= 3:
                    deltas = pd.Series(idx).diff().dropna()
                    median_bar = deltas.median()
                    if hasattr(median_bar, "total_seconds") and median_bar.total_seconds() < 86400 * 0.9:
                        logger.error(
                            f"[S03] {symbol} — REJECTED: candles are sub-daily "
                            f"(median {median_bar}). Turtle periods are denominated in DAYS."
                        )
                        return None
            except Exception:
                pass  # non-datetime index (tests) — skip guard

            # 1. Validate DataFrame minimum history
            is_valid, reason = self.validate_ohlcv_dataframe(df, min_candles=self.min_candles_required)
            if not is_valid:
                logger.warning(f"[S03] {symbol} — {reason}")
                return None

            close  = np.asarray(df["Close"], dtype=float)
            high   = np.asarray(df["High"], dtype=float)
            low    = np.asarray(df["Low"], dtype=float)
            open_  = np.asarray(df["Open"], dtype=float)
            volume = np.asarray(df["Volume"], dtype=float) if "Volume" in df.columns else np.zeros_like(close)

            score: int = 0
            reasons: List[str] = []

            # ── 1. Donchian 20-Day High Breakout (HARD SENTRY 1) ───────────────
            # Exclude current bar — use confirmed prior 20-day high
            if precomputed_indicators and "donchian_high_20" in precomputed_indicators:
                lookback_high_20 = float(precomputed_indicators["donchian_high_20"])
            else:
                lookback_high_20 = float(np.max(high[-self.BREAKOUT_PERIOD_S1 - 1 : -1]))

            latest_close = float(close[-1])
            is_breakout_20 = latest_close > lookback_high_20

            # HARD SENTRY: Must break above the 20-day high
            if not is_breakout_20 or lookback_high_20 <= 0:
                return None

            breakout_pct = round((latest_close - lookback_high_20) / lookback_high_20 * 100.0, 2)
            reasons.append(f"20-day Donchian high breakout (+{breakout_pct}%)")

            # ── 2. EMA200 Macro Trend Filter (HARD SENTRY 2) ─────────────────
            if precomputed_indicators and "ema_long" in precomputed_indicators:
                ema200_val = float(precomputed_indicators["ema_long"])
            else:
                ema200 = ind.EMA(close, timeperiod=self.EMA_LONG)
                ema200_val = float(ema200[-1]) if len(ema200) > 0 else float("nan")

            if np.isnan(ema200_val):
                logger.warning(f"[S03] {symbol} — EMA200 is NaN")
                return None

            # HARD SENTRY: Cannot buy breakouts below 200 EMA
            if latest_close <= ema200_val:
                return None

            # ── 3. Turtle N (ATR-20 Volatility Unit) ─────────────────────────
            if precomputed_indicators and "atr" in precomputed_indicators and "atr_avg" in precomputed_indicators:
                curr_atr = float(precomputed_indicators["atr"])
                avg_atr  = float(precomputed_indicators["atr_avg"])
            else:
                atr_vals = ind.ATR(high, low, close, timeperiod=self.N_ATR_PERIOD)
                curr_atr = float(atr_vals[-1]) if len(atr_vals) > 0 else 0.0
                avg_atr  = float(np.nanmean(atr_vals[-self.N_ATR_PERIOD - 1 : -1])) if len(atr_vals) > self.N_ATR_PERIOD else curr_atr

            if np.isnan(curr_atr) or curr_atr <= 0:
                logger.warning(f"[S03] {symbol} — NaN or zero ATR")
                return None

            n_unit = curr_atr  # The Turtle N

            # ── 4. Clean Breakout Close (No Shooting Stars / Bull Traps) ─────
            latest_high = float(high[-1])
            is_clean_close = latest_close >= (latest_high - (0.25 * n_unit))

            if is_clean_close:
                score += 25
                reasons.append("Clean breakout close near candle high (Buyers in full control)")
            else:
                reasons.append("Breakout bar closed with upper wick pullback")

            # ── 5. System 2 (55-Day Major Breakout) & ATR Expansion ──────────
            lookback_high_55 = float(np.max(high[-self.BREAKOUT_PERIOD_S2 - 1 : -1])) if len(high) >= self.BREAKOUT_PERIOD_S2 + 1 else lookback_high_20
            is_breakout_55 = latest_close > lookback_high_55
            is_atr_expanding = curr_atr > avg_atr

            if is_breakout_55:
                score += 25
                reasons.append("Major 55-day (Quarterly) Donchian breakout confirmed (System 2)")
            elif is_atr_expanding:
                score += 18
                reasons.append(f"ATR volatility expanding ({curr_atr:.2f} > avg {avg_atr:.2f})")
            else:
                reasons.append("20-day standard breakout without major 55-day expansion")

            # ── 6. Pre-Breakout Tight Base Consolidation (Coiled Spring) ─────
            prior_20_high = float(np.max(high[-self.BREAKOUT_PERIOD_S1 - 1 : -1]))
            prior_20_low  = float(np.min(low[-self.BREAKOUT_PERIOD_S1 - 1 : -1]))
            base_width = (prior_20_high - prior_20_low) / (n_unit + 1e-10)

            if base_width <= 3.5:
                score += 10
                reasons.append(f"Tight Pre-Breakout Consolidation Base ({base_width:.1f} Ns — Coiled Spring)")

            # ── 7. Institutional Volume Flow Surge ───────────────────────────
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
                score += 25
                reasons.append(f"Institutional volume surge (RVOL: {latest_rvol:.2f}x >= {self.VOLUME_CONFIRM:.2f}x, CMF: {latest_cmf:.2f})")
            elif latest_rvol >= 1.0:
                score += 12
                reasons.append(f"Average volume confirmed (RVOL: {latest_rvol:.2f}x)")
            else:
                reasons.append(f"Sub-par breakout volume (RVOL: {latest_rvol:.2f}x)")

            # ── 8. Trend Velocity Confirmation (ADX & Directional Movement) ──
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

            if latest_adx >= self.ADX_MIN_STRENGTH and latest_plus_di > latest_minus_di:
                score += 25
                reasons.append(f"Strong trend velocity (ADX: {latest_adx:.1f} >= {self.ADX_MIN_STRENGTH:.0f}, +DI > -DI)")
            elif latest_plus_di > latest_minus_di:
                score += 15
                reasons.append(f"Positive directional momentum (+DI > -DI, ADX: {latest_adx:.1f})")
            else:
                reasons.append(f"Weak directional velocity (ADX: {latest_adx:.1f})")

            # ── 9. Multi-Timeframe Check (HTF Filter) ────────────────────────
            if higher_tf_df is not None and len(higher_tf_df) >= 50:
                htf_close = np.asarray(higher_tf_df["Close"], dtype=float)
                htf_ema50 = ind.EMA(htf_close, timeperiod=50)
                if htf_close[-1] < htf_ema50[-1]:
                    score = max(0, score - 15)
                    reasons.append("Higher timeframe (Weekly/Daily) EMA50 resistance penalty applied")

            # ── Score Gate Check ─────────────────────────────────────────────
            final_score = min(100.0, float(score))
            if final_score < self.MIN_SCORE:
                return None

            # ── TURTLE RISK: Initial stop = entry - 2N ───────────────────────
            hard_stop_2n = latest_close - (self.RISK_MULTIPLE_N * n_unit)
            if hard_stop_2n <= 0:
                logger.warning(f"[S03] {symbol} — 2N stop non-positive")
                return None

            # Trailing EXIT reference: confirmed prior 10-day low
            # (the original Turtle exit; enforced by the position
            # tracker as a trail, not by this one-shot signal).
            trail_exit_low = float(np.min(low[-self.SL_PERIOD - 1 : -1]))
            if np.isnan(trail_exit_low) or trail_exit_low <= 0:
                logger.warning(f"[S03] trail_exit_low NaN for {symbol}")
                return None

            # Emit the 2N stop as the RISK anchor (swing_low slot —
            # consumed downstream as the stop level). The 10-day-low
            # trail travels alongside as an explicit exit rule.
            pyramid_step = round(0.5 * n_unit, 4)

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
                swing_low=round(hard_stop_2n, 2),
                sl_method="TURTLE_2N",
                timeframe=self.timeframe,
                asset_class=self.asset_class,
                atr=round(n_unit, 4),
                candle_pattern="DONCHIAN_BREAKOUT",
                indicator_values={
                    "rvol": round(latest_rvol, 2),
                    "cmf": round(latest_cmf, 4),
                    "atr_n": round(n_unit, 4),
                    "adx": round(latest_adx, 2),
                    "lookback_high_20": round(lookback_high_20, 2),
                    "lookback_high_55": round(lookback_high_55, 2),
                    "hard_stop_2n": round(hard_stop_2n, 2),
                    "trail_exit_low_10d": round(trail_exit_low, 2),
                    "pyramid_step": pyramid_step,
                    "breakout_pct": breakout_pct,
                    "ema_long": round(ema200_val, 2),
                },
                extra_metadata={
                    "vix": round(float(vix), 2),
                    "market_state": market_state,
                    "mqi_level": mqi_level,
                    "is_breakout_55": is_breakout_55,
                    "exit_rule": "TRAIL_10_DAY_LOW",
                    "min_holding_days": self.min_holding_days,
                    "max_holding_days": self.max_holding_days,
                },
            )

        except Exception as e:
            logger.warning(f"[S03] generate_signal exception for {symbol}: {e}")
            return None

    def get_parameters(self) -> Dict[str, Any]:
        """All S03 parameters for MLflow experiment tracking."""
        return {
            "strategy_id":            self.name,
            "version":                self.version,
            "breakout_period_s1":     self.BREAKOUT_PERIOD_S1,
            "breakout_period_s2":     self.BREAKOUT_PERIOD_S2,
            "n_atr_period":           self.N_ATR_PERIOD,
            "risk_multiple_n":        self.RISK_MULTIPLE_N,
            "sl_period":              self.SL_PERIOD,
            "volume_period":          self.VOLUME_PERIOD,
            "volume_confirm":         self.VOLUME_CONFIRM,
            "ema_long":               self.EMA_LONG,
            "adx_period":             self.ADX_PERIOD,
            "adx_min_strength":       self.ADX_MIN_STRENGTH,
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
            f"S03 Turtle Breakout v{self.version} (original-rules faithful) — "
            f"{self.BREAKOUT_PERIOD_S1}-day Donchian breakout above EMA{self.EMA_LONG}; "
            f"N=ATR({self.N_ATR_PERIOD}), risk stop entry-{self.RISK_MULTIPLE_N:.0f}N, "
            f"exit trails the {self.SL_PERIOD}-day low (TURTLE_2N). DAILY bars required. "
            f"Positional {self.min_holding_days}-{self.max_holding_days} days (cap only). Min score {self.MIN_SCORE}/100."
        )
