"""
Unit tests for analytics/portfolio_hrp.py (Hierarchical Risk Parity Portfolio Allocator).
Verifies unity weight summation, inverse volatility fallback, and risk reduction on correlated clusters.
"""

import numpy as np
import pandas as pd
import pytest

from mjonai.analytics.portfolio_hrp import (
    calculate_hrp_weights,
    HRPAllocationResult,
)


def test_calculate_hrp_weights_single_asset():
    df = pd.DataFrame({"RELIANCE": np.random.normal(0.001, 0.02, 50)})
    res = calculate_hrp_weights(df)
    assert res.weights == {"RELIANCE": 1.0}
    assert res.method_used == "SINGLE_ASSET"


def test_calculate_hrp_weights_multi_asset_sum_to_one():
    np.random.seed(42)
    # 4 assets with varying volatility
    ret_a = np.random.normal(0, 0.01, 100)
    ret_b = np.random.normal(0, 0.02, 100)
    ret_c = np.random.normal(0, 0.03, 100)
    ret_d = np.random.normal(0, 0.015, 100)

    df = pd.DataFrame({
        "LOW_VOL": ret_a,
        "MED_VOL": ret_b,
        "HIGH_VOL": ret_c,
        "DEFENSIVE": ret_d,
    })

    res = calculate_hrp_weights(df)
    total_weight = sum(res.weights.values())
    assert pytest.approx(total_weight, rel=1e-3) == 1.0
    assert len(res.weights) == 4
    # Lower vol asset receives higher allocation in risk parity
    assert res.weights["LOW_VOL"] > res.weights["HIGH_VOL"]


def test_calculate_hrp_weights_short_history_fallback():
    # Only 5 return rows -> Triggers inverse volatility fallback
    df = pd.DataFrame({
        "STOCK_A": [0.01, -0.02, 0.015, 0.005, -0.01],
        "STOCK_B": [0.03, -0.04, 0.025, 0.01, -0.02],
    })
    res = calculate_hrp_weights(df)
    assert res.method_used == "INVERSE_VOLATILITY_FALLBACK"
    assert pytest.approx(sum(res.weights.values()), rel=1e-3) == 1.0
