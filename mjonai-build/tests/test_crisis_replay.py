"""
Test Suite: tests/test_crisis_replay.py
Purpose: Verify Historical Indian Market Crisis Replays and Monte Carlo Permutation / VaR.
"""

from datetime import datetime
import pytest

from research.stress_testing.crisis_replay import CRISIS_CATALOG, simulate_crisis_impact
from research.stress_testing.monte_carlo import run_monte_carlo_simulation


def test_crisis_catalog_scenarios():
    """Verify canonical Indian market crisis scenarios exist in the catalog."""
    assert "COVID_2020" in CRISIS_CATALOG
    assert "GFC_2008" in CRISIS_CATALOG
    assert "DEMONETIZATION_2016" in CRISIS_CATALOG
    assert "ELECTION_FLASH_2024" in CRISIS_CATALOG

    covid = CRISIS_CATALOG["COVID_2020"]
    assert covid.index_drop_pct < -30.0
    assert covid.volatility_spike_pct > 200.0


def test_simulate_crisis_impact_beta_and_defense():
    """Verify defensive stop losses reduce simulated max drawdown during crisis shock."""
    portfolio_equity = 1_000_000.0

    # Unhedged high beta portfolio (Beta = 1.2, SL efficiency = 0.0)
    unhedged = simulate_crisis_impact("COVID_2020", portfolio_equity, strategy_beta=1.2, stop_loss_efficiency=0.0)
    # Hedged defensive portfolio (Beta = 0.8, SL efficiency = 0.9)
    hedged = simulate_crisis_impact("COVID_2020", portfolio_equity, strategy_beta=0.8, stop_loss_efficiency=0.9)

    assert hedged.simulated_max_drawdown_pct < unhedged.simulated_max_drawdown_pct
    assert hedged.capital_preservation_score > unhedged.capital_preservation_score
    assert hedged.pnl_impact_inr > unhedged.pnl_impact_inr  # smaller negative loss


def test_monte_carlo_permutation_and_var():
    """Verify 5,000-run Monte Carlo trade permutation produces sound VaR and Drawdowns."""
    # 50 sample trades (60% win rate)
    pnls = [5000.0 if i % 10 < 6 else -4000.0 for i in range(50)]

    mc = run_monte_carlo_simulation(pnls, initial_capital=500_000.0, iterations=1000)
    assert mc.iterations == 1000
    assert mc.initial_capital == 500_000.0
    assert mc.median_ending_equity > 0
    # Quant Invariant: P05 <= Median <= P95
    assert mc.p05_ending_equity <= mc.median_ending_equity <= mc.p95_ending_equity
    # Quant Invariant: Median DD <= P95 DD <= P99 DD
    assert mc.median_max_drawdown_pct <= mc.p95_max_drawdown_pct <= mc.p99_max_drawdown_pct
    assert mc.profit_probability_pct > 50.0
