"""
Module: research/forecasting/timesfm_adapter.py
Purpose: Google TimesFM (Time-series Foundation Model) adapter behind ForecastModel (ADR-0002).

TimesFM (Google Research, ICML 2024) is a pretrained decoder-only foundation
model for zero-shot time-series forecasting. This adapter targets the CURRENT
release line — **TimesFM 3.0** (`timesfm3.torch.TimesFM3Forecaster`), which is
native-multivariate, supports covariates, and ranks #1 on fev-bench / TIME /
GIFT-Eval. (The previous adapter targeted the retired TimesFM 1.0
`timesfm.TimesFm` API, which no longer exists in the shipped package.)

WEIGHTS LICENSING (read before enabling):
  - TimesFM 3.0 pretrained weights (`google/timesfm-3.0-pytorch`) are distributed
    under a SEPARATE non-commercial / non-production license. That is compatible
    with MJONAI's current posture (personal, paper-only — Golden Rule 10).
  - TimesFM weights up to 2.5 remain Apache-2.0 (commercial/production OK) and
    remain available upstream if the project ever needs commercial clearance.
  - The SOURCE CODE here is Apache-2.0 either way.

This adapter is LAZY and HONEST:
  - Never downloads weights implicitly or without opt-in (research opt-in, same
    posture as the Kronos adapter — the core venv / CI stay torch-free).
  - Raises ForecastUnavailableError when the timesfm package or checkpoint is
    missing — never fabricates a forecast.
  - Respects closed-bar slice boundaries with zero lookahead bias.
  - Maps TimesFM's native 9-quantile grid (q10..q90) onto MJONAI's
    QUANTILE_LEVELS (0.10/0.25/0.50/0.75/0.90) by exact pick + linear
    interpolation — never by invention.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from mjonai.research.forecasting.base import (
    QUANTILE_LEVELS,
    ForecastModel,
    ForecastResult,
    ForecastUnavailableError,
    check_ohlcv,
    gaussian_quantiles_from_residuals,
)

# TimesFM 3.0 native quantile grid (see _ModelConfig default in timesfm3_forecaster.py)
_TIMESFM3_QUANTILES: tuple = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)

# Default HuggingFace checkpoint. NOTE: 3.0 weights carry a non-commercial /
# non-production license — fine for MJONAI's paper-only personal posture.
DEFAULT_CHECKPOINT = "google/timesfm-3.0-pytorch"


def _interpolate_quantile_column(
    q_matrix: np.ndarray,
    src_level: float,
    dst_level: float,
) -> np.ndarray:
    """Linearly interpolate a TimesFM native quantile column onto a target level.

    q_matrix is (horizon, n_native). Returns a length-horizon array. Used only
    for target levels that fall BETWEEN two native levels (0.25, 0.75).
    """
    native = np.asarray(_TIMESFM3_QUANTILES, dtype=float)
    if dst_level in native:
        return q_matrix[:, int(np.where(native == dst_level)[0][0])]
    hi_idx = int(np.searchsorted(native, dst_level))
    lo_idx = hi_idx - 1
    lo, hi = native[lo_idx], native[hi_idx]
    frac = (dst_level - lo) / (hi - lo)
    return q_matrix[:, lo_idx] * (1.0 - frac) + q_matrix[:, hi_idx] * frac


class TimesFMModel:
    """ForecastModel implementation backed by Google TimesFM 3.0."""

    def __init__(
        self,
        checkpoint: str = DEFAULT_CHECKPOINT,
        context_len: int = 1024,
        device: Optional[str] = None,
        local_files_only: bool = False,
    ):
        if not checkpoint or not str(checkpoint).strip():
            raise ValueError("checkpoint must be a non-empty HuggingFace repo id or local path")
        if context_len < 8:
            raise ValueError("context_len must be >= 8")
        self.checkpoint = str(checkpoint).strip()
        self.context_len = int(context_len)
        self.device = device
        self.local_files_only = bool(local_files_only)
        self._tfm = None

    @property
    def name(self) -> str:
        # "google/timesfm-3.0-pytorch" or "D:\\...\\timesfm-3.0-pytorch" -> "timesfm_3.0"
        leaf = self.checkpoint.replace("\\", "/").rstrip("/").split("/")[-1]
        tag = leaf
        for suffix in ("-pytorch", "-torch"):
            if tag.endswith(suffix):
                tag = tag[: -len(suffix)]
        tag = tag.replace("timesfm-", "").replace("timesfm_", "")
        return f"timesfm_{tag}" if tag else "timesfm"

    @property
    def loaded(self) -> bool:
        return self._tfm is not None

    def _load(self):
        """Load TimesFM 3.0 forecaster. Import- and weight-fail-closed."""
        if self._tfm is not None:
            return self._tfm

        try:
            from timesfm3.torch import TimesFM3Forecaster
        except ImportError as exc:
            raise ForecastUnavailableError(
                "timesfm3 package is not installed. Install the research ML "
                "opt-in (`pip install timesfm`) — the core venv / CI stay "
                "torch-free by design."
            ) from exc

        try:
            tfm = TimesFM3Forecaster.from_pretrained(
                self.checkpoint,
                device=self.device,
                local_files_only=self.local_files_only,
            )
        except Exception as exc:
            raise ForecastUnavailableError(
                f"TimesFM checkpoint '{self.checkpoint}' unavailable: {exc}. "
                "Ensure the local HuggingFace cache contains the checkpoint files."
            ) from exc

        self._tfm = tfm
        return self._tfm

    def predict(self, df: Any, horizon: int) -> ForecastResult:
        """Produce multi-quantile forecast path for the next `horizon` bars."""
        if horizon <= 0:
            raise ValueError("horizon must be positive")

        check_ohlcv(df)
        tfm = self._load()

        close_series = np.asarray(df["Close"].values, dtype=np.float32)
        if len(close_series) < 3:
            raise ForecastUnavailableError("Input series too short (<3 bars)")

        # Zero-lookahead slice: use at most context_len historical bars.
        input_series = close_series[-self.context_len :]

        try:
            out = tfm.predict(
                context=input_series,
                horizon=int(horizon),
                return_quantiles=True,
            )
        except Exception as exc:
            raise ForecastUnavailableError(f"TimesFM inference failed: {exc}") from exc

        # Point forecast (median). TimesFM returns it explicitly.
        point_raw = getattr(out, "forecast", None)
        if point_raw is None:
            raise ForecastUnavailableError("TimesFM returned no point forecast")
        point_path = [float(x) for x in np.asarray(point_raw).reshape(-1)[:horizon]]
        if len(point_path) != horizon:
            raise ForecastUnavailableError(
                f"TimesFM point path length {len(point_path)} != horizon {horizon}"
            )

        # Quantile paths. TimesFM native grid is q10..q90 (9 columns).
        q_raw = getattr(out, "quantiles", None)
        quantiles: Dict[float, List[float]] = {}
        if q_raw is not None:
            q_matrix = np.asarray(q_raw, dtype=float)
            if q_matrix.ndim == 3:  # (batch, horizon, n_quantiles)
                q_matrix = q_matrix[0]
            if q_matrix.ndim == 2 and q_matrix.shape[1] >= len(_TIMESFM3_QUANTILES):
                q_matrix = q_matrix[:horizon]
                for level in QUANTILE_LEVELS:
                    col = _interpolate_quantile_column(q_matrix, 0.0, level)
                    quantiles[level] = [float(v) for v in col]
            else:
                q_raw = None  # fall through to honest Gaussian residual head

        if not quantiles:
            # Honest fallback: Gaussian residual head around the point path.
            residuals = np.diff(input_series).tolist()
            quantiles = gaussian_quantiles_from_residuals(
                residuals, point_path, QUANTILE_LEVELS
            )

        quantiles[0.5] = point_path

        result = ForecastResult(
            model=self.name,
            horizon=horizon,
            quantiles=quantiles,
        )
        result.validate()
        return result
