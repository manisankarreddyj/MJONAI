from __future__ import annotations

from dataclasses import dataclass

from research.config import ResearchConfig


@dataclass(slots=True)
class ResearchContext:
    """
    Immutable description of one research job.

    Bootstrap resolves symbols into Instrument objects.
    """

    config: ResearchConfig

    symbols: list[str]

    strategy_ids: list[str]