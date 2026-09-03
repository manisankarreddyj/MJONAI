"""
Module: research/forecasting/kronos_adapter.py
Purpose: Kronos (shiyu-coder/Kronos, MIT) adapter behind ForecastModel.

Kronos is the ADR-0002 first-choice TSFM: natively consumes OHLCV K-lines,
open weights (mini 4.1M / small 24.7M / base 102.3M), probabilistic sampling.

This adapter is LAZY and HONEST: it never downloads weights implicitly and
raises ForecastUnavailableError with setup instructions when anything is
missing. Runtime verification requires the owner to opt into the weight
download (~50-500MB per size) — nothing here touches the network silently.
"""

from __future__ import annotations

from typing import List

import numpy as np

from research.forecasting.base import (
    ForecastUnavailableError,
    check_ohlcv,
)

# Maps MJONAI size aliases to HuggingFace repo ids.
KRONOS_SIZES = {
    "mini": "NeoQuasar/Kronos-mini",
    "small": "NeoQuasar/Kronos-small",
    "base": "NeoQuasar/Kronos-base",
}

# Per-size context limits from the Kronos README (tokens ~= bars).
KRONOS_CONTEXT = {"mini": 2048, "small": 512, "base": 512}


class KronosModel:
    """ForecastModel implementation backed by local Kronos weights."""

    def __init__(self, size: str = "small", device: str | None = None):
        if size not in KRONOS_SIZES:
            raise ValueError(f"size must be one of {sorted(KRONOS_SIZES)}")
        self.size = size
        self.device = device  # None -> torch auto selection
        self._predictor = None  # lazy

    # -- setup ---------------------------------------------------------------

    def _load(self):
        """Load tokenizer+predictor from LOCAL cache only (no silent net)."""
        if self._predictor is not None:
            return self._predictor

        try:
            from kronos import Kronos, KronosPredictor, KronosTokenizer  # type: ignore
        except ImportError as exc:
            raise ForecastUnavailableError(
                "kronos package not installed. Install per "
                "https://github.com/shiyu-coder/Kronos (pip install -e . of the "
                "repo) and download weights via huggingface_hub snapshot_download."
            ) from exc

        from huggingface_hub import snapshot_download  # guarded: kronos dep

        repo = KRONOS_SIZES[self.size]
        try:
            path = snapshot_download(repo, local_files_only=True)
        except Exception as exc:
            raise ForecastUnavailableError(
                f"Kronos weights for '{self.size}' ({repo}) not present in the "
                "local HF cache. Download them once with: "
                f"python -c \"from huggingface_hub import snapshot_download; "
                f"snapshot_download('{repo}')\""
            ) from exc

        tokenizer = KronosTokenizer.from_pretrained(path)
        model = Kronos.from_pretrained(path)
        self._predictor = KronosPredictor(
            model, tokenizer, device=self.device, max_context=KRONOS_CONTEXT[self.size]
        )
        return self._predictor

    @property
    def loaded(self) -> bool:
        return self._predictor is not None

    # -- ForecastModel contract ----------------------------------------------

    def predict(self, df, horizon: int) -> "object":
        """
        Returns a ForecastResult built from sampled paths (median path +
        empirical quantiles across samples). Raises ForecastUnavailableError
        when the package/weights are missing rather than fabricating output.
        """
        predictor = self._load()  # may raise ForecastUnavailableError

        from research.forecasting.base import QUANTILE_LEVELS, ForecastResult

        check_ohlcv(df)

        required = {"Open", "High", "Low", "Close", "Volume", "Amount"}
        missing = [c for c in required if c not in df.columns]
        work = df.copy()
        for col in missing:
            if col == "Amount":
                work["Amount"] = work["Close"] * work["Volume"]
            else:
                raise ForecastUnavailableError(f"Kronos needs column {col}")

        sample_count = 8
        T = 2.0
        top_p = 0.9

        try:
            pred_df = predictor.predict(
                df=work,
                x_timestamp=list(work.index),
                y_timestamp=[
                    work.index[-1] + (work.index[-1] - work.index[-2]) * (i + 1)
                    for i in range(horizon)
                ],
                pred_len=horizon,
                T=T,
                top_p=top_p,
                sample_count=sample_count,
            )
        except Exception as exc:  # inference failures are honest failures
            raise ForecastUnavailableError(f"Kronos inference failed: {exc}") from exc

        close_paths = np.asarray(pred_df["close"], dtype=float)
        if close_paths.ndim == 1:
            close_paths = close_paths[:, None]

        median = np.median(close_paths, axis=1).tolist()
        quantiles = {
            float(level): [
                float(np.quantile(close_paths[t], min(max(level, 0.0), 1.0)))
                for t in range(horizon)
            ]
            for level in QUANTILE_LEVELS
        }

        return ForecastResult(
            model=f"kronos_{self.size}",
            horizon=horizon,
            quantiles={0.5: median, **quantiles},
        )
