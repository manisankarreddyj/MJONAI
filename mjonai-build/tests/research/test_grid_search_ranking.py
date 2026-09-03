"""Optimization ranking: risk-adjusted objective with a
minimum-trades gate on selection."""

from analytics.models import (
    EquityStatistics,
    PerformanceReport,
    PerformanceStatistics,
    TradeStatistics,
)
from research.backtest.models import EquityCurve
from research.optimization.grid_search import GridSearchOptimizer
from research.optimization.models import (
    OptimizationResult,
    ParameterSet,
)


def make_report(*, sharpe, profit_factor, total_return, total_trades):
    trade = TradeStatistics(
        total_trades=total_trades, winning_trades=0, losing_trades=0,
        win_rate_pct=0.0, average_return_pct=0.0, average_win_pct=0.0,
        average_loss_pct=0.0, largest_win_pct=0.0, largest_loss_pct=0.0,
        profit_factor=profit_factor, payoff_ratio=0.0, expectancy=0.0,
        consecutive_wins=0, consecutive_losses=0,
    )

    equity = EquityStatistics(
        initial_capital=100_000.0, final_capital=110_000.0,
        total_return_pct=total_return, peak_equity=110_000.0,
        max_drawdown_pct=5.0, current_drawdown_pct=0.0,
        equity_curve=EquityCurve(points=[]),
    )

    performance = PerformanceStatistics(
        cagr_pct=0.0, annualized_return_pct=0.0, sharpe_ratio=sharpe,
        sortino_ratio=0.0, calmar_ratio=0.0, recovery_factor=0.0,
        mar_ratio=0.0,
    )

    return PerformanceReport(
        trade=trade, equity=equity, performance=performance,
    )


def make_result(*, sharpe, profit_factor=1.5, total_return=10.0, total_trades=50):
    return OptimizationResult(
        strategy="S",
        symbol="SYM",
        parameters=ParameterSet(values={}),
        report=make_report(
            sharpe=sharpe,
            profit_factor=profit_factor,
            total_return=total_return,
            total_trades=total_trades,
        ),
    )


def test_sharpe_beats_raw_return():
    lucky = make_result(sharpe=0.4, total_return=120.0)
    solid = make_result(sharpe=1.6, total_return=12.0)

    summary = GridSearchOptimizer().rank([lucky, solid])

    assert summary.best_result is solid


def test_min_trades_gate_blocks_undertraded_best():
    fluke = make_result(sharpe=2.5, total_trades=6)
    robust = make_result(sharpe=0.9, total_trades=45)

    summary = GridSearchOptimizer(min_trades=30).rank([fluke, robust])

    assert summary.best_result is robust
    # Under-traded run stays visible in the full ranking.
    assert fluke in summary.results


def test_no_eligible_run_means_no_best():
    thin = make_result(sharpe=2.0, total_trades=10)

    summary = GridSearchOptimizer(min_trades=30).rank([thin])

    assert summary.best_result is None
    assert summary.total_runs == 1


def test_profit_factor_breaks_sharpe_ties():
    a = make_result(sharpe=1.0, profit_factor=1.2)
    b = make_result(sharpe=1.0, profit_factor=1.9)

    summary = GridSearchOptimizer().rank([a, b])

    assert summary.best_result is b


def test_empty_results():
    summary = GridSearchOptimizer().rank([])

    assert summary.total_runs == 0
    assert summary.best_result is None
