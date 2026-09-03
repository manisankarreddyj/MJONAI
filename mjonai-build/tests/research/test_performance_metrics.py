"""Risk-adjusted metrics: real Sharpe/Sortino/CAGR/Calmar on
hand-built equity curves, plus degenerate-input safety."""

import math
from datetime import datetime

import pytest

from analytics.models import EquityStatistics
from analytics.risk_metrics import (
    PerformanceMetricsCalculator,
)
from analytics.models import TradeStatistics
from research.backtest.models import EquityCurve, EquityPoint


INITIAL = 100_000.0


def make_equity(values, dates):
    points = [
        EquityPoint(
            timestamp=ts,
            equity=value,
            available_capital=value,
            invested_capital=0.0,
            realized_pnl=value - INITIAL,
            unrealized_pnl=0.0,
        )
        for ts, value in zip(dates, values)
    ]

    peak = INITIAL
    max_dd = 0.0

    for value in values:
        peak = max(peak, value)
        max_dd = max(max_dd, (peak - value) / peak * 100)

    return EquityStatistics(
        initial_capital=INITIAL,
        final_capital=values[-1],
        total_return_pct=(values[-1] / INITIAL - 1) * 100,
        peak_equity=peak,
        max_drawdown_pct=max_dd,
        current_drawdown_pct=0.0,
        equity_curve=EquityCurve(points=points),
    )


def make_trade_stats():
    return TradeStatistics(
        total_trades=4, winning_trades=2, losing_trades=2,
        win_rate_pct=50.0, average_return_pct=0.5, average_win_pct=2.0,
        average_loss_pct=-1.0, largest_win_pct=2.0, largest_loss_pct=-1.0,
        profit_factor=2.0, payoff_ratio=2.0, expectancy=0.5,
        consecutive_wins=1, consecutive_losses=1,
    )


def bdates(*args):
    return [datetime(y, m, d) for y, m, d in args]


def test_sharpe_and_annualized_return_are_computed():
    equity = make_equity(
        [101_000.0, 100_000.0, 102_000.0, 103_000.0],
        bdates((2024, 1, 1), (2024, 1, 2), (2024, 1, 3), (2024, 1, 4)),
    )

    stats = PerformanceMetricsCalculator().calculate(
        make_trade_stats(), equity,
    )

    assert stats.sharpe_ratio > 0
    # Mean daily return ~ +0.25% -> annualized well above zero.
    assert stats.annualized_return_pct > 25


def test_cagr_is_exact_for_known_span():
    # 10% growth over 2024-01-01 .. 2024-04-10 (100 days).
    equity = make_equity(
        [101_000.0, 105_000.0, 108_000.0, 110_000.0],
        bdates((2024, 1, 1), (2024, 2, 1), (2024, 3, 1), (2024, 4, 10)),
    )

    days = (datetime(2024, 4, 10) - datetime(2024, 1, 1)).days
    expected_cagr = ((1.10) ** (365.25 / days) - 1) * 100

    stats = PerformanceMetricsCalculator().calculate(
        make_trade_stats(), equity,
    )

    assert stats.cagr_pct == pytest.approx(expected_cagr, rel=1e-6)


def test_calmar_is_cagr_over_max_drawdown():
    equity = make_equity(
        [120_000.0, 90_000.0, 110_000.0],
        bdates((2024, 1, 1), (2024, 1, 2), (2024, 1, 3)),
    )

    stats = PerformanceMetricsCalculator().calculate(
        make_trade_stats(), equity,
    )

    assert equity.max_drawdown_pct == pytest.approx(25.0)
    assert stats.calmar_ratio == pytest.approx(
        stats.cagr_pct / 25.0, rel=1e-6,
    )


def test_higher_risk_free_lowers_sharpe():
    values = [101_000.0, 100_000.0, 102_000.0, 103_000.0]
    dates = bdates((2024, 1, 1), (2024, 1, 2), (2024, 1, 3), (2024, 1, 4))
    equity = make_equity(values, dates)

    base = PerformanceMetricsCalculator(risk_free_annual=0.0)
    high = PerformanceMetricsCalculator(risk_free_annual=0.10)

    base_sharpe = base.calculate(make_trade_stats(), equity).sharpe_ratio
    high_sharpe = high.calculate(make_trade_stats(), equity).sharpe_ratio

    assert high_sharpe < base_sharpe


def test_flat_equity_has_zero_sharpe():
    equity = make_equity(
        [INITIAL, INITIAL, INITIAL],
        bdates((2024, 1, 1), (2024, 1, 2), (2024, 1, 3)),
    )

    stats = PerformanceMetricsCalculator().calculate(
        make_trade_stats(), equity,
    )

    assert stats.sharpe_ratio == 0.0
    assert stats.sortino_ratio == 0.0
    assert stats.annualized_return_pct == 0.0


def test_empty_curve_degenerates_safely():
    equity = EquityStatistics(
        initial_capital=INITIAL,
        final_capital=INITIAL,
        total_return_pct=0.0,
        peak_equity=INITIAL,
        max_drawdown_pct=0.0,
        current_drawdown_pct=0.0,
        equity_curve=EquityCurve(points=[]),
    )

    stats = PerformanceMetricsCalculator().calculate(
        make_trade_stats(), equity,
    )

    assert stats.sharpe_ratio == 0.0
    assert stats.cagr_pct == 0.0
    assert stats.calmar_ratio == 0.0
