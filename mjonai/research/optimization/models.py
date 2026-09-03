from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mjonai.analytics.models import PerformanceReport


@dataclass(slots=True, frozen=True)
class ParameterDefinition:

    name: str

    values: list[Any]


@dataclass(slots=True)
class ParameterSet:

    values: dict[str, Any]

    def get(
        self,
        name: str,
        default: Any = None,
    ) -> Any:

        return self.values.get(
            name,
            default,
        )

    def __getitem__(
        self,
        name: str,
    ) -> Any:

        return self.values[name]

    def __contains__(
        self,
        name: str,
    ) -> bool:

        return name in self.values


@dataclass(slots=True)
class OptimizationResult:

    strategy: str

    symbol: str

    parameters: ParameterSet

    report: PerformanceReport


@dataclass(slots=True)
class OptimizationSummary:

    strategy: str

    symbol: str

    total_runs: int

    best_result: OptimizationResult | None

    results: list[OptimizationResult] = field(
        default_factory=list,
    )