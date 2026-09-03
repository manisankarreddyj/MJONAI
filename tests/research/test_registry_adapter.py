"""Tests for the registry adapter bridge (research <-> live strategies)."""

import numpy as np
import pandas as pd
import pytest

from mjonai.research.optimization.models import ParameterSet
from mjonai.research.registry_adapter import (
    RegistryStrategyAdapter,
    available_registry_strategies,
    load_registry_strategy,
)


def make_df(n=300, seed=11):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0.05, 1.0, n))
    return pd.DataFrame(
        {
            "Open": close + 0.2,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": rng.integers(50_000, 200_000, n).astype(float),
        },
        index=pd.date_range("2024-01-01", periods=n, freq="B"),
    )


def test_loads_real_registry_strategy():
    adapted = load_registry_strategy("S01_MomentumRSI")

    assert adapted.name == "S01_MomentumRSI"
    # The LIVE version, not the archived research copy.
    assert adapted.version == "6.0"
    assert adapted.min_bars == 100


def test_unknown_id_raises():
    with pytest.raises(ValueError):
        load_registry_strategy("S99_Nope")


def test_flat_data_yields_none_or_valid_signal():
    adapted = load_registry_strategy("S01_MomentumRSI")

    flat = pd.DataFrame(
        {
            "Open": [100.0] * 250,
            "High": [100.5] * 250,
            "Low": [99.5] * 250,
            "Close": [100.0] * 250,
            "Volume": [10_000.0] * 250,
        }
    )

    result = adapted.generate_signal(flat)

    if result is not None:
        assert result.signal in ("LONG", "SHORT")
        assert result.index == len(flat) - 1


def test_random_data_respects_signal_contract():
    adapted = load_registry_strategy("S01_MomentumRSI")

    df = make_df()

    result = adapted.generate_signal(df)

    if result is not None:
        assert result.signal in ("LONG", "SHORT")
        # Signal fires on the LAST completed bar of the window.
        assert result.index == len(df) - 1
        assert result.strategy_id == "S01_MomentumRSI"


def test_configure_shadows_instance_without_class_leak():
    from mjonai.strategy.registry import MomentumRSI

    a = RegistryStrategyAdapter(MomentumRSI())
    b = RegistryStrategyAdapter(MomentumRSI())

    a.configure(ParameterSet(values={"RSI_MIN": 61.0}))

    # Configured instance sees the new value...
    assert a._s.RSI_MIN == 61.0
    # ...the untouched instance is NOT affected (no class-level leak)...
    assert b._s.RSI_MIN == 55.0
    # ...and the class default itself is unchanged.
    assert MomentumRSI.RSI_MIN == 55.0


def test_all_twelve_ids_registered():
    ids = available_registry_strategies()

    assert len(ids) == 12
    assert "S01_MomentumRSI" in ids
    assert "S12_MacroCommodityCrypto" in ids
