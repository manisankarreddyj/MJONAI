from __future__ import annotations

from dataclasses import dataclass

from analytics.models import PerformanceReport
from data.instruments.models import Instrument


@dataclass(slots=True)
class ResearchResult:
    """
    Result produced by running one strategy
    on one instrument.
    """

    strategy_id: str

    instrument: Instrument

    signals: int

    trades: int

    report: PerformanceReport

    # G5: raw executed trades retained so statistical validation (DSR / WRC /
    # Monte Carlo) can consume real OOS outcomes instead of claims.
    trades_list: list | None = None