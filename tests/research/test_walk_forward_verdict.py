"""Walk-forward verdict wiring: pool_summaries + verdict_exit_code.

Guards the fail-closed contract: a zero-window run must exit 2 (cannot
validate), an overfit run must exit 1, only a robust run may exit 0, and —
crucially — a run whose pooled out-of-sample trade count is below
MIN_POOLED_OOS_TRADES must read NOT ROBUST (a tiny OOS sample cannot
distinguish a real edge from noise).
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from mjonai.research.walk_forward.walk_forward_engine import (
    MIN_POOLED_OOS_TRADES,
    WalkForwardEngine,
)
from mjonai.research.walk_forward.walk_forward_models import (
    WalkForwardEfficiencyReport,
    WalkForwardResult,
    WalkForwardSummary,
    WalkForwardWindow,
)


def _window(*, validation_trades=None, is_return=10.0, oos_return=10.0):
    def _report(ret):
        return SimpleNamespace(performance=SimpleNamespace(annualized_return_pct=ret))

    return WalkForwardResult(
        window=WalkForwardWindow(
            datetime(2020, 1, 1),
            datetime(2022, 1, 1),
            datetime(2022, 1, 8),
            datetime(2023, 1, 8),
        ),
        parameters={"rsi_len": 14},
        training_report=_report(is_return),
        validation_report=_report(oos_return),
        validation_trades=validation_trades,
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


def _report(*, is_robust: bool, pooled_oos_trades: int = 0) -> WalkForwardEfficiencyReport:
    return WalkForwardEfficiencyReport(
        annualized_is_return=30.0,
        annualized_oos_return=20.0 if is_robust else 5.0,
        wfe_pct=66.7 if is_robust else 16.7,
        is_robust=is_robust,
        plateau_stability_score=1.0 if is_robust else 0.0,
        pooled_oos_trades=pooled_oos_trades,
    )


def test_verdict_exit_code_robust_is_zero():
    assert WalkForwardEngine.verdict_exit_code(_report(is_robust=True), 5) == 0


def test_verdict_exit_code_overfit_is_one():
    assert WalkForwardEngine.verdict_exit_code(_report(is_robust=False), 5) == 1


def test_verdict_exit_code_sample_too_small_is_one():
    # Sample-too-small is NOT robust — it must exit 1 (overfit family), never 0.
    report = _report(is_robust=False, pooled_oos_trades=MIN_POOLED_OOS_TRADES - 1)
    assert WalkForwardEngine.verdict_exit_code(report, 5) == 1


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
    assert report.pooled_oos_trades == 0
    assert "No walk-forward windows" in report.notes


# ── Pooled OOS trade-count floor ────────────────────────────────────────────


def test_wfe_sample_too_small_is_not_robust_never_wins():
    # 2 windows x 10 trades = 20 pooled < floor — even with WFE 100% and
    # positive OOS the verdict MUST be NOT ROBUST (noise indistinguishable).
    summary = WalkForwardSummary(
        strategy="S01",
        symbol="INFY",
        windows=[
            _window(validation_trades=[object() for _ in range(10)], is_return=30.0, oos_return=30.0),
            _window(validation_trades=[object() for _ in range(10)], is_return=30.0, oos_return=30.0),
        ],
    )
    report = WalkForwardEngine.evaluate_walk_forward_efficiency(summary)
    assert report.wfe_pct == 100.0
    assert report.pooled_oos_trades == 20
    assert report.is_robust is False
    assert "Sample too small" in report.notes
    assert f"{MIN_POOLED_OOS_TRADES}" in report.notes


def test_wfe_trades_one_below_floor_is_not_robust():
    # 29 pooled trades (< floor) → NOT ROBUST even with WFE 100%.
    summary = WalkForwardSummary(
        strategy="S01",
        symbol="INFY",
        windows=[
            _window(validation_trades=[object() for _ in range(MIN_POOLED_OOS_TRADES - 1)],
                    is_return=30.0, oos_return=30.0),
        ],
    )
    report = WalkForwardEngine.evaluate_walk_forward_efficiency(summary)
    assert report.pooled_oos_trades == MIN_POOLED_OOS_TRADES - 1
    assert report.is_robust is False
    assert "Sample too small" in report.notes


def test_wfe_trades_at_floor_is_admissible():
    # Exactly 30 pooled trades MEETS the floor: robust requires WFE/OOS to
    # also hold, but sample size alone no longer forces NOT ROBUST.
    summary = WalkForwardSummary(
        strategy="S01",
        symbol="INFY",
        windows=[
            _window(validation_trades=[object() for _ in range(MIN_POOLED_OOS_TRADES)],
                    is_return=30.0, oos_return=30.0),
        ],
    )
    report = WalkForwardEngine.evaluate_walk_forward_efficiency(summary)
    assert report.pooled_oos_trades == MIN_POOLED_OOS_TRADES
    assert report.is_robust is True


def test_wfe_trades_above_floor_can_be_robust():
    # 2 windows x 20 trades = 40 pooled >= floor, WFE 66.7%, OOS > 0 → robust.
    summary = WalkForwardSummary(
        strategy="S01",
        symbol="INFY",
        windows=[
            _window(validation_trades=[object() for _ in range(20)], is_return=30.0, oos_return=20.0),
            _window(validation_trades=[object() for _ in range(20)], is_return=30.0, oos_return=20.0),
        ],
    )
    report = WalkForwardEngine.evaluate_walk_forward_efficiency(summary)
    assert report.pooled_oos_trades == 40
    assert report.wfe_pct == pytest.approx(66.7, abs=0.1)
    assert report.is_robust is True
    assert "Robust" in report.notes


def test_wfe_floor_met_but_negative_oos_not_robust():
    # Floor met but OOS negative → NOT ROBUST (overfitting family).
    summary = WalkForwardSummary(
        strategy="S01",
        symbol="INFY",
        windows=[
            _window(validation_trades=[object() for _ in range(20)], is_return=30.0, oos_return=-5.0),
            _window(validation_trades=[object() for _ in range(20)], is_return=30.0, oos_return=-5.0),
        ],
    )
    report = WalkForwardEngine.evaluate_walk_forward_efficiency(summary)
    assert report.pooled_oos_trades == 40
    assert report.is_robust is False
    assert "Overfitting" in report.notes


def test_wfe_tally_ignores_missing_validation_trades():
    # Windows with validation_trades=None contribute 0 trades, never crash.
    summary = WalkForwardSummary(
        strategy="S01",
        symbol="INFY",
        windows=[
            _window(validation_trades=None, is_return=30.0, oos_return=20.0),
            _window(validation_trades=[object() for _ in range(5)], is_return=30.0, oos_return=20.0),
        ],
    )
    report = WalkForwardEngine.evaluate_walk_forward_efficiency(summary)
    assert report.pooled_oos_trades == 5
    assert report.is_robust is False
    assert "Sample too small" in report.notes