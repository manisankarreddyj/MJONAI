# -*- coding: utf-8 -*-
"""
Module: research/data/feature_scaling.py
Purpose: Leakage-safe fitted-feature machinery (purged scalers + purged splits).

CONCEPT SOURCE (clean-room): ml4trading's leakage-safe fitted features
(purged/KFold scalers) — reimplemented here with zero new dependencies
(numpy only; the repo has no sklearn requirement and gains none).

Contract:
  * A scaler is FIT on train bars only, then APPLIED to test bars. Fitting
    on the test window (or on the full frame before splitting) is look-ahead
    and is made structurally awkward: there is no `fit_transform(X)` that
    fits and returns in one call on un-split data — only `fit(train)` +
    `transform(X)`, and `fit` refuses to run twice without an explicit reset.
  * Splits purge an embargo around every test fold (both sides), so labels
    computed over forward windows cannot leak into training features.
"""

from __future__ import annotations

from typing import Iterator, List, Optional, Sequence, Tuple

import numpy as np


class PurgedStandardScaler:
    """Standard scaler that can only be fit once, on train data.

    Mean/std are population moments (ddof=0); a zero-variance column gets
    scale 1.0 (centered values stay 0.0) instead of dividing by zero.
    `transform` fail-closes on feature-count mismatch or use-before-fit —
    a silently mis-scaled test frame is worse than an exception.
    """

    def __init__(self) -> None:
        self.mean_: Optional[np.ndarray] = None
        self.scale_: Optional[np.ndarray] = None
        self.n_features_: Optional[int] = None
        self.constant_columns_: Tuple[int, ...] = ()

    @property
    def is_fitted(self) -> bool:
        return self.mean_ is not None

    def fit(self, train: Sequence[Sequence[float]]) -> "PurgedStandardScaler":
        """Fit on TRAIN bars only. Raises if already fitted (reset first)."""
        if self.is_fitted:
            raise RuntimeError(
                "PurgedStandardScaler is already fitted — create a new scaler "
                "per split instead of re-fitting (re-fitting on a later window "
                "would carry earlier-window statistics forward silently)."
            )
        x = np.asarray(train, dtype=float)
        if x.ndim != 2 or x.shape[0] == 0:
            raise ValueError("train must be a non-empty 2-D array")
        if not np.all(np.isfinite(x)):
            raise ValueError("train contains non-finite values — clean before fitting")
        mean = x.mean(axis=0)
        var = ((x - mean) ** 2).mean(axis=0)
        scale = np.sqrt(var)
        constant = tuple(int(i) for i in np.where(scale <= 0.0)[0])
        scale = np.where(scale > 0.0, scale, 1.0)
        self.mean_ = mean
        self.scale_ = scale
        self.n_features_ = x.shape[1]
        self.constant_columns_ = constant
        return self

    def transform(self, data: Sequence[Sequence[float]]) -> np.ndarray:
        """Apply train-fitted moments. Raises on use-before-fit or width mismatch."""
        if not self.is_fitted:
            raise RuntimeError("transform called before fit — fit on train first")
        x = np.asarray(data, dtype=float)
        if x.ndim != 2 or x.shape[1] != self.n_features_:
            raise ValueError(
                f"feature-width mismatch: scaler fitted on {self.n_features_} "
                f"columns, got {x.shape[1] if x.ndim == 2 else '?'}"
            )
        if not np.all(np.isfinite(x)):
            raise ValueError("data contains non-finite values — clean before transforming")
        assert self.mean_ is not None and self.scale_ is not None
        return (x - self.mean_) / self.scale_

    def reset(self) -> "PurgedStandardScaler":
        """Forget fitted moments (explicit re-arm for a new split)."""
        self.mean_ = None
        self.scale_ = None
        self.n_features_ = None
        self.constant_columns_ = ()
        return self


def purged_kfold_splits(
    n: int,
    n_splits: int = 5,
    embargo: int = 0,
) -> Iterator[Tuple[List[int], List[int]]]:
    """Contiguous K-fold splits with an embargo moat around each test fold.

    Test folds are contiguous blocks (time order preserved); `embargo` bars on
    EACH side of a test block are dropped from the train set, so forward-window
    labels near the boundary cannot leak into training features. Yields
    (train_idx, test_idx) with train sorted ascending.
    """
    n = int(n)
    n_splits = int(n_splits)
    embargo = max(0, int(embargo))
    if n <= 0 or n_splits < 2:
        raise ValueError("need n > 0 and n_splits >= 2")
    if n_splits > n:
        raise ValueError("n_splits cannot exceed n")
    base, extra = divmod(n, n_splits)
    start = 0
    for fold in range(n_splits):
        size = base + (1 if fold < extra else 0)
        test = list(range(start, start + size))
        lo = max(0, start - embargo)
        hi = min(n, start + size + embargo)
        banned = set(range(lo, hi))
        train = [i for i in range(n) if i not in banned]
        yield train, test
        start += size


def expanding_window_splits(
    n: int,
    min_train: int,
    step: int = 1,
    embargo: int = 0,
) -> Iterator[Tuple[List[int], List[int]]]:
    """Expanding-window walk-forward splits with an embargo gap.

    Train is always [0, cutoff-embargo); test is a `step`-sized block starting
    at `cutoff`, where cutoff runs from min_train to n-step. The embargo
    separates train-end from test-start — the same moat the walk-forward
    engine enforces at the bar level.
    """
    n = int(n)
    min_train = int(min_train)
    step = max(1, int(step))
    embargo = max(0, int(embargo))
    if n <= 0 or min_train < 1:
        raise ValueError("need n > 0 and min_train >= 1")
    cutoff = min_train
    while cutoff + step <= n:
        train = list(range(0, max(0, cutoff - embargo)))
        test = list(range(cutoff, cutoff + step))
        if train and test:
            yield train, test
        cutoff += step
