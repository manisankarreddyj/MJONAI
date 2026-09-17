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
class CPCVFoldResult:
    """Outcome of one CPCV fold: best parameters fit on the fold's train
    intervals, measured on the disjoint test intervals."""
    fold_id: int
    train_intervals: list[tuple[datetime, datetime]]
    test_intervals: list[tuple[datetime, datetime]]
    parameters: dict
    training_report: PerformanceReport
    validation_report: PerformanceReport
    validation_trades: list | None = None


@dataclass(slots=True)
class CPCVSummary:
    """Consolidated CPCV verdict for one strategy/symbol."""
    strategy: str
    symbol: str
    folds: list[CPCVFoldResult]

    def to_walk_forward_summary(self) -> "WalkForwardSummary":
        """Map fold outcomes onto WalkForwardResult windows so the existing
        pooled WFE / statistical-validation path has ONE verdict definition
        regardless of the validation scheme used."""
        return WalkForwardSummary(
            strategy=self.strategy,
            symbol=self.symbol,
            windows=[
                WalkForwardResult(
                    window=WalkForwardWindow(
                        train_start=f.train_intervals[0][0] if f.train_intervals else datetime.min,
                        train_end=f.train_intervals[-1][1] if f.train_intervals else datetime.min,
                        validation_start=f.test_intervals[0][0] if f.test_intervals else datetime.min,
                        validation_end=f.test_intervals[-1][1] if f.test_intervals else datetime.min,
                    ),
                    parameters=f.parameters,
                    training_report=f.training_report,
                    validation_report=f.validation_report,
                    validation_trades=list(f.validation_trades or []),
                )
                for f in self.folds
            ],
        )


@dataclass(slots=True)
class WalkForwardEfficiencyReport:
    """Walk-Forward Efficiency (WFE %) and Parameter Stability Report.

    is_robust additionally requires a minimum pooled out-of-sample trade
    count (see WalkForwardEngine.MIN_POOLED_OOS_TRADES): a tiny OOS sample
    cannot distinguish a real edge from noise, so it must never read robust.
    """
    annualized_is_return: float
    annualized_oos_return: float
    wfe_pct: float
    is_robust: bool  # True if WFE >= 50.0% and OOS > 0 and pooled OOS trades >= floor
    plateau_stability_score: float  # 0.0 - 1.0 stability metric
    pooled_oos_trades: int = 0  # pooled out-of-sample trades across all windows
    notes: str = ""