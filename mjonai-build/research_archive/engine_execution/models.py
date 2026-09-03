from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TransactionCost:

    brokerage: float

    slippage: float

    taxes: float

    total: float