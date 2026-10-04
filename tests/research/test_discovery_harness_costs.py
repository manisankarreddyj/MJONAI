"""
Regression pins for research/discovery/harness.py cost accounting.

The engine charges ONE-WAY cost (round-trip / 2) per unit of |dpos|. Charging
the full round-trip rate per unit of |dpos| bills a completed 0->1->0 round trip
TWICE and understates every net return. These tests pin the correct semantics.
"""
import numpy as np
import pandas as pd
import pytest

from mjonai.research.discovery import harness as H


def _flat(n=40, px=100.0):
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.DataFrame({"close": np.full(n, px)}, index=idx), idx


def test_flat_price_roundtrip_costs_exactly_one_roundtrip():
    """A 0->+1->0 round trip on a FLAT price (zero gross) must lose exactly ONE
    canonical round-trip cost, never two."""
    df, idx = _flat()
    sig = pd.Series(0.0, index=idx)
    sig.iloc[5] = 1.0
    sig.iloc[10] = 0.0            # exit
    sig.iloc[15] = 1.0
    sig.iloc[20] = 0.0            # exit -> 2 complete round trips
    out = H.backtest(df, sig, asset_class="FUTURES", product_type="INTRADAY",
                     cost_ref_price=100.0)
    rt_bps = H.roundtrip_cost_bps(100.0, asset_class="FUTURES", product_type="INTRADAY")
    charged_bps = float(out.daily["cost"].sum()) * 10000.0
    assert out.daily["gross"].abs().sum() == pytest.approx(0.0, abs=1e-12), "flat price -> no gross"
    assert charged_bps == pytest.approx(2.0 * rt_bps, rel=0.02), (
        f"two round trips must cost 2x the round-trip rate, got {charged_bps:.2f} vs {2*rt_bps:.2f}")


def test_one_way_cost_is_half_the_roundtrip_rate():
    """The per-unit cost constant must be exactly half the round-trip rate."""
    df, idx = _flat()
    sig = pd.Series(0.0, index=idx)
    sig.iloc[5] = 1.0
    sig.iloc[10] = 0.0
    out = H.backtest(df, sig, asset_class="FUTURES", product_type="INTRADAY",
                     cost_ref_price=100.0)
    rt_bps = H.roundtrip_cost_bps(100.0, asset_class="FUTURES", product_type="INTRADAY")
    charged_bps = float(out.daily["cost"].sum()) * 10000.0
    # one round trip = entry dpos 1 + exit dpos 1 = 2 units, each at rt/2
    assert charged_bps == pytest.approx(1.0 * rt_bps, rel=0.02)


def test_backtest_applies_one_bar_execution_lag():
    """A signal decided on bar t must earn bar t+1's return, never bar t's."""
    idx = pd.bdate_range("2020-01-01", periods=10)
    close = np.array([100, 110, 120, 130, 140, 150, 160, 170, 180, 190], dtype=float)
    df = pd.DataFrame({"close": close}, index=idx)
    sig = pd.Series(0.0, index=idx)
    sig.iloc[0] = 1.0            # long from bar 0 onward
    out = H.backtest(df, sig, asset_class="FUTURES", product_type="INTRADAY",
                     cost_ref_price=100.0)
    # bar 0 return is NaN (no prior close); bar 1 return is +10% and must be
    # EARNED because the signal was executed one bar earlier.
    assert out.daily.loc[idx[1], "pos_used"] == 1.0
    assert out.daily.loc[idx[1], "gross"] == pytest.approx(0.10, rel=1e-6)
    assert out.daily.loc[idx[0], "pos_used"] == 0.0, "no position on the signal bar itself"
