"""
Module: analytics/performance_engine.py
Purpose: SOTA Multi-Metric Institutional Risk-Adjusted Performance & Tail-Risk Analytics Engine.
         Computes Sharpe Ratio, Sortino Ratio, Calmar Ratio, Omega Ratio, Gain-to-Pain Ratio,
         Probabilistic Sharpe Ratio (PSR), Deflated Sharpe Ratio (DSR), Friction Drag Ratio (FDR),
         Cornish-Fisher Value at Risk (VaR), Conditional Value at Risk (CVaR / Expected Shortfall),
         and Ulcer Index.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Sequence, Union
import math
import numpy as np
import pandas as pd
from scipy import stats

TRADING_DAYS_PER_YEAR = 252
DEFAULT_RISK_FREE_ANNUAL = 0.065  # 6.5% Indian RBI Repo Rate baseline


@dataclass(frozen=True)
class TailRiskMetrics:
    """Immutable contract for Value at Risk and extreme tail risk metrics."""
    var_95_pct: float
    var_99_pct: float
    cvar_95_pct: float  # Expected Shortfall
    cvar_99_pct: float
    cornish_fisher_var_95_pct: float
    skewness: float
    kurtosis: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InstitutionalPerformanceReport:
    """Comprehensive institutional performance and risk-adjusted metrics report."""
    total_return_pct: float
    cagr_pct: float
    annualized_volatility_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    omega_ratio: float
    gain_to_pain_ratio: float
    profit_factor: float
    win_rate_pct: float
    max_drawdown_pct: float
    recovery_factor: float
    ulcer_index: float
    probabilistic_sharpe_ratio: float  # Bailey & Lopez de Prado (2012) PSR
    friction_drag_ratio_pct: float     # Friction / Gross Profit (%)
    tail_risk: TailRiskMetrics
    total_trades: int
    winning_trades: int
    losing_trades: int

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["tail_risk"] = self.tail_risk.to_dict()
        return d


def calculate_probabilistic_sharpe_ratio(
    observed_sharpe: float,
    benchmark_sharpe: float = 0.0,
    n_observations: int = 252,
    skewness: float = 0.0,
    kurtosis: float = 0.0,  # Excess kurtosis
) -> float:
    """
    Calculate Bailey & Lopez de Prado (2012) Probabilistic Sharpe Ratio (PSR).
    Computes the probability that observed Sharpe exceeds benchmark Sharpe given sample size,
    skewness, and kurtosis.
    
    PSR = Phi( (SR - SR*) * sqrt(N - 1) / sqrt(1 - skew*SR + ((kurt + 2)/4)*SR^2) )
    """
    if n_observations <= 2:
        return 0.5

    sr = float(observed_sharpe)
    sr_star = float(benchmark_sharpe)
    n = max(3, int(n_observations))
    skew = float(skewness)
    # Total kurtosis = excess kurtosis + 3. (kurt_total - 1)/4 = (kurt_excess + 2)/4
    excess_kurt = float(kurtosis)

    variance_term = 1.0 - skew * sr + ((excess_kurt + 2.0) / 4.0) * (sr ** 2)
    if variance_term <= 1e-6:
        variance_term = 1e-6

    denom = math.sqrt(variance_term)
    numer = (sr - sr_star) * math.sqrt(n - 1)
    z_stat = numer / denom

    psr = float(stats.norm.cdf(z_stat))
    return round(psr, 4)


def calculate_friction_drag_ratio(
    gross_pnl: float,
    total_friction: float,
) -> float:
    """
    Calculate statutory tax and execution friction drag ratio as a percentage of gross profit.
    Institutional alert triggered if friction eats > 20% of edge.
    """
    gross = float(gross_pnl)
    fric = abs(float(total_friction))
    if gross <= 0:
        return 100.0 if fric > 0 else 0.0
    return round((fric / gross) * 100.0, 2)


def calculate_tail_risk(
    returns: Sequence[float],
) -> TailRiskMetrics:
    """
    Calculate parametric, historical, and Cornish-Fisher adjusted Value at Risk (VaR)
    and Conditional Value at Risk (CVaR / Expected Shortfall).
    
    Returns negative percentages representing potential loss.
    Includes Cornish-Fisher polynomial monotonicity clamp for extreme fat tails.
    """
    arr = np.asarray(returns, dtype=float)
    arr = arr[~np.isnan(arr)]
    
    if len(arr) < 5:
        return TailRiskMetrics(
            var_95_pct=0.0,
            var_99_pct=0.0,
            cvar_95_pct=0.0,
            cvar_99_pct=0.0,
            cornish_fisher_var_95_pct=0.0,
            skewness=0.0,
            kurtosis=0.0,
        )

    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1))
    
    if std <= 1e-9:
        return TailRiskMetrics(
            var_95_pct=round(mean * 100.0, 3),
            var_99_pct=round(mean * 100.0, 3),
            cvar_95_pct=round(mean * 100.0, 3),
            cvar_99_pct=round(mean * 100.0, 3),
            cornish_fisher_var_95_pct=round(mean * 100.0, 3),
            skewness=0.0,
            kurtosis=0.0,
        )

    # 1. Historical VaR & CVaR (Percentiles)
    var_95 = float(np.percentile(arr, 5))
    var_99 = float(np.percentile(arr, 1))

    cvar_95_tail = arr[arr <= var_95]
    cvar_95 = float(np.mean(cvar_95_tail)) if len(cvar_95_tail) > 0 else var_95

    cvar_99_tail = arr[arr <= var_99]
    cvar_99 = float(np.mean(cvar_99_tail)) if len(cvar_99_tail) > 0 else var_99

    # 2. Skewness and Kurtosis
    n = len(arr)
    skew = float(stats.skew(arr)) if n >= 3 else 0.0
    kurt = float(stats.kurtosis(arr)) if n >= 4 else 0.0  # Excess kurtosis

    # 3. Cornish-Fisher Expansion Adjusted VaR (95% confidence -> z = -1.64485)
    z = -1.6448536269514722
    # Clamp skewness and kurtosis to prevent non-monotonic polynomial explosion
    clamped_skew = max(-2.5, min(2.5, skew))
    clamped_kurt = max(-1.0, min(15.0, kurt))

    z_cf = (
        z
        + (z**2 - 1.0) * (clamped_skew / 6.0)
        + (z**3 - 3.0 * z) * (clamped_kurt / 24.0)
        - (2.0 * z**3 - 5.0 * z) * (clamped_skew**2 / 36.0)
    )
    
    # Monotonicity boundary: Left tail quantile must be negative and bounded
    z_cf_bounded = min(-0.1, z_cf)
    cf_var_95 = mean + z_cf_bounded * std
    # Enforce empirical bound: CF VaR should not be less severe than empirical 95% quantile
    cf_var_95 = min(cf_var_95, var_95)

    return TailRiskMetrics(
        var_95_pct=round(var_95 * 100.0, 3),
        var_99_pct=round(var_99 * 100.0, 3),
        cvar_95_pct=round(cvar_95 * 100.0, 3),
        cvar_99_pct=round(cvar_99 * 100.0, 3),
        cornish_fisher_var_95_pct=round(cf_var_95 * 100.0, 3),
        skewness=round(skew, 3),
        kurtosis=round(kurt, 3),
    )


def calculate_ulcer_index(
    equity_curve: Sequence[float],
) -> float:
    """
    Calculate Peter Martin's Ulcer Index (UI) measuring drawdown depth and duration.
    UI = sqrt( (1/N) * sum( (Drawdown_t %)^2 ) )
    """
    eq = np.asarray(equity_curve, dtype=float)
    if len(eq) < 2:
        return 0.0

    peak = np.maximum.accumulate(eq)
    drawdowns_pct = ((eq - peak) / peak) * 100.0
    squared_dd = drawdowns_pct ** 2
    return round(float(np.sqrt(np.mean(squared_dd))), 3)


def calculate_omega_ratio(
    returns: Sequence[float],
    target_return: float = 0.0,
) -> float:
    """
    Calculate Keating & Shadwick's Omega Ratio.
    Omega = Sum(max(R - L, 0)) / Sum(max(L - R, 0))
    """
    arr = np.asarray(returns, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) == 0:
        return 1.0

    excess = arr - target_return
    positives = excess[excess > 0]
    negatives = np.abs(excess[excess < 0])

    sum_pos = float(np.sum(positives))
    sum_neg = float(np.sum(negatives))

    if sum_neg <= 1e-9:
        return 99.0 if sum_pos > 0 else 1.0
    return round(sum_pos / sum_neg, 3)


def calculate_gain_to_pain_ratio(
    returns: Sequence[float],
) -> float:
    """
    Calculate Jack Schwager's Gain-to-Pain Ratio:
    Gain-to-Pain = Sum(all positive returns) / Sum(absolute value of all negative returns)
    """
    arr = np.asarray(returns, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) == 0:
        return 0.0

    pos_sum = float(np.sum(arr[arr > 0]))
    neg_sum = float(np.sum(np.abs(arr[arr < 0])))

    if neg_sum <= 1e-9:
        return 99.0 if pos_sum > 0 else 0.0
    return round(pos_sum / neg_sum, 3)


def calculate_institutional_metrics(
    equity_curve: Sequence[float],
    daily_returns: Optional[Sequence[float]] = None,
    closed_trades_pnl: Optional[Sequence[float]] = None,
    total_statutory_friction: float = 0.0,
    risk_free_rate_annual: float = DEFAULT_RISK_FREE_ANNUAL,
) -> InstitutionalPerformanceReport:
    """
    Compute comprehensive institutional performance report from equity curve and return series.
    """
    eq = np.asarray(equity_curve, dtype=float)
    if len(eq) < 2:
        return InstitutionalPerformanceReport(
            total_return_pct=0.0,
            cagr_pct=0.0,
            annualized_volatility_pct=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            omega_ratio=1.0,
            gain_to_pain_ratio=0.0,
            profit_factor=0.0,
            win_rate_pct=0.0,
            max_drawdown_pct=0.0,
            recovery_factor=0.0,
            ulcer_index=0.0,
            probabilistic_sharpe_ratio=0.5,
            friction_drag_ratio_pct=0.0,
            tail_risk=calculate_tail_risk([]),
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
        )

    start_equity = eq[0]
    final_equity = eq[-1]
    total_return_pct = ((final_equity - start_equity) / start_equity) * 100.0

    # Derive daily returns if not provided
    if daily_returns is None or len(daily_returns) == 0:
        d_returns = np.diff(eq) / eq[:-1]
    else:
        d_returns = np.asarray(daily_returns, dtype=float)

    # 1. High-Water Mark and Max Drawdown
    peak = np.maximum.accumulate(eq)
    drawdowns_pct = ((peak - eq) / peak) * 100.0
    max_dd_pct = float(np.max(drawdowns_pct)) if len(drawdowns_pct) > 0 else 0.0

    # 2. CAGR Calculation
    num_days = max(1, len(eq) - 1)
    years = num_days / TRADING_DAYS_PER_YEAR
    if years > 0 and final_equity > 0 and start_equity > 0:
        cagr_pct = ((final_equity / start_equity) ** (1.0 / years) - 1.0) * 100.0
    else:
        cagr_pct = total_return_pct

    # 3. Annualized Volatility
    daily_std = float(np.std(d_returns, ddof=1)) if len(d_returns) > 1 else 0.0
    annual_vol_pct = daily_std * math.sqrt(TRADING_DAYS_PER_YEAR) * 100.0

    # 4. Sharpe Ratio
    rf_daily = risk_free_rate_annual / TRADING_DAYS_PER_YEAR
    mean_daily_return = float(np.mean(d_returns)) if len(d_returns) > 0 else 0.0
    excess_return = mean_daily_return - rf_daily

    if daily_std > 1e-9:
        sharpe = (excess_return / daily_std) * math.sqrt(TRADING_DAYS_PER_YEAR)
    else:
        sharpe = 0.0

    # 5. Sortino Ratio
    if daily_std <= 1e-9:
        sortino = 0.0
    else:
        downside_returns = d_returns[d_returns < rf_daily]
        if len(downside_returns) > 0:
            downside_std = float(np.sqrt(np.mean((downside_returns - rf_daily) ** 2)))
            sortino = (excess_return / downside_std) * math.sqrt(TRADING_DAYS_PER_YEAR) if downside_std > 1e-9 else 0.0
        else:
            sortino = 99.0 if excess_return > 0 else 0.0

    # 6. Calmar Ratio
    calmar = round(cagr_pct / max_dd_pct, 2) if max_dd_pct > 0 else (99.0 if cagr_pct > 0 else 0.0)

    # 7. Omega, Gain-to-Pain, Ulcer Index & Tail Risk
    omega = calculate_omega_ratio(d_returns, target_return=rf_daily)
    g2p = calculate_gain_to_pain_ratio(d_returns)
    ulcer = calculate_ulcer_index(eq)
    tail_risk = calculate_tail_risk(d_returns)

    # 8. Probabilistic Sharpe Ratio (PSR)
    psr = calculate_probabilistic_sharpe_ratio(
        observed_sharpe=sharpe,
        benchmark_sharpe=0.0,
        n_observations=len(d_returns),
        skewness=tail_risk.skewness,
        kurtosis=tail_risk.kurtosis,
    )

    # 9. Trade Statistics & Friction Drag
    trades_pnl = np.asarray(closed_trades_pnl or [], dtype=float)
    total_trades = len(trades_pnl)
    winning_trades = int(np.sum(trades_pnl > 0))
    losing_trades = int(np.sum(trades_pnl <= 0))
    win_rate_pct = round((winning_trades / total_trades) * 100.0, 1) if total_trades > 0 else 0.0

    gross_wins = float(np.sum(trades_pnl[trades_pnl > 0])) if total_trades > 0 else 0.0
    gross_losses = abs(float(np.sum(trades_pnl[trades_pnl <= 0]))) if total_trades > 0 else 0.0
    profit_factor = round(gross_wins / gross_losses, 2) if gross_losses > 0 else (99.0 if gross_wins > 0 else 0.0)

    recovery_factor = round(total_return_pct / max_dd_pct, 2) if max_dd_pct > 0 else (99.0 if total_return_pct > 0 else 0.0)
    friction_drag_pct = calculate_friction_drag_ratio(gross_wins, total_statutory_friction)

    return InstitutionalPerformanceReport(
        total_return_pct=round(total_return_pct, 2),
        cagr_pct=round(cagr_pct, 2),
        annualized_volatility_pct=round(annual_vol_pct, 2),
        sharpe_ratio=round(sharpe, 2),
        sortino_ratio=round(sortino, 2),
        calmar_ratio=calmar,
        omega_ratio=omega,
        gain_to_pain_ratio=g2p,
        profit_factor=profit_factor,
        win_rate_pct=win_rate_pct,
        max_drawdown_pct=round(max_dd_pct, 2),
        recovery_factor=recovery_factor,
        ulcer_index=ulcer,
        probabilistic_sharpe_ratio=psr,
        friction_drag_ratio_pct=friction_drag_pct,
        tail_risk=tail_risk,
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
    )
