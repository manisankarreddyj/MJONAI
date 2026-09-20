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


def test_all_backtestable_ids_registered():
    ids = available_registry_strategies()

    assert len(ids) == 16
    assert "S01_MomentumRSI" in ids
    assert "S12_MacroCommodityCrypto" in ids
    # The S13-S18 cohort is backtestable (signal math reproducible on daily OHLCV).
    assert "S13_GammaFlip" in ids
    assert "S14_PostEarningsDrift" in ids
    assert "S16_CrossSectionalMomentum" in ids
    assert "S18_GapFillFVG" in ids


def test_data_gated_strategies_are_not_backtestable():
    """S15 (network at signal time) and S17 (fabricated order book) must be
    IMPOSSIBLE to backtest, not merely discouraged — with the reason
    documented next to the gate."""
    from mjonai.research.registry_adapter import RESEARCH_DATA_GATED

    ids = available_registry_strategies()
    assert "S15_FIIShortSqueeze" not in ids
    assert "S17_OrderFlowMicroPrice" not in ids
    with pytest.raises(ValueError):
        load_registry_strategy("S15_FIIShortSqueeze")
    with pytest.raises(ValueError):
        load_registry_strategy("S17_OrderFlowMicroPrice")

    assert "S15_FIIShortSqueeze" in RESEARCH_DATA_GATED
    assert "S17_OrderFlowMicroPrice" in RESEARCH_DATA_GATED
    assert RESEARCH_DATA_GATED["S15_FIIShortSqueeze"]
    assert RESEARCH_DATA_GATED["S17_OrderFlowMicroPrice"]


@pytest.mark.parametrize(
    "strategy_id",
    [
        "S13_GammaFlip",
        "S14_PostEarningsDrift",
        "S16_CrossSectionalMomentum",
        "S18_GapFillFVG",
    ],
)
def test_new_cohort_respects_signal_contract(strategy_id):
    """The S13-S18 backtestable cohort runs through the same adapter contract as
    S01-S12: signal fires on the LAST bar of the window, direction is
    tradable, and the result is attributed to the right strategy."""
    adapted = load_registry_strategy(strategy_id)

    df = make_df()
    result = adapted.generate_signal(df)

    if result is not None:
        assert result.signal in ("LONG", "SHORT")
        assert result.index == len(df) - 1
        assert result.strategy_id == strategy_id


def test_grid_names_resolve_to_uppercase_class_attrs():
    """get_parameters() returns lowercase keys but the grid must emit
    UPPERCASE names matching the class attributes that `configure` sets."""
    adapted = load_registry_strategy("S01_MomentumRSI")
    grid = adapted.parameters
    names = {d.name for d in grid}

    assert "RSI_MIN" in names
    assert "ADX_MIN_STRENGTH" in names
    assert "DONCHIAN_PERIOD" in names
    # No lowercase leakage from get_parameters.
    assert "rsi_min" not in names
    assert "adx_min_strength" not in names


def test_s01_widened_grid_contains_search_space():
    adapted = load_registry_strategy("S01_MomentumRSI")
    grid = adapted.parameters
    grid_map = {d.name: d.values for d in grid}

    assert grid_map["RSI_MIN"] == [50.0, 55.0, 60.0]
    assert grid_map["ADX_MIN_STRENGTH"] == [15.0, 20.0, 25.0]
    assert grid_map["RVOL_MIN_THRESHOLD"] == [1.20, 1.35, 1.50]
    assert grid_map["DONCHIAN_PERIOD"] == [15, 20, 25]


def test_s01_grid_combinatorial_count():
    """4 widened params × 3 values = 81 default combos
    (plus single-point cells from non-searchable params)."""
    adapted = load_registry_strategy("S01_MomentumRSI")
    grid = adapted.parameters

    multi = [d for d in grid if len(d.values) > 1]
    single = [d for d in grid if len(d.values) == 1]
    assert len(multi) == 4
    # Combinatorial product of all 4 multi-value cells.
    count = 1
    for d in multi:
        count *= len(d.values)
    assert count == 81


def test_configure_applies_grid_value():
    """configure must actually apply the parameter — the historical
    no-op when names were lowercase is guarded against."""
    from mjonai.strategy.registry import MomentumRSI

    adapted = RegistryStrategyAdapter(MomentumRSI())
    original = adapted._s.RSI_MIN

    adapted.configure(ParameterSet(values={"RSI_MIN": original + 10}))
    assert adapted._s.RSI_MIN == original + 10


def test_strategies_not_in_grid_keep_single_point():
    """A strategy without a widened grid keeps one value per parameter."""
    adapted = load_registry_strategy("S03_TurtleBreakout")
    grid = adapted.parameters

    for defn in grid:
        assert len(defn.values) == 1
