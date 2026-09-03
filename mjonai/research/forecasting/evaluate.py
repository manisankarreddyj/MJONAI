"""
Module: research/forecasting/evaluate.py
Purpose: Rolling-origin evaluation harness shared by ALL forecasters
         (classical and TSFM alike). Metrics chosen for trading relevance:
           - MAE on close (level accuracy)
           - Directional accuracy at h=1..h (does sign of predicted change match?)
           - Quantile coverage: empirical share inside the [q10, q90] band

ADR-0002 rule: a TSFM is only interesting if it beats these baselines here —
and ultimately improves risk-adjusted metrics through the FULL pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np


@dataclass
class ForecastEvaluation:
    model: str
    forecasts: int = 0
    mae: float = 0.0
    directional_accuracy: float = 0.0
    q10_q90_coverage: float = 0.0
    errors: List[str] = field(default_factory=list)

    def as_row(self) -> str:
        return (
            f"{self.model:<28} {self.forecasts:>6} {self.mae:>10.4f} "
            f"{self.directional_accuracy:>9.1%} {self.q10_q90_coverage:>12.1%}"
        )


def evaluate_forecaster(
    model,
    df,
    horizon: int = 5,
    min_history: int = 250,
    step: int = 1,
    max_origins: int = 500,
) -> ForecastEvaluation:
    """
    Rolling-origin evaluation: forecast once per `step` bars from an expanding
    past, score against realised closes. Deterministic; no leakage (the model
    only ever sees data strictly before each origin).
    """
    evaluation = ForecastEvaluation(model=getattr(model, "name", str(model)))

    abs_errs: List[float] = []
    dir_hits: List[int] = []
    cover_hits: List[int] = []
    cover_total = 0

    closes = np.asarray(df["Close"], dtype=float)
    n = len(closes)
    if n <= min_history + horizon:
        evaluation.errors.append(
            f"frame too short: need >{min_history + horizon} bars, got {n}"
        )
        return evaluation

    origins = range(min_history, n - horizon, max(1, step))
    ran = 0
    for origin in origins:
        if ran >= max_origins:
            break
        window = df.iloc[:origin]

        try:
            result = model.predict(window, horizon)
            result.validate()
        except Exception as exc:
            evaluation.errors.append(f"origin {origin}: {exc}")
            continue

        ran += 1
        actual = closes[origin : origin + horizon]
        point = np.asarray(result.point_path(), dtype=float)

        abs_errs.extend(np.abs(point - actual).tolist())

        # Direction of change vs origin close, first `horizon` steps.
        prev = np.concatenate(([closes[origin - 1]], actual[:-1]))
        pred_delta = np.sign(point - closes[origin - 1])
        true_delta = np.sign(actual - prev)
        dir_hits.append(float(np.mean(pred_delta == true_delta)))

        lo = np.asarray(result.quantiles.get(0.1, []), dtype=float)
        hi = np.asarray(result.quantiles.get(0.9, []), dtype=float)
        if len(lo) == horizon and len(hi) == horizon:
            inside = ((actual >= lo) & (actual <= hi)).sum()
            cover_hits.append(int(inside))
            cover_total += horizon

    evaluation.forecasts = ran
    if ran:
        evaluation.mae = float(np.mean(abs_errs))
        evaluation.directional_accuracy = float(np.mean(dir_hits))
        evaluation.q10_q90_coverage = (
            sum(cover_hits) / cover_total if cover_total else 0.0
        )
    return evaluation


def compare_models(models, df, **kwargs) -> List[ForecastEvaluation]:
    """Evaluate every model on identical origins; returns rows sorted by MAE."""
    rows = [evaluate_forecaster(m, df, **kwargs) for m in models]
    usable = [r for r in rows if r.forecasts > 0]
    unusable = [r for r in rows if r.forecasts == 0]
    usable.sort(key=lambda r: r.mae)
    return usable + unusable


def print_leaderboard(rows: List[ForecastEvaluation]) -> None:
    print(f"{'MODEL':<28} {'FCSTS':>6} {'MAE':>10} {'DIR ACC':>9} {'Q10-Q90 COV':>12}")
    print("-" * 72)
    for row in rows:
        print(row.as_row())
        for err in row.errors[:3]:
            print(f"    ! {err}")
