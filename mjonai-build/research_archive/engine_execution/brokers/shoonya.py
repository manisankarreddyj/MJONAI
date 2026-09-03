from __future__ import annotations

from engine.execution.brokers.base import BrokerCostModel
from engine.execution.models import TransactionCost


class ShoonyaCostModel(BrokerCostModel):

    @property
    def name(self) -> str:
        return "SHOONYA"

    def calculate(
        self,
        *,
        entry_price: float,
        exit_price: float,
        quantity: int,
        slippage_bps: float = 5.0,
    ) -> TransactionCost:
        """
        Stub model: taxes/brokerage not yet implemented
        (deferred until live trading). Slippage still applies.
        """

        turnover = (
            entry_price + exit_price
        ) * quantity

        slippage = round(
            turnover *
            slippage_bps /
            10000,
            2,
        )

        return TransactionCost(
            brokerage=0.0,
            slippage=slippage,
            taxes=0.0,
            total=slippage,
        )