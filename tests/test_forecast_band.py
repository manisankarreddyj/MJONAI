"""ADR-0012 research-preview contract: the Kronos forecast band must fail closed
(no torch/weights, fetch failure, thin history => honest miss with reason) and must
carry the failed-verdict disclosure on EVERY payload — the band is never fabricated
and never presented as a signal.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from mjonai.research.forecasting.base import ForecastUnavailableError
from apps.web import data_views as dv


@pytest.fixture(autouse=True)
def _clear_cache():
    dv._FORECAST_CACHE.clear()
    yield
    dv._FORECAST_CACHE.clear()


def _daily_frame(n: int = 160, start: float = 100.0) -> pd.DataFrame:
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    import numpy as np

    vals = start + np.arange(n, dtype=float) * 0.1          # plain array: no index re-alignment
    return pd.DataFrame(
        {"Open": vals, "High": vals + 0.5, "Low": vals - 0.5, "Close": vals, "Volume": 1000.0},
        index=idx,
    )


class _FakeResult:
    def __init__(self, horizon: int, base: float = 100.0):
        self.quantiles = {
            0.1: [base - 1.0 + i for i in range(horizon)],
            0.5: [base + 0.5 + i for i in range(horizon)],
            0.9: [base + 2.0 + i for i in range(horizon)],
        }


class _FakeKronos:
    calls = 0

    def __init__(self, size: str = "small", device=None):
        self.size = size

    @property
    def name(self) -> str:
        return f"kronos_{self.size}"

    def predict(self, df, horizon: int):
        type(self).calls += 1
        return _FakeResult(horizon, base=float(df["Close"].iloc[-1]))


def test_band_happy_path_with_cache():
    frame = _daily_frame()
    with patch("mjonai.data.angelone.historical.fetch_historical_candles", return_value=frame), \
         patch("mjonai.research.forecasting.kronos_adapter.KronosModel", _FakeKronos):
        out = dv.build_forecast_band("infy", horizon=5)
        assert out["available"] is True
        assert out["model"] == "kronos_mini"
        assert len(out["path"]["median"]) == 5
        assert len(out["path"]["time"]) == 5
        assert out["path"]["time"][0] > out["history"][-1]["time"]     # path is in the future
        assert "FAILED" in out["disclosure"] and "Not a signal" in out["disclosure"]
        assert out["history"][-1]["close"] == round(float(frame["Close"].iloc[-1]), 2)
        # cache: second call does not re-run inference
        again = dv.build_forecast_band("INFY", horizon=5)
        assert again is out
        assert _FakeKronos.calls == 1


def test_band_fails_closed_when_model_unavailable():
    frame = _daily_frame()

    class _Broken(_FakeKronos):
        def predict(self, df, horizon: int):
            raise ForecastUnavailableError("weights missing")

    with patch("mjonai.data.angelone.historical.fetch_historical_candles", return_value=frame), \
         patch("mjonai.research.forecasting.kronos_adapter.KronosModel", _Broken):
        out = dv.build_forecast_band("tcs", horizon=5)
    assert out["available"] is False
    assert "path" not in out and "history" not in out           # no fabricated band
    assert out["reason"]
    assert "FAILED" in out["disclosure"]                        # verdict still travels


def test_band_fails_closed_on_thin_history():
    with patch("mjonai.data.angelone.historical.fetch_historical_candles", return_value=_daily_frame(n=10)):
        out = dv.build_forecast_band("sbin", horizon=5)
    assert out["available"] is False and "insufficient" in out["reason"].lower()


def test_band_fails_closed_on_fetch_error():
    with patch("mjonai.data.angelone.historical.fetch_historical_candles", side_effect=RuntimeError("boom")):
        out = dv.build_forecast_band("itc", horizon=5)
    assert out["available"] is False and "boom" in out["reason"]
