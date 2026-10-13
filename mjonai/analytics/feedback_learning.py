"""
Module: analytics/feedback_learning.py
Purpose: SOTA Continuous Feedback Learning, Agent Calibration,
         Information Coefficient (IC) Analysis, Laplace Pattern Memory Self-Healing,
         and Strategy Parameter Drift Sentry.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple, Union, Sequence
import math
import numpy as np
from scipy import stats
import logging

logger = logging.getLogger(__name__)

DEFAULT_LEARNING_RATE_ETA = 1.5
MIN_AGENT_WEIGHT = 0.05
MAX_AGENT_WEIGHT = 0.50
MIN_TRADES_FOR_QUARANTINE = 10
QUARANTINE_WIN_RATE_THRESHOLD = 0.40

# Verdict vocabulary (kept identical to db.agents.evaluate_verdict_accuracy so
# the calibration direction and the accuracy scoreboard agree on what is bullish
# vs bearish). NEUTRAL/CAUTION/unrecognised -> no directional information.
BULLISH_VERDICTS = frozenset({"BUY", "STRONG_BUY", "APPROVE", "BULLISH"})
BEARISH_VERDICTS = frozenset({"SELL", "STRONG_SELL", "REJECT", "BEARISH", "HIGH_RISK", "VETO"})


def normalize_confidence_scale(values: Sequence[float]) -> np.ndarray:
    """Bring a list of agent confidences onto the probability scale [0, 1].

    LLM agents are prompted for an ``0-100`` confidence (and every writer stores
    that raw value), while hand-built/test vectors use ``0.0-1.0``. A whole-array
    decision (divide by 100 when every finite value lies in ``[0, 100]`` and at
    least one exceeds 1.0) is used rather than a per-value test, because a
    legitimate 1% confidence (``1``) in an otherwise percent-scale vector must not
    be read as certainty (``1.0``). Out-of-range inputs (``-5``, ``200``) are left
    for a plain ``[0, 1]`` clip. Non-finite entries survive as NaN so callers can
    decide how to treat absent data.
    """
    arr = np.asarray(values, dtype=float)
    if arr.size:
        finite = arr[np.isfinite(arr)]
        # Treat the vector as percent-scale only when it is plausibly 0-100:
        # every finite value inside [0, 100] and at least one above 1.0. Out-of-
        # range "wild" inputs (e.g. -5 / 200) are left for a plain [0,1] clip,
        # preserving the torture-test contract.
        if (finite.size and float(np.min(finite)) >= 0.0
                and 1.0 < float(np.max(finite)) <= 100.0):
            arr = arr / 100.0
    return np.clip(arr, 0.0, 1.0)


def verdict_to_probability(verdict: Any, probability: float) -> float:
    """Map an agent's directional verdict + confidence magnitude to P(trade WINS).

    A bullish verdict means the agent's confidence IS the win probability; a
    bearish verdict means high confidence predicts a LOSS (``1 - p``). Neutral or
    unrecognised verdicts carry no directional edge and return the uninformative
    prior 0.5. This is what makes Bear (and a rejecting Supervisor) calibrate on
    the correct side — previously every agent's raw confidence was scored as if it
    were already P(win), inverting Bear/REJECT skill.
    """
    try:
        p = float(probability)
    except (TypeError, ValueError):
        return 0.5
    if not math.isfinite(p):
        return 0.5
    p = min(1.0, max(0.0, p))
    v = str(verdict or "").strip().upper()
    if v in BULLISH_VERDICTS:
        return p
    if v in BEARISH_VERDICTS:
        return 1.0 - p
    return 0.5


@dataclass(frozen=True)
class AgentCalibrationScore:
    """Evaluation metrics for an individual AI specialist persona."""
    agent_name: str
    sample_size: int
    brier_score: float  # Lower is better (0.0 = perfect calibration, 1.0 = total error)
    brier_skill_score: float  # BSS = 1 - (BS / 0.25). >0 means beats uninformative coin toss
    accuracy_pct: float
    information_coefficient: float  # Spearman rank correlation vs forward returns
    ic_t_stat: float
    current_weight: float
    updated_weight: float


@dataclass(frozen=True)
class SetupHashMemoryStatus:
    """Status contract for a strategy setup hash pattern memory."""
    setup_hash: str
    strategy_id: str
    total_trades: int
    winning_trades: int
    raw_win_rate_pct: float
    laplace_win_rate_pct: float
    is_quarantined: bool
    reason: str


@dataclass(frozen=True)
class StrategyDriftReport:
    """Strategy performance decay and parameter drift alert contract."""
    strategy_id: str
    live_sample_size: int
    live_sharpe: float
    backtest_sharpe_baseline: float
    sharpe_drift_z_score: float
    is_decay_flagged: bool
    recommended_action: str  # "HEALTHY", "MONITOR", "RECALIBRATE_PARAMETERS", "HALT_STRATEGY"


def calculate_brier_score(
    forecast_probabilities: Sequence[float],
    realized_outcomes: Sequence[int],
) -> float:
    """
    Calculate Glenn Brier's Probability Calibration Score:
    BS = (1/N) * sum( (f_t - o_t)^2 )
    
    Range: [0.0, 1.0] where 0.0 is perfect prediction.
    """
    f = np.asarray(forecast_probabilities, dtype=float)
    o = np.asarray(realized_outcomes, dtype=float)
    
    if len(f) == 0 or len(f) != len(o):
        return 0.25  # Neutral default for empty sample

    # Accept either the raw 0-100 agent confidence or an already-normalised
    # probability. Whole-array scale detection prevents 0-100 values from being
    # clipped to 1.0 (which made every agent's Brier score identical).
    f_clipped = normalize_confidence_scale(f)
    o_binary = np.where(o > 0, 1.0, 0.0)

    squared_errors = (f_clipped - o_binary) ** 2
    return round(float(np.mean(squared_errors)), 4)


def calculate_brier_skill_score(
    brier_score: float,
    reference_brier: float = 0.25,
) -> float:
    """
    Calculate Brier Skill Score (BSS) relative to an uninformative 50/50 prior (BS_ref = 0.25).
    BSS = 1 - (BS / BS_ref)
    BSS > 0 denotes skill; BSS <= 0 denotes performance no better than chance.
    """
    bs = max(0.0, float(brier_score))
    ref = max(1e-6, float(reference_brier))
    return round(1.0 - (bs / ref), 4)


def calculate_information_coefficient(
    forecasts: Sequence[float],
    forward_returns: Sequence[float],
) -> Tuple[float, float]:
    """
    Calculate Spearman Rank Information Coefficient (IC) and its t-statistic:
    IC = SpearmanRankCorr(forecasts, forward_returns)
    t = IC * sqrt(N - 2) / sqrt(1 - IC^2)

    Honesty rule (2026-09-17): missing values are masked JOINTLY — a pair with
    a non-finite forecast OR non-finite forward return is dropped from BOTH
    arrays before the rank correlation, and N counts only the surviving pairs.
    Previously a None/NaN in either side leaked nan into spearmanr and was
    silently reported as IC=0.0 — a fabricated "no signal" on missing data.
    With masking, IC=0.0 now means a real zero correlation on real data, or
    an N < 5 sample (callers must floor on the returned pair count).
    """
    f_raw = np.asarray(forecasts, dtype=float)
    r_raw = np.asarray(forward_returns, dtype=float)
    n = min(len(f_raw), len(r_raw))
    f_cut, r_cut = f_raw[:n], r_raw[:n]

    # Joint mask: drop pairs where EITHER side is non-finite (absent/Nan/Inf).
    valid = np.isfinite(f_cut) & np.isfinite(r_cut)
    f, r = f_cut[valid], r_cut[valid]
    n = len(f)

    if n < 5:
        return 0.0, 0.0

    corr, _ = stats.spearmanr(f, r)
    if np.isnan(corr):
        return 0.0, 0.0

    ic = float(corr)
    # t-statistic calculation
    denom = max(1e-6, math.sqrt(max(0.0, 1.0 - ic ** 2)))
    t_stat = ic * math.sqrt(n - 2) / denom
    return round(ic, 4), round(t_stat, 2)


def newey_west_lag_length(n: int) -> int:
    """Newey & West (1994) automatic lag truncation: floor(4·(n/100)^(2/9)).

    Returns 0 for n < 2 (no autocorrelation to correct with a single point).
    """
    n = int(n)
    if n < 2:
        return 0
    return int(math.floor(4.0 * ((n / 100.0) ** (2.0 / 9.0))))


def newey_west_standard_error(
    values: Sequence[float],
    lags: Optional[int] = None,
) -> Optional[float]:
    """HAC standard error of the mean with a Bartlett kernel (Newey & West, 1987).

    Non-finite entries are dropped before estimation (honest masking, same
    contract as ``calculate_information_coefficient``). Returns None when
    fewer than 2 finite values survive or the long-run variance is not
    positive — a zero-variance series has no defined t-statistic, and a
    fabricated 0.0 SE would imply infinite significance.
    """
    xs = [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(float(v))]
    n = len(xs)
    if n < 2:
        return None
    mean = sum(xs) / n
    resid = [x - mean for x in xs]
    max_lag = newey_west_lag_length(n) if lags is None else max(0, int(lags))
    max_lag = min(max_lag, n - 1)
    gamma0 = sum(e * e for e in resid) / n
    long_run = gamma0
    for j in range(1, max_lag + 1):
        cov = sum(resid[i] * resid[i + j] for i in range(n - j)) / n
        long_run += 2.0 * (1.0 - j / (max_lag + 1)) * cov
    if not math.isfinite(long_run) or long_run <= 0.0:
        return None
    return round(math.sqrt(long_run / n), 6)


def newey_west_t_stat(
    values: Sequence[float],
    lags: Optional[int] = None,
) -> Optional[float]:
    """Newey-West autocorrelation-robust t-statistic of the mean.

    t = mean / HAC-SE. Returns None when the SE is undefined (thin sample,
    zero variance, or non-finite long-run variance) — never a fabricated 0.0.
    With lags=0 the kernel keeps only the contemporaneous term (no
    autocorrelation correction); note it normalises by n, not n-1, so it is
    close to — but not exactly — the classical IID t-statistic.
    """
    xs = [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(float(v))]
    if len(xs) < 2:
        return None
    se = newey_west_standard_error(xs, lags=lags)
    if se is None or se <= 0.0:
        return None
    mean = sum(xs) / len(xs)
    t = mean / se
    if not math.isfinite(t):
        return None
    return round(t, 2)


def recalibrate_agent_weights(
    agent_forecasts: Dict[str, Sequence[float]],
    realized_outcomes: Sequence[int],
    forward_returns: Optional[Sequence[float]] = None,
    current_weights: Optional[Dict[str, float]] = None,
    learning_rate_eta: float = DEFAULT_LEARNING_RATE_ETA,
) -> Dict[str, AgentCalibrationScore]:
    """
    Recalibrate multi-agent voting weights based on empirical Brier Calibration Scores and IC.
    Uses exponential loss weighting: w_{i, new} = w_{i, old} * exp(-eta * BrierScore_i).

    Each agent's forecasts are normalised to the probability scale first
    (``0-100`` raw confidences are divided by 100; ``0-1`` vectors pass through),
    so a percent-scale input can no longer collapse every Brier score to the same
    value. Forecasts must already be P(trade WINS) — agents that emit a directional
    verdict must be mapped by the caller (see ``verdict_to_probability``).
    """
    agents = list(agent_forecasts.keys())
    if not agents:
        return {}

    default_equal_weight = 1.0 / len(agents)
    curr_w = current_weights or {a: default_equal_weight for a in agents}
    
    outcomes = np.asarray(realized_outcomes, dtype=float)
    raw_updated_weights: Dict[str, float] = {}
    calibration_scores: Dict[str, AgentCalibrationScore] = {}

    for agent, f_list in agent_forecasts.items():
        f_arr = normalize_confidence_scale(f_list)
        n = min(len(f_arr), len(outcomes))
        
        if n == 0:
            bs = 0.25
            bss = 0.0
            acc = 50.0
            ic = 0.0
            t_stat = 0.0
        else:
            bs = calculate_brier_score(f_arr[:n], outcomes[:n])
            bss = calculate_brier_skill_score(bs)
            pred_bin = (f_arr[:n] >= 0.5).astype(int)
            out_bin = (outcomes[:n] > 0).astype(int)
            acc = round(float(np.mean(pred_bin == out_bin)) * 100.0, 1)

            if forward_returns is not None and len(forward_returns) >= n:
                ic, t_stat = calculate_information_coefficient(f_arr[:n], forward_returns[:n])
            else:
                ic, t_stat = 0.0, 0.0

        old_w = curr_w.get(agent, default_equal_weight)
        # Exponential update: lower Brier score -> higher weight multiplier
        decay_mult = math.exp(-learning_rate_eta * bs)
        unnormalized_w = old_w * decay_mult
        raw_updated_weights[agent] = max(MIN_AGENT_WEIGHT, min(MAX_AGENT_WEIGHT, unnormalized_w))

        calibration_scores[agent] = AgentCalibrationScore(
            agent_name=agent,
            sample_size=n,
            brier_score=bs,
            brier_skill_score=bss,
            accuracy_pct=acc,
            information_coefficient=ic,
            ic_t_stat=t_stat,
            current_weight=round(old_w, 4),
            updated_weight=0.0,
        )

    # Normalize weights so sum(weights) == 1.0
    total_w = sum(raw_updated_weights.values())
    final_scores: Dict[str, AgentCalibrationScore] = {}
    for agent, score in calibration_scores.items():
        norm_w = round(raw_updated_weights[agent] / total_w, 4)
        final_scores[agent] = AgentCalibrationScore(
            agent_name=score.agent_name,
            sample_size=score.sample_size,
            brier_score=score.brier_score,
            brier_skill_score=score.brier_skill_score,
            accuracy_pct=score.accuracy_pct,
            information_coefficient=score.information_coefficient,
            ic_t_stat=score.ic_t_stat,
            current_weight=score.current_weight,
            updated_weight=norm_w,
        )

    return final_scores


def evaluate_setup_hash_memory(
    setup_hash: str,
    strategy_id: str,
    trades: List[Dict[str, Any]],
) -> SetupHashMemoryStatus:
    """
    Evaluate pattern memory with Laplace Smoothing:
    Laplace Win Rate = (Wins + 1) / (Total + 2)
    
    Quarantines pattern if Total >= 10 trades and Laplace Win Rate < 40%.
    """
    total = len(trades)
    wins = sum(1 for t in trades if float(t.get("net_pnl") or t.get("pnl") or 0) > 0)
    
    raw_wr = round((wins / total) * 100.0, 1) if total > 0 else 0.0
    laplace_wr = round(((wins + 1.0) / (total + 2.0)) * 100.0, 1)

    is_quarantined = False
    reason = "Setup pattern within statistical tolerance"

    if total >= MIN_TRADES_FOR_QUARANTINE and (laplace_wr / 100.0) < QUARANTINE_WIN_RATE_THRESHOLD:
        is_quarantined = True
        reason = f"Quarantined: Laplace win-rate {laplace_wr}% below {QUARANTINE_WIN_RATE_THRESHOLD*100}% threshold across {total} trades"

    return SetupHashMemoryStatus(
        setup_hash=setup_hash,
        strategy_id=strategy_id,
        total_trades=total,
        winning_trades=wins,
        raw_win_rate_pct=raw_wr,
        laplace_win_rate_pct=laplace_wr,
        is_quarantined=is_quarantined,
        reason=reason,
    )


def detect_strategy_parameter_drift(
    strategy_id: str,
    live_returns: Sequence[float],
    backtest_sharpe_baseline: float,
    backtest_sample_length: int = 252,
) -> StrategyDriftReport:
    """
    Detect statistical parameter drift and alpha decay.
    Compares live rolling Sharpe against backtest expectation using Opdyke (2007) Sharpe standard error.
    """
    arr = np.asarray(live_returns, dtype=float)
    arr = arr[~np.isnan(arr)]
    n = len(arr)

    if n < 10:
        return StrategyDriftReport(
            strategy_id=strategy_id,
            live_sample_size=n,
            live_sharpe=0.0,
            backtest_sharpe_baseline=backtest_sharpe_baseline,
            sharpe_drift_z_score=0.0,
            is_decay_flagged=False,
            recommended_action="HEALTHY",
        )

    mean_ret = float(np.mean(arr))
    std_ret = float(np.std(arr, ddof=1))
    
    if std_ret <= 1e-9:
        live_sharpe = 0.0
    else:
        live_sharpe = (mean_ret / std_ret) * math.sqrt(252)

    # Standard error of Sharpe Ratio (Lo, 2002 / Opdyke, 2007)
    sharpe_se = math.sqrt((1.0 + 0.5 * (live_sharpe ** 2)) / n)
    z_score = round((live_sharpe - backtest_sharpe_baseline) / max(0.01, sharpe_se), 2)

    is_decay = False
    action = "HEALTHY"

    if z_score < -2.5:
        is_decay = True
        action = "HALT_STRATEGY"
    elif z_score < -1.75:
        is_decay = True
        action = "RECALIBRATE_PARAMETERS"
    elif z_score < -1.0:
        action = "MONITOR"

    return StrategyDriftReport(
        strategy_id=strategy_id,
        live_sample_size=n,
        live_sharpe=round(live_sharpe, 2),
        backtest_sharpe_baseline=round(backtest_sharpe_baseline, 2),
        sharpe_drift_z_score=z_score,
        is_decay_flagged=is_decay,
        recommended_action=action,
    )
