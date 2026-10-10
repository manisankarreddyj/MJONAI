"""Kronos adapter contract (research tier). No torch required: when the vendored
code or weights are absent the adapter must raise ForecastUnavailableError — never
fabricate a forecast. This keeps the core venv/CI torch-free while pinning the seam.
"""
import pandas as pd
import pytest

from mjonai.research.forecasting.base import ForecastUnavailableError
from mjonai.research.forecasting import kronos_adapter as ka


def test_size_and_context_maps():
    assert set(ka.KRONOS_SIZES) == {"mini", "small", "base"}
    assert ka.KRONOS_CONTEXT == {"mini": 2048, "small": 512, "base": 512}
    assert all(v.startswith("NeoQuasar/") for v in ka.KRONOS_SIZES.values())


def test_invalid_size_rejected():
    with pytest.raises(ValueError):
        ka.KronosModel(size="gigantic")


def test_predict_is_lazy_until_loaded():
    m = ka.KronosModel(size="mini")
    assert m.loaded is False            # nothing loaded at construction


def test_predict_without_stack_raises_never_fabricates():
    """In a torch-free/weight-free sandbox, predict must fail honestly."""
    m = ka.KronosModel(size="mini")
    df = pd.DataFrame({"Close": [1.0, 2.0, 3.0, 4.0, 5.0]})
    with pytest.raises(ForecastUnavailableError):
        m.predict(df, horizon=3)
    assert m.loaded is False            # a failed load must not leave a half-baked predictor


def test_vendor_and_cache_paths_anchor_at_repo_root():
    # storage/vendor/kronos (code) and storage/models/kronos (weights), both under repo root.
    assert ka._VENDOR.name == "kronos" and ka._VENDOR.parent.name == "vendor"
    assert ka._MODEL_CACHE.name == "kronos" and ka._MODEL_CACHE.parent.name == "models"
