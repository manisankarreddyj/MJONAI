"""Integration: PerformanceAnalyzer produces a full report with
non-stubbed risk metrics."""

from datetime import datetime

from mjonai.analytics.performance import PerformanceAnalyzer
from mjonai.research.backtest.models import TradeResult
from mjonai.research.backtest.models import TransactionCost


def make_trade(entry_date, exit_date, entry_price, exit_price,
               gross_pnl, net_return_pct):
    return TradeResult(
        symbol="RELIANCE",
        strategy="TEST",
        direction="LONG",
        entry_index=0,
        exit_index=1,
        entry_date=entry_date,
        exit_date=exit_date,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=100,
        invested_capital=entry_price * 100,
        gross_pnl=gross_pnl,
        net_pnl=gross_pnl - 20.0,
        stop_loss=entry_price * 0.97,
        target=entry_price * 1.09,
        holding_bars=1,
        exit_reason="TARGET",
        gross_return_pct=net_return_pct + 0.2,
        net_return_pct=net_return_pct,
        risk_reward=2.0,
        mfe=2.0,
        mae=-1.0,
        transaction_cost=TransactionCost(0.0, 5.0, 15.0, 20.0),
    )


trades = [
    make_trade(datetime(2024, 1, 1), datetime(2024, 1, 2), 100.0, 105.0, 500.0, 5.0),
    make_trade(datetime(2024, 2, 1), datetime(2024, 2, 2), 100.0, 97.0, -300.0, -3.0),
    make_trade(datetime(2024, 3, 1), datetime(2024, 3, 4), 100.0, 103.0, 300.0, 3.0),
]


def test_report_is_fully_populated():
    report = PerformanceAnalyzer().analyze(trades, initial_capital=10_000.0)

    assert report.trade.total_trades == 3
    assert report.trade.winning_trades == 2
    assert report.equity.final_capital > report.equity.initial_capital
    assert report.equity.max_drawdown_pct >= 0

    # The old stub returned exactly these zeros.
    assert report.performance.sharpe_ratio != 0.0
    assert report.performance.cagr_pct != 0.0
    assert report.performance.calmar_ratio != 0.0
