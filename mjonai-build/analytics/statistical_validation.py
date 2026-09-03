"""
Module: analytics/statistical_validation.py
Purpose: Institutional statistical validation for quantitative strategies.
         - Deflated Sharpe Ratio (DSR): Adjusts for multiple testing / data mining bias.
         - White's Reality Check (WRC): Bootstraps to verify strategy edge over benchmark.
         - Monte Carlo Reshuffling: Computes P95 Max Drawdown and terminal equity distribution.
"""

import math
import logging
from statistics import NormalDist
from typing import Dict, List, Any

from research.backtest.engine import INITIAL_CAPITAL

logger = logging.getLogger(__name__)


def deflated_sharpe_ratio(
    returns: List[float],
    num_trials: int = 10,
) -> float:
    """
    Deflated Sharpe Ratio (Bailey & López de Prado, 2014), unit-consistent.

    G5 rewrite: the previous version computed sample variance on PERIOD
    returns but compared it against an ANNUALIZED Sharpe plus an ad-hoc
    '×0.1' scaled expected-max term — dimensionally inconsistent, so real
    edges scored negative and noise could pass. This version stays entirely
    on the per-period scale:

      sr      = mean/std of period returns
      V[SR]   = (1 − skew·sr + ((kurt−1)/4)·sr²) / (n − 1)
      SR0     = sqrt(V[SR]) · E[max of `num_trials` standard normals]
      DSR     = (sr − SR0) / sqrt(V[SR])

    DSR > 0 ⇒ observed Sharpe exceeds the expected maximum under the null
    after multiple-testing deflation.

    Args:
        returns: strategy period returns (daily bars, or trade-level as an
                 explicitly-labelled non-IID approximation)
        num_trials: number of independent configurations tested

    Returns:
        DSR z-score (float). 0.0 when there is not enough data.
    """
    n = len(returns)
    if n < 10:
        return 0.0

    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    std_dev = math.sqrt(variance)
    if std_dev <= 0:
        return 0.0

    sr = mean / std_dev  # per-period Sharpe — SAME units as V[SR] below

    skew = sum(((r - mean) / std_dev) ** 3 for r in returns) / n
    kurt = sum(((r - mean) / std_dev) ** 4 for r in returns) / n

    sr_var = (1.0 - skew * sr + ((kurt - 1.0) / 4.0) * (sr ** 2)) / max(1, n - 1)
    if sr_var <= 0:
        return 0.0
    sr_sd = math.sqrt(sr_var)

    # E[max] over N draws of a standard normal via extreme-value quantiles.
    trials = max(2, int(num_trials))
    gamma = 0.5772156649
    z1 = NormalDist().inv_cdf(1.0 - 1.0 / trials)
    z2 = NormalDist().inv_cdf(1.0 - 1.0 / (trials * math.e))
    expected_max_sr = sr_sd * ((1.0 - gamma) * z1 + gamma * z2)

    dsr = (sr - expected_max_sr) / sr_sd
    return float(round(dsr, 4))


def whites_reality_check(
    strategy_returns: List[float],
    benchmark_returns: List[float] = None,
    num_bootstrap: int = 1000
) -> Dict[str, float]:
    """
    White's Reality Check (White 2000) via stationary bootstrap.
    Tests null hypothesis: Strategy has no superior predictive ability over benchmark.
    
    Args:
        strategy_returns: List of strategy returns
        benchmark_returns: List of benchmark (e.g. Nifty 50) returns
        num_bootstrap: Number of bootstrap iterations
        
    Returns:
        dict with 'sharpe', 'p_value', 'is_significant'
    """
    import random
    n = len(strategy_returns)
    if n < 15:
        return {"sharpe": 0.0, "p_value": 1.0, "is_significant": False}
    
    if benchmark_returns is None or len(benchmark_returns) != n:
        benchmark_returns = [0.0] * n
        
    # Excess returns over benchmark
    excess = [s - b for s, b in zip(strategy_returns, benchmark_returns)]
    actual_mean = sum(excess) / n
    raw_std = math.sqrt(sum((x - actual_mean) ** 2 for x in excess) / (n - 1)) if n > 1 else 0.0
    actual_std = raw_std if raw_std > 0 else 1e-9  # zero-variance edge case
    actual_t_stat = (actual_mean / actual_std) * math.sqrt(n)
    
    # Bootstrap centered returns (under H0: mean = 0)
    centered = [x - actual_mean for x in excess]
    better_count = 0
    
    for _ in range(num_bootstrap):
        sample = [random.choice(centered) for _ in range(n)]
        b_mean = sum(sample) / n
        raw_b_std = math.sqrt(sum((x - b_mean) ** 2 for x in sample) / (n - 1)) if n > 1 else 0.0
        b_std = raw_b_std if raw_b_std > 0 else 1e-9
        b_t_stat = (b_mean / b_std) * math.sqrt(n)
        if b_t_stat >= actual_t_stat:
            better_count += 1
            
    p_value = better_count / num_bootstrap
    return {
        "sharpe": float(round((actual_mean / actual_std) * math.sqrt(252), 2)),
        "p_value": float(round(p_value, 4)),
        "is_significant": bool(p_value < 0.05)
    }


