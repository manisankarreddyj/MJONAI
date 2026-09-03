import pytest
from execution.trade_efficiency import (
    calculate_trade_efficiency,
    TradeEfficiencyMetrics,
)


def test_trade_efficiency_perfect_run():
    """Verify Profit Capture Efficiency for a winning long trade with high MFE capture."""
    # Long Entry: 100, Exit: 108, MFE: 110, MAE: 99, SL: 95
    res = calculate_trade_efficiency(
        symbol="RELIANCE",
        entry_price=100.0,
        exit_price=108.0,
        initial_sl=95.0,
        mfe_price=110.0,
        mae_price=99.0,
        direction="LONG",
    )
    assert res.realized_pnl_pts == 8.0
    assert res.mfe_potential_pts == 10.0
    assert res.profit_capture_efficiency_pct == 80.0
    assert res.adverse_risk_ratio == 0.20  # 1 pt heat on 5 pt risk
    assert res.classification == "PERFECT_RUN"


def test_trade_efficiency_controlled_loss():
    """Verify Adverse Risk Ratio for a disciplined stop-loss exit."""
    # Long Entry: 100, Exit: 95, MFE: 101, MAE: 95, SL: 95
    res = calculate_trade_efficiency(
        symbol="TCS",
        entry_price=100.0,
        exit_price=95.0,
        initial_sl=95.0,
        mfe_price=101.0,
        mae_price=95.0,
        direction="LONG",
    )
    assert res.realized_pnl_pts == -5.0
    assert res.profit_capture_efficiency_pct == 0.0
    assert res.adverse_risk_ratio == 1.0  # Hit exact 1.0R stop loss
    assert res.classification == "CONTROLLED_LOSS"


def test_trade_efficiency_short_trade():
    """Verify Short direction MAE/MFE calculations."""
    # Short Entry: 200, Exit: 185, MFE: 180, MAE: 202, SL: 210
    res = calculate_trade_efficiency(
        symbol="INFY",
        entry_price=200.0,
        exit_price=185.0,
        initial_sl=210.0,
        mfe_price=180.0,
        mae_price=202.0,
        direction="SHORT",
    )
    assert res.realized_pnl_pts == 15.0
    assert res.mfe_potential_pts == 20.0
    assert res.profit_capture_efficiency_pct == 75.0
    assert res.adverse_risk_ratio == 0.20  # 2 pt heat on 10 pt risk
    assert res.classification == "PERFECT_RUN"
