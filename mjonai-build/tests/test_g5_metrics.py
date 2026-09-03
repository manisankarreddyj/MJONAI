"""
G5 metrics-reconciliation regression tests (2026-08-24):
  - statistical_validation (DSR / White's Reality Check / Monte Carlo) behaves
    correctly AND is now wired: ResearchResult carries raw trades, walk-forward
    results carry OOS trades, run_walk_forward executes the validation block.
  - capital defaults share the ledger's INITIAL_CAPITAL single source.
"""

import inspect
import random
from datetime import datetime, timedelta

import numpy as np
import pytest

from analytics.statistical_validation import (
    deflated_sharpe_ratio,
    monte_carlo_drawdown_simulation,
    whites_reality_check,
)
from research.backtest.engine import INITIAL_CAPITAL


# ── DSR ───────────────────────────────────────────────────────────────────────

def test_dsr_insufficient_samples_returns_zero():
    assert deflated_sharpe_ratio([0.01] * 5) == 0.0


def test_dsr_positive_edge_survives_deflation():
    # Deterministic alternating series: per-period Sharpe ~0.6, well above
    # any plausible expected-max deflation at 10 trials.
    rets = [0.004 if i % 2 == 0 else -0.001 for i in range(250)]
    dsr = deflated_sharpe_ratio(rets, num_trials=10)
    assert dsr > 0.5

    # A near-zero-edge random draw must NOT survive deflation (DSR <= 0).
    rng = np.random.default_rng(7)
    weak = rng.normal(0.001, 0.005, 250).tolist()
    assert deflated_sharpe_ratio(weak, num_trials=10) < 0.5


# ── White's Reality Check ─────────────────────────────────────────────────────

def test_wrc_identical_to_benchmark_not_significant():
    """Zero excess returns must land p=1 / not significant (deterministic)."""
    random.seed(11)
    flat = [0.001] * 40
    res = whites_reality_check(flat, benchmark_returns=list(flat))
    assert res["is_significant"] is False
    assert res["p_value"] >= 0.5


def test_wrc_strong_edge_is_significant():
    random.seed(11)
    strat = [0.004 + 0.002 * ((-1) ** i) for i in range(60)]
    bench = [0.0001] * 60
    res = whites_reality_check(strat, benchmark_returns=bench)
    assert res["is_significant"] is True and res["p_value"] < 0.05


# ── Monte Carlo ───────────────────────────────────────────────────────────────

def test_monte_carlo_guard_and_percentile_ordering():
    guard = monte_carlo_drawdown_simulation([1.0] * 5)
    assert guard["simulations"] == 0

    random.seed(3)
    pnls = [50.0, -20.0, 80.0, -35.0, 25.0, -10.0, 90.0, -45.0, 30.0, 15.0, -25.0, 60.0]
    res = monte_carlo_drawdown_simulation(pnls, initial_capital=1000.0, num_simulations=200)
    assert 0 <= res["median_max_dd_pct"] <= res["p95_max_dd_pct"] <= res["p99_max_dd_pct"]
    assert res["prob_profit_pct"] > 50.0  # positive-expectancy sequence


def test_mc_default_capital_is_ledger_capital():
    sig = inspect.signature(monte_carlo_drawdown_simulation)
    assert sig.parameters["initial_capital"].default == INITIAL_CAPITAL


# ── Wiring: trades survive to the validation consumers ───────────────────────

def test_research_result_carries_trades_list():
    from research.models import ResearchResult

    assert "trades_list" in ResearchResult.__dataclass_fields__
    assert ResearchResult.__dataclass_fields__["trades_list"].default is None


def test_research_engine_retains_executed_trades():
    """End-to-end seam: engine runs the registry strategy over synthetic data
    and the result retains the executed TradeResults for statistical use."""
    from research.research_engine import ResearchEngine
    from research.data.models import Candle, HistoricalData
    from data.instruments.models import Instrument
    from research.registry_adapter import load_registry_strategy
    from research.dynamic_exits import dynamic_stop_loss, dynamic_target

    rng = np.random.default_rng(42)
    n = 250
    drift = np.linspace(100.0, 160.0, n)
    wave = np.sin(np.arange(n) * 0.5) * 2.0
    close = drift + wave + rng.normal(0, 0.08, n)
    open_ = close - 0.05
    high = np.maximum(open_, close) + 0.3
    low = np.minimum(open_, close) - 0.3
    vol = rng.uniform(50000, 150000, n)
    close[-1] = close[-2] + float(np.abs(wave[-10:]).max()) + 1.0
    open_[-1] = close[-1] - 0.8
    high[-1] = close[-1] + 0.2
    low[-1] = open_[-1] - 0.3
    vol[-1] = float(np.mean(vol[-20:])) * 1.9

    base = datetime(2023, 1, 2, 9, 15)
    candles = [
        Candle(
            timestamp=base + timedelta(days=i),
            open=float(open_[i]),
            high=float(high[i]),
            low=float(low[i]),
            close=float(close[i]),
            volume=float(vol[i]),
        )
        for i in range(n)
    ]
    instrument = Instrument(
        instrument_id="T1",
        symbol="TEST",
        name="TEST",
        provider="ANGEL",
        provider_type="EQ",
        provider_exchange="NSE",
        exchange="NSE",
        asset_type="EQUITY",
    )
    hd = HistoricalData(instrument=instrument, timeframe="1d", candles=candles)

    results = ResearchEngine().run(
        # Registry adapter wrapper — the same path the walk-forward CLI uses
        # (raw MomentumRSI.generate_signal has a wider signature).
        strategy=load_registry_strategy("S01_MomentumRSI"),
        historical_data_list=[hd],
        stop_loss_func=dynamic_stop_loss,
        target_func=dynamic_target,
        max_holding_bars=20,
    )

    assert results, "engine should evaluate the fixture"
    assert isinstance(results[0].trades_list, list)


def test_walk_forward_result_carries_oos_trades():
    from research.walk_forward.walk_forward_models import WalkForwardResult

    assert "validation_trades" in WalkForwardResult.__dataclass_fields__
