"""
Test Suite: tests/test_ml_feature_store.py
Purpose: Verify Fractional Differentiation (FracDiff), microstructure proxies,
         volatility metrics, and the MetaLabelClassifier bet-sizing engine.
"""

import pandas as pd
import numpy as np
import pytest

from mjonai.research.ml.feature_pipeline import (
    get_fractional_weights,
    frac_diff,
    corwin_schultz_spread,
    roll_spread,
    garman_klass_volatility,
    calculate_hurst_exponent,
    build_ml_features,
)
from mjonai.research.ml.meta_model import MetaLabelClassifier


def test_fractional_differentiation_weights_and_convergence():
    """Verify fractional binomial weights expansion and convergence."""
    weights = get_fractional_weights(d=0.4, size=10)
    assert len(weights) == 10
    # The last weight (most recent) should be positive 1.0
    assert weights[-1] == 1.0

    # Test frac_diff series output
    dates = pd.date_range("2023-01-01", periods=100, freq="D")
    prices = pd.Series([100.0 + i * 0.5 + np.sin(i) * 2.0 for i in range(100)], index=dates)
    diffed = frac_diff(prices, d=0.5, thres=1e-3)
    assert len(diffed) > 0
    assert not diffed.isna().any()


def test_microstructure_and_volatility_estimators():
    """Verify Corwin-Schultz, Roll spread, and Garman-Klass volatility."""
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    df = pd.DataFrame({
        "open": [100.0 + i * 0.2 for i in range(60)],
        "high": [102.0 + i * 0.2 for i in range(60)],
        "low": [98.0 + i * 0.2 for i in range(60)],
        "close": [101.0 + i * 0.2 for i in range(60)],
        "volume": [50000 + i * 100 for i in range(60)],
    }, index=dates)

    cs = corwin_schultz_spread(df)
    assert len(cs) == 60
    assert (cs >= 0.0).all()

    roll = roll_spread(df["close"])
    assert roll >= 0.0

    gk = garman_klass_volatility(df, window=14)
    assert len(gk) == 60
    assert (gk >= 0.0).all()

    hurst = calculate_hurst_exponent(df["close"])
    assert 0.0 <= hurst <= 1.0

    feat_matrix = build_ml_features(df)
    assert not feat_matrix.empty
    assert "gk_vol_14" in feat_matrix.columns
    assert "cs_spread" in feat_matrix.columns
    assert "atr_ratio" in feat_matrix.columns


def test_meta_label_classifier_and_bet_sizing():
    """Verify MetaLabelClassifier training, confidence calibration, and bet sizing scalar."""
    np.random.seed(42)
    n = 100
    X = pd.DataFrame({
        "feat1": np.random.randn(n),
        "feat2": np.random.randn(n),
        "feat3": np.random.uniform(0, 1, n),
    })
    # Label is 1 when feat1 + feat2 > 0
    y = pd.Series(((X["feat1"] + X["feat2"]) > 0).astype(int))

    clf = MetaLabelClassifier(min_confidence=0.55)
    metrics = clf.fit(X, y)
    assert metrics.samples == 100
    assert 0.0 <= metrics.auc_roc <= 1.0

    # High conviction input vector -> bet size > 0.0
    high_conviction = pd.Series({"feat1": 2.5, "feat2": 2.5, "feat3": 0.5})
    size_high = clf.predict_bet_size(high_conviction)
    assert size_high > 0.0

    # Low conviction input vector -> bet size = 0.0 (veto)
    low_conviction = pd.Series({"feat1": -3.0, "feat2": -3.0, "feat3": 0.5})
    size_low = clf.predict_bet_size(low_conviction)
    assert size_low == 0.0
