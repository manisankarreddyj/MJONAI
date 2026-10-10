"""Leakage-safe SMC research features — contract tests (research tier, --run-research).

The decisive test is causality: truncating the frame at bar k must NOT change the feature at
bar k. If the wrapper leaked the future it would, because appending later bars would rewrite a
value that (incorrectly) depended on them. smart-money-concepts is vendored pure pandas/numpy —
no torch required.
"""
import numpy as np
import pandas as pd
import pytest

from mjonai.research.discovery import smc_features as sf


def _frame(n=400, seed=7):
    rng = np.random.RandomState(seed)
    idx = pd.date_range("2022-01-03", periods=n, freq="B")
    price = 100 + np.cumsum(rng.randn(n) * 0.8)
    high = price + np.abs(rng.randn(n)) * 0.6 + 0.2
    low = price - np.abs(rng.randn(n)) * 0.6 - 0.2
    op = price + rng.randn(n) * 0.2
    cl = price + rng.randn(n) * 0.2
    # keep OHLC internally consistent
    high = np.maximum.reduce([high, op, cl])
    low = np.minimum.reduce([low, op, cl])
    return pd.DataFrame(
        {"Open": op, "High": high, "Low": low, "Close": cl,
         "Volume": rng.randint(50_000, 400_000, n)}, index=idx
    )


def test_features_load_and_shape():
    df = _frame(300)
    feat = sf.smc_features(df, swing_length=10)
    assert len(feat) == len(df)
    assert {"smc_swing_hl", "smc_dist_to_swing", "smc_fvg_dir",
            "smc_in_bull_fvg", "smc_in_bear_fvg"}.issubset(feat.columns)


def test_causality_truncation_does_not_rewrite_the_present():
    """Gold-standard no-lookahead: feature at bar k is identical whether computed on the full
    frame or only on df.iloc[:k+1]. A leak would make later bars change an earlier value."""
    df = _frame(360, seed=11)
    full = sf.smc_features(df, swing_length=10, confirm_lag=12)
    warm = 2 * 12 + 5
    checked = 0
    for k in [warm + 20, warm + 80, warm + 150, 300, 359]:
        trunc = sf.smc_features(df.iloc[: k + 1], swing_length=10, confirm_lag=12)
        assert full.iloc[k].equals(trunc.iloc[k]), (
            f"feature at {k} changed when future bars were appended -> LEAK: "
            f"full={full.iloc[k].to_dict()} trunc={trunc.iloc[k].to_dict()}"
        )
        checked += 1
    assert checked == 5


def test_features_are_finite_or_nan_no_inf():
    df = _frame(240, seed=3)
    feat = sf.smc_features(df, swing_length=8)
    assert not np.isinf(feat.to_numpy(dtype=float)).any()
    # swing_hl must be within {-1,0,1}
    assert set(feat["smc_swing_hl"].dropna().unique()).issubset({-1.0, 0.0, 1.0})


def test_missing_vendor_raises_error_not_fabrication(monkeypatch):
    monkeypatch.setattr(sf, "_VENDOR", sf.Path("D:/definitely/not/here"))
    with pytest.raises(RuntimeError):
        sf.load_smc()
