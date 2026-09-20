"""Tests for the F&O EOD chain loader and its research wiring (S13 GEX).

The chain warehouse is gitignored runtime data (built by run_fno_backfill.py)
and therefore ABSENT in this sandbox. Every fallback path is tested against
the real fail-closed code, and the enrichment path against a synthetic month
parquet written with the canonical schema.
"""

import numpy as np
import pandas as pd
import pytest

from mjonai.research.data.fno_eod import load_eod_chain_for_date
from mjonai.research.registry_adapter import (
    RegistryStrategyAdapter,
    load_registry_strategy,
)

CANON = [
    "trade_date", "underlying", "kind", "option_type", "strike", "expiry",
    "open", "high", "low", "close", "last", "settle", "prev_close",
    "underlying_price", "volume", "turnover", "trades", "oi", "oi_change",
    "lot_size",
]


def build_month_frame(
    day: pd.Timestamp,
    underlying="NIFTY",
    call_oi=100_000,
    put_oi=100_000,
) -> pd.DataFrame:
    """One trading day's chain with two expiries; the nearer (2024-06-27) and
    a farther one (2024-07-04) so nearest-expiry selection is observable."""
    rows = []
    expiry = pd.Timestamp("2024-06-27").normalize()
    far = pd.Timestamp("2024-07-04").normalize()
    strikes = [24500, 24600, 24700]
    for exp in (expiry, far):
        for k in strikes:
            for opt in ("CE", "PE"):
                rows.append(
                    {
                        "trade_date": day,
                        "underlying": underlying,
                        "kind": "OPT",
                        "option_type": opt,
                        "strike": float(k),
                        "expiry": exp.date(),
                        "open": 0.0,
                        "high": 0.0,
                        "low": 0.0,
                        "close": 0.0,
                        "last": 0.0,
                        "settle": 0.0,
                        "prev_close": 0.0,
                        "underlying_price": 24500.0,
                        "volume": 0,
                        "turnover": 0.0,
                        "trades": 0,
                        "oi": call_oi if opt == "CE" else put_oi,
                        "oi_change": 0,
                        "lot_size": 65,
                    }
                )
    return pd.DataFrame(rows, columns=CANON)


def write_month(tmp_path, day: pd.Timestamp, **kw) -> str:
    frame = build_month_frame(day, **kw)
    path = tmp_path / "eod" / f"{day:%Y-%m}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return str(tmp_path)


def test_load_returns_nearest_expiry_only(tmp_path):
    day = pd.Timestamp("2024-06-14").normalize()
    out_dir = write_month(tmp_path, day)
    frame = load_eod_chain_for_date(out_dir, "NIFTY", day)

    assert frame is not None
    # Nearest expiry only (2024-06-27, dte 13) — the far expiry is excluded.
    expiries = set(pd.to_datetime(frame["expiry"]).dt.normalize())
    assert expiries == {pd.Timestamp("2024-06-27")}
    assert len(frame) == 6  # 3 strikes x CE/PE
    assert set(frame["strike"]) == {24500.0, 24600.0, 24700.0}
    assert set(frame["option_type"]) == {"CE", "PE"}


def test_load_missing_month_returns_none(tmp_path):
    assert load_eod_chain_for_date(str(tmp_path), "NIFTY", pd.Timestamp("2024-06-14")) is None


def test_load_missing_underlying_returns_none(tmp_path):
    day = pd.Timestamp("2024-06-14").normalize()
    out_dir = write_month(tmp_path, day)
    assert load_eod_chain_for_date(out_dir, "BANKNIFTY", day) is None


def test_load_non_trading_day_returns_none(tmp_path):
    day = pd.Timestamp("2024-06-14").normalize()
    out_dir = write_month(tmp_path, day)
    assert load_eod_chain_for_date(out_dir, "NIFTY", pd.Timestamp("2024-06-15")) is None


def test_load_lowers_underlying_case(tmp_path):
    day = pd.Timestamp("2024-06-14").normalize()
    out_dir = write_month(tmp_path, day)
    assert load_eod_chain_for_date(out_dir, "nifty", day) is not None


