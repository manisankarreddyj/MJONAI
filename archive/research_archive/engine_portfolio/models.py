from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Position:

    quantity: int

    invested_capital: float

    risk_amount: float


@dataclass(slots=True)
class Capital:

    initial: float

    available: float

    invested: float

    realized_pnl: float

    unrealized_pnl: float

    peak_equity: float = field(init=False)

    max_drawdown: float = 0.0

    def __post_init__(self) -> None:

        self.peak_equity = self.initial

    @property
    def equity(self) -> float:

        return round(
            self.available
            + self.invested
            + self.unrealized_pnl,
            2,
        )

    @property
    def total_pnl(self) -> float:

        return round(
            self.realized_pnl
            + self.unrealized_pnl,
            2,
        )

    @property
    def return_pct(self) -> float:

        if self.initial == 0:
            return 0.0

        return round(
            (
                self.total_pnl
                / self.initial
            )
            * 100,
            4,
        )

    def update_equity_metrics(
        self,
    ) -> None:

        current_equity = self.equity

        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

        if self.peak_equity > 0:

            drawdown = (
                (
                    self.peak_equity
                    - current_equity
                )
                / self.peak_equity
            ) * 100

            if drawdown > self.max_drawdown:
                self.max_drawdown = round(
                    drawdown,
                    4,
                )