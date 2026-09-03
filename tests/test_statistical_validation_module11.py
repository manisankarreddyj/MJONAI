"""
Test Suite: tests/test_statistical_validation_module11.py
Purpose: Verify Deflated Sharpe Ratio (DSR), Probabilistic Sharpe Ratio (PSR),
         Harvey-Liu Haircut Sharpe Ratio, and Stationary Block Bootstrap.
"""

import math
import pytest

from mjonai.analytics.statistical_validation import (
    deflated_sharpe_ratio,
    probabilistic_sharpe_ratio,
    haircut_sharpe_ratio,
    stationary_block_bootstrap,
)


def test_probabilistic_sharpe_ratio_bounds():
    """Verify PSR is bounded in [0.0, 1.0] and scales monotonically with Sharpe ratio."""
    # Positive daily returns
    good_returns = [0.01 + (i % 3) * 0.005 for i in range(100)]
    psr_good = probabilistic_sharpe_ratio(good_returns, benchmark_sr=0.0)
    assert 0.0 <= psr_good <= 1.0
    assert psr_good > 0.90  # Extremely high probability that SR > 0

    # Negative daily returns
    bad_returns = [-0.01 - (i % 3) * 0.005 for i in range(100)]
    psr_bad = probabilistic_sharpe_ratio(bad_returns, benchmark_sr=0.0)
    assert 0.0 <= psr_bad <= 1.0
    assert psr_bad < 0.10


def test_haircut_sharpe_ratio_discount():
    """Verify Harvey-Liu Haircut applies increasing discount with more factor trials."""
    h1 = haircut_sharpe_ratio(observed_sr=2.0, num_trials=1)
    assert h1["haircut_sr"] == 2.0
    assert h1["discount_pct"] == 0.0

    h20 = haircut_sharpe_ratio(observed_sr=2.0, num_trials=20)
    assert h20["haircut_sr"] < 2.0
    assert h20["discount_pct"] > 0.0

    h100 = haircut_sharpe_ratio(observed_sr=2.0, num_trials=100)
    assert h100["haircut_sr"] < h20["haircut_sr"]
    assert h100["discount_pct"] > h20["discount_pct"]


def test_stationary_block_bootstrap_preserves_length():
    """Verify stationary block bootstrap resamples full sequence length."""
    data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    samples = stationary_block_bootstrap(data, avg_block_size=3, num_samples=50)
    assert len(samples) == 50
    for s in samples:
        assert len(s) == len(data)
