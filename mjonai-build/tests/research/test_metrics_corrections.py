"""Trade statistics corrections: breakeven handling, gross profit
factor, standard expectancy formula."""

from datetime import datetime

from analytics.metrics import MetricsCalculator
from research.backtest.models import TradeResult
from research.backtest.models import TransactionCost


def make_trade(net_return_pct, gross_pnl):
    return TradeResult(
        symbol="TEST",
        strategy="T",
        direction="LONG",
        entry_index=0,
        exit_index=1,
        entry_date=datetime(2024, 1, 1),
        exit_date=datetime(2024, 1, 2),
        entry_price=100.0,
        exit_price=100.0 + net_return_pct,
        quantity=100,
        invested_capital=10_000.0,
        gross_pnl=gross_pnl,
        net_pnl=gross_pnl,
        stop_loss=95.0,
        target=110.0,
        holding_bars=1,
        exit_reason="TARGET",
        gross_return_pct=net_return_pct,
        net_return_pct=net_return_pct,
        risk_reward=2.0,
        mfe=1.0,
        mae=-1.0,
        transaction_cost=TransactionCost(0.0, 0.0, 0.0, 0.0),
    )


def test_breakeven_excluded_from_win_loss_split():
    trades = [
        make_trade(5.0, 500.0),
        make_trade(0.0, 0.0),   # breakeven
        make_trade(-3.0, -300.0),
    ]

    stats = MetricsCalculator().calculate(trades)

    assert stats.total_trades == 3
    assert stats.winning_trades == 1
    assert stats.losing_trades == 1
    # Win rate is over DECIDED trades only.
    assert stats.win_rate_pct == 50.0


def test_profit_factor_uses_gross_pnl():
    # Net-based PF would be (5 + 4) / 3 = 3.0;
    # gross-based is (500 + 400) / 200 = 4.5.
    trades = [
        make_trade(5.0, 500.0),
        make_trade(4.0, 400.0),
        make_trade(-3.0, -200.0),
    ]

    stats = MetricsCalculator().calculate(trades)

    assert stats.profit_factor == 4.5


def test_expectancy_uses_standard_formula():
    # avg_win = 4.5, avg_loss = -3:
    # 2/3 * 4.5 + 1/3 * (-3) = 2.0  (average return would also be
    # 2.0 here by coincidence, so use an asymmetric case below)
    trades = [
        make_trade(5.0, 500.0),
        make_trade(4.0, 400.0),
        make_trade(-3.0, -300.0),
    ]

    stats = MetricsCalculator().calculate(trades)

    expected = (2 / 3) * 4.5 + (1 / 3) * (-3.0)
    assert abs(stats.expectancy - expected) < 1e-6


def test_expectancy_matches_mean_return_by_definition():
    # Under empirical frequencies, win_rate*avg_win + loss_rate*avg_loss
    # is algebraically the mean per-trade return; the explicit formula
    # documents the probability weighting rather than changing it.
    trades = [
        make_trade(20.0, 2000.0),
        make_trade(-1.0, -100.0),
        make_trade(-1.0, -100.0),
    ]

    stats = MetricsCalculator().calculate(trades)

    expected = (1 / 3) * 20.0 + (2 / 3) * (-1.0)
    assert abs(stats.expectancy - expected) < 1e-6
    assert abs(stats.expectancy - stats.average_return_pct) < 1e-6


def test_breakeven_is_streak_neutral():
    trades = [
        make_trade(2.0, 200.0),
        make_trade(0.0, 0.0),
        make_trade(-2.0, -200.0),
        make_trade(-2.0, -200.0),
    ]

    stats = MetricsCalculator().calculate(trades)

    assert stats.consecutive_wins == 1
    assert stats.consecutive_losses == 2


def test_all_breakeven_has_no_undefined_stats():
    trades = [make_trade(0.0, 0.0)]

    stats = MetricsCalculator().calculate(trades)

    assert stats.win_rate_pct == 0.0
    assert stats.profit_factor == 0.0
    assert stats.expectancy == 0.0
