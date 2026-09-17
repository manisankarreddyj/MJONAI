"""
Module: app/routes/research.py
Purpose: FastAPI REST endpoints for the MJONAI Research Lab,
         Walk-Forward Optimization, ML Meta-Labeling, and Crisis Stress Testing.
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from apps.web.auth import verify_api_token
from mjonai.research.stress_testing.crisis_replay import CRISIS_CATALOG, simulate_crisis_impact
from mjonai.research.stress_testing.monte_carlo import run_monte_carlo_simulation
from mjonai.analytics.statistical_validation import deflated_sharpe_ratio, probabilistic_sharpe_ratio, haircut_sharpe_ratio

router = APIRouter(
    prefix="/api/research",
    tags=["Research Lab"],
    dependencies=[Depends(verify_api_token)],
)


class CrisisSimulationRequest(BaseModel):
    scenario_id: str = Field(default="COVID_2020", description="Crisis identifier (COVID_2020, GFC_2008, DEMONETIZATION_2016, ELECTION_FLASH_2024)")
    portfolio_equity: float = Field(default=1_000_000.0, ge=1000.0)
    strategy_beta: float = Field(default=0.85, ge=0.0, le=3.0)
    stop_loss_efficiency: float = Field(default=0.80, ge=0.0, le=1.0)


class MonteCarloRequest(BaseModel):
    trades_pnl: List[float] = Field(..., min_length=1)
    initial_capital: float = Field(default=1_000_000.0, ge=1000.0)
    iterations: int = Field(default=2000, ge=100, le=10000)


class StatValidationRequest(BaseModel):
    returns: List[float] = Field(..., min_length=5)
    benchmark_sr: float = Field(default=0.0)
    num_trials: int = Field(default=20, ge=1)


@router.get("/status")
def get_research_status() -> Dict[str, Any]:
    """Return status of the research engine, available models, and crisis catalog."""
    return {
        "status": "ONLINE",
        "engine": "MJONAI Walk-Forward Research Engine v2.0",
        "supported_timeframes": ["1d", "15m", "5m", "1m"],
        "available_crises": list(CRISIS_CATALOG.keys()),
        "features_available": [
            "Combinatorial Purged Cross-Validation (CPCV)",
            "Triple-Barrier Meta-Labeling",
            "Fractional Differentiation (FracDiff)",
            "Deflated & Haircut Sharpe Ratios",
            "10,000-run Monte Carlo VaR",
        ],
    }


@router.get("/crises")
def list_crisis_scenarios() -> Dict[str, Any]:
    """List all supported historical market stress scenarios."""
    scenarios = []
    for s in CRISIS_CATALOG.values():
        scenarios.append({
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "start_date": s.start_date.strftime("%Y-%m-%d"),
            "end_date": s.end_date.strftime("%Y-%m-%d"),
            "index_drop_pct": s.index_drop_pct,
            "volatility_spike_pct": s.volatility_spike_pct,
            "key_drivers": s.key_drivers,
        })
    return {"count": len(scenarios), "scenarios": scenarios}


@router.post("/simulate-crisis")
def simulate_crisis(req: CrisisSimulationRequest) -> Dict[str, Any]:
    """Simulate the impact of a historical crisis shock on portfolio equity."""
    if req.scenario_id not in CRISIS_CATALOG:
        raise HTTPException(status_code=404, detail=f"Crisis scenario '{req.scenario_id}' not found.")

    res = simulate_crisis_impact(
        scenario_id=req.scenario_id,
        portfolio_equity=req.portfolio_equity,
        strategy_beta=req.strategy_beta,
        stop_loss_efficiency=req.stop_loss_efficiency,
    )
    return {
        "scenario_id": res.scenario_id,
        "scenario_name": res.scenario_name,
        "simulated_max_drawdown_pct": res.simulated_max_drawdown_pct,
        "capital_preservation_score": res.capital_preservation_score,
        "circuit_breaker_tripped": res.circuit_breaker_tripped,
        "ruin_event": res.ruin_event,
        "pnl_impact_inr": res.pnl_impact_inr,
        "survival_rating": res.survival_rating,
    }


@router.post("/monte-carlo")
def run_monte_carlo(req: MonteCarloRequest) -> Dict[str, Any]:
    """Execute Monte Carlo permutation on closed trade PnLs to derive empirical VaR and ruin risk."""
    res = run_monte_carlo_simulation(
        trades_pnl=req.trades_pnl,
        initial_capital=req.initial_capital,
        iterations=req.iterations,
    )
    return {
        "iterations": res.iterations,
        "initial_capital": res.initial_capital,
        "median_ending_equity": res.median_ending_equity,
        "p05_ending_equity": res.p05_ending_equity,
        "p95_ending_equity": res.p95_ending_equity,
        "median_max_drawdown_pct": res.median_max_drawdown_pct,
        "p95_max_drawdown_pct": res.p95_max_drawdown_pct,
        "p99_max_drawdown_pct": res.p99_max_drawdown_pct,
        "empirical_var_95_inr": res.empirical_var_95_inr,
        "empirical_var_99_inr": res.empirical_var_99_inr,
        "ruin_probability_pct": res.ruin_probability_pct,
        "profit_probability_pct": res.profit_probability_pct,
    }


@router.post("/validate-statistics")
def validate_statistics(req: StatValidationRequest) -> Dict[str, Any]:
    """Calculate institutional DSR, PSR, and Haircut Sharpe ratio for multiple-testing bias."""
    dsr = deflated_sharpe_ratio(req.returns, num_trials=req.num_trials)
    psr = probabilistic_sharpe_ratio(req.returns, benchmark_sr=req.benchmark_sr)
    
    # Compute base observed Sharpe for haircut
    import numpy as np
    import math
    n = len(req.returns)
    mean = sum(req.returns) / n
    variance = sum((r - mean) ** 2 for r in req.returns) / (n - 1)
    std = math.sqrt(variance) if variance > 0 else 1e-9
    observed_sr = (mean / std) * math.sqrt(252)

    haircut = haircut_sharpe_ratio(observed_sr=observed_sr, num_trials=req.num_trials)

    return {
        "observed_sharpe": round(observed_sr, 2),
        "deflated_sharpe_z": dsr,
        "probabilistic_sharpe_ratio": psr,
        "haircut_sharpe": haircut["haircut_sr"],
        "multiple_testing_discount_pct": haircut["discount_pct"],
        "is_statistically_significant": bool(dsr > 0.0 and psr > 0.95),
    }
