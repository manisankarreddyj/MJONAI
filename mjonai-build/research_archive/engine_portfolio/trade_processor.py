from __future__ import annotations

from engine.backtest.models import TradeResult

from engine.execution.brokers.enums import Broker
from engine.execution.costs import (
    TransactionCostCalculator,
)

from engine.portfolio.portfolio import Portfolio


class TradeProcessor:

    def __init__(
        self,
        portfolio: Portfolio,
    ):

        self._portfolio = portfolio

        self._cost_calculator = (
            TransactionCostCalculator()
        )

    def process(
        self,
        *,
        trade: TradeResult,
        broker: Broker,
    ) -> TradeResult | None:
        """
        Apply sizing, costs and capital effects to a simulated
        trade. Returns None when no share is affordable.
        """

        capital = self._portfolio.capital.capital

        trade.equity_before = capital.equity

        trade.available_capital_before = (
            capital.available
        )

        position = (
            self._portfolio.position_sizer.calculate(
                capital=capital.available,
                risk_percent=1.0,
                entry_price=trade.entry_price,
                stop_loss=trade.stop_loss,
            )
        )

        # The sizer respects risk but not affordability;
        # clamp the quantity to what capital can actually buy.
        quantity = min(
            position.quantity,
            int(
                capital.available
                / trade.entry_price
            ),
        )

        if quantity < 1:
            return None

        trade.quantity = quantity

        trade.invested_capital = round(
            trade.entry_price * quantity,
            2,
        )

        self._portfolio.capital.allocate(
            trade.invested_capital,
        )

        trade.gross_pnl = round(
            (
                trade.exit_price
                - trade.entry_price
            )
            * trade.quantity,
            2,
        )

        if trade.direction == "SHORT":
            trade.gross_pnl *= -1

        trade.transaction_cost = (
            self._cost_calculator.calculate(
                broker=broker,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                quantity=trade.quantity,
            )
        )

        trade.net_pnl = round(
            trade.gross_pnl
            - trade.transaction_cost.total,
            2,
        )

        trade.net_return_pct = round(
            (
                trade.net_pnl
                / trade.invested_capital
            )
            * 100,
            4,
        )

        self._portfolio.capital.release(
            trade.invested_capital,
        )

        self._portfolio.capital.apply_trade_result(
            trade.net_pnl,
        )

        trade.equity_after = (
            capital.equity
        )

        trade.available_capital_after = (
            capital.available
        )

        trade.portfolio_drawdown_pct = (
            capital.max_drawdown
        )

        self._portfolio.add_closed_trade(
            trade,
        )

        return trade