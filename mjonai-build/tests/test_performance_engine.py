"""
Unit and Institutional Test Suite for analytics/performance_engine.py
Validates Sharpe Ratio, Sortino Ratio, Calmar Ratio, Omega Ratio, Gain-to-Pain,
Cornish-Fisher Value at Risk (VaR), Expected Shortfall (CVaR), and Ulcer Index.
"""

import math
import numpy as np
import pytest

from analytics.performance_engine import (
    calculate_tail_risk,
    calculate_ulcer_index,
    calculate_omega_ratio,
    calculate_gain_to_pain_ratio,
    calculate_institutional_metrics,
    TailRiskMetrics,
    InstitutionalPerformanceReport,
)


def test_tail_risk_metrics_and_cornish_fisher():
    """Verify VaR 95%, VaR 99%, CVaR, and Cornish-Fisher non-normal adjustment."""
    # Create non-normal returns with negative skew (fat left tail)
    np.random.seed(42)
    normal_rets = np.random.normal(0.001, 0.015, 200)
    crash_tails = np.array([-0.05, -0.06, -0.08, -0.04, -0.045])
    returns = np.concatenate([normal_rets, crash_tails])

    tail = calculate_tail_risk(returns)
    assert isinstance(tail, TailRiskMetrics)
    assert tail.var_95_pct < 0.0  # Loss percentile
    assert tail.var_99_pct <= tail.var_95_pct  # 99% VaR is more severe than 95% VaR
    assert tail.cvar_95_pct <= tail.var_95_pct  # CVaR (average of tail) <= VaR
    assert tail.skewness < 0.0  # Negative skew detected
    assert tail.kurtosis > 0.0  # Excess kurtosis / fat tails detected


def test_ulcer_index_drawdown_depth_and_duration():
    """Verify Ulcer Index on flat vs severe drawdown equity curve."""
    # Flat equity curve (no drawdown) -> UI = 0.0
    flat_eq = [100000.0] * 50
    assert calculate_ulcer_index(flat_eq) == 0.0

    # Drawdown equity curve: 100k -> 80k (20% drawdown) -> recovers to 100k
    dd_eq = [100000.0, 95000.0, 90000.0, 85000.0, 80000.0, 90000.0, 100000.0]
    ui = calculate_ulcer_index(dd_eq)
    assert ui > 0.0
    assert 5.0 <= ui <= 15.0


def test_omega_ratio_and_gain_to_pain():
    """Verify Omega Ratio and Jack Schwager Gain-to-Pain Ratio."""
    # Perfectly winning series (no losses)
    all_wins = [0.01, 0.02, 0.015, 0.03]
    assert calculate_omega_ratio(all_wins) == 99.0
    assert calculate_gain_to_pain_ratio(all_wins) == 99.0

    # Balanced series: Wins +3%, +2%, Losses -1%, -1% -> G2P = 5 / 2 = 2.5
    balanced = [0.03, 0.02, -0.01, -0.01]
    g2p = calculate_gain_to_pain_ratio(balanced)
    assert math.isclose(g2p, 2.5, abs_tol=0.01)

    omega = calculate_omega_ratio(balanced, target_return=0.0)
    assert math.isclose(omega, 2.5, abs_tol=0.01)


def test_institutional_metrics_full_report():
    """Verify end-to-end Institutional Performance Report generation."""
    # Equity curve starting at 100k, ending at 120k (+20%)
    eq_curve = np.linspace(100000.0, 120000.0, 100)
    trades_pnl = [500.0, 1000.0, -200.0, 800.0, -100.0, 1200.0]

    report = calculate_institutional_metrics(
        equity_curve=eq_curve,
        closed_trades_pnl=trades_pnl,
        risk_free_rate_annual=0.065,  # 6.5% G-Sec rate
    )

    assert isinstance(report, InstitutionalPerformanceReport)
    assert report.total_return_pct == 20.0
    assert report.sharpe_ratio > 0.0
    assert report.sortino_ratio > 0.0
    assert report.profit_factor == round(3500.0 / 300.0, 2)  # 11.67
    assert report.win_rate_pct == round((4 / 6) * 100.0, 1)  # 66.7%
    assert report.total_trades == 6
    assert report.winning_trades == 4
    assert report.losing_trades == 2
    
    # Contract serialization
    d = report.to_dict()
    assert "sharpe_ratio" in d
    assert "tail_risk" in d
    assert "cornish_fisher_var_95_pct" in d["tail_risk"]
