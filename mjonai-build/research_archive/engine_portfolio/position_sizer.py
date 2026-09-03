from __future__ import annotations

from engine.portfolio.models import Position


class FixedRiskPositionSizer:

    def calculate(
        self,
        *,
        capital: float,
        risk_percent: float,
        entry_price: float,
        stop_loss: float,
    ) -> Position:

        risk_amount = (
            capital *
            risk_percent /
            100
        )

        risk_per_share = abs(
            entry_price -
            stop_loss
        )

        quantity = max(
            1,
            int(
                risk_amount /
                risk_per_share
            ),
        )

        invested = (
            quantity *
            entry_price
        )

        return Position(
            quantity=quantity,
            invested_capital=invested,
            risk_amount=risk_amount,
        )