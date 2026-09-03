from __future__ import annotations

from engine.portfolio.models import Capital


class CapitalManager:

    def __init__(
        self,
        initial_capital: float,
    ):

        self._capital = Capital(
            initial=initial_capital,
            available=initial_capital,
            invested=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
        )

    @property
    def capital(self) -> Capital:

        return self._capital

    def allocate(
        self,
        amount: float,
    ) -> None:

        if amount <= 0:
            raise ValueError(
                "Allocation amount must be greater than zero."
            )

        if amount > self._capital.available:
            raise ValueError(
                "Insufficient available capital."
            )

        self._capital.available = round(
            self._capital.available - amount,
            2,
        )

        self._capital.invested = round(
            self._capital.invested + amount,
            2,
        )

        self._capital.update_equity_metrics()

    def release(
        self,
        amount: float,
    ) -> None:

        if amount <= 0:
            raise ValueError(
                "Release amount must be greater than zero."
            )

        if amount > self._capital.invested:
            raise ValueError(
                "Release amount exceeds invested capital."
            )

        self._capital.invested = round(
            self._capital.invested - amount,
            2,
        )

        self._capital.available = round(
            self._capital.available + amount,
            2,
        )

        self._capital.update_equity_metrics()

    def apply_trade_result(
        self,
        net_pnl: float,
    ) -> None:

        self._capital.realized_pnl = round(
            self._capital.realized_pnl + net_pnl,
            2,
        )

        self._capital.available = round(
            self._capital.available + net_pnl,
            2,
        )

        self._capital.update_equity_metrics()

    @property
    def total_equity(self) -> float:

        return self._capital.equity