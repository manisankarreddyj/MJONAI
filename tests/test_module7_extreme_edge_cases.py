"""
Unit and Institutional Test Suite for Module 7 Extreme Edge Cases & Chaos Stress Testing.
Validates Performance Engine, Feedback Learning, and EOD Reconciler under extreme degenerate
data, catastrophic crash distributions, zero divisions, and broker break anomalies.
"""

import math
import numpy as np
import pytest

from mjonai.analytics.performance_engine import (
    calculate_tail_risk,
    calculate_ulcer_index,
    calculate_omega_ratio,
    calculate_gain_to_pain_ratio,
    calculate_probabilistic_sharpe_ratio,
    calculate_friction_drag_ratio,
    calculate_institutional_metrics,
)
from mjonai.analytics.feedback_learning import (
    calculate_brier_score,
    calculate_brier_skill_score,
    calculate_information_coefficient,
    recalibrate_agent_weights,
    evaluate_setup_hash_memory,
    detect_strategy_parameter_drift,
)


# ==============================================================================
# 1. PERFORMANCE ENGINE EXTREME EDGE CASES
# ==============================================================================

def test_m7_perf_engine_zero_volatility_flatline():
    """Torture test Performance Engine with a completely flat equity curve (zero volatility)."""
    flat_eq = [100000.0] * 50
    rep = calculate_institutional_metrics(
        equity_curve=flat_eq,
        closed_trades_pnl=[],
    )
    assert rep.annualized_volatility_pct == 0.0
    assert rep.sharpe_ratio == 0.0
    assert rep.sortino_ratio == 0.0
    assert rep.ulcer_index == 0.0
    assert rep.max_drawdown_pct == 0.0


def test_m7_perf_engine_100_percent_losses_vs_100_percent_wins():
    """Torture test Performance Engine with 100% losing trades vs 100% winning trades."""
    # 1. 100% Losses
    loss_pnl = [-500.0, -200.0, -1000.0, -300.0]
    loss_returns = [-0.01, -0.005, -0.02, -0.008]
    rep_loss = calculate_institutional_metrics(
        equity_curve=[100000.0, 99500.0, 99300.0, 98300.0, 98000.0],
        closed_trades_pnl=loss_pnl,
        daily_returns=loss_returns,
    )
    assert rep_loss.profit_factor == 0.0
    assert rep_loss.gain_to_pain_ratio == 0.0
    assert rep_loss.win_rate_pct == 0.0
    assert rep_loss.omega_ratio < 1.0

    # 2. 100% Wins (Zero Loss Denominator Division Protection)
    win_pnl = [500.0, 200.0, 1000.0, 300.0]
    win_returns = [0.01, 0.005, 0.02, 0.008]
    rep_win = calculate_institutional_metrics(
        equity_curve=[100000.0, 100500.0, 100700.0, 101700.0, 102000.0],
        closed_trades_pnl=win_pnl,
        daily_returns=win_returns,
    )
    assert rep_win.profit_factor == 99.0
    assert rep_win.gain_to_pain_ratio == 99.0
    assert rep_win.win_rate_pct == 100.0
    assert rep_win.sortino_ratio == 99.0
    assert rep_win.omega_ratio == 99.0


def test_m7_perf_engine_extreme_fat_tail_cornish_fisher_clamping():
    """Torture test Cornish-Fisher VaR with extreme black-swan skewness (-15.0) and kurtosis (120.0)."""
    np.random.seed(42)
    # Normal returns with a catastrophic -50% flash crash outlier
    rets = list(np.random.normal(0.001, 0.01, 100))
    rets.extend([-0.30, -0.40, -0.50])  # Extreme fat left tail

    tail = calculate_tail_risk(rets)
    # Monotonicity check: Cornish-Fisher VaR must NOT invert into a positive return
    assert tail.cornish_fisher_var_95_pct < 0.0
    assert tail.cornish_fisher_var_95_pct <= tail.var_95_pct


def test_m7_perf_engine_friction_drag_churn_edge():
    """Torture test Friction Drag Ratio on zero profits and extreme churn."""
    # Zero profit -> 100% drag
    assert calculate_friction_drag_ratio(gross_pnl=0.0, total_friction=500.0) == 100.0
    # Churning: Gross 1,000, Friction 400 -> 40% friction drag
    assert calculate_friction_drag_ratio(gross_pnl=1000.0, total_friction=400.0) == 40.0


# ==============================================================================
# 2. FEEDBACK LEARNING EXTREME EDGE CASES
# ==============================================================================

def test_m7_feedback_brier_out_of_bounds_and_empty():
    """Torture test Brier score on empty lists and out-of-bounds probabilities."""
    # Empty inputs
    assert calculate_brier_score([], []) == 0.25
    assert calculate_brier_skill_score(0.25) == 0.0

    # Wild probability inputs (e.g. -5.0 or 10.0) are clipped to [0, 1]
    bs_clipped = calculate_brier_score([-5.0, 10.0], [0, 1])
    assert bs_clipped == 0.0  # -5.0 clipped to 0 matches 0, 10.0 clipped to 1 matches 1


def test_m7_feedback_ic_constant_series_zero_variance():
    """Torture test Information Coefficient on flat constant forward returns."""
    forecasts = [0.8, 0.7, 0.6, 0.9, 0.4]
    flat_rets = [0.0, 0.0, 0.0, 0.0, 0.0]  # Zero variance!
    ic, t_stat = calculate_information_coefficient(forecasts, flat_rets)
    assert ic == 0.0
    assert t_stat == 0.0


def test_m7_feedback_agent_weight_recalibration_catastrophic_overconfidence():
    """Torture test Agent Weight Recalibration when an agent predicts 1.0 on 100% losing trades.

    Corrected contract (2026-10-14): the 0.50 cap plus only 2 agents forces
    (0.5, 0.5) — the old assertion pinned the cap-breaking bug. A third
    middling agent leaves room to discriminate while every weight honors
    the cap and the book sums to 1.0.
    """
    forecasts = {
        "AGENT_BLIND": [1.0] * 10,       # 100% wrong
        "AGENT_RELIABLE": [0.1] * 10,    # 100% right
        "AGENT_MID": [0.5] * 10,         # coin toss
    }
    outcomes = [0] * 10  # All losses

    scores = recalibrate_agent_weights(forecasts, outcomes)
    assert scores["AGENT_RELIABLE"].brier_score < scores["AGENT_BLIND"].brier_score
    assert scores["AGENT_RELIABLE"].updated_weight > scores["AGENT_MID"].updated_weight > scores["AGENT_BLIND"].updated_weight
    # Weight must not breach minimum floor, must respect the cap, must sum to 1
    assert scores["AGENT_BLIND"].updated_weight >= 0.05
    assert all(s.updated_weight <= 0.50 + 1e-9 for s in scores.values())
    assert abs(sum(s.updated_weight for s in scores.values()) - 1.0) < 0.01


def test_m7_feedback_setup_hash_insufficient_sample_tolerance():
    """Verify setup hash is NOT prematurely quarantined before N=10 sample threshold."""
    # 2 losses out of 2 trades: raw WR = 0%, but N=2 < 10 threshold -> NOT quarantined yet
    small_bad_sample = [{"net_pnl": -100.0}] * 2
    mem = evaluate_setup_hash_memory("hash_early", "S01", small_bad_sample)
    assert mem.is_quarantined is False
    assert mem.total_trades == 2
