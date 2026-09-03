"""Post-simulation processing: position sizing, transaction costs,
and capital tracking for the backtest ledger.

Inlined replacement for the old Portfolio/CapitalManager/
PositionSizer/TradeProcessor layer (absorbed per ENGINE_TRIAGE.md).
Observable behavior is identical to the 2026-08-22-fixed pipeline.
"""

from __future__ import annotations

from mjonai.research.backtest.costs import (
    equity_delivery_cost,
)
from mjonai.research.backtest.models import TradeResult


class _CapitalTracker:
    """
    Minimal single-ledger capital tracker.

    Tracks available cash, peak equity and max drawdown with the
    same rounding semantics as the old CapitalManager.
    """

    def __init__(
        self,
        initial_capital: float,
    ):

        self.initial = initial_capital

        self.available = initial_capital

        self.realized_pnl = 0.0

        self._peak_equity = initial_capital

        self.max_drawdown = 0.0

    @property
    def equity(
        self,
    ) -> float:

        return round(
            self.available,
            2,
        )

    def spend(
        self,
        amount: float,
    ) -> None:

        if amount <= 0:

            raise ValueError(
                "Allocation amount must be greater than zero."
            )

        if amount > self.available:

            raise ValueError(
                "Insufficient available capital."
            )

        self.available = round(
            self.available - amount,
            2,
        )

        self._update()

    def settle(
        self,
        net_pnl: float,
    ) -> None:

        self.realized_pnl = round(
            self.realized_pnl + net_pnl,
            2,
        )

        self.available = round(
            self.available + net_pnl,
            2,
        )

        self._update()

    def _update(
        self,
    ) -> None:

        equity = self.equity

        if equity > self._peak_equity:

            self._peak_equity = equity

        if self._peak_equity > 0:

            drawdown = (
                (
                    self._peak_equity
                    - equity
                )
                / self._peak_equity
            ) * 100

            if drawdown > self.max_drawdown:

                self.max_drawdown = round(
                    drawdown,
                    4,
                )


class TradeProcessor:
    """
    Applies sizing, costs and capital effects to one simulated
    trade. Returns None when no share is affordable.
    """

    def __init__(
        self,
        initial_capital: float,
        *,
        risk_percent: float = 1.0,
    ):

        self._capital = _CapitalTracker(
            initial_capital,
        )

        self._risk_percent = risk_percent

    @property
    def capital(
        self,
    ) -> _CapitalTracker:

        return self._capital

    def process(
        self,
        *,
        trade: TradeResult,
    ) -> TradeResult | None:

        available = (
            self._capital.available
        )

        trade.equity_before = (
            self._capital.equity
        )

        trade.available_capital_before = (
            available
        )

        # Fixed-risk sizing (1% of available by default),
        # clamped to what capital can actually buy.
        risk_amount = (
            available *
            self._risk_percent /
            100
        )

        risk_per_share = abs(
            trade.entry_price -
            trade.stop_loss
        )

        if risk_per_share <= 0:
            return None

        sized_quantity = max(
            1,
            int(
                risk_amount /
                risk_per_share
            ),
        )

        affordable = int(
            available /
            trade.entry_price
        )

        quantity = min(
            sized_quantity,
            affordable,
        )

        if quantity < 1:
            return None

        trade.quantity = quantity

        invested = round(
            trade.entry_price * quantity,
            2,
        )

        trade.invested_capital = invested

        self._capital.spend(
            invested,
        )

        gross_pnl = round(
            (
                trade.exit_price
                - trade.entry_price
            )
            * quantity,
            2,
        )

        if trade.direction == "SHORT":

            gross_pnl *= -1

        trade.gross_pnl = gross_pnl

        trade.transaction_cost = (
            equity_delivery_cost(
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                quantity=quantity,
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

        # The position was held only virtually during
        # simulation; settle the result on the ledger.
        self._capital.settle(
            trade.net_pnl,
        )

        trade.equity_after = (
            self._capital.equity
        )

        trade.available_capital_after = (
            self._capital.available
        )

        trade.portfolio_drawdown_pct = (
            self._capital.max_drawdown
        )

        return trade
