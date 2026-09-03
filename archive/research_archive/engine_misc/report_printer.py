from __future__ import annotations
from engine.analytics.models import PerformanceReport

def print_report(
    report: PerformanceReport,
) -> None:
    trade = report.trade
    equity = report.equity
    print()
    print("=" * 80)
    print("PERFORMANCE REPORT")
    print()
    print(f"Trades           : {trade.total_trades}")
    print(f"Wins             : {trade.winning_trades}")
    print(f"Losses           : {trade.losing_trades}")
    print(f"Win Rate         : {trade.win_rate_pct:.2f}%")
    print(f"Return           : {equity.total_return_pct:.2f}%")
    print(f"Average Trade    : {trade.average_return_pct:.2f}%")
    print(f"Average Win      : {trade.average_win_pct:.2f}%")
    print(f"Average Loss     : {trade.average_loss_pct:.2f}%")
    print(f"Profit Factor    : {trade.profit_factor:.2f}")
    print(f"Expectancy       : {trade.expectancy:.2f}%")
    print(f"Max Drawdown     : {equity.max_drawdown_pct:.2f}%")
