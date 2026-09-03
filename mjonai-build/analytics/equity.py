from __future__ import annotations

from analytics.models import EquityStatistics
from research.backtest.models import (
    EquityCurve,
    EquityPoint,
    TradeResult,
)


class EquityCalculator:

    def calculate(
        self,
        trades: list[TradeResult],
        initial_capital: float,
    ) -> EquityStatistics:

        equity = initial_capital

        peak_equity = initial_capital

        current_drawdown = 0.0

        max_drawdown = 0.0

        points: list[EquityPoint] = []

        for trade in trades:

            equity += trade.net_pnl

            peak_equity = max(
                peak_equity,
                equity,
            )

            current_drawdown = (
                (
                    peak_equity
                    - equity
                )
                / peak_equity
            ) * 100

            max_drawdown = max(
                max_drawdown,
                current_drawdown,
            )

            points.append(
                EquityPoint(
                    timestamp=trade.exit_date,
                    equity=round(
                        equity,
                        2,
                    ),
                    available_capital=round(
                        trade.available_capital_after,
                        2,
                    ),
                    invested_capital=0.0,
                    realized_pnl=round(
                        equity - initial_capital,
                        2,
                    ),
                    unrealized_pnl=0.0,
                )
            )

        equity_curve = EquityCurve(
            points=points,
        )

        total_return_pct = (
            (
                (equity - initial_capital)
                / initial_capital
            )
            * 100
            if initial_capital
            else 0.0
        )

        return EquityStatistics(
            initial_capital=initial_capital,
            final_capital=round(
                equity,
                2,
            ),
            total_return_pct=round(
                total_return_pct,
                4,
            ),
            peak_equity=round(
                peak_equity,
                2,
            ),
            max_drawdown_pct=round(
                max_drawdown,
                4,
            ),
            current_drawdown_pct=round(
                current_drawdown,
                4,
            ),
            equity_curve=equity_curve,
        )