from __future__ import annotations

from dataclasses import dataclass

from mjonai.analytics.models import (
    TradeStatistics,
)
from mjonai.research.backtest.models import TradeResult


class MetricsCalculator:

    def calculate(
        self,
        trades: list[TradeResult],
    ) -> TradeStatistics:

        if not trades:

            return TradeStatistics(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate_pct=0.0,
                average_return_pct=0.0,
                average_win_pct=0.0,
                average_loss_pct=0.0,
                largest_win_pct=0.0,
                largest_loss_pct=0.0,
                profit_factor=0.0,
                payoff_ratio=0.0,
                expectancy=0.0,
                consecutive_wins=0,
                consecutive_losses=0,
            )

        # Breakeven trades count toward total but are
        # excluded from the win/loss split.
        wins = [
            trade
            for trade in trades
            if trade.net_return_pct > 0
        ]

        losses = [
            trade
            for trade in trades
            if trade.net_return_pct < 0
        ]

        total_trades = len(trades)

        winning_trades = len(wins)

        losing_trades = len(losses)

        decided_trades = (
            winning_trades + losing_trades
        )

        win_rate = (
            winning_trades
            * 100
            / decided_trades
            if decided_trades
            else 0.0
        )

        total_return = sum(
            trade.net_return_pct
            for trade in trades
        )

        average_return = (
            total_return
            / total_trades
        )

        average_win = (
            sum(
                trade.net_return_pct
                for trade in wins
            )
            / winning_trades
            if winning_trades
            else 0.0
        )

        average_loss = (
            sum(
                trade.net_return_pct
                for trade in losses
            )
            / losing_trades
            if losing_trades
            else 0.0
        )

        largest_win = (
            max(
                (
                    trade.net_return_pct
                    for trade in wins
                ),
                default=0.0,
            )
        )

        largest_loss = (
            min(
                (
                    trade.net_return_pct
                    for trade in losses
                ),
                default=0.0,
            )
        )

        # Profit factor uses gross rupee P&L so that
        # costs are not double-counted per side.
        gross_profit = sum(
            trade.gross_pnl
            for trade in wins
        )

        gross_loss = abs(
            sum(
                trade.gross_pnl
                for trade in losses
            )
        )

        profit_factor = (
            gross_profit
            / gross_loss
            if gross_loss
            else 0.0
        )

        payoff_ratio = (
            abs(
                average_win
                / average_loss
            )
            if average_loss
            else 0.0
        )

        # Standard expectancy:
        # win_rate * avg_win + loss_rate * avg_loss.
        loss_rate = (
            losing_trades / decided_trades
            if decided_trades
            else 0.0
        )

        expectancy = (
            win_rate / 100 * average_win
            + loss_rate * average_loss
        )

        consecutive_wins = 0
        max_consecutive_wins = 0

        consecutive_losses = 0
        max_consecutive_losses = 0

        for trade in trades:

            if trade.net_return_pct > 0:

                consecutive_wins += 1
                consecutive_losses = 0

            elif trade.net_return_pct < 0:

                consecutive_losses += 1
                consecutive_wins = 0

            max_consecutive_wins = max(
                max_consecutive_wins,
                consecutive_wins,
            )

            max_consecutive_losses = max(
                max_consecutive_losses,
                consecutive_losses,
            )

        return TradeStatistics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate_pct=round(
                win_rate,
                2,
            ),
            average_return_pct=round(
                average_return,
                4,
            ),
            average_win_pct=round(
                average_win,
                4,
            ),
            average_loss_pct=round(
                average_loss,
                4,
            ),
            largest_win_pct=round(
                largest_win,
                4,
            ),
            largest_loss_pct=round(
                largest_loss,
                4,
            ),
            profit_factor=round(
                profit_factor,
                4,
            ),
            payoff_ratio=round(
                payoff_ratio,
                4,
            ),
            expectancy=round(
                expectancy,
                4,
            ),
            consecutive_wins=max_consecutive_wins,
            consecutive_losses=max_consecutive_losses,
        )