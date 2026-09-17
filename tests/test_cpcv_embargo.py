"""
Test Suite: tests/test_cpcv_embargo.py
Purpose: Verify Combinatorial Purged Cross-Validation (CPCV), embargo margins,
         and Walk-Forward Efficiency (WFE %) robustness evaluations.
"""

from datetime import datetime, timedelta
import pytest

from mjonai.research.walk_forward.walk_forward_windows import WalkForwardWindowGenerator
from mjonai.research.walk_forward.walk_forward_models import WalkForwardSummary, WalkForwardResult, WalkForwardWindow
from mjonai.research.walk_forward.walk_forward_engine import WalkForwardEngine
from mjonai.analytics.models import PerformanceReport, PerformanceStatistics, TradeStatistics, EquityStatistics, EquityCurve


def test_cpcv_combinatorial_fold_count():
    """Verify nCk combination count for CPCV folds."""
    gen = WalkForwardWindowGenerator()
    start = datetime(2020, 1, 1)
    end = datetime(2025, 1, 1)

    # 5 partitions choosing 2 test blocks -> 5C2 = 10 folds
    folds = gen.generate_cpcv_folds(start=start, end=end, n_partitions=5, k_test_partitions=2)
    assert len(folds) == 10
    for f in folds:
        assert len(f.test_intervals) == 2
        assert 1 <= len(f.embargo_intervals) <= 2
        assert len(f.train_intervals) >= 1


def test_cpcv_zero_lookahead_leakage_and_embargo():
    """Verify that training intervals never overlap with test, purge, or embargo intervals."""
    gen = WalkForwardWindowGenerator()
    start = datetime(2020, 1, 1)
    end = datetime(2023, 1, 1)

    folds = gen.generate_cpcv_folds(start=start, end=end, n_partitions=4, k_test_partitions=1, embargo_days=10, purge_days=5)
    assert len(folds) == 4

    for f in folds:
        for t_start, t_end in f.test_intervals:
            for tr_start, tr_end in f.train_intervals:
                # No overlap between train and test
                assert not (tr_start < t_end and tr_end > t_start), f"Train [{tr_start}, {tr_end}] overlapped test [{t_start}, {t_end}]"

        for e_start, e_end in f.embargo_intervals:
            for tr_start, tr_end in f.train_intervals:
                # No overlap between train and embargo
                assert not (tr_start < e_end and tr_end > e_start), f"Train [{tr_start}, {tr_end}] overlapped embargo [{e_start}, {e_end}]"


def test_walk_forward_efficiency_calculation():
    """Verify WFE% calculation and robustness certification threshold (WFE >= 50%)."""
    from unittest.mock import MagicMock

    from mjonai.research.walk_forward.walk_forward_engine import MIN_POOLED_OOS_TRADES

    def make_perf_report(ann_return: float):
        return MagicMock(performance=MagicMock(annualized_return_pct=ann_return))

    def make_trades(n: int):
        # WFE counts pooled OOS trades; the "robust" fixture needs enough to
        # clear the statistical floor (see MIN_POOLED_OOS_TRADES).
        return [MagicMock() for _ in range(n)]

    # Robust strategy: IS = 30%, OOS = 20% -> WFE = 66.7% (>= 50%), and the
    # pooled OOS trade count clears the statistical floor.
    w1 = WalkForwardResult(
        window=WalkForwardWindow(datetime(2020, 1, 1), datetime(2022, 1, 1), datetime(2022, 1, 8), datetime(2023, 1, 8)),
        parameters={"rsi_len": 14},
        training_report=make_perf_report(30.0),
        validation_report=make_perf_report(20.0),
        validation_trades=make_trades(MIN_POOLED_OOS_TRADES),
    )
    summary_robust = WalkForwardSummary(strategy="S01", symbol="INFY", windows=[w1])
    rep_robust = WalkForwardEngine.evaluate_walk_forward_efficiency(summary_robust)
    assert rep_robust.wfe_pct == pytest.approx(66.67, 0.1)
    assert rep_robust.pooled_oos_trades == MIN_POOLED_OOS_TRADES
    assert rep_robust.is_robust is True
    assert rep_robust.plateau_stability_score == 1.0

    # Overfitted strategy: IS = 40%, OOS = 10% -> WFE = 25.0% (< 50%)
    w2 = WalkForwardResult(
        window=WalkForwardWindow(datetime(2020, 1, 1), datetime(2022, 1, 1), datetime(2022, 1, 8), datetime(2023, 1, 8)),
        parameters={"rsi_len": 14},
        training_report=make_perf_report(40.0),
        validation_report=make_perf_report(10.0),
        validation_trades=make_trades(MIN_POOLED_OOS_TRADES),
    )
    summary_overfit = WalkForwardSummary(strategy="S01", symbol="INFY", windows=[w2])
    rep_overfit = WalkForwardEngine.evaluate_walk_forward_efficiency(summary_overfit)
    assert rep_overfit.wfe_pct == pytest.approx(25.0, 0.1)
    assert rep_overfit.is_robust is False

    # Sample-too-small: WFE 66.7% with ZERO pooled OOS trades must read
    # NOT ROBUST — a tiny sample cannot certify an edge.
    w3 = WalkForwardResult(
        window=WalkForwardWindow(datetime(2020, 1, 1), datetime(2022, 1, 1), datetime(2022, 1, 8), datetime(2023, 1, 8)),
        parameters={"rsi_len": 14},
        training_report=make_perf_report(30.0),
        validation_report=make_perf_report(20.0),
        validation_trades=None,
    )
    summary_thin = WalkForwardSummary(strategy="S01", symbol="INFY", windows=[w3])
    rep_thin = WalkForwardEngine.evaluate_walk_forward_efficiency(summary_thin)
    assert rep_thin.wfe_pct == pytest.approx(66.67, 0.1)
    assert rep_thin.pooled_oos_trades == 0
    assert rep_thin.is_robust is False
    assert "Sample too small" in rep_thin.notes
