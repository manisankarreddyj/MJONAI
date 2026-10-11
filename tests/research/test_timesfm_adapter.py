"""
Unit tests for research/forecasting/timesfm_adapter.py (TimesFMModel, TimesFM 3.0).
Verifies contract compliance, checkpoint validation, honest ForecastUnavailableError,
native-quantile -> QUANTILE_LEVELS mapping (incl. interpolation), and quantile monotonicity.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from mjonai.research.forecasting.base import (
    ForecastResult,
    ForecastUnavailableError,
    QUANTILE_LEVELS,
)
from mjonai.research.forecasting.timesfm_adapter import (
    DEFAULT_CHECKPOINT,
    TimesFMModel,
    _interpolate_quantile_column,
)


def _make_sample_df(n: int = 50) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    np.random.seed(42)
    prices = 1000.0 + np.cumsum(np.random.randn(n) * 2.0)
    return pd.DataFrame(
        {
            "Open": prices * 0.999,
            "High": prices * 1.002,
            "Low": prices * 0.998,
            "Close": prices,
            "Volume": 10000.0,
        },
        index=dates,
    )


def _mock_forecast_output(horizon: int, n_native: int = 9, base: float = 1010.0):
    """Build a ForecastOutput-like object with a monotonic quantile matrix."""
    point = np.array([base + i for i in range(horizon)], dtype=float)
    # (horizon, 9): quantile t spreads outward from the point path
    q = np.zeros((horizon, n_native), dtype=float)
    for t in range(horizon):
        for j in range(n_native):
            offset = (j - n_native // 2) * 0.5
            q[t, j] = point[t] + offset
    return SimpleNamespace(forecast=point, quantiles=q)


def test_checkpoint_validation():
    m = TimesFMModel()
    assert m.checkpoint == DEFAULT_CHECKPOINT
    assert m.name == "timesfm_3.0"
    assert m.loaded is False

    with pytest.raises(ValueError, match="checkpoint must be"):
        TimesFMModel(checkpoint="")
    with pytest.raises(ValueError, match="context_len"):
        TimesFMModel(context_len=2)


def test_name_derivation_from_checkpoint():
    assert TimesFMModel(checkpoint="google/timesfm-3.0-pytorch").name == "timesfm_3.0"
    assert TimesFMModel(checkpoint="/models/timesfm-2.5-torch").name == "timesfm_2.5"
    assert TimesFMModel(checkpoint="local/timesfm-custom").name == "timesfm_custom"
    # Windows-style absolute path (local weights dir)
    assert (
        TimesFMModel(checkpoint=r"D:\MJONAI\storage\models\timesfm-3.0-pytorch").name
        == "timesfm_3.0"
    )


def test_timesfm_honest_uninstalled_error():
    """With no local weights and no network, must raise ForecastUnavailableError — never fabricate."""
    # Deterministic: a checkpoint id that will never resolve, offline-only.
    m = TimesFMModel(checkpoint="google/timesfm-nonexistent-test", local_files_only=True)
    df = _make_sample_df(20)
    with pytest.raises(ForecastUnavailableError):
        m.predict(df, horizon=5)


def test_timesfm_input_validation():
    m = TimesFMModel()
    df = _make_sample_df(20)

    with pytest.raises(ValueError, match="horizon must be positive"):
        m.predict(df, horizon=0)

    bad_df = pd.DataFrame({"Price": [100.0, 101.0, 102.0]})
    with pytest.raises(ForecastUnavailableError, match="Close"):
        m.predict(bad_df, horizon=5)

    short_df = pd.DataFrame({"Close": [100.0, 101.0]})
    with pytest.raises(ForecastUnavailableError, match="too short"):
        m.predict(short_df, horizon=5)


def test_timesfm_mocked_prediction_maps_quantiles():
    """Mocked TimesFM3 backend: ForecastResult construction + quantile mapping."""
    df = _make_sample_df(40)
    horizon = 6

    mock_tfm = MagicMock()
    mock_tfm.predict.return_value = _mock_forecast_output(horizon)

    m = TimesFMModel()
    m._tfm = mock_tfm

    result = m.predict(df, horizon=horizon)

    assert isinstance(result, ForecastResult)
    assert result.model == "timesfm_3.0"
    assert result.horizon == horizon
    assert len(result.point_path()) == horizon
    assert all(level in result.quantiles for level in QUANTILE_LEVELS)
    result.validate()  # monotonic, non-crossing, length == horizon

    # TimesFM was called with the closed-bar slice, horizon, and quantiles on.
    kwargs = mock_tfm.predict.call_args.kwargs
    assert kwargs["horizon"] == horizon
    assert kwargs["return_quantiles"] is True
    ctx = kwargs["context"]
    assert len(ctx) == 40  # context_len default 1024 > 40, so full slice


def test_timesfm_context_slice_is_zero_lookahead():
    """The model must never see bars beyond the input frame."""
    df = _make_sample_df(1500)
    mock_tfm = MagicMock()
    mock_tfm.predict.return_value = _mock_forecast_output(3)
    m = TimesFMModel(context_len=256)
    m._tfm = mock_tfm
    m.predict(df, horizon=3)
    ctx = mock_tfm.predict.call_args.kwargs["context"]
    assert len(ctx) == 256
    # Last context bar == last Close of the frame
    assert float(ctx[-1]) == pytest.approx(float(df["Close"].iloc[-1]))


def test_quantile_interpolation_picks_exact_and_interpolates():
    """0.10/0.50/0.90 picked exactly; 0.25/0.75 linearly interpolated."""
    q = np.array([
        [90.0, 95.0, 97.0, 99.0, 100.0, 101.0, 103.0, 105.0, 110.0],
    ])  # single bar, 9 native quantiles
    assert _interpolate_quantile_column(q, 0.0, 0.10)[0] == pytest.approx(90.0)
    assert _interpolate_quantile_column(q, 0.0, 0.50)[0] == pytest.approx(100.0)
    assert _interpolate_quantile_column(q, 0.0, 0.90)[0] == pytest.approx(110.0)
    # 0.25 is midway between 0.20 (95.0) and 0.30 (97.0) -> 96.0
    assert _interpolate_quantile_column(q, 0.0, 0.25)[0] == pytest.approx(96.0)
    # 0.75 is midway between 0.70 (103.0) and 0.80 (105.0) -> 104.0
    assert _interpolate_quantile_column(q, 0.0, 0.75)[0] == pytest.approx(104.0)


def test_gaussian_fallback_when_no_quantiles():
    """When TimesFM returns no quantile matrix, fall back to the honest residual head."""
    df = _make_sample_df(40)
    horizon = 4
    point = np.array([1010.0, 1011.0, 1012.0, 1013.0])
    mock_tfm = MagicMock()
    mock_tfm.predict.return_value = SimpleNamespace(forecast=point, quantiles=None)

    m = TimesFMModel()
    m._tfm = mock_tfm
    result = m.predict(df, horizon=horizon)

    result.validate()
    assert result.point_path() == pytest.approx([1010.0, 1011.0, 1012.0, 1013.0])
    # Fallback quantiles are Gaussian-scaled around the point path
    assert result.quantiles[0.1][0] < result.quantiles[0.5][0] < result.quantiles[0.9][0]


def test_malformed_quantile_shape_falls_back():
    """A short/wrong-shaped quantile matrix must fall back, not crash."""
    df = _make_sample_df(30)
    horizon = 3
    point = np.array([1000.0, 1001.0, 1002.0])
    bad_q = np.zeros((horizon, 2))  # only 2 native quantiles — too few
    mock_tfm = MagicMock()
    mock_tfm.predict.return_value = SimpleNamespace(forecast=point, quantiles=bad_q)

    m = TimesFMModel()
    m._tfm = mock_tfm
    result = m.predict(df, horizon=horizon)
    result.validate()


def test_inference_exception_is_fail_closed():
    df = _make_sample_df(20)
    mock_tfm = MagicMock()
    mock_tfm.predict.side_effect = RuntimeError("cuda OOM")
    m = TimesFMModel()
    m._tfm = mock_tfm
    with pytest.raises(ForecastUnavailableError, match="inference failed"):
        m.predict(df, horizon=3)
