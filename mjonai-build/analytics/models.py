from __future__ import annotations

from dataclasses import dataclass

from research.backtest.models import EquityCurve


@dataclass(slots=True)
class TradeStatistics:

    total_trades: int

    winning_trades: int

    losing_trades: int

    win_rate_pct: float

    average_return_pct: float

    average_win_pct: float

    average_loss_pct: float

    largest_win_pct: float

    largest_loss_pct: float

    profit_factor: float

    payoff_ratio: float

    expectancy: float

    consecutive_wins: int

    consecutive_losses: int


@dataclass(slots=True)
class EquityStatistics:

    initial_capital: float

    final_capital: float

    total_return_pct: float

    peak_equity: float

    max_drawdown_pct: float

    current_drawdown_pct: float

    equity_curve: EquityCurve


@dataclass(slots=True)
class PerformanceStatistics:

    cagr_pct: float

    annualized_return_pct: float

    sharpe_ratio: float

    sortino_ratio: float

    calmar_ratio: float

    recovery_factor: float

    mar_ratio: float


@dataclass(slots=True)
class PerformanceReport:

    trade: TradeStatistics

    equity: EquityStatistics

    performance: PerformanceStatistics