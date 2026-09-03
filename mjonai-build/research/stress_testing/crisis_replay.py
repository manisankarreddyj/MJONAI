"""
Module: research/stress_testing/crisis_replay.py
Purpose: Historical stress replay simulator for Indian equity market tail-risk shocks.
         Tests portfolio survival and circuit breaker resilience under extreme market dislocations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Any
import numpy as np


@dataclass(slots=True)
class CrisisScenario:
    id: str
    name: str
    description: str
    start_date: datetime
    end_date: datetime
    index_drop_pct: float
    volatility_spike_pct: float
    key_drivers: str


# Canonical Indian Market Crisis Catalog
CRISIS_CATALOG: Dict[str, CrisisScenario] = {
    "COVID_2020": CrisisScenario(
        id="COVID_2020",
        name="COVID-19 Global Pandemic Crash",
        description="Fastest 38% collapse in NIFTY history with repeated 10% lower circuit breaker halts.",
        start_date=datetime(2020, 2, 20),
        end_date=datetime(2020, 3, 25),
        index_drop_pct=-38.4,
        volatility_spike_pct=+350.0,
        key_drivers="Global lockdown panic, liquidity squeeze, margin liquidation cascades.",
    ),
    "GFC_2008": CrisisScenario(
        id="GFC_2008",
        name="2008 Global Financial Crisis",
        description="Protracted 60% bear market triggered by subprime credit collapse.",
        start_date=datetime(2008, 1, 8),
        end_date=datetime(2008, 10, 27),
        index_drop_pct=-59.8,
        volatility_spike_pct=+280.0,
        key_drivers="Lehman Brothers collapse, global credit freeze, systemic FII outflows.",
    ),
    "DEMONETIZATION_2016": CrisisScenario(
        id="DEMONETIZATION_2016",
        name="2016 Currency Demonetization Shock",
        description="Sudden invalidation of 86% of currency in circulation; domestic consumption shock.",
        start_date=datetime(2016, 11, 8),
        end_date=datetime(2016, 12, 26),
        index_drop_pct=-7.5,
        volatility_spike_pct=+65.0,
        key_drivers="Acute cash liquidity deficit, micro-cap collapse, NBFC credit stress.",
    ),
    "ELECTION_FLASH_2024": CrisisScenario(
        id="ELECTION_FLASH_2024",
        name="June 4, 2024 General Election Flash Crash",
        description="Historic 6% intra-day index plunge and massive IV crush on vote-counting day.",
        start_date=datetime(2024, 6, 3),
        end_date=datetime(2024, 6, 5),
        index_drop_pct=-5.9,
        volatility_spike_pct=+120.0,
        key_drivers="Election results divergence from exit polls, panic institutional short-covering.",
    ),
}


@dataclass(slots=True)
class StressSimulationResult:
    scenario_id: str
    scenario_name: str
    simulated_max_drawdown_pct: float
    capital_preservation_score: float  # 0.0 - 100.0
    circuit_breaker_tripped: bool
    ruin_event: bool
    pnl_impact_inr: float
    survival_rating: str  # AAA, AA, A, B, FAILED


def simulate_crisis_impact(
    scenario_id: str,
    portfolio_equity: float,
    strategy_beta: float = 0.85,
    stop_loss_efficiency: float = 0.80,
) -> StressSimulationResult:
    """
    Simulate portfolio performance under the specified historical market crisis shock.
    """
    scenario = CRISIS_CATALOG.get(scenario_id, CRISIS_CATALOG["COVID_2020"])

    # Effective portfolio shock factoring in strategy beta and defensive stop loss coverage
    unmitigated_drop = abs(scenario.index_drop_pct) * strategy_beta
    mitigated_drop = unmitigated_drop * (1.0 - (0.55 * stop_loss_efficiency))

    sim_dd = min(100.0, mitigated_drop)
    pnl_loss = portfolio_equity * (sim_dd / 100.0)

    # Scoring: 100 - (2 * DD)
    score = max(0.0, min(100.0, 100.0 - (1.8 * sim_dd)))
    cb_tripped = sim_dd >= 15.0
    ruin = sim_dd >= 40.0

    if score >= 85:
        rating = "AAA"
    elif score >= 70:
        rating = "AA"
    elif score >= 55:
        rating = "A"
    elif score >= 40:
        rating = "B"
    else:
        rating = "FAILED"

    return StressSimulationResult(
        scenario_id=scenario.id,
        scenario_name=scenario.name,
        simulated_max_drawdown_pct=round(sim_dd, 2),
        capital_preservation_score=round(score, 1),
        circuit_breaker_tripped=cb_tripped,
        ruin_event=ruin,
        pnl_impact_inr=round(-pnl_loss, 2),
        survival_rating=rating,
    )
