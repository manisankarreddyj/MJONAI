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
    normalize_confidence_scale,
    verdict_to_probability,
    newey_west_lag_length,
    newey_west_standard_error,
    newey_west_t_stat,
    fit_temperature,
    apply_temperature,
    expected_calibration_error,
    fit_abstention_threshold,
    AgentCalibrationScore,
    SetupHashMemoryStatus,
    StrategyDriftReport,
)


# ── TEMPERATURE SCALING + ECE + ABSTENTION (laya, clean-room) ────────────────

def test_temperature_softens_overconfidence():
    """Systematically overconfident probs (0.9 always, wins 60%) must fit
    T > 1 and the scaled probs must lower NLL vs raw."""
    probs = [0.9] * 30
    outcomes = [1] * 18 + [0] * 12
    t = fit_temperature(probs, outcomes)
    assert t > 1.0
    scaled = apply_temperature(probs, t)
    assert all(s < 0.9 for s in scaled)


def test_temperature_degenerate_input_returns_identity():
    assert fit_temperature([], []) == 1.0
    assert fit_temperature([0.7], [1]) == 1.0  # below min_n floor
    assert fit_temperature([0.8] * 12, [1] * 12) == 1.0  # zero outcome variance
    assert list(apply_temperature([0.2, 0.8], 1.0)) == [0.2, 0.8]
    assert list(apply_temperature([0.2, 0.8], -3.0)) == [0.2, 0.8]


def test_ece_perfect_and_worthless():
    perfect = expected_calibration_error([1.0, 0.0, 1.0, 0.0], [1, 0, 1, 0])
    assert perfect == 0.0
    bad = expected_calibration_error([0.9] * 10, [1, 0] * 5)
    assert bad > 0.3
    assert math.isnan(expected_calibration_error([], []))


def test_abstention_threshold_fits_target_error():
    """High-confidence wins + low-confidence coin flips: the fitted floor
    must sit above the noisy region with error within target."""
    confs = [0.95] * 8 + [0.55] * 8
    outcomes = [1] * 8 + [1, 0] * 4
    thresh = fit_abstention_threshold(confs, outcomes, target_error=0.35)
    assert thresh is not None
    assert thresh > 0.55
    assert fit_abstention_threshold([0.6] * 4, [1, 0, 1, 0]) is None  # below min_n
    assert fit_abstention_threshold(confs, outcomes, target_error=99.0) is None


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


def test_confidence_scale_normalization_and_direction_awareness():
    """Regression (2026-09-18): percent-scale confidences must not collapse to
    a single Brier score, and bearish verdicts must invert the win probability."""
    # Identical inputs on the 0-100 scale must behave exactly like 0-1.
    assert calculate_brier_score([100.0, 0.0, 100.0, 0.0], [1, 0, 1, 0]) == 0.0
    assert calculate_brier_score([0.0, 100.0, 0.0, 100.0], [1, 0, 1, 0]) == 1.0

    # Array-aware scale detection: one >1 value means the vector is percent-scale,
    # so a 1 in that same vector is 1% (not certainty).
    assert list(normalize_confidence_scale([100.0, 1.0, 0.0])) == [1.0, 0.01, 0.0]
    assert list(normalize_confidence_scale([0.9, 0.5, 0.0])) == [0.9, 0.5, 0.0]

    # Direction-aware mapping: bullish -> p, bearish -> 1-p, neutral -> 0.5.
    assert verdict_to_probability("BUY", 0.8) == 0.8
    assert verdict_to_probability("APPROVE", 0.8) == 0.8
    assert verdict_to_probability("VETO", 0.8) == pytest.approx(0.2)
    assert verdict_to_probability("REJECT", 0.8) == pytest.approx(0.2)
    assert verdict_to_probability("NEUTRAL", 0.8) == 0.5

    # The old bug: two differently-calibrated agents on the percent scale tied.
    scores = recalibrate_agent_weights(
        agent_forecasts={
            "GOOD": [90.0, 10.0, 85.0, 15.0],
            "BAD": [10.0, 90.0, 15.0, 85.0],
        },
        realized_outcomes=[1, 0, 1, 0],
    )
    assert scores["GOOD"].brier_score < scores["BAD"].brier_score
    assert scores["GOOD"].updated_weight > scores["BAD"].updated_weight


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


def test_newey_west_lag_length_automatic_rule():
    """Newey-West (1994) automatic lag: floor(4·(n/100)^(2/9))."""
    assert newey_west_lag_length(1) == 0
    assert newey_west_lag_length(10) == 2
    assert newey_west_lag_length(100) == 4
    assert newey_west_lag_length(1000) == 6


def test_newey_west_standard_error_honest_floors():
    """HAC SE is None on thin/degenerate samples — never a fabricated 0.0."""
    assert newey_west_standard_error([]) is None
    assert newey_west_standard_error([1.0]) is None
    assert newey_west_standard_error([2.0, 2.0, 2.0]) is None  # zero variance
    assert newey_west_standard_error([float("nan"), float("inf")]) is None
    se = newey_west_standard_error([1.0, 2.0, 3.0, 4.0, 5.0], lags=0)
    assert se is not None and se > 0.0


def test_newey_west_t_stat_penalises_autocorrelation():
    """A trending series must score LOWER under HAC than under lags=0.

    Positive autocorrelation inflates the long-run variance, so the NW
    t-statistic is the conservative one — the whole point of the hardening.
    """
    trending = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    t_iid = newey_west_t_stat(trending, lags=0)
    t_nw = newey_west_t_stat(trending)  # automatic lags=2 at n=8
    assert t_iid is not None and t_nw is not None
    assert t_nw < t_iid
    # Lags=0 on [1..5]: mean=3, sum e^2=10, var_mean=10/25=0.4, t=3/sqrt(0.4).
    assert newey_west_t_stat([1.0, 2.0, 3.0, 4.0, 5.0], lags=0) == pytest.approx(4.74, abs=0.01)
    assert newey_west_t_stat([1.0]) is None
    assert newey_west_t_stat([5.0, 5.0, 5.0]) is None