def monte_carlo_drawdown_simulation(
    trades_pnl: List[float],
    initial_capital: float = INITIAL_CAPITAL,
    num_simulations: int = 1000
) -> Dict[str, Any]:
    """
    Monte Carlo Reshuffling simulation.
    Randomly reshuffles trade sequences 1,000 times to determine robustness
    against bad trade sequence clusters (drawdown streaks).
    
    Args:
        trades_pnl: List of closed trade net PnLs (₹)
        initial_capital: Account starting capital
        num_simulations: Number of Monte Carlo iterations
        
    Returns:
        dict with median_max_dd_pct, p95_max_dd_pct, p99_max_dd_pct, prob_profit_pct
    """
    import random
    if len(trades_pnl) < 10:
        return {
            "median_max_dd_pct": 0.0,
            "p95_max_dd_pct": 0.0,
            "p99_max_dd_pct": 0.0,
            "prob_profit_pct": 0.0,
            "simulations": 0
        }
        
    max_drawdowns = []
    final_equities = []
    
    for _ in range(num_simulations):
        shuffled = list(trades_pnl)
        random.shuffle(shuffled)
        
        equity = initial_capital
        peak = equity
        max_dd = 0.0
        
        for pnl in shuffled:
            equity += pnl
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
                
        max_drawdowns.append(max_dd * 100.0)
        final_equities.append(equity)
        
    max_drawdowns.sort()
    final_equities.sort()
    
    p50_idx = int(num_simulations * 0.50)
    p95_idx = int(num_simulations * 0.95)
    p99_idx = int(num_simulations * 0.99)
    
    prob_profit = sum(1 for e in final_equities if e > initial_capital) / num_simulations
    
    return {
        "median_max_dd_pct": round(max_drawdowns[p50_idx], 2),
        "p95_max_dd_pct": round(max_drawdowns[p95_idx], 2),
        "p99_max_dd_pct": round(max_drawdowns[p99_idx], 2),
        "prob_profit_pct": round(prob_profit * 100.0, 1),
        "simulations": num_simulations
    }


def probabilistic_sharpe_ratio(
    returns: List[float],
    benchmark_sr: float = 0.0,
    annualization_factor: float = math.sqrt(252),
) -> float:
    """
    Probabilistic Sharpe Ratio (PSR) (López de Prado, 2012).
    Calculates the probability that the observed Sharpe Ratio exceeds benchmark_sr,
    accounting for non-normality (skewness and kurtosis).

    Returns:
        float: Probability in [0.0, 1.0] that True SR > benchmark_sr.
    """
    n = len(returns)
    if n < 10:
        return 0.0

    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    std_dev = math.sqrt(variance)
    if std_dev <= 0:
        return 0.0

    sr = (mean / std_dev) * annualization_factor
    benchmark = benchmark_sr

    skew = sum(((r - mean) / std_dev) ** 3 for r in returns) / n
    kurt = sum(((r - mean) / std_dev) ** 4 for r in returns) / n

    # Variance of the sample Sharpe ratio estimator
    sr_var = (1.0 - skew * sr + ((kurt - 1.0) / 4.0) * (sr ** 2)) / max(1, n - 1)
    if sr_var <= 0:
        return 0.0

    sr_sd = math.sqrt(sr_var)
    z_score = (sr - benchmark) / sr_sd

    # Cumulative standard normal distribution
    psr = NormalDist().cdf(z_score)
    return float(round(psr, 4))


def haircut_sharpe_ratio(
    observed_sr: float,
    num_trials: int = 20,
    sample_years: float = 5.0,
) -> Dict[str, float]:
    """
    Harvey-Liu Haircut Sharpe Ratio (Harvey & Liu, 2015).
    Discounts observed backtest Sharpe ratios for multiple-testing factor discovery bias.

    Returns:
        dict: {'haircut_sr': float, 'discount_pct': float, 'is_acceptable': bool}
    """
    if observed_sr <= 0:
        return {"haircut_sr": 0.0, "discount_pct": 100.0, "is_acceptable": False}

    trials = max(1, int(num_trials))
    if trials == 1:
        return {"haircut_sr": observed_sr, "discount_pct": 0.0, "is_acceptable": True}

    # Bonferroni/Harvey-Liu asymptotic haircut penalty
    penalty = math.sqrt(2.0 * math.log(trials) / max(1.0, sample_years))
    haircut_sr = max(0.0, observed_sr - (0.45 * penalty))
    discount_pct = ((observed_sr - haircut_sr) / observed_sr) * 100.0 if observed_sr > 0 else 0.0

    return {
        "haircut_sr": float(round(haircut_sr, 2)),
        "discount_pct": float(round(discount_pct, 1)),
        "is_acceptable": bool(haircut_sr >= 1.0),
    }


def stationary_block_bootstrap(
    data: List[float],
    avg_block_size: int = 10,
    num_samples: int = 1000,
) -> List[List[float]]:
    """
    Stationary Block Bootstrap (Politis & Romano, 1994).
    Preserves autocorrelation and volatility clustering by sampling blocks
    of geometric random length with mean `avg_block_size`.
    """
    import random
    n = len(data)
    if n == 0:
        return []

    p = 1.0 / max(1, avg_block_size)
    bootstrap_series: List[List[float]] = []

    for _ in range(num_samples):
        resampled = []
        current_idx = random.randint(0, n - 1)
        while len(resampled) < n:
            resampled.append(data[current_idx])
            # With probability p, start a new block at random; else increment index wrapping around
            if random.random() < p:
                current_idx = random.randint(0, n - 1)
            else:
                current_idx = (current_idx + 1) % n
        bootstrap_series.append(resampled)

    return bootstrap_series
