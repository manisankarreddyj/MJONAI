"""
Module: research/forecasting/kronos_adapter.py
Purpose: Kronos (shiyu-coder/Kronos, MIT) adapter behind the ForecastModel port.

Kronos is the ADR-0002 first-choice TSFM: natively consumes OHLCV K-lines,
ships open weights (mini 4.1M / small 24.7M / base 102.3M), probabilistic
sampling. It is vendored (pinned) under storage/vendor/kronos via
tools/scripts/fetch_kronos.py; its HF WEIGHTS live in storage/models/kronos.

This adapter is LAZY and HONEST: it never downloads implicitly and raises
ForecastUnavailableError with setup instructions when anything is missing —
it never returns fabricated numbers. The torch stack is research-only
(requirements-research-ml.txt); the core venv / CI stay torch-free.

Kronos integration notes (verified against the vendored model/kronos.py):
  - the tokenizer is a SEPARATE HF repo from the model -> both are resolved.
  - Kronos consumes LOWERCASE open/high/low/close (volume/amount optional,
    auto-zeroed); MJONAI frames are Capitalized -> mapped here.
  - x/y timestamps must be pandas Series (Kronos calls .dt) -> passed as Series.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

from mjonai.research.forecasting.base import (
    ForecastUnavailableError,
    check_ohlcv,
)

# Vendored Kronos code + local HF weight cache -- both gitignored; the research
# tier stays torch-free unless the owner opts in (requirements-research-ml.txt).
_VENDOR = Path(__file__).resolve().parents[3] / "storage" / "vendor" / "kronos"
_MODEL_CACHE = Path(__file__).resolve().parents[3] / "storage" / "models" / "kronos"

# Maps MJONAI size aliases to HuggingFace repo ids. The tokenizer ships as a
# SEPARATE repo from the model (per the Kronos README) -> resolved independently.
KRONOS_SIZES = {
    "mini": "NeoQuasar/Kronos-mini",
    "small": "NeoQuasar/Kronos-small",
    "base": "NeoQuasar/Kronos-base",
}
KRONOS_TOKENIZER = {
    "mini": "NeoQuasar/Kronos-Tokenizer-2k",
    "small": "NeoQuasar/Kronos-Tokenizer-base",
    "base": "NeoQuasar/Kronos-Tokenizer-base",
}
# Per-size context limits from the Kronos README (tokens ~= bars).
KRONOS_CONTEXT = {"mini": 2048, "small": 512, "base": 512}


class KronosModel:
    """ForecastModel implementation backed by local Kronos code + weights."""

    def __init__(self, size: str = "small", device: str | None = None):
        if size not in KRONOS_SIZES:
            raise ValueError(f"size must be one of {sorted(KRONOS_SIZES)}")
        self.size = size
        self.device = device  # None -> Kronos auto selection (cpu here)
        self._predictor = None  # lazy

    # -- setup ---------------------------------------------------------------

    def _load(self):
        """Load tokenizer + model from the vendored code + LOCAL weight cache only."""
        if self._predictor is not None:
            return self._predictor

        vendor = str(_VENDOR)
        if vendor not in sys.path:
            sys.path.insert(0, vendor)
        try:
            from model import Kronos, KronosPredictor, KronosTokenizer  # type: ignore  # vendored repo
        except ImportError as exc:
            raise ForecastUnavailableError(
                "Kronos is not usable: its vendored code (storage/vendor/kronos) or its torch "
                "stack is missing. Vendor it with `python tools/scripts/fetch_kronos.py` and "
                "`python -m pip install -r requirements-research-ml.txt` (torch is research-only — "
                "the core venv / CI stay torch-free by design)."
            ) from exc

        from huggingface_hub import snapshot_download  # guarded: kronos dep

        model_repo, tok_repo = KRONOS_SIZES[self.size], KRONOS_TOKENIZER[self.size]
        try:
            model_path = snapshot_download(model_repo, cache_dir=str(_MODEL_CACHE), local_files_only=True)
            tok_path = snapshot_download(tok_repo, cache_dir=str(_MODEL_CACHE), local_files_only=True)
        except Exception as exc:
            raise ForecastUnavailableError(
                f"Kronos weights for '{self.size}' are not in the local cache {_MODEL_CACHE} "
                f"(model={model_repo}, tokenizer={tok_repo}). Download once with: python -c "
                f"\"from huggingface_hub import snapshot_download; "
                f"[snapshot_download(r, cache_dir=r'{_MODEL_CACHE}') for r in ('{model_repo}','{tok_repo}')]\""
            ) from exc

        tokenizer = KronosTokenizer.from_pretrained(tok_path)
        model = Kronos.from_pretrained(model_path)
        self._predictor = KronosPredictor(
            model, tokenizer, device=self.device, max_context=KRONOS_CONTEXT[self.size]
        )
        return self._predictor

    @property
    def loaded(self) -> bool:
        return self._predictor is not None

    # -- ForecastModel contract ----------------------------------------------

    def predict(self, df, horizon: int):
        """
        Returns a ForecastResult built from sampled paths (median path +
        empirical quantiles across samples). Raises ForecastUnavailableError
        when the package/weights are missing OR inference fails — never fabricates.
        """
        predictor = self._load()  # may raise ForecastUnavailableError

        from mjonai.research.forecasting.base import QUANTILE_LEVELS, ForecastResult

        check_ohlcv(df)
        kdf = self._to_kronos_frame(df)  # lowercase OHLCV for Kronos; may raise

        horizon = int(horizon)
        idx = pd.DatetimeIndex(kdf.index)
        step = idx[-1] - idx[-2] if len(idx) >= 2 else pd.Timedelta(days=1)
        x_ts = pd.Series(idx)
        y_ts = pd.Series(pd.date_range(start=idx[-1] + step, periods=horizon, freq=step))

        try:
            pred_df = predictor.predict(
                df=kdf,
                x_timestamp=x_ts,
                y_timestamp=y_ts,
                pred_len=horizon,
                T=2.0,
                top_p=0.9,
                sample_count=8,
                verbose=False,
            )
        except Exception as exc:  # inference failures are honest failures
            raise ForecastUnavailableError(f"Kronos inference failed: {exc}") from exc

        close_paths = np.asarray(pred_df["close"], dtype=float)
        if close_paths.ndim == 1:
            close_paths = close_paths[:, None]

        median = [float(np.median(close_paths[t])) for t in range(horizon)]
        quantiles = {
            float(level): [
                float(np.quantile(close_paths[t], min(max(level, 0.0), 1.0)))
                for t in range(horizon)
            ]
            for level in QUANTILE_LEVELS
            if abs(level - 0.5) > 1e-9
        }
        quantiles[0.5] = median

        result = ForecastResult(
            model=f"kronos_{self.size}",
            horizon=horizon,
            quantiles=quantiles,
        )
        result.validate()  # port contract: no quantile crossing, lengths match
        return result

    @staticmethod
    def _to_kronos_frame(df) -> "pd.DataFrame":
        """Map an MJONAI (Capitalized) OHLCV frame to Kronos's lowercase contract."""
        cols = {str(c).lower(): c for c in df.columns}
        out = {}
        for low in ("open", "high", "low", "close"):
            src = cols.get(low)
            if src is None:
                raise ForecastUnavailableError(f"Kronos adapter needs a '{low}' column")
            out[low] = df[src].astype(float).to_numpy()
        work = pd.DataFrame(out, index=df.index)
        # volume/amount optional (Kronos auto-zeros if absent); include if present, NaN->0.
        for low in ("volume", "amount"):
            if low in cols:
                work[low] = df[cols[low]].astype(float).fillna(0.0).to_numpy()
        if work[["open", "high", "low", "close"]].isnull().values.any():
            raise ForecastUnavailableError("Kronos input has NaN in the price columns")
        return work