def test_adapter_chain_precomputed_real_gex(tmp_path):
    day = pd.Timestamp("2024-06-14").normalize()
    out_dir = write_month(tmp_path, day, call_oi=250_000, put_oi=100_000)
    adapted = load_registry_strategy("S13_GammaFlip", symbol="NIFTY")
    adapted._fno_chain_dir = out_dir

    rng = np.random.default_rng(11)
    close = 23_000 + np.cumsum(rng.normal(0.05, 100.0, 300))
    df = pd.DataFrame(
        {
            "Open": close + 10.0,
            "High": close + 50.0,
            "Low": close - 50.0,
            "Close": close,
            "Volume": rng.integers(50_000, 200_000, 300).astype(float),
        },
        index=pd.date_range("2024-01-01", periods=300, freq="B"),
    )
    result = adapted.generate_signal(df)

    # The decision bar's date must be exactly the synthetic chain day for the
    # loader to resolve it; make_df ends in 2025 so the chain will miss. Use a
    # frame whose last bar lands on the chain date instead.
    df2 = df.iloc[:200].copy()
    df2.index = pd.date_range("2023-04-01", periods=200, freq="B")
    # align so the LAST index matches 2024-06-14
    df2.index = pd.date_range(end=day, periods=200, freq="B")
    precomp = adapted._chain_precomputed(df2)

    assert precomp is not None
    assert set(precomp) == {"zero_gamma_level", "total_gex_crores"}
    assert precomp["zero_gamma_level"] > 0
    assert isinstance(precomp["total_gex_crores"], float)

    # Real, deterministic asymmetric GEX: calls carry 2.5x puts' OI, so net
    # dealer GEX must net POSITIVE, not zero and not a fabricated figure.
    assert precomp["total_gex_crores"] > 0


def test_adapter_chain_precomputed_fail_closed_without_warehouse(tmp_path):
    adapted = load_registry_strategy("S13_GammaFlip", symbol="NIFTY")
    adapted._fno_chain_dir = str(tmp_path)

    rng = np.random.default_rng(11)
    close = 23_000 + np.cumsum(rng.normal(0.05, 100.0, 250))
    df = pd.DataFrame(
        {
            "Open": close + 10.0,
            "High": close + 50.0,
            "Low": close - 50.0,
            "Close": close,
            "Volume": rng.integers(50_000, 200_000, 250).astype(float),
        },
        index=pd.date_range(end=pd.Timestamp("2024-06-14"), periods=250, freq="B"),
    )

    # No warehouse -> honest None (S13 then uses its EMA-20 proxy).
    assert adapted._chain_precomputed(df) is None


def test_adapter_chain_precomputed_not_chain_aware():
    from mjonai.strategy.registry import MomentumRSI

    adapter = RegistryStrategyAdapter(MomentumRSI(), symbol="NIFTY")
    rng = np.random.default_rng(11)
    close = 100 + np.cumsum(rng.normal(0.05, 1.0, 250))
    df = pd.DataFrame(
        {
            "Open": close + 0.2,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": rng.integers(50_000, 200_000, 250).astype(float),
        },
        index=pd.date_range("2024-01-01", periods=250, freq="B"),
    )
    assert adapter._chain_precomputed(df) is None


def test_runner_threads_symbol_into_adapter():
    from mjonai.research.runner import StrategyRunner

    rng = np.random.default_rng(11)
    close = 100 + np.cumsum(rng.normal(0.05, 1.0, 250))
    df = pd.DataFrame(
        {
            "Open": close + 0.2,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": rng.integers(50_000, 200_000, 250).astype(float),
        },
        index=pd.date_range("2024-01-01", periods=250, freq="B"),
    )

    adapted = load_registry_strategy("S13_GammaFlip")
    assert adapted.symbol == ""
    runner = StrategyRunner(adapted)
    runner.run(symbol="NIFTY", data=df)

    # The engine shares one adapter across symbols; the runner must push the
    # current run's symbol down before the bar loop so chain lookups key
    # correctly.
    assert adapted.symbol == "NIFTY"