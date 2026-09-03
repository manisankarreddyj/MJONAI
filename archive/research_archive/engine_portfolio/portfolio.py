from __future__ import annotations

from engine.backtest.models import TradeResult

from engine.portfolio.capital import CapitalManager
from engine.portfolio.position import Position
from engine.portfolio.position_sizer import (
    FixedRiskPositionSizer,
)


class Portfolio:

    def __init__(
        self,
        initial_capital: float,
    ):

        self.capital = CapitalManager(
            initial_capital,
        )

        self.position_sizer = (
            FixedRiskPositionSizer()
        )

        self._open_positions: list[Position] = []

        self._closed_trades: list[TradeResult] = []

    @property
    def open_positions(
        self,
    ) -> list[Position]:

        return self._open_positions

    @property
    def closed_trades(
        self,
    ) -> list[TradeResult]:

        return self._closed_trades

    def add_position(
        self,
        position: Position,
    ) -> None:

        self._open_positions.append(
            position,
        )

    def remove_position(
        self,
        position: Position,
    ) -> None:

        self._open_positions.remove(
            position,
        )

    def add_closed_trade(
        self,
        trade: TradeResult,
    ) -> None:

        self._closed_trades.append(
            trade,
        )

    @property
    def total_open_positions(
        self,
    ) -> int:

        return len(
            self._open_positions,
        )

    @property
    def total_closed_trades(
        self,
    ) -> int:

        return len(
            self._closed_trades,
        )