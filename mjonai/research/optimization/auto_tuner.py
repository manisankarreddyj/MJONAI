"""
Module: research/optimization/auto_tuner.py
Purpose: SOTA Automated Strategy Regime Auto-Tuner.
         Partitions historical walk-forward windows by market regime (Low Vol, High Vol,
         Trending, Mean-Reverting) to discover regime-optimal parameter sets and measure
         parameter stability across market transitions under canonical friction (ADR-0002).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
import pandas as pd

from mjonai.research.optimization.models import (
    ParameterDefinition,
    ParameterSet,
    OptimizationResult,
    OptimizationSummary,
)
from mjonai.research.optimization.parameters import ParameterGrid
from mjonai.research.optimization.grid_search import GridSearchOptimizer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegimeCalibration:
    """Optimal calibrated parameter configuration for a specific market regime."""
    regime_name: str
    best_parameters: Dict[str, Any]
    sharpe_ratio: float
    profit_factor: float
    total_trades: int
    win_rate_pct: float
    sample_bars: int


@dataclass(frozen=True)
class RegimeAutoTuningReport:
    """Consolidated report across all market regimes with parameter stability score."""
    strategy_name: str
    symbol: str
    calibrations: Dict[str, RegimeCalibration]
    parameter_stability_score: float  # 0.0 (overfitted/unstable) to 1.0 (highly robust)
    default_fallback_parameters: Dict[str, Any]


class StrategyAutoTuner:
    """
    Automated Multi-Regime Strategy Parameter Calibration Engine.
    """

    def __init__(
        self,
        min_trades_per_regime: int = 5,
        friction_bps: float = 11.42,
    ):
        self.min_trades = min_trades_per_regime
        self.friction_bps = friction_bps
        self._optimizer = GridSearchOptimizer(min_trades=min_trades_per_regime)

    def partition_by_regime(
        self,
        df: pd.DataFrame,
        vix_series: Optional[Sequence[float]] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        Partition historical candle DataFrame into distinct regime sub-frames.
        """
        if df is None or len(df) < 50:
            return {"NORMAL": df if df is not None else pd.DataFrame()}

        close = np.asarray(df["Close"], dtype=float)
        # 20-period rolling volatility proxy (annualized %)
        log_ret = np.diff(np.log(close), prepend=0.0)
        rolling_std = pd.Series(log_ret, index=df.index).rolling(20).std().fillna(0.01) * np.sqrt(252) * 100.0

        low_vol_mask = rolling_std < 14.0
        high_vol_mask = rolling_std > 22.0
        normal_mask = (~low_vol_mask) & (~high_vol_mask)

        return {
            "LOW_VOLATILITY": df[low_vol_mask],
            "HIGH_VOLATILITY": df[high_vol_mask],
            "NORMAL": df[normal_mask],
        }

    def evaluate_stability(
        self,
        calibrations: Dict[str, RegimeCalibration],
    ) -> float:
        """
        Calculate parameter stability across market regimes.
        Measures parameter variance across regimes (1.0 = identical parameters optimal across all regimes).
        """
        if len(calibrations) <= 1:
            return 1.0

        param_names = set()
        for c in calibrations.values():
            param_names.update(c.best_parameters.keys())

        if not param_names:
            return 1.0

        agreement_count = 0
        total_checks = 0

        first_cal = list(calibrations.values())[0]
        for p in param_names:
            base_val = first_cal.best_parameters.get(p)
            for other_cal in list(calibrations.values())[1:]:
                total_checks += 1
                if other_cal.best_parameters.get(p) == base_val:
                    agreement_count += 1

        return round(agreement_count / max(1, total_checks), 2)
