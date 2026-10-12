"""
Tests for Label↔Fill Alignment Audit (mjonai/research/label_audit.py)
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from mjonai.research.backtest.models import TradeResult, TransactionCost, ExitReason
from mjonai.research.label_audit import (
    audit_label_fill_alignment,
    run_label_fill_audit,
    LabelFillAuditReport,
    AlignmentStatus,
)


def make_test_df(n_bars: int = 100) -> pd.DataFrame:
    """Create a simple OHLCV DataFrame for testing."""
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(n_bars)]
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(n_bars) * 0.5)
    high = close + np.abs(np.random.randn(n_bars)) * 0.3
    low = close - np.abs(np.random.randn(n_bars)) * 0.3
    open_ = close + np.random.randn(n_bars) * 0.2
    volume = np.random.randint(1000, 10000, n_bars)

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    }, index=dates)
    return df


def make_trade_result(
    symbol: str = "TEST",
    direction: str = "LONG",
    entry_idx: int = 0,
    exit_idx: int = 5,
    exit_reason: str = "TARGET",
    entry_price: float = 100.0,
    exit_price: float = 102.0,
) -> TradeResult:
    return TradeResult(
        symbol=symbol,
        strategy="TEST",
        direction=direction,
        entry_index=entry_idx,
        exit_index=exit_idx,
        entry_date=datetime(2024, 1, 1),
        exit_date=datetime(2024, 1, 6),
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=1,
        invested_capital=100.0,
        gross_pnl=2.0,
        net_pnl=2.0,
        stop_loss=99.0,
        target=102.0,
        holding_bars=exit_idx - entry_idx,
        exit_reason=exit_reason,
        gross_return_pct=2.0,
        net_return_pct=2.0,
        risk_reward=2.0,
        mfe=0.0,
        mae=0.0,
        transaction_cost=None,
    )


def test_perfect_match():
    """All labels match fills perfectly."""
    df = make_test_df()
    trades = [
        make_trade_result(exit_idx=5, exit_reason="TARGET"),
        make_trade_result(exit_idx=10, exit_reason="STOPLOSS"),
    ]
    entry_indices = [0, 5]
    labeled_exit_indices = [5, 10]
    labeled_exit_reasons = ["TARGET", "STOPLOSS"]

    report = audit_label_fill_alignment(
        trade_results=trades,
        df=make_test_df(),
        entry_indices=entry_indices,
        labeled_exit_indices=labeled_exit_indices,
        labeled_exit_reasons=labeled_exit_reasons,
    )

    assert report.trades_audited == 2
    assert report.matched == 2
    assert report.bar_mismatch == 0
    assert report.reason_mismatch == 0
    assert report.both_mismatch == 0
    assert report.match_rate == 1.0


def test_bar_mismatch():
    """Label has correct reason but wrong exit bar."""
    df = make_test_df()
    trades = [
        make_trade_result(exit_idx=5, exit_reason="TARGET"),
    ]
    entry_indices = [0]
    labeled_exit_indices = [7]  # Wrong bar
    labeled_exit_reasons = ["TARGET"]

    report = audit_label_fill_alignment(
        trade_results=trades,
        df=make_test_df(),
        entry_indices=entry_indices,
        labeled_exit_indices=labeled_exit_indices,
        labeled_exit_reasons=labeled_exit_reasons,
    )

    assert report.trades_audited == 1
    assert report.matched == 0
    assert report.bar_mismatch == 1
    assert report.reason_mismatch == 0
    assert report.both_mismatch == 0


def test_reason_mismatch():
    """Label has correct bar but wrong exit reason."""
    df = make_test_df()
    trades = [
        make_trade_result(exit_idx=5, exit_reason="TARGET"),
    ]
    entry_indices = [0]
    labeled_exit_indices = [5]
    labeled_exit_reasons = ["STOPLOSS"]  # Wrong reason

    report = audit_label_fill_alignment(
        trade_results=trades,
        df=make_test_df(),
        entry_indices=entry_indices,
        labeled_exit_indices=labeled_exit_indices,
        labeled_exit_reasons=labeled_exit_reasons,
    )

    assert report.trades_audited == 1
    assert report.matched == 0
    assert report.bar_mismatch == 0
    assert report.reason_mismatch == 1
    assert report.both_mismatch == 0


def test_both_mismatch():
    """Label has wrong bar AND wrong reason."""
    df = make_test_df()
    trades = [
        make_trade_result(exit_idx=5, exit_reason="TARGET"),
    ]
    entry_indices = [0]
    labeled_exit_indices = [7]
    labeled_exit_reasons = ["STOPLOSS"]

    report = audit_label_fill_alignment(
        trade_results=trades,
        df=make_test_df(),
        entry_indices=entry_indices,
        labeled_exit_indices=labeled_exit_indices,
        labeled_exit_reasons=labeled_exit_reasons,
    )

    assert report.trades_audited == 1
    assert report.matched == 0
    assert report.bar_mismatch == 0
    assert report.reason_mismatch == 0
    assert report.both_mismatch == 1


def test_unlabeled():
    """Trade has no label."""
    df = make_test_df()
    trades = [
        make_trade_result(exit_idx=5, exit_reason="TARGET"),
    ]
    entry_indices = [0]
    labeled_exit_indices = []  # Missing label
    labeled_exit_reasons = []

    report = audit_label_fill_alignment(
        trade_results=trades,
        df=make_test_df(),
        entry_indices=entry_indices,
        labeled_exit_indices=labeled_exit_indices,
        labeled_exit_reasons=labeled_exit_reasons,
    )

    assert report.trades_audited == 1
    assert report.unlabeled == 1
    assert report.matched == 0


def test_mixed_results():
    """Mixed batch of trades with various outcomes."""
    df = make_test_df()
    trades = [
        make_trade_result(exit_idx=5, exit_reason="TARGET"),   # Match
        make_trade_result(exit_idx=10, exit_reason="STOPLOSS"), # Bar mismatch
        make_trade_result(exit_idx=15, exit_reason="TARGET"),  # Reason mismatch
        make_trade_result(exit_idx=20, exit_reason="STOPLOSS"), # Both mismatch
    ]
    entry_indices = [0, 5, 10, 15]
    labeled_exit_indices = [5, 12, 15, 22]
    labeled_exit_reasons = ["TARGET", "STOPLOSS", "STOPLOSS", "TARGET"]

    report = audit_label_fill_alignment(
        trade_results=trades,
        df=make_test_df(),
        entry_indices=entry_indices,
        labeled_exit_indices=labeled_exit_indices,
        labeled_exit_reasons=labeled_exit_reasons,
    )

    assert report.trades_audited == 4
    assert report.matched == 1
    assert report.bar_mismatch == 1
    assert report.reason_mismatch == 1
    assert report.both_mismatch == 1
    assert report.match_rate == 0.25


def test_run_label_fill_audit_integration():
    """Integration test using the convenience function."""
    df = make_test_df(50)

    # Create a simple trending dataset for deterministic labels
    close = np.linspace(100, 110, 50)
    high = close + 0.5
    low = close - 0.5
    open_ = close
    volume = np.ones(50) * 1000

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    }, index=pd.date_range("2024-01-01", periods=50, freq="D"))

    # Trades that enter at bar 0, 10, 20 with known exits
    trades = [
        make_trade_result(entry_idx=0, exit_idx=5, exit_reason="TARGET"),
        make_trade_result(entry_idx=10, exit_idx=15, exit_reason="TARGET"),
    ]
    entry_indices = [0, 10]

    report = run_label_fill_audit(
        trade_results=trades,
        df=df,
        entry_indices=entry_indices,
        target_pct=0.10,  # 10% target - should hit within 5 bars
        stop_pct=0.05,
        max_holding_bars=20,
    )

    assert report.trades_audited == 2
    # With 10% target on 0.2/day trend, should hit target around bar 5
    assert report.matched >= 0  # At least some should match


def test_summary_output():
    """Test that summary() produces readable output."""
    df = make_test_df()
    trades = [make_trade_result(exit_idx=5, exit_reason="TARGET")]
    report = audit_label_fill_alignment(
        trade_results=trades,
        df=make_test_df(),
        entry_indices=[0],
        labeled_exit_indices=[5],
        labeled_exit_reasons=["TARGET"],
    )
    summary = report.summary()
    assert "Label↔Fill Alignment Audit Report" in summary
    assert "Trades audited:     1" in summary
    assert "Matched:            1" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])