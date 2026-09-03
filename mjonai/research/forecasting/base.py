"""
Module: research/forecasting/base.py
Purpose: ForecastModel port (ADR-0002). The ONLY interface the forecasting
         wave adds; TSFM and classical implementations live behind it.

Contract:
  - predict(df, horizon) receives a CLOSED-bar OHLCV frame ordered oldest->newest
    and returns quantile paths for the NEXT `horizon` bars.
  - Implementations must be leakage-free: they may only use data in `df`.
  - A forecaster that cannot run raises ForecastUnavailableError — never
    returns fabricated numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Protocol, Sequence


class ForecastUnavailableError(RuntimeError):
    """Raised when a model's library or weights are unavailable."""


QUANTILE_LEVELS: tuple = (0.1, 0.25, 0.5, 0.75, 0.9)


@dataclass(frozen=True)
class ForecastResult:
    """Quantile forecast paths for one instrument, one origin."""

    model: str
    horizon: int
    # {level -> [q10, ..., q90] path of length horizon} for the CLOSE series
    quantiles: Dict[float, List[float]]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def point_path(self) -> List[float]:
        return self.quantiles[0.5]

    def validate(self) -> None:
        if self.horizon <= 0:
            raise ValueError("horizon must be positive")
        for level, path in self.quantiles.items():
            if len(path) != self.horizon:
                raise ValueError(f"quantile {level}: path length != horizon")
        levels = sorted(self.quantiles)
        for i in range(len(levels) - 1):
            hi_path = self.quantiles[levels[i + 1]]
            lo_path = self.quantiles[levels[i]]
            if any(h < l for h, l in zip(hi_path, lo_path)):
                raise ValueError(
                    f"quantile crossing between {levels[i]} and {levels[i+1]}"
                )


class ForecastModel(Protocol):

    name: str

    def predict(self, df, horizon: int) -> ForecastResult:
        ...


def check_ohlcv(df) -> None:
    """Minimal shared input validation for all forecasters."""
    required = {"Close"}
    if df is None or not required.issubset(set(str(c) for c in df.columns)):
        raise ForecastUnavailableError("forecast input needs a Close column")
    if len(df) < 3:
        raise ForecastUnavailableError("forecast input too short (<3 bars)")


def gaussian_quantiles_from_residuals(
    residuals: Sequence[float],
    center_path: List[float],
    levels: Sequence[float] = QUANTILE_LEVELS,
) -> Dict[float, List[float]]:
    """
    Shared classical quantile head: Gaussian approximation around the point
    path with scale = residual std. Deterministic, dependency-free.
    """
    from scipy.stats import norm

    n = len(residuals)
    std = 0.0
    if n >= 2:
        mu = sum(residuals) / n
        std = (sum((r - mu) ** 2 for r in residuals) / (n - 1)) ** 0.5
    return {
        level: [c + float(norm.ppf(level)) * std for c in center_path]
        for level in levels
    }
