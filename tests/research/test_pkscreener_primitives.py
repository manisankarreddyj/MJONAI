"""PKScreener-style research primitives (A9/A10/A11) — leakage-safety + validity.

These are clean-room reimplementations of India-native scanner IDEAS (no PKScreener code is
copied; its license is unverified). The decisive test is causality: truncating the frame at bar k
must not rewrite the signal at k — a forward-looking window would leak the future and fail here."""
import numpy as np
import pandas as pd

from mjonai.research.discovery import signals as S


def _daily(n=420, seed=5):
    rng = np.random.RandomState(seed)
    idx = pd.date_range("2015-01-05", periods=n, freq="B")
    px = 100 + np.cumsum(rng.randn(n) * 0.9)
    hi = px + np.abs(rng.randn(n)) * 0.6 + 0.2
    lo = px - np.abs(rng.randn(n)) * 0.6 - 0.2
    op = px + rng.randn(n) * 0.3
    cl = px + rng.randn(n) * 0.3
    hi = np.maximum.reduce([hi, op, cl]); lo = np.minimum.reduce([lo, op, cl])
    return pd.DataFrame(
        {"open": op, "high": hi, "low": lo, "close": cl,
         "volume": rng.randint(1e4, 1e5, n)}, index=idx
    )


_FAMILIES = {
    "narrow_range": (S.sig_narrow_range, {"n": 7, "ma": 5}),
    "vcp": (S.sig_vcp_breakout, {"window": 40, "atr_ratio": 0.9}),
    "consolidation": (S.sig_consolidation_breakout, {"window": 40, "band": 0.10}),
}


def test_positions_are_valid():
    df = _daily()
    for name, (fn, p) in _FAMILIES.items():
        s = fn(df, p)
        assert set(s.dropna().unique()).issubset({-1.0, 0.0, 1.0}), f"{name} emitted {set(s.unique())}"
        assert len(s) == len(df)


def test_causality_truncation_does_not_rewrite_present():
    """Truncating at bar k must not change the signal at k (no future leak)."""
    df = _daily(420, seed=9)
    for name, (fn, p) in _FAMILIES.items():
        full = fn(df, p)
        for k in (200, 300, 419):
            trunc = fn(df.iloc[: k + 1], p)
            assert full.iloc[k] == trunc.iloc[k], (
                f"{name}: signal at {k} changed with future bars -> LEAK "
                f"(full={full.iloc[k]}, trunc={trunc.iloc[k]})"
            )
