"""
Unit and Institutional Test Suite for analytics/feedback_learning.py
Validates Brier Score Probability Calibration, Multi-Agent Exponential Weight Updates,
Laplace Setup-Hash Memory & Quarantine, and Statistical Parameter Drift Detection.
"""

import math
import numpy as np
import pytest

from mjonai.analytics.feedback_learning import (
    calculate_brier_score,
    recalibrate_agent_weights,
    evaluate_setup_hash_memory,
    detect_strategy_parameter_drift,
    AgentCalibrationScore,
    SetupHashMemoryStatus,
    StrategyDriftReport,
)


def test_brier_score_calibration():
    """Verify Brier Score on perfect, uncalibrated, and totally wrong forecasts."""
    # 1. Perfect forecast: Predicted 1.0 on win (1) and 0.0 on loss (0) -> BS = 0.0
    perfect_f = [1.0, 0.0, 1.0, 0.0]
    perfect_o = [1, 0, 1, 0]
    assert calculate_brier_score(perfect_f, perfect_o) == 0.0

    # 2. Totally wrong forecast: Predicted 0.0 on win and 1.0 on loss -> BS = 1.0
    wrong_f = [0.0, 1.0, 0.0, 1.0]
    assert calculate_brier_score(wrong_f, perfect_o) == 1.0

    # 3. Uninformative / 50% coin toss -> BS = (0.5 - 1)^2 = 0.25
    coin_f = [0.5, 0.5, 0.5, 0.5]
    assert calculate_brier_score(coin_f, perfect_o) == 0.25


def test_recalibrate_agent_weights_exponential_updating():
    """Verify high-accuracy agent receives increased voting weight while poor agent decays."""
    forecasts = {
        "BULL": [0.9, 0.1, 0.85, 0.15],   # Highly calibrated
        "BEAR": [0.1, 0.9, 0.15, 0.85],   # Contrarian / poorly aligned on long wins
        "QUANT": [0.7, 0.3, 0.75, 0.25],  # Moderately calibrated
    }
    outcomes = [1, 0, 1, 0]  # Realized trade outcomes
    initial_weights = {"BULL": 0.3333, "BEAR": 0.3333, "QUANT": 0.3333}

    scores = recalibrate_agent_weights(
        agent_forecasts=forecasts,
        realized_outcomes=outcomes,
        current_weights=initial_weights,
    )

    assert "BULL" in scores
    assert "BEAR" in scores
    assert "QUANT" in scores

    # Bull has lower Brier score and higher accuracy -> Updated weight must increase
    assert scores["BULL"].brier_score < scores["BEAR"].brier_score
    assert scores["BULL"].updated_weight > scores["BEAR"].updated_weight
    # Sum of updated weights must normalize to 1.0
    total_w = sum(s.updated_weight for s in scores.values())
    assert math.isclose(total_w, 1.0, rel_tol=1e-3)


def test_setup_hash_laplace_memory_and_quarantine():
    """Verify Laplace smoothing and automatic quarantine on toxic setup pattern."""
    # Healthy setup: 8 wins out of 10 trades -> Laplace WR = (8+1)/(10+2) = 75%
    healthy_trades = [{"net_pnl": 100.0}] * 8 + [{"net_pnl": -50.0}] * 2
    mem_healthy = evaluate_setup_hash_memory("hash_abc123", "S01_MomentumRSI", healthy_trades)
    assert mem_healthy.is_quarantined is False
    assert mem_healthy.laplace_win_rate_pct == 75.0

    # Toxic setup: 2 wins out of 10 trades -> Laplace WR = (2+1)/(10+2) = 25% (<40% threshold)
    toxic_trades = [{"net_pnl": 100.0}] * 2 + [{"net_pnl": -50.0}] * 8
    mem_toxic = evaluate_setup_hash_memory("hash_bad999", "S02_MeanReversion", toxic_trades)
    assert mem_toxic.is_quarantined is True
    assert mem_toxic.laplace_win_rate_pct == 25.0
    assert "Quarantined" in mem_toxic.reason


def test_strategy_parameter_drift_detection():
    """Verify parameter drift sentry flags decaying alpha vs healthy performance."""
    # Healthy strategy: Live returns match backtest Sharpe baseline 2.0
    healthy_rets = [0.005, 0.003, 0.004, -0.001, 0.002] * 12  # Consistent ~1.8 Sharpe
    rep_healthy = detect_strategy_parameter_drift("S01_MomentumRSI", healthy_rets, backtest_sharpe_baseline=2.0)
    assert rep_healthy.is_decay_flagged is False
    assert rep_healthy.recommended_action in ("HEALTHY", "MONITOR")

    # Decaying strategy: Live returns collapse into negative Sharpe vs baseline 2.0
    decay_rets = [-0.005, -0.003, -0.004, 0.001, -0.002] * 12
    rep_decay = detect_strategy_parameter_drift("S04_BollingerSqueeze", decay_rets, backtest_sharpe_baseline=2.0)
    assert rep_decay.is_decay_flagged is True
    assert rep_decay.recommended_action in ("RECALIBRATE_PARAMETERS", "HALT_STRATEGY")
