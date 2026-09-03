"""
Module: research/forecasting/classical.py
Purpose: Mandatory classical baselines (ADR-0002). Any TSFM claim must beat
         these on the SAME evaluation harness before further spend.

Hand-rolled, zero new dependencies:
  - SeasonalNaiveModel  : repeat last season's path (weekly season, daily bars)
  - DriftModel          : random walk with drift (global mean-return baseline)
  - ExpSmoothingModel   : simple exponential smoothing + additive drift term

All produce Gaussian quantile paths from in-sample residual std.
"""

from __future__ import annotations

import math
from typing import List

import numpy as np

from research.forecasting.base import (
    ForecastModel,
    ForecastResult,
    QUANTILE_LEVELS,
    check_ohlcv,
    gaussian_quantiles_from_residuals,
)


class SeasonalNaiveModel:
    """Point forecast = close[t - season_length] repeated for the horizon."""

    name = "seasonal_naive"

    def __init__(self, season_length: int = 5):
        if season_length < 1:
            raise ValueError("season_length must be >= 1")
        self.season_length = int(season_length)

    def predict(self, df, horizon: int) -> ForecastResult:
        check_ohlcv(df)
        closes = np.asarray(df["Close"], dtype=float)

        if len(closes) <= 2 * self.season_length:
            raise ValueError(
                f"{self.name}: needs > 2 seasons ({2 * self.season_length} bars), got {len(closes)}"
            )

        # One-season-ahead path repeated to cover the horizon.
        season_path = closes[-self.season_length:]
        point: List[float] = [
            float(season_path[i % self.season_length]) for i in range(horizon)
        ]

        # Residuals of the same construction one season out-of-sample.
        residuals = (
            closes[self.season_length:]
            - closes[: len(closes) - self.season_length]
        )

        return ForecastResult(
            model=self.name,
            horizon=horizon,
            quantiles=gaussian_quantiles_from_residuals(
                residuals.tolist(), point, QUANTILE_LEVELS
            ),
        )


class DriftModel:
    """Random walk with drift: mu = mean(log return); path compounds mu."""

    name = "rw_drift"

    def predict(self, df, horizon: int) -> ForecastResult:
        check_ohlcv(df)
        closes = np.asarray(df["Close"], dtype=float)

        if (closes <= 0).any():
            raise ValueError(f"{self.name}: non-positive closes present")

        log_ret = np.diff(np.log(closes))
        mu = float(np.mean(log_ret))

        last = float(closes[-1])
        # Center path is constructed in LOG space so residual symmetry holds,
        # then every quantile path is mapped back through exp — otherwise the
        # served "prices" are literally log-prices (caught by F-wave tests).
        log_center = [math.log(last) + mu * (i + 1) for i in range(horizon)]
        residuals = (log_ret - mu).tolist()

        log_quantiles = gaussian_quantiles_from_residuals(
            residuals, log_center, QUANTILE_LEVELS
        )
        quantiles = {
            level: [math.exp(v) for v in path]
            for level, path in log_quantiles.items()
        }

        return ForecastResult(
            model=self.name,
            horizon=horizon,
            quantiles=quantiles,
        )


class ExpSmoothingModel:
    """Simple exponential smoothing with fitted-in-window alpha plus a linear
    drift term from the smoothed slope. Alpha chosen by in-sample SSE grid."""

    name = "exp_smoothing"

    def __init__(self, alpha_grid: tuple = (0.1, 0.2, 0.3, 0.5, 0.8)):
        if not alpha_grid:
            raise ValueError("alpha_grid must be non-empty")
        self.alpha_grid = tuple(float(a) for a in alpha_grid)

    def predict(self, df, horizon: int) -> ForecastResult:
        check_ohlcv(df)
        y = np.asarray(df["Close"], dtype=float)

        best_alpha, best_sse, best_level = None, math.inf, None
        for alpha in self.alpha_grid:
            level = float(y[0])
            sse = 0.0
            for t in range(1, len(y)):
                error = float(y[t]) - level
                sse += error * error
                level = level + alpha * error
            if sse < best_sse:
                best_alpha, best_sse, best_level = alpha, sse, level

        # Smoothed slope over the last few updates gives the drift term.
        tail_slope = float(np.polyfit(
            np.arange(min(10, len(y))), y[-min(10, len(y)):], 1
        )[0])

        point = [float(best_level) + tail_slope * (i + 1) for i in range(horizon)]

        # In-sample one-step residuals at the chosen alpha.
        residuals = []
        level = float(y[0])
        for t in range(1, len(y)):
            residuals.append(float(y[t]) - level)
            level = level + best_alpha * (float(y[t]) - level)

        return ForecastResult(
            model=f"{self.name}(alpha={best_alpha})",
            horizon=horizon,
            quantiles=gaussian_quantiles_from_residuals(residuals, point, QUANTILE_LEVELS),
        )
