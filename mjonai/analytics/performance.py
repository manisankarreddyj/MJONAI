from __future__ import annotations

from mjonai.analytics.equity import EquityCalculator
from mjonai.analytics.metrics import MetricsCalculator
from mjonai.analytics.models import PerformanceReport
from mjonai.analytics.risk_metrics import (
    PerformanceMetricsCalculator,
)
from mjonai.research.backtest.engine import INITIAL_CAPITAL
from mjonai.research.backtest.models import TradeResult


class PerformanceAnalyzer:

    def __init__(self) -> None:

        self._trade_metrics = MetricsCalculator()

        self._equity_metrics = EquityCalculator()

        self._performance_metrics = (
            PerformanceMetricsCalculator()
        )

    def analyze(
        self,
        trades: list[TradeResult],
        initial_capital: float = INITIAL_CAPITAL,
    ) -> PerformanceReport:
        # H7 fix: default was ₹100k while the backtest ledger runs on
        # INITIAL_CAPITAL (₹1M) — every %-return/drawdown metric was
        # mislabeled ~10x when callers omitted capital. Defaults now share
        # the ledger's single source of truth.

        trade_statistics = self._trade_metrics.calculate(
            trades,
        )

        equity_statistics = self._equity_metrics.calculate(
            trades=trades,
            initial_capital=initial_capital,
        )

        performance_statistics = (
            self._performance_metrics.calculate(
                trade=trade_statistics,
                equity=equity_statistics,
            )
        )

        return PerformanceReport(
            trade=trade_statistics,
            equity=equity_statistics,
            performance=performance_statistics,
        )