"""Leakage-safe fitted features + feature-spec register (ml4trading items 5-6).

Covers `mjonai/research/data/feature_scaling.py` (PurgedStandardScaler,
purged K-fold splits, expanding-window splits) and
`mjonai/research/data/feature_registry.py` (FeatureSpec register +
discovery-primitive declarations).
"""

import math

import numpy as np
import pytest

from mjonai.research.data.feature_registry import (
    FEATURE_REGISTRY,
    FeatureRegistry,
    FeatureSpec,
    register_discovery_primitives,
    register_feature_spec,
)
from mjonai.research.data.feature_scaling import (
    PurgedStandardScaler,
    expanding_window_splits,
    purged_kfold_splits,
)


# ── Scaler ───────────────────────────────────────────────────────────────────

def test_scaler_fit_transform_train_only():
    train = [[1.0, 10.0], [2.0, 20.0], [3.0, 30.0]]
    test = [[4.0, 40.0]]
    sc = PurgedStandardScaler().fit(train)
    out = sc.transform(test)
    # Column 0: mean 2, pop-std sqrt(2/3); (4-2)/0.8165 = 2.4495.
    assert out[0][0] == pytest.approx(2.4495, abs=1e-3)
    # Train itself centers to mean 0.
    centered = sc.transform(train)
    assert abs(float(np.mean(centered[:, 0]))) < 1e-9


def test_scaler_refuses_refit_and_use_before_fit():
    sc = PurgedStandardScaler()
    with pytest.raises(RuntimeError):
        sc.transform([[1.0]])
    sc.fit([[1.0, 2.0], [3.0, 4.0]])
    with pytest.raises(RuntimeError):
        sc.fit([[1.0, 2.0], [3.0, 4.0]])
    sc.reset()
    assert sc.is_fitted is False
    sc.fit([[1.0, 2.0], [3.0, 4.0]])
    assert sc.is_fitted is True


def test_scaler_constant_column_and_width_mismatch():
    sc = PurgedStandardScaler().fit([[5.0, 1.0], [5.0, 2.0], [5.0, 3.0]])
    assert sc.constant_columns_ == (0,)
    out = sc.transform([[5.0, 4.0]])
    assert out[0][0] == pytest.approx(0.0)  # centered constant stays 0, no div-by-zero
    with pytest.raises(ValueError):
        sc.transform([[1.0, 2.0, 3.0]])
    with pytest.raises(ValueError):
        PurgedStandardScaler().fit([[1.0, float("nan")], [2.0, 3.0]])


# ── Splits ───────────────────────────────────────────────────────────────────

def test_purged_kfold_embargo_moat_both_sides():
    splits = list(purged_kfold_splits(20, n_splits=4, embargo=2))
    assert len(splits) == 4
    for train, test in splits:
        # No train index within the 2-bar embargo moat of any test index.
        for ti in test:
            assert all(abs(tr - ti) >= 2 for tr in train)
        # Test folds partition the frame exactly once.
        assert len(test) == 5
    covered = sorted(i for _, test in splits for i in test)
    assert covered == list(range(20))


def test_purged_kfold_zero_embargo_is_plain_contiguous():
    splits = list(purged_kfold_splits(10, n_splits=2, embargo=0))
    assert splits[0][1] == [0, 1, 2, 3, 4]
    assert splits[1][1] == [5, 6, 7, 8, 9]
    assert splits[0][0] == [5, 6, 7, 8, 9]
    with pytest.raises(ValueError):
        list(purged_kfold_splits(3, n_splits=5))


def test_expanding_window_monotonic_with_embargo_gap():
    splits = list(expanding_window_splits(10, min_train=4, step=2, embargo=1))
    assert splits[0] == ([0, 1, 2], [4, 5])
    assert splits[1] == ([0, 1, 2, 3, 4], [6, 7])
    assert splits[2] == ([0, 1, 2, 3, 4, 5, 6], [8, 9])
    for train, test in splits:
        assert max(train) <= min(test) - 2  # 1-bar embargo moat
    # Train windows strictly expand across splits.
    assert splits[1][0][:3] == splits[0][0]


# ── Register ─────────────────────────────────────────────────────────────────

def test_register_rejects_duplicate_name_with_different_spec():
    reg = FeatureRegistry()
    reg.register(FeatureSpec(name="ret_1d", inputs=("close",), version="1.0.0"))
    # Identical re-registration is idempotent (import-safe).
    same = reg.register(FeatureSpec(name="ret_1d", inputs=("close",), version="1.0.0"))
    assert same.name == "ret_1d"
    with pytest.raises(ValueError):
        reg.register(FeatureSpec(name="ret_1d", inputs=("open",), version="2.0.0"))
    with pytest.raises(ValueError):
        reg.register(FeatureSpec(name="  "))
    assert "ret_1d" in reg
    assert "nope" not in reg
    assert len(reg) == 1


def test_register_discovery_primitives_declares_eleven():
    reg = FeatureRegistry()
    specs = register_discovery_primitives(registry=reg)
    assert len(specs) == 11
    assert len(reg) == 11
    families = {s.family for s in reg.list()}
    assert "A1_ts_momentum" in families and "A11_consolidation" in families
    # Every declaration carries a leakage contract.
    assert all("bars <=" in s.leakage_notes or "embargo" in s.leakage_notes for s in specs)
    # Global registry accepts the same declarations idempotently.
    again = register_discovery_primitives()
    assert len(again) == 11
    assert "sig_donchian" in FEATURE_REGISTRY


def test_register_into_explicit_empty_registry_lands_there():
    """Regression: `registry or GLOBAL` silently reroutes an empty registry.

    An empty FeatureRegistry is falsy via __len__, so a truthiness-based
    default would drop its specs into the global registry. Both helpers
    must use identity checks.
    """
    reg = FeatureRegistry()
    assert len(reg) == 0
    spec = register_feature_spec("empty_trap_probe_xyz", registry=reg)
    assert spec.name in reg
    assert "empty_trap_probe_xyz" not in FEATURE_REGISTRY
    fresh = FeatureRegistry()
    register_discovery_primitives(registry=fresh)
    assert len(fresh) == 11


def test_register_helper_freezes_params():
    spec = register_feature_spec(
        "tmp_probe", inputs=("close",), params={"window": 20}, registry=FeatureRegistry()
    )
    assert spec.params == (("window", "20"),)
    assert "window=20" in spec.describe()
