"""
Module: research/forecasting
Purpose: MJONAI forecasting layer (ADR-0002). Classical baselines are the
         mandatory reference point; TSFMs plug in behind the same port and
         the same evaluation harness.
"""

from research.forecasting.base import (
    QUANTILE_LEVELS,
    ForecastModel,
    ForecastResult,
    ForecastUnavailableError,
)
from research.forecasting.classical import (
    DriftModel,
    ExpSmoothingModel,
    SeasonalNaiveModel,
)
from research.forecasting.kronos_adapter import KronosModel
from research.forecasting.timesfm_adapter import TimesFMModel

__all__ = [
    "QUANTILE_LEVELS",
    "ForecastModel",
    "ForecastResult",
    "ForecastUnavailableError",
    "DriftModel",
    "ExpSmoothingModel",
    "SeasonalNaiveModel",
    "KronosModel",
    "TimesFMModel",
]
