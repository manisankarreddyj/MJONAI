"""Kronos adapter contract (research tier). No torch required: when the vendored
code or weights are absent the adapter must raise ForecastUnavailableError — never
fabricate a forecast. This keeps the core venv/CI torch-free while pinning the seam.
"""
import numpy as np
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


def test_name_matches_cli_model_key():
    """Regression: leaderboards label rows by model.name; without this property
    Kronos rows printed as '<KronosModel object at 0x...>' in both tables."""
    assert ka.KronosModel(size="mini").name == "kronos_mini"
    assert ka.KronosModel(size="small").name == "kronos_small"


def test_predict_never_fabricates():
    """Contract: with a valid OHLCV input, predict either returns a well-formed forecast
    (stack+weights present) or raises ForecastUnavailableError (absent) — it NEVER returns
    fabricated/empty numbers. Env-agnostic: green in the torch-free core venv/CI AND in a
    research venv with weights."""
    m = ka.KronosModel(size="mini")
    p = 100.0 + np.cumsum(np.random.RandomState(1).randn(60) * 0.2)
    df = pd.DataFrame(
        {"Open": p, "High": p + 0.3, "Low": p - 0.3, "Close": p, "Volume": 1000.0},
        index=pd.date_range("2025-01-01", periods=60, freq="D"),
    )
    try:
        res = m.predict(df, horizon=3)
    except ka.ForecastUnavailableError:
        # stack/weights unavailable -> honest failure, not a fabricated forecast
        assert m.loaded is False
        return
    # available -> a real, well-formed forecast
    assert m.loaded is True
    assert res.model == "kronos_mini" and len(res.point_path()) == 3
    res.validate()


def test_vendor_and_cache_paths_anchor_at_repo_root():
    # storage/vendor/kronos (code) and storage/models/kronos (weights), both under repo root.
    assert ka._VENDOR.name == "kronos" and ka._VENDOR.parent.name == "vendor"
    assert ka._MODEL_CACHE.name == "kronos" and ka._MODEL_CACHE.parent.name == "models"


def test_to_kronos_frame_maps_capitalized_to_lowercase():
    """MJONAI frames are Capitalized (Open/High/Low/Close); Kronos needs lowercase."""
    import numpy as np
    idx = pd.date_range("2025-01-01", periods=6, freq="D")
    df = pd.DataFrame(
        {"Open": 1, "High": 2, "Low": 0.5, "Close": 1.5, "Volume": 10}, index=idx
    )
    kdf = ka.KronosModel._to_kronos_frame(df)
    assert list(kdf.columns)[:4] == ["open", "high", "low", "close"]
    assert "volume" in kdf.columns


def test_predict_runs_when_stack_present():
    """Real end-to-end run gated on the research opt-in (torch + mini weights). Skips in the
    torch-free core venv/CI and wherever weights aren't cached."""
    pytest.importorskip("torch")  # core venv is torch-free by design
    idx = pd.date_range("2025-01-01 09:15", periods=400, freq="5min")
    price = 100.0 + np.random.RandomState(0).randn(400).cumsum() * 0.2
    df = pd.DataFrame(
        {
            "Open": price, "High": price + 0.3, "Low": price - 0.3,
            "Close": price, "Volume": 1000.0,
        },
        index=idx,
    )
    try:
        res = ka.KronosModel("mini").predict(df, horizon=3)
    except ka.ForecastUnavailableError:
        pytest.skip("Kronos mini weights not cached locally")
    assert res.model == "kronos_mini" and res.horizon == 3
    assert len(res.point_path()) == 3
    res.validate()

