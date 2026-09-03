"""
Package: research/ml
Institutional Machine Learning & Meta-Labeling Layer.
"""

from research.ml.triple_barrier import apply_triple_barrier, BarrierEvent
from research.ml.feature_pipeline import (
    frac_diff,
    get_fractional_weights,
    corwin_schultz_spread,
    roll_spread,
    garman_klass_volatility,
    calculate_hurst_exponent,
    build_ml_features,
)
from research.ml.meta_model import MetaLabelClassifier, MetaModelMetrics

__all__ = [
    "apply_triple_barrier",
    "BarrierEvent",
    "frac_diff",
    "get_fractional_weights",
    "corwin_schultz_spread",
    "roll_spread",
    "garman_klass_volatility",
    "calculate_hurst_exponent",
    "build_ml_features",
    "MetaLabelClassifier",
    "MetaModelMetrics",
]
