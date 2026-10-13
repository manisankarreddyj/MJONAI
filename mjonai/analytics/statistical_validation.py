"""
Module: analytics/statistical_validation.py
Purpose: Institutional statistical validation for quantitative strategies.
         - Deflated Sharpe Ratio (DSR): Adjusts for multiple testing / data mining bias.
           Two formulations, deliberately named apart -- `deflated_sharpe_ratio`
           returns a z-SCORE from a return series (the canonical walk-forward
           gate's form); `deflated_sharpe_pvalue` returns a p-VALUE from a
           precomputed Sharpe. Never interchangeable.
         - White's Reality Check (WRC): Bootstraps to verify strategy edge over benchmark.
         - Monte Carlo Reshuffling: Computes P95 Max Drawdown and terminal equity distribution.

This module is the SINGLE home of the Sharpe-validation family (DSR z-score,
DSR p-value, PSR, haircut Sharpe). A duplicate `deflated_sharpe_ratio` lived
in `strategy/registry/quant_math.py` until 2026-10-04 with a different
signature and a different return type; it was consolidated here.
"""

import math
import logging
from statistics import NormalDist
from typing import Dict, List, Any

from mjonai.research.backtest.engine import INITIAL_CAPITAL

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


def deflated_sharpe_pvalue(
    sharpe_ratio: float,
    num_trials: int,
    sample_length: int,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """
    Deflated Sharpe Ratio expressed as a p-VALUE (Bailey & López de Prado, 2014).

    Same null hypothesis as `deflated_sharpe_ratio` (which returns a z-SCORE),
    but computed in the p-value formulation: the caller supplies an already
    computed Sharpe and sample length instead of a return series, and gets back
    P(true Sharpe > 0) rather than a z-statistic.

    THE TWO ARE NOT INTERCHANGEABLE. `deflated_sharpe_ratio` returns an
    unbounded z-score (negative when the edge is inside the noise band);
    this returns a value in [0, 1]. They were previously two functions with the
    SAME name and DIFFERENT signatures and return types — one in this module
    and one in `strategy/registry/quant_math.py` — which is a trap: a caller
    swapping them silently reinterprets the result. Consolidated 2026-10-04
    into one home (this module) under distinct names. The canonical
    walk-forward gate (`apps/research/run_walk_forward.py`) uses the z-score.

    Args:
        sharpe_ratio: observed Sharpe ratio (same units as the null below).
        num_trials: number of independent configurations tested.
        sample_length: number of return observations behind the Sharpe.
        skewness: return skewness (0.0 = normal).
        kurtosis: return kurtosis (3.0 = normal).

    Returns:
        DSR p-value in [0, 1]. >= 0.95 is the conventional significance bar.
    """
    n = max(2, int(num_trials))
    t = max(10, int(sample_length))
    sr = float(sharpe_ratio)

    gamma = 0.5772156649015328606  # Euler-Mascheroni constant
    nd = NormalDist()
    # Expected maximum Sharpe under the null of zero true alpha.
    expected_max_sr = (1.0 - gamma) * nd.inv_cdf(1.0 - 1.0 / n) + gamma * nd.inv_cdf(
        1.0 - 1.0 / (n * math.e)
    )

    # Variance of the Sharpe ratio under non-normality.
    sr_var = (
        1.0 + 0.5 * (sr ** 2) - skewness * sr + ((kurtosis - 3.0) / 4.0) * (sr ** 2)
    ) / float(t)
    sr_std = math.sqrt(max(1e-8, sr_var))

    z = (sr - expected_max_sr) / sr_std
    return float(round(nd.cdf(z), 4))


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


def probability_of_backtest_overfit(
    is_matrix: List[List[float]],
    oos_matrix: List[List[float]],
) -> Dict[str, float]:
    """Probability of Backtest Overfit, PBO (Bailey et al., 2014/2016).

    Inputs are S×N matrices over S combinatorial (CSCV/CPCV) splits and N
    trials: ``is_matrix[s][n]`` = in-sample Sharpe of trial n on split s,
    ``oos_matrix[s][n]`` = the same trial's out-of-sample Sharpe. For each
    split, the IS-optimal trial's OOS rank (1 = worst … N = best) is mapped
    through logit(r) = ln(r / (1 - r)); PBO is the fraction of splits whose
    logit falls below zero (IS-best lands below the OOS median).

    PBO near 0 ⇒ the selection procedure generalises; near 0.5+ ⇒ the
    backtest is likely overfit. Rows with non-finite entries are dropped
    pair-wise; fewer than 2 usable splits returns pbo=1.0 (maximal doubt,
    never a fabricated clean bill).

    NOTE (wiring): the live CPCV engine (`run_cpcv`) retains only each
    fold's IS-best parameters, not the full trial×fold OOS matrix this
    needs — so PBO is computed from caller-supplied matrices, not inside
    the engine. Wiring the full grid×fold OOS evaluation into `run_cpcv`
    is a compute-heavy follow-up, not smuggled in here.
    """
    if len(is_matrix) != len(oos_matrix):
        raise ValueError("IS and OOS matrices must have the same split count")
    logits: List[float] = []
    usable_splits = 0
    trial_count = 0
    for is_row, oos_row in zip(is_matrix, oos_matrix):
        if len(is_row) != len(oos_row):
            raise ValueError("every split needs the same trial count in IS and OOS")
        if len(is_row) < 2:
            continue
        pairs = [
            (s, o) for s, o in zip(is_row, oos_row)
            if isinstance(s, (int, float)) and isinstance(o, (int, float))
            and math.isfinite(float(s)) and math.isfinite(float(o))
        ]
        if len(pairs) < 2:
            continue
        usable_splits += 1
        trial_count = len(pairs)
        is_vals = [p[0] for p in pairs]
        oos_vals = [p[1] for p in pairs]
        best = max(range(len(pairs)), key=lambda i: is_vals[i])
        # Rank of the IS-best among OOS values (average rank for ties).
        below = sum(1 for v in oos_vals if v < oos_vals[best])
        equal = sum(1 for v in oos_vals if v == oos_vals[best])
        rank = (below + equal / 2.0 + 0.5) / len(pairs)  # in (0, 1)
        rank = min(1.0 - 1e-9, max(1e-9, rank))
        logits.append(math.log(rank / (1.0 - rank)))
    if usable_splits < 2:
        return {"pbo": 1.0, "splits": usable_splits, "trials": trial_count, "mean_logit": 0.0}
    pbo = sum(1 for l in logits if l < 0.0) / usable_splits
    return {
        "pbo": float(round(pbo, 4)),
        "splits": usable_splits,
        "trials": trial_count,
        "mean_logit": float(round(sum(logits) / usable_splits, 4)),
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


def _clamp_p(value: float) -> float:
    """Clamp a p-value into [0, 1]; non-finite inputs become 1.0 (least significant)."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 1.0
    if not math.isfinite(f):
        return 1.0
    return min(1.0, max(0.0, f))


def bonferroni_adjusted(p_values: List[float]) -> List[float]:
    """Bonferroni family-wise correction: adj = min(1, p * m).

    Controls the probability of ANY false discovery; conservative when tests
    are correlated (which discovery-grid configs are). Values are rounded to
    4 decimals to match the DSR/WRC reporting precision.
    """
    ps = [_clamp_p(p) for p in p_values]
    m = len(ps)
    if m == 0:
        return []
    return [round(min(1.0, p * m), 4) for p in ps]


def benjamini_hochberg_adjusted(p_values: List[float]) -> List[float]:
    """Benjamini-Hochberg FDR step-up adjusted q-values (independent/PRDS tests).

    Sort p ascending, compute q_i = p_(i) * m / i, then enforce monotonicity
    from the largest rank downward (q_i = min(q_i, q_{i+1})). Returns values
    in the caller's original order, rounded to 4 decimals.
    """
    ps = [_clamp_p(p) for p in p_values]
    m = len(ps)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: ps[i])
    adjusted = [0.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        idx = order[rank - 1]
        q = ps[idx] * m / rank
        q = min(q, prev)
        prev = min(1.0, q)
        adjusted[idx] = round(min(1.0, q), 4)
    return adjusted


def benjamini_yekutieli_adjusted(p_values: List[float]) -> List[float]:
    """Benjamini-Yekutieli FDR adjustment (arbitrary dependence).

    Same step-up as BH but scaled by c(m) = sum_{i=1..m} 1/i, so it holds
    under any dependence structure — the honest choice for a discovery grid
    whose configs overlap heavily (e.g. nr4 vs nr7 on the same bars). Always
    >= the BH value for the same input; capped at 1.0.
    """
    ps = [_clamp_p(p) for p in p_values]
    m = len(ps)
    if m == 0:
        return []
    harmonic = sum(1.0 / i for i in range(1, m + 1))
    order = sorted(range(m), key=lambda i: ps[i])
    adjusted = [0.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        idx = order[rank - 1]
        q = ps[idx] * m * harmonic / rank
        q = min(q, prev)
        prev = min(1.0, q)
        adjusted[idx] = round(min(1.0, q), 4)
    return adjusted


def fdr_reject(
    p_values: List[float],
    alpha: float = 0.05,
    method: str = "bh",
) -> List[bool]:
    """FDR rejection mask at level ``alpha`` using an adjusted-p comparison.

    method: "bh" (default), "by", or "bonferroni". Unknown methods raise
    ValueError rather than silently falling back to a weaker bar.
    """
    a = float(alpha)
    if not (0.0 < a < 1.0):
        raise ValueError(f"alpha must be in (0, 1), got {alpha!r}")
    key = str(method).strip().lower()
    if key in ("bh", "benjamini-hochberg", "benjamini_hochberg"):
        adj = benjamini_hochberg_adjusted(p_values)
    elif key in ("by", "benjamini-yekutieli", "benjamini_yekutieli"):
        adj = benjamini_yekutieli_adjusted(p_values)
    elif key in ("bonferroni", "bonf"):
        adj = bonferroni_adjusted(p_values)
    else:
        raise ValueError(f"unknown FDR method {method!r} (expected 'bh', 'by', or 'bonferroni')")
    return [bool(q < a) for q in adj]


def apply_fdr_to_family(
    rows: List[Dict[str, Any]],
    p_key: str = "WRC_p",
    alpha: float = 0.05,
) -> List[Dict[str, Any]]:
    """Attach FDR-adjusted WRC p-values to one discovery family's verdict rows.

    Returns NEW dicts (the input rows are never mutated) with three added
    JSON-safe keys: ``WRC_p_bh``, ``WRC_p_by``, ``WRC_p_bonf``, plus
    ``fdr_bh_significant`` (BH rejection at ``alpha``). Missing/non-numeric
    p-values are treated as 1.0 (least significant) — an absent p-value is
    never presented as significant. This is DISCLOSURE, not a gate change:
    ``is_robust`` keeps its DSR/WRC definition; FDR tells the operator how
    the family's significance survives multiple-testing correction.
    """
    ps = []
    for r in rows:
        try:
            ps.append(float(r.get(p_key)))
        except (TypeError, ValueError):
            ps.append(float("nan"))
    bh = benjamini_hochberg_adjusted(ps)
    by_ = benjamini_yekutieli_adjusted(ps)
    bonf = bonferroni_adjusted(ps)
    rej = fdr_reject(ps, alpha=alpha, method="bh")
    out = []
    for r, q_bh, q_by, q_bonf, sig in zip(rows, bh, by_, bonf, rej):
        row = dict(r)
        row["WRC_p_bh"] = q_bh
        row["WRC_p_by"] = q_by
        row["WRC_p_bonf"] = q_bonf
        row["fdr_bh_significant"] = bool(sig)
        out.append(row)
    return out
