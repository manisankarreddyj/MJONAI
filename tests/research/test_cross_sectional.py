"""
Regression pins for research/discovery/cross_sectional.py — the PIT Nifty 50
cross-sectional factor engine. These guard the four things that would silently
invalidate every reported number: lookahead, cost accounting, PIT masking, and
factor direction.

Run: pytest tests/research/test_cross_sectional.py -q
"""
import numpy as np
import pandas as pd
import pytest

from mjonai.research.discovery import cross_sectional as CS


def _panel(n=300, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n)
    cols = ["AAA", "BBB", "CCC", "DDD"]
    data = {}
    for i, c in enumerate(cols):
        drift = 0.0002 * (i + 1)
        vol = 0.01 * (i + 1)
        p = 100 * np.exp(np.cumsum(rng.normal(drift, vol, n)))
        data[c] = p
    return pd.DataFrame(data, index=idx)


def test_low_vol_factor_holds_lower_vol_names():
    """Factor DIRECTION guard: factor_low_vol ranks the steadiest names first.
    A sign error here would silently turn 'low vol' into 'high vol'."""
    panel = _panel()
    fv = CS.factor_low_vol(panel)
    r = CS.backtest_cross_sectional(panel, fv, top_k=2, rebalance="B", buffer_mult=1.0)
    rvol = panel.pct_change().rolling(60, min_periods=40).std()
    held = r.holdings.dropna()
    # the two steadiest (AAA, BBB) should be the ones held
    last = held.iloc[-1]
    assert set(last) == {"AAA", "BBB"}, f"expected lowest-vol pair, got {last}"


def test_cost_accounting_one_way_times_traded_notional():
    """Cost guard: a forced buy + close/open swap must be charged
    one_way_bps * traded_notional (== canonical round trip for a full RT)."""
    idx = pd.bdate_range("2020-01-01", periods=90)
    up = pd.Series(np.linspace(100, 130, len(idx)), index=idx)
    dn = pd.Series(np.linspace(100, 80, len(idx)), index=idx)
    px = pd.DataFrame({"AAA": up, "BBB": dn}, index=idx)
    fac = pd.DataFrame(
        {"AAA": np.r_[np.zeros(40), np.ones(50)],
         "BBB": np.r_[np.ones(40), np.zeros(50)]}, index=idx
    )
    r = CS.backtest_cross_sectional(px, fac, top_k=1, rebalance="B", buffer_mult=1.0)
    traded = float(r.daily["turnover"].sum())
    assert traded == pytest.approx(3.0, abs=1e-6), "1.0 buy + 2.0 swap expected"
    rt = CS._equity_cost_bps(100.0)
    charged = float(r.daily["cost"].sum()) * 10000.0
    assert charged == pytest.approx(1.5 * rt, abs=1.0), "cost must be one_way * traded"


def test_no_lookahead_perturbation_invariance():
    """No-lookahead guard (perturbation test): rewriting the factor AFTER date X
    must leave every return BEFORE X bit-identical. If any future factor value
    leaked backwards, the earlier returns would move."""
    panel = _panel(n=200, seed=3)
    rng = np.random.default_rng(7)
    fac_a = pd.DataFrame(rng.normal(size=panel.shape), index=panel.index, columns=panel.columns)
    fac_b = fac_a.copy()
    cut = panel.index[150]
    fac_b.loc[cut:] = rng.normal(size=fac_b.loc[cut:].shape)  # scramble the future only
    ra = CS.backtest_cross_sectional(panel, fac_a, top_k=2, rebalance="B", buffer_mult=1.0)
    rb = CS.backtest_cross_sectional(panel, fac_b, top_k=2, rebalance="B", buffer_mult=1.0)
    pre_a = ra.daily.loc[:cut, "gross"].to_numpy()
    pre_b = rb.daily.loc[:cut, "gross"].to_numpy()
    np.testing.assert_allclose(pre_a, pre_b, rtol=0, atol=1e-12)


def test_equal_weight_benchmark_zero_turnover_after_build():
    """Sanity: holding all members (top_k=None) with a constant factor and a
    stable universe turns over exactly ONCE (the initial build) and never again.
    Regression guard for rebalance churn in the benchmark."""
    panel = _panel()
    const = pd.DataFrame(1.0, index=panel.index, columns=panel.columns)
    members = {d: set(panel.columns) for d in panel.index}
    r = CS.backtest_cross_sectional(panel, const, top_k=None, rebalance="M",
                                    members_by_date=members)
    # exactly one unit of turnover in total (the single initial position build)
    assert r.daily["turnover"].sum() == pytest.approx(1.0, abs=1e-6)
    years = (panel.index[-1] - panel.index[0]).days / 365.25
    assert r.total_turnover_yr == pytest.approx(1.0 / years, rel=0.02)


def test_pit_masking_excludes_non_members():
    """Universe guard: a symbol not in the PIT member set on a date can never be
    held, even if its factor is the best available."""
    panel = _panel()
    fac = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    fac["AAA"] = 1.0
    members = {d: {"BBB", "CCC", "DDD"} for d in panel.index}  # AAA never a member
    r = CS.backtest_cross_sectional(panel, fac, top_k=1, rebalance="M",
                                    buffer_mult=1.0, members_by_date=members)
    held = set(r.holdings.dropna().iloc[-1])
    assert "AAA" not in held, "non-member must be excluded"
