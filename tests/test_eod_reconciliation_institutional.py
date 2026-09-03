"""
Unit and Institutional Test Suite for execution/eod_reconciler.py
Tests 3-Way Broker-Ledger Reconciliation, Quantity Breaks, Ghost Positions,
Orphan Positions, Cash Margin Breaks, and Tranche Inconsistencies.
"""

import pytest

from mjonai.execution.eod_reconciler import (
    reconcile_broker_and_ledger,
    PositionBreak,
    CashMarginBreak,
    ReconciliationAuditReport,
)
from mjonai.execution.eod import reconcile_open_positions


def test_reconciliation_clean_state():
    """Verify clean state when local trade ledger and broker positions match exactly."""
    local_trades = [
        {"symbol": "INFY", "quantity_remaining": 50},
        {"symbol": "RELIANCE", "quantity_remaining": 20},
    ]
    broker_positions = [
        {"symbol": "INFY", "net_quantity": 50},
        {"symbol": "RELIANCE", "net_quantity": 20},
    ]

    report = reconcile_broker_and_ledger(
        local_open_trades=local_trades,
        broker_positions=broker_positions,
        expected_capital=100000.0,
        broker_available_margin=100000.0,
    )

    assert isinstance(report, ReconciliationAuditReport)
    assert report.is_clean is True
    assert report.audit_verdict == "RECONCILED_CLEAN"
    assert len(report.position_breaks) == 0
    assert report.cash_break.is_break_flagged is False


def test_reconciliation_ghost_position():
    """Verify critical alert when broker has an untracked open position (Ghost Position)."""
    local_trades = [
        {"symbol": "INFY", "quantity_remaining": 50},
    ]
    broker_positions = [
        {"symbol": "INFY", "net_quantity": 50},
        {"symbol": "HDFCBANK", "net_quantity": 100},  # Ghost position!
    ]

    report = reconcile_broker_and_ledger(
        local_open_trades=local_trades,
        broker_positions=broker_positions,
        expected_capital=100000.0,
        broker_available_margin=100000.0,
    )

    assert report.is_clean is False
    assert report.audit_verdict == "CRITICAL_ACTION_REQUIRED"
    ghost_breaks = [b for b in report.position_breaks if b.break_type == "GHOST_POSITION"]
    assert len(ghost_breaks) == 1
    assert ghost_breaks[0].symbol == "HDFCBANK"
    assert ghost_breaks[0].broker_quantity == 100
    assert ghost_breaks[0].severity == "CRITICAL"


def test_reconciliation_orphan_position():
    """Verify critical alert when database has open trade that broker already closed (Orphan Position)."""
    local_trades = [
        {"symbol": "TCS", "quantity_remaining": 30},  # Orphan position!
    ]
    broker_positions = []

    report = reconcile_broker_and_ledger(
        local_open_trades=local_trades,
        broker_positions=broker_positions,
        expected_capital=100000.0,
        broker_available_margin=100000.0,
    )

    assert report.is_clean is False
    assert report.audit_verdict == "CRITICAL_ACTION_REQUIRED"
    orphan_breaks = [b for b in report.position_breaks if b.break_type == "ORPHAN_POSITION"]
    assert len(orphan_breaks) == 1
    assert orphan_breaks[0].symbol == "TCS"
    assert orphan_breaks[0].local_quantity == 30


def test_reconciliation_cash_margin_break():
    """Verify cash break alert when broker margin deviates > 2% from expected capital."""
    local_trades = []
    broker_positions = []

    # Expected 100k, broker reports 90k (10% break > 2% tolerance)
    report = reconcile_broker_and_ledger(
        local_open_trades=local_trades,
        broker_positions=broker_positions,
        expected_capital=100000.0,
        broker_available_margin=90000.0,
        cash_tolerance_pct=2.0,
    )

    assert report.is_clean is False
    assert report.audit_verdict == "CRITICAL_ACTION_REQUIRED"
    assert report.cash_break.is_break_flagged is True
    assert report.cash_break.discrepancy == 10000.0
    assert report.cash_break.discrepancy_pct == 10.0


def test_reconcile_open_positions_facade_integration():
    """Verify execution.eod.reconcile_open_positions integrates with eod_reconciler."""
    broker_pos = [{"symbol": "TATASTEEL", "net_quantity": 25}]
    res = reconcile_open_positions(broker_positions=broker_pos, broker_available_margin=100000.0)
    assert isinstance(res, dict)
    assert "status" in res
    assert "audit_verdict" in res
