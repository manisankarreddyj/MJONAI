"""Walk-forward verdict wiring: pool_summaries + verdict_exit_code.

Guards the fail-closed contract: a zero-window run must exit 2 (cannot
validate), an overfit run must exit 1, and only a robust run may exit 0.
"""

from datetime import datetime

import pytest

from mjonai.research.walk_forward.walk_forward_engine import WalkForwardEngine
from mjonai.research.walk_forward.walk_forward_models import (
    WalkForwardEfficiencyReport,
    WalkForwardResult,
    WalkForwardSummary,
    WalkForwardWindow,
)


def _window() -> WalkForwardResult:
    return WalkForwardResult(
        window=WalkForwardWindow(
            datetime(2020, 1, 1),
            datetime(2022, 1, 1),
            datetime(2022, 1, 8),
            datetime(2023, 1, 8),
        ),
        parameters={"rsi_len": 14},
        training_report=None,
        validation_report=None,
    )


def _summary(symbol: str, n_windows: int) -> WalkForwardSummary:
    return WalkForwardSummary(
        strategy="S01",
        symbol=symbol,
        windows=[_window() for _ in range(n_windows)],
    )


def test_pool_summaries_merges_windows():
    pooled = WalkForwardEngine.pool_summaries(
        "S01",
        [_summary("INFY", 2), _summary("TCS", 3)],
    )
    assert pooled.symbol == "2 SYMBOLS"
    assert len(pooled.windows) == 5


def test_pool_summaries_empty_is_zero_windows():
    pooled = WalkForwardEngine.pool_summaries("S01", [])
    assert len(pooled.windows) == 0


def _report(*, is_robust: bool) -> WalkForwardEfficiencyReport:
    return WalkForwardEfficiencyReport(
        annualized_is_return=30.0,
        annualized_oos_return=20.0 if is_robust else 5.0,
        wfe_pct=66.7 if is_robust else 16.7,
        is_robust=is_robust,
        plateau_stability_score=1.0 if is_robust else 0.0,
    )


def test_verdict_exit_code_robust_is_zero():
    assert WalkForwardEngine.verdict_exit_code(_report(is_robust=True), 5) == 0


def test_verdict_exit_code_overfit_is_one():
    assert WalkForwardEngine.verdict_exit_code(_report(is_robust=False), 5) == 1


def test_verdict_exit_code_zero_windows_is_two_even_if_robust():
    # Fail-closed: a report can never carry a robust verdict with no
    # completed windows, but the gate must not trust one even if it did.
    assert WalkForwardEngine.verdict_exit_code(_report(is_robust=True), 0) == 2


def test_zero_window_summary_reports_not_robust():
    report = WalkForwardEngine.evaluate_walk_forward_efficiency(
        WalkForwardEngine.pool_summaries("S01", []),
    )
    assert report.wfe_pct == 0.0
    assert report.is_robust is False
    assert "No walk-forward windows" in report.notes