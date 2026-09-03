"""
Module: research/ml/meta_model.py
Purpose: Institutional meta-classifier and bet sizing engine.
         Uses gradient boosting to predict the probability of success P(Y=1|X)
         for candidate rule-based strategy signals and scales trade allocation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score, brier_score_loss
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


class PureNumpyLogisticClassifier:
    """Pure NumPy L2-regularized Logistic Regression classifier with Sigmoid squashing."""

    def __init__(self, lr: float = 0.05, iters: int = 300, l2: float = 0.01):
        self.lr = lr
        self.iters = iters
        self.l2 = l2
        self.weights: Optional[np.ndarray] = None
        self.bias: float = 0.0
        self.mean: Optional[np.ndarray] = None
        self.std: Optional[np.ndarray] = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        n, m = X.shape
        self.weights = np.zeros(m)
        self.bias = 0.0
        self.mean = np.mean(X, axis=0)
        self.std = np.std(X, axis=0)
        self.std[self.std == 0] = 1.0

        X_norm = (X - self.mean) / self.std

        for _ in range(self.iters):
            linear = np.dot(X_norm, self.weights) + self.bias
            linear = np.clip(linear, -25.0, 25.0)
            probs = 1.0 / (1.0 + np.exp(-linear))
            error = probs - y
            dw = (1.0 / n) * np.dot(X_norm.T, error) + (self.l2 * self.weights)
            db = (1.0 / n) * np.sum(error)
            self.weights -= self.lr * dw
            self.bias -= self.lr * db

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.weights is None or self.mean is None or self.std is None:
            n = len(X)
            return np.full((n, 2), 0.5)

        X_norm = (X - self.mean) / self.std
        linear = np.dot(X_norm, self.weights) + self.bias
        linear = np.clip(linear, -25.0, 25.0)
        p1 = 1.0 / (1.0 + np.exp(-linear))
        p0 = 1.0 - p1
        return np.column_stack([p0, p1])


@dataclass
class MetaModelMetrics:
    auc_roc: float
    brier_score: float
    accuracy: float
    samples: int
    positive_rate: float


class MetaLabelClassifier:
    """
    Gradient-boosted or pure-NumPy meta-model for trade filtering and bet sizing (López de Prado).
    """

    def __init__(self, min_confidence: float = 0.55):
        self.min_confidence = min_confidence
        if HAS_SKLEARN:
            self.model = HistGradientBoostingClassifier(
                max_iter=100,
                learning_rate=0.05,
                max_depth=5,
                random_state=42
            )
        else:
            self.model = PureNumpyLogisticClassifier(lr=0.05, iters=300)
        self.is_fitted = False
        self.feature_names: List[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> MetaModelMetrics:
        """Train the meta-model on feature matrix X and triple-barrier labels y."""
        if len(X) < 10:
            return MetaModelMetrics(auc_roc=0.5, brier_score=0.25, accuracy=0.5, samples=len(X), positive_rate=0.5)

        self.feature_names = list(X.columns)
        self.model.fit(X.values, y.values)
        self.is_fitted = True

        preds_proba = self.model.predict_proba(X.values)[:, 1]
        preds_class = (preds_proba >= 0.5).astype(int)

        if HAS_SKLEARN:
            try:
                auc = float(roc_auc_score(y.values, preds_proba))
            except Exception:
                auc = 0.5
            brier = float(brier_score_loss(y.values, preds_proba))
        else:
            # Analytical trapezoidal AUC-ROC approximation
            y_arr = y.values
            pos = preds_proba[y_arr == 1]
            neg = preds_proba[y_arr == 0]
            if len(pos) > 0 and len(neg) > 0:
                auc = float(np.mean(pos[:, None] > neg))
            else:
                auc = 0.5
            brier = float(np.mean((preds_proba - y_arr) ** 2))

        acc = float(np.mean(preds_class == y.values))
        pos_rate = float(np.mean(y.values))

        return MetaModelMetrics(
            auc_roc=round(auc, 4),
            brier_score=round(brier, 4),
            accuracy=round(acc, 4),
            samples=len(X),
            positive_rate=round(pos_rate, 4),
        )

    def predict_bet_size(self, feature_vector: pd.Series) -> float:
        """
        Predict conditional probability and compute bet size multiplier.
        Returns:
            float: Sizing scalar between 0.0 (veto trade) and 1.0 (full conviction size).
        """
        if not self.is_fitted:
            return 1.0  # Pass-through when meta-model is uninitialized

        vals = feature_vector.reindex(self.feature_names).fillna(0.0).values.reshape(1, -1)
        prob = float(self.model.predict_proba(vals)[0, 1])

        if prob < self.min_confidence:
            return 0.0  # Veto trade

        # Scale bet size between min_confidence and 1.0
        scaled = (prob - self.min_confidence) / (1.0 - self.min_confidence)
        return float(round(max(0.2, min(1.0, scaled)), 2))
