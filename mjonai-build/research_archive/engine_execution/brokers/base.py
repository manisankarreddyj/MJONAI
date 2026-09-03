from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from engine.execution.models import TransactionCost


class BrokerCostModel(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def calculate(
        self,
        *,
        entry_price: float,
        exit_price: float,
        quantity: int,
        slippage_bps: float = 5.0,
    ) -> TransactionCost:
        ...