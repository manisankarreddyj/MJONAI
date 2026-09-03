from __future__ import annotations

from engine.execution.brokers.angel_one import (
    AngelOneCostModel,
)
from engine.execution.brokers.enums import Broker
from engine.execution.brokers.registry import (
    BrokerRegistry,
)
from engine.execution.brokers.shoonya import (
    ShoonyaCostModel,
)
from engine.execution.brokers.zerodha import (
    ZerodhaCostModel,
)
from engine.execution.models import TransactionCost


class TransactionCostCalculator:

    def __init__(self):

        self._registry = BrokerRegistry()

        self._registry.register(
            ZerodhaCostModel(),
        )

        self._registry.register(
            AngelOneCostModel(),
        )

        self._registry.register(
            ShoonyaCostModel(),
        )

    def calculate(
        self,
        *,
        broker: Broker = Broker.ZERODHA,
        entry_price: float,
        exit_price: float,
        quantity: int = 1,
        slippage_bps: float = 5.0,
    ) -> TransactionCost:

        model = self._registry.get(
            broker.value,
        )

        return model.calculate(
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            slippage_bps=slippage_bps,
        )