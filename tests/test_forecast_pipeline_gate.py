"""
Forecast→pipeline gate tests (ADR-0002 final gate):
  - friction reference is DERIVED from the canonical execution/tax.py engine
  - policy extraction: median path vs origin close → long/flat
  - trending series: drift-driven policy captures the move net of costs
  - sine series: seasonal-naive policy beats drift net (mirrors MAE ranking)
  - whipsaw series: costs visibly bite (gross > net, exposure churns)
"""

import numpy as np
import pandas as pd
import pytest

from mjonai.research.forecasting import DriftModel, SeasonalNaiveModel
from mjonai.research.forecasting.pipeline_gate import (
    REFERENCE_ROUND_TRIP_BPS,
    _policy_position,
    compare_trading_edge,
    evaluate_trading_edge,
    reference_round_trip_bps,
)
from mjonai.research.forecasting.classical import ForecastResult


def make_df(closes):
    closes = np.asarray(closes, dtype=float)
    idx = pd.date_range("2023-01-02", periods=len(closes), freq="D")
    return pd.DataFrame({
        "Open": closes - 0.05, "High": closes + 0.3, "Low": closes - 0.3,
        "Close": closes, "Volume": np.full(len(closes), 1000.0),
    }, index=idx)


def test_reference_bps_derived_from_canonical_engine():
    from mjonai.execution.tax import calculate_all_in_friction

    ref = calculate_all_in_friction(buy_price=100.0, sell_price=100.0, quantity=10_000)
    expected = ref["total_friction"] / (100.0 * 10_000 * 2) * 10_000
    assert reference_round_trip_bps() == pytest.approx(expected, abs=0.01)
    assert 5.0 < REFERENCE_ROUND_TRIP_BPS < 25.0  # sane large-cap delivery band


def test_policy_position_extraction():
    result = ForecastResult(
        model="t", horizon=3,
        quantiles={0.5: [101.0, 99.0, 103.0]},
    )
    # Origin close 100: above → +1, below → flat, above → +1.
    assert _policy_position(result, 3, 100.0) == [1, 0, 1]


def test_trending_series_drift_policy_captures_move():
    closes = [100.0 * (1.005 ** i) for i in range(320)]
    df = make_df(closes)

    report = evaluate_trading_edge(
        DriftModel(), df, horizon=5, min_history=250, step=2, max_origins=30
    )
    assert report.positions_taken > 0
    assert report.exposure_pct > 80.0          # persistent uptrend → mostly long
    assert report.net_return_pct > 0.0         # captures the drift net of costs


def test_sine_series_seasonal_beats_drift_net():
    t = np.arange(400)
    closes = 100 + 10 * np.sin(t * (2 * np.pi / 10))
    df = make_df(closes)

    rows = compare_trading_edge(
        [SeasonalNaiveModel(season_length=10), DriftModel()],
        df, horizon=5, min_history=250, step=5, max_origins=25,
    )
    by_name = {r.model: r for r in rows}
    assert by_name["seasonal_naive"].net_return_pct > by_name["rw_drift"].net_return_pct


def test_whipsaw_series_costs_bite():
    # Violent 2-bar alternation: a seasonal-naive (season=2) policy chases the
    # oscillation, churns in/out, and pays friction on every entry.
    closes = [100.0 + (2.0 if i % 2 == 0 else -2.0) for i in range(320)]
    df = make_df(closes)

    report = evaluate_trading_edge(
        SeasonalNaiveModel(season_length=2), df,
        horizon=4, min_history=250, step=1, max_origins=60,
    )
    assert report.positions_taken > 0
    assert report.costs_pct > 0.0
    assert report.gross_return_pct == pytest.approx(
        report.net_return_pct + report.costs_pct, abs=0.02
    )
