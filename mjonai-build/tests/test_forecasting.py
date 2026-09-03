"""
F-wave forecasting tests (ADR-0002):
  - classical baselines produce correct, leakage-free quantile forecasts
  - the shared evaluation harness scores and ranks honestly
  - the Kronos adapter fails HONESTLY (ForecastUnavailableError) when the
    package/weights are absent — never fabricated numbers
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from research.forecasting import (
    DriftModel,
    ExpSmoothingModel,
    ForecastResult,
    ForecastUnavailableError,
    SeasonalNaiveModel,
)
from research.forecasting.evaluate import compare_models, evaluate_forecaster


def make_df(closes, start=datetime(2023, 1, 2), freq="D"):
    closes = np.asarray(closes, dtype=float)
    idx = pd.date_range(start, periods=len(closes), freq=freq)
    return pd.DataFrame(
        {
            "Open": closes - 0.05,
            "High": closes + 0.3,
            "Low": closes - 0.3,
            "Close": closes,
            "Volume": np.full(len(closes), 1000.0),
        },
        index=idx,
    )


# ── classical baseline math ──────────────────────────────────────────────────

def test_seasonal_naive_point_path_repeats_last_season():
    season = [10.0, 11.0, 12.0, 13.0, 14.0]
    closes = season * 12 + season[:4]  # 64 bars, deterministic pattern
    df = make_df(closes)

    result = SeasonalNaiveModel(season_length=5).predict(df, horizon=5)

    # Data ends mid-season (64 bars = 12 seasons + 4): the naive forecast
    # repeats the LAST season's values, i.e. closes[-5:] = [14,10,11,12,13].
    assert result.point_path() == pytest.approx([14.0, 10.0, 11.0, 12.0, 13.0])


def test_drift_model_compounds_mean_log_return():
    closes = [100.0 * (1.01 ** i) for i in range(60)]  # exact +1%/bar
    df = make_df(closes)

    result = DriftModel().predict(df, horizon=2)

    last = closes[-1]
    assert result.point_path()[0] == pytest.approx(last * 1.01, rel=1e-6)
    assert result.point_path()[1] == pytest.approx(last * 1.01 ** 2, rel=1e-6)


def test_exp_smoothing_forecast_is_finite_and_ordered():
    rng = np.random.default_rng(5)
    closes = 100 + np.cumsum(rng.normal(0.02, 1.0, 200))
    df = make_df(closes)

    result = ExpSmoothingModel().predict(df, horizon=4)

    path = result.point_path()
    assert all(np.isfinite(path))
    assert result.quantiles[0.9][0] >= result.quantiles[0.1][0]


def test_all_classical_results_validate_quantile_contract():
    rng = np.random.default_rng(6)
    df = make_df(100 + np.cumsum(rng.normal(0.01, 1.0, 300)))
    for model in (SeasonalNaiveModel(), DriftModel(), ExpSmoothingModel()):
        result = model.predict(df, horizon=7)
        assert isinstance(result, ForecastResult)
        result.validate()  # raises on crossing / length mismatch


# ── evaluation harness ───────────────────────────────────────────────────────

def test_evaluation_scores_and_ranks_models():
    # Strong sine series: seasonal-naive should be near-perfect; drift mediocre.
    t = np.arange(400)
    closes = 100 + 10 * np.sin(t * (2 * np.pi / 10))
    df = make_df(closes)

    rows = compare_models(
        [SeasonalNaiveModel(season_length=10), DriftModel()],
        df,
        horizon=5,
        min_history=250,
        step=5,
        max_origins=20,
    )

    by_name = {r.model: r for r in rows}
    naive = by_name["seasonal_naive"]
    assert naive.forecasts > 0
    # Sign accuracy at flat sine turning points caps well below 1.0.
    assert naive.directional_accuracy > 0.7
    assert naive.mae < by_name["rw_drift"].mae


def test_evaluation_reports_short_frame_as_error_not_crash():
    df = make_df([100.0 + i for i in range(50)])
    evaluation = evaluate_forecaster(DriftModel(), df, horizon=5, min_history=250)
    assert evaluation.forecasts == 0
    assert evaluation.errors


# ── Kronos adapter honesty ───────────────────────────────────────────────────

def test_kronos_missing_weights_fail_honestly(monkeypatch):
    """Without the kronos package installed locally the adapter must raise
    ForecastUnavailableError with setup guidance — never fabricate output."""
    from research.forecasting.kronos_adapter import KronosModel

    model = KronosModel(size="small")
    df = make_df([100 + i for i in range(60)])

    try:
        import kronos  # noqa: F401

        pytest.skip("kronos package installed on this machine")
    except ImportError:
        pass

    with pytest.raises(ForecastUnavailableError) as excinfo:
        model.predict(df, horizon=5)
    assert "kronos" in str(excinfo.value).lower()


def test_kronos_invalid_size_rejected_immediately():
    from research.forecasting.kronos_adapter import KronosModel

    with pytest.raises(ValueError):
        KronosModel(size="jumbo")
