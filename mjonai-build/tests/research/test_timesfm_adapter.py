"""
Unit tests for research/forecasting/timesfm_adapter.py (TimesFMModel).
Verifies contract compliance, input validation, honest ForecastUnavailableError,
and quantile monotonicity.
"""

from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import pytest

from research.forecasting.base import (
    ForecastResult,
    ForecastUnavailableError,
    QUANTILE_LEVELS,
)
from research.forecasting.timesfm_adapter import TimesFMModel


def _make_sample_df(n: int = 50) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=n, freq="15min")
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


def test_timesfm_size_validation():
    m200 = TimesFMModel(size="200m")
    assert m200.name == "timesfm_200m"
    assert m200.loaded is False

    m500 = TimesFMModel(size="500m")
    assert m500.name == "timesfm_500m"

    with pytest.raises(ValueError, match="size must be one of"):
        TimesFMModel(size="invalid_size")


def test_timesfm_honest_uninstalled_error():
    """Verify TimesFMModel raises ForecastUnavailableError when timesfm package is uninstalled."""
    m = TimesFMModel(size="200m")
    df = _make_sample_df(20)

    # Without timesfm installed / weights downloaded, must raise ForecastUnavailableError
    with pytest.raises(ForecastUnavailableError):
        m.predict(df, horizon=5)


def test_timesfm_input_validation():
    m = TimesFMModel(size="200m")

    # Invalid horizon
    df = _make_sample_df(20)
    with pytest.raises(ValueError, match="horizon must be positive"):
        m.predict(df, horizon=0)

    # Missing Close column
    bad_df = pd.DataFrame({"Price": [100.0, 101.0, 102.0]})
    with pytest.raises(ForecastUnavailableError, match="Close"):
        m.predict(bad_df, horizon=5)

    # Too short
    short_df = pd.DataFrame({"Close": [100.0, 101.0]})
    with pytest.raises(ForecastUnavailableError, match="too short"):
        m.predict(short_df, horizon=5)


def test_timesfm_mocked_prediction():
    """Verify ForecastResult construction and quantile validation with mocked backend."""
    df = _make_sample_df(40)
    horizon = 6

    mock_tfm = MagicMock()
    # Mock forecast output: point_forecast = [[1010.0, 1012.0, 1014.0, 1016.0, 1018.0, 1020.0]]
    point_preds = np.array([[1010.0, 1012.0, 1014.0, 1016.0, 1018.0, 1020.0]])
    mock_tfm.forecast.return_value = (point_preds, None)

    m = TimesFMModel(size="200m")
    m._tfm = mock_tfm  # inject mock

    result = m.predict(df, horizon=horizon)

    assert isinstance(result, ForecastResult)
    assert result.model == "timesfm_200m"
    assert result.horizon == horizon
    assert len(result.point_path()) == horizon
    assert 0.5 in result.quantiles
    assert all(level in result.quantiles for level in QUANTILE_LEVELS)

    # Ensure quantile validation passes (monotonic non-crossing)
    result.validate()
