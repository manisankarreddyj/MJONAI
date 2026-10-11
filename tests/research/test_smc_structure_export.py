"""SMC structure export contract (research tier).

compute_structure must return leakage-safe markers (every zone/swing timestamp at
or before the last bar), detect a constructed bullish FVG, and expose the current
gap-hold state — and it must fail loudly (RuntimeError with the fetch command)
when the vendored library is absent rather than fabricate markers.
"""
import numpy as np
import pandas as pd
import pytest

from apps.research.run_smc_structure_export import SNAPSHOT_DISCLOSURE, compute_structure


def _frame_with_bullish_fvg(n: int = 60) -> pd.DataFrame:
    """A synthetic frame whose last third contains a clean bullish FVG:
    bar i-1 high < bar i+1 low around a rising bar i."""
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    close = 100.0 + np.arange(n, dtype=float) * 0.2
    high = close + 0.5
    low = close - 0.5
    openp = close - 0.1
    i = n - 20
    high[i - 1] = close[i - 1] - 1.0          # prior bar capped low
    low[i + 1] = close[i + 1] + 1.0           # next bar lifts off -> gap between
    df = pd.DataFrame({"Open": openp, "High": high, "Low": low, "Close": close, "Volume": 1000.0}, index=idx)
    return df


def test_compute_structure_detects_fvg_and_is_causal():
    df = _frame_with_bullish_fvg()
    out = compute_structure(df, timeframe="1d", swing_length=10)
    assert out["available"] is True
    last_ts = int(pd.Timestamp(df.index[-1]).timestamp())

    zones = out["fvg_zones"]
    assert zones, "expected at least one confirmed FVG on the synthetic frame"
    for z in zones:
        assert z["time"] <= last_ts                        # confirmed zones never read the future
        assert z["low"] <= z["high"] and z["dir"] in (1, -1)
    for s in out["swings"]:
        assert s["time"] <= last_ts                        # swing lagged by its look-ahead
        assert s["dir"] in (1, -1)

    cur = out["current"]
    assert set(cur) == {"smc_fvg_dir", "smc_swing_hl", "in_bull_fvg", "in_bear_fvg", "dist_to_swing"}
    assert "RISK OVERLAY, NOT ALPHA" in out["disclosure"]
    assert out["disclosure"] == SNAPSHOT_DISCLOSURE
    assert out["bars"][-1]["time"] == last_ts


def test_compute_structure_requires_ohlcv_columns():
    with pytest.raises(ValueError):
        compute_structure(pd.DataFrame({"Close": [1.0, 2.0, 3.0]}), timeframe="1d")


def test_missing_vendor_raises_with_fetch_command(monkeypatch):
    from mjonai.research.discovery import smc_features as sf

    monkeypatch.setattr(sf, "_VENDOR", sf.Path("/nonexistent/vendor/path"))
    with pytest.raises(RuntimeError, match="fetch_smc"):
        compute_structure(_frame_with_bullish_fvg(n=40), timeframe="1d")
