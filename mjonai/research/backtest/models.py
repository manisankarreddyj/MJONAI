from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal



TradeDirection = Literal[
    "LONG",
    "SHORT",
]

ExitReason = Literal[
    "TARGET",
    "STOPLOSS",
    "TIMEOUT",
    "END_OF_DATA",
]


@dataclass(slots=True)
class TransactionCost:

    brokerage: float

    slippage: float

    taxes: float

    total: float



@dataclass(slots=True)
class TradeResult:

    symbol: str

    strategy: str

    direction: TradeDirection

    entry_index: int

    exit_index: int

    entry_date: datetime

    exit_date: datetime

    entry_price: float

    exit_price: float

    quantity: int

    invested_capital: float

    gross_pnl: float

    net_pnl: float

    stop_loss: float

    target: float

    holding_bars: int

    exit_reason: ExitReason

    gross_return_pct: float

    net_return_pct: float

    risk_reward: float

    mfe: float

    mae: float

    transaction_cost: TransactionCost

    equity_before: float = 0.0

    equity_after: float = 0.0

    available_capital_before: float = 0.0

    available_capital_after: float = 0.0

    portfolio_drawdown_pct: float = 0.0


@dataclass(slots=True)
class BacktestResult:

    strategy: str

    symbol: str

    trades: list[TradeResult]

    initial_capital: float

    final_capital: float

    total_return_pct: float

    max_drawdown_pct: float

    win_rate_pct: float

    profit_factor: float

    average_win_pct: float

    average_loss_pct: float

    expectancy: float

    equity_curve: "EquityCurve | None" = None


@dataclass(slots=True)
class EquityPoint:

    timestamp: datetime

    equity: float

    available_capital: float

    invested_capital: float

    realized_pnl: float

    unrealized_pnl: float


@dataclass(slots=True)
class EquityCurve:

    points: list[EquityPoint] = field(
        default_factory=list,
    )