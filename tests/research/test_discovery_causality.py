"""Causality battery over EVERY discovery primitive — the qanat leak-test shape.

qanat (fidetolabs/qanat, MIT) structures its leak test as "one cheating step, every
route it could take to the future; each must be refused or earn ~nothing". The
transferable design lesson is exhaustiveness: the guarantee is only as strong as
the set of vectors it covers. MJONAI already pinned causality for A9-A11
(test_pkscreener_primitives), the SMC wrapper (test_smc_features), the next-bar-open
fill rule (test_no_lookahead), and PIT mask wiring — but not as ONE battery over
every registered family.

This is that battery. The vector is truncation: a signal on bar k must not change
when bars > k are removed. A forward-looking window (shift(-n), a non-shifted
rolling max, a full-frame .iloc[-1]) leaks the future and breaks equality here.
Every family in mjonai.research.discovery.signals is registered below; adding a new
primitive without registering it leaves a hole, so the registry is the knobs.
"""
import numpy as np
import pandas as pd
import pytest

from mjonai.research.discovery import signals as S

# bar k must be well past every window in the registry (ma=200 / swing=20 dominate)
_TRUNC_POINTS = (250, 350, 419)


def _daily(n=420, seed=5):
    rng = np.random.RandomState(seed)
    idx = pd.date_range("2015-01-05", periods=n, freq="B")
    px = 100 + np.cumsum(rng.randn(n) * 0.9)
    hi = px + np.abs(rng.randn(n)) * 0.6 + 0.2
    lo = px - np.abs(rng.randn(n)) * 0.6 - 0.2
    op = px + rng.randn(n) * 0.3
    cl = px + rng.randn(n) * 0.3
    hi = np.maximum.reduce([hi, op, cl])
    lo = np.minimum.reduce([lo, op, cl])
    return pd.DataFrame(
        {"open": op, "high": hi, "low": lo, "close": cl,
         "volume": rng.randint(1e4, 1e5, n)},
        index=idx,
    )


#: every registered family -> (fn, params). A new primitive must be added here.
FAMILIES = {
    "A1_ts_momentum": (S.sig_ts_momentum, {"lookback": 20, "thr": 0.0, "allow_short": True}),
    "A2_donchian": (S.sig_donchian, {"entry": 20, "exit": 10, "allow_short": True}),
    "A3_sma_cross": (S.sig_sma_cross, {"fast": 20, "slow": 50, "allow_short": True}),
    "A4_ma_filter_bh": (S.sig_ma_filter_bh, {"ma": 200}),
    "A5_vol_target": (S.sig_vol_target, {"vol_win": 20, "target_vol": 0.15, "max_size": 1.0}),
    "A6_calendar": (S.sig_calendar, {"months": [1, 11, 12]}),
    "A7_dayofweek": (S.sig_dayofweek, {"days": [0, 4]}),
    "A8_smc_structure": (S.sig_smc_structure, {"swing_length": 20, "allow_short": True}),
    "A9_narrow_range": (S.sig_narrow_range, {"n": 7, "ma": 5, "allow_short": True}),
    "A10_vcp_breakout": (S.sig_vcp_breakout, {"window": 40, "atr_ratio": 0.9, "allow_short": True}),
    "A11_consolidation": (S.sig_consolidation_breakout, {"window": 40, "band": 0.10, "allow_short": True}),
}


def _same(a, b) -> bool:
    return (pd.isna(a) and pd.isna(b)) or (not pd.isna(a) and not pd.isna(b) and a == b)


def test_registry_covers_the_module():
    """The battery must cover every public sig_ primitive in signals.py."""
    public = {n for n in dir(S) if n.startswith("sig_") and callable(getattr(S, n))}
    covered = {fn.__name__ for fn, _ in FAMILIES.values()}
    assert public == covered, (
        f"unregistered primitives would escape the causality battery: {public ^ covered}"
    )


@pytest.mark.parametrize("name", sorted(FAMILIES))
def test_positions_are_valid(name):
    fn, p = FAMILIES[name]
    s = fn(_daily(), p)
    assert len(s) == len(_daily()), f"{name} did not return one row per bar"
    # A5 vol-target is a sizing overlay: fractional exposure in [0,1], not the
    # {-1,0,1} discrete contract the other families follow. Bound is [-1,1] so any
    # primitive that leaves the legal exposure range (e.g. accidental leverage) fails.
    vals = pd.Series(s).dropna().unique()
    assert min(vals) >= -1.0 and max(vals) <= 1.0, (
        f"{name} emitted exposure outside [-1,1]: {sorted(vals)}"
    )


@pytest.mark.parametrize("name", sorted(FAMILIES))
def test_no_future_leak_under_truncation(name):
    """A signal at bar k must be identical whether or not bars > k exist.

    This is the single vector qanat's battery is built around: a family that reads
    the future looks brilliant on a full frame and only collapses when the frame is
    cut at the decision bar. Equality across every truncation point is the proof it
    never did.
    """
    fn, p = FAMILIES[name]
    df = _daily(420, seed=9)
    full = fn(df, p)
    for k in _TRUNC_POINTS:
        trunc = fn(df.iloc[: k + 1], p)
        assert _same(full.iloc[k], trunc.iloc[k]), (
            f"{name}: signal at {k} changed once future bars were removed -> LEAK "
            f"(full={full.iloc[k]}, trunc={trunc.iloc[k]})"
        )
