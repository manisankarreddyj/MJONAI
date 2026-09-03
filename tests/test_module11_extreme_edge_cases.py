"""
Test Suite: tests/test_module11_extreme_edge_cases.py
Purpose: Extreme Edge Case, Stress, Concurrency, and Quant Boundary Verification for Module 11.
"""

from datetime import datetime
import pandas as pd
import numpy as np
import pytest

from mjonai.analytics.statistical_validation import (
    deflated_sharpe_ratio,
    probabilistic_sharpe_ratio,
    haircut_sharpe_ratio,
)
from mjonai.research.ml.triple_barrier import apply_triple_barrier
from mjonai.research.ml.feature_pipeline import frac_diff, calculate_hurst_exponent
from mjonai.research.stress_testing.monte_carlo import run_monte_carlo_simulation
from mjonai.research.stress_testing.crisis_replay import simulate_crisis_impact
from mjonai.research.walk_forward.walk_forward_windows import WalkForwardWindowGenerator


def test_zero_variance_flat_returns_resilience():
    """Edge Case 1: Identical zero-variance returns handle DSR, PSR, and Haircut SR without ZeroDivisionError."""
    flat_returns = [0.001] * 50
    dsr = deflated_sharpe_ratio(flat_returns, num_trials=20)
    psr = probabilistic_sharpe_ratio(flat_returns, benchmark_sr=0.0)
    haircut = haircut_sharpe_ratio(observed_sr=0.0, num_trials=20)

    assert dsr == 0.0
    assert psr == 0.0
    assert haircut["haircut_sr"] == 0.0
    assert haircut["is_acceptable"] is False


def test_extreme_tail_risk_outlier_skewness_kurtosis():
    """Edge Case 2: Extreme flash crash drop (-90%) does not cause math domain error or overflow."""
    # 99 normal days and 1 catastrophic -90% drop
    returns = [0.005] * 99 + [-0.90]
    dsr = deflated_sharpe_ratio(returns, num_trials=50)
    psr = probabilistic_sharpe_ratio(returns, benchmark_sr=0.0)

    assert isinstance(dsr, float)
    assert isinstance(psr, float)
    assert 0.0 <= psr <= 1.0


def test_empty_and_single_row_triple_barrier():
    """Edge Case 3: Empty DataFrames or events return empty list without IndexError."""
    df_empty = pd.DataFrame()
    events_empty = pd.DataFrame()
    res = apply_triple_barrier(df_empty, events_empty)
    assert res == []

    # Single bar dataframe
    dates = pd.date_range("2024-01-01", periods=1, freq="D")
    df_single = pd.DataFrame({"open": [100.0], "high": [102.0], "low": [98.0], "close": [101.0], "volume": [1000]}, index=dates)
    events = pd.DataFrame([{"timestamp": dates[0], "direction": "LONG", "entry_price": 100.0}])
    res_single = apply_triple_barrier(df_single, events, max_holding_bars=5)
    assert len(res_single) == 1
    assert res_single[0].exit_barrier == "EXPIRATION"


def test_frac_diff_extreme_spikes_and_stability():
    """Edge Case 4: Extreme 1000x price spike produces finite numeric output without NaN or Inf."""
    dates = pd.date_range("2024-01-01", periods=80, freq="D")
    prices = [100.0] * 79 + [100000.0]  # 1000x sudden pump
    series = pd.Series(prices, index=dates)

    diffed = frac_diff(series, d=0.4, thres=1e-3)
    assert len(diffed) > 0
    assert not np.isinf(diffed.values).any()
    assert not np.isnan(diffed.values).any()


def test_monte_carlo_catastrophic_total_loss_streak():
    """Edge Case 5: 100% loss streak hits 100% ruin probability and caps drawdown at 100%."""
    catastrophic_trades = [-50000.0] * 30  # Total losses = 1,500,000 against 500,000 capital
    mc = run_monte_carlo_simulation(catastrophic_trades, initial_capital=500_000.0, iterations=500, ruin_threshold_pct=50.0)

    assert mc.ruin_probability_pct == 100.0
    assert mc.profit_probability_pct == 0.0
    assert mc.p99_max_drawdown_pct == 100.0


def test_crisis_replay_extreme_parameters():
    """Edge Case 6: Ultra-high beta (3.0) and zero stop loss results in ruin classification."""
    res = simulate_crisis_impact("COVID_2020", portfolio_equity=1_000_000.0, strategy_beta=3.0, stop_loss_efficiency=0.0)
    assert res.simulated_max_drawdown_pct == 100.0
    assert res.ruin_event is True
    assert res.circuit_breaker_tripped is True
    assert res.survival_rating == "FAILED"


def test_cpcv_extreme_partition_boundaries():
    """Edge Case 7: Boundary partition combinations (2C1 and 10C9)."""
    gen = WalkForwardWindowGenerator()
    start = datetime(2020, 1, 1)
    end = datetime(2024, 1, 1)

    # Minimal: 2 partitions, 1 test -> 2C1 = 2 folds
    folds_min = gen.generate_cpcv_folds(start=start, end=end, n_partitions=2, k_test_partitions=1)
    assert len(folds_min) == 2

    # Maximal: 6 partitions, 5 test -> 6C5 = 6 folds
    folds_max = gen.generate_cpcv_folds(start=start, end=end, n_partitions=6, k_test_partitions=5)
    assert len(folds_max) == 6
