"""
Unit tests for research/optimization/auto_tuner.py (StrategyAutoTuner).
Verifies regime partitioning, stability scoring, and calibration contract safety.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import pytest

from mjonai.research.optimization.auto_tuner import (
    StrategyAutoTuner,
    RegimeCalibration,
    RegimeAutoTuningReport,
)


def test_partition_by_regime():
    # Build synthetic 300-day series with varying volatility
    np.random.seed(42)
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(300)]
    close = 100.0 * np.exp(np.cumsum(np.random.normal(0, 0.015, 300)))
    df = pd.DataFrame({
        "Open": close,
        "High": close * 1.01,
        "Low": close * 0.99,
        "Close": close,
        "Volume": [100000] * 300,
    }, index=dates)

    tuner = StrategyAutoTuner()
    partitions = tuner.partition_by_regime(df)
    assert "LOW_VOLATILITY" in partitions
    assert "HIGH_VOLATILITY" in partitions
    assert "NORMAL" in partitions
    assert sum(len(p) for p in partitions.values()) == 300


def test_evaluate_stability_perfect_agreement():
    tuner = StrategyAutoTuner()
    calibrations = {
        "LOW_VOLATILITY": RegimeCalibration(
            regime_name="LOW_VOLATILITY",
            best_parameters={"rsi_period": 14, "atr_mult": 2.0},
            sharpe_ratio=1.8,
            profit_factor=2.1,
            total_trades=20,
            win_rate_pct=65.0,
            sample_bars=100,
        ),
        "HIGH_VOLATILITY": RegimeCalibration(
            regime_name="HIGH_VOLATILITY",
            best_parameters={"rsi_period": 14, "atr_mult": 2.0},
            sharpe_ratio=1.4,
            profit_factor=1.8,
            total_trades=15,
            win_rate_pct=60.0,
            sample_bars=100,
        ),
    }
    stability = tuner.evaluate_stability(calibrations)
    assert stability == 1.0  # Perfect agreement across regimes


def test_evaluate_stability_divergence():
    tuner = StrategyAutoTuner()
    calibrations = {
        "LOW_VOLATILITY": RegimeCalibration(
            regime_name="LOW_VOLATILITY",
            best_parameters={"rsi_period": 14, "atr_mult": 1.5},
            sharpe_ratio=1.8,
            profit_factor=2.1,
            total_trades=20,
            win_rate_pct=65.0,
            sample_bars=100,
        ),
        "HIGH_VOLATILITY": RegimeCalibration(
            regime_name="HIGH_VOLATILITY",
            best_parameters={"rsi_period": 21, "atr_mult": 3.0},
            sharpe_ratio=1.4,
            profit_factor=1.8,
            total_trades=15,
            win_rate_pct=60.0,
            sample_bars=100,
        ),
    }
    stability = tuner.evaluate_stability(calibrations)
    assert stability == 0.0  # Complete divergence across regimes
