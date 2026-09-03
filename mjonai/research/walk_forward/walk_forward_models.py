from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from mjonai.analytics.models import PerformanceReport


@dataclass(slots=True)
class WalkForwardWindow:
    train_start: datetime
    train_end: datetime
    validation_start: datetime
    validation_end: datetime


@dataclass(slots=True)
class WalkForwardResult:
    window: WalkForwardWindow
    parameters: dict
    training_report: PerformanceReport
    validation_report: PerformanceReport
    # G5: raw out-of-sample trades for statistical validation downstream.
    validation_trades: list | None = None


@dataclass(slots=True)
class WalkForwardSummary:
    strategy: str
    symbol: str
    windows: list[WalkForwardResult]


@dataclass(slots=True)
class CPCVFold:
    """Combinatorial Purged Cross-Validation Fold (López de Prado)."""
    fold_id: int
    train_intervals: list[tuple[datetime, datetime]]
    test_intervals: list[tuple[datetime, datetime]]
    purged_intervals: list[tuple[datetime, datetime]]
    embargo_intervals: list[tuple[datetime, datetime]]


@dataclass(slots=True)
class WalkForwardEfficiencyReport:
    """Walk-Forward Efficiency (WFE %) and Parameter Stability Report."""
    annualized_is_return: float
    annualized_oos_return: float
    wfe_pct: float
    is_robust: bool  # True if WFE >= 50.0% and positive
    plateau_stability_score: float  # 0.0 - 1.0 stability metric
    notes: str = ""