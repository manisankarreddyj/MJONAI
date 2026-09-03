"""
Unit and Institutional Test Suite for risk/devil_checks.py
Tests 8 Deterministic Veto Checks, Bidirectional Short Math,
Multi-Asset Underlying Extraction, and DevilCheckResult Contracts.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from risk.devil_checks import (
    DevilCheckResult,
    check_gap_risk,
    check_liquidity,
    check_data_quality,
    check_pattern_memory,
    check_correlation,
    check_real_rr,
    check_portfolio_limits,
    check_event_risk,
    run_all_devil_checks,
    evaluate_devil_checks,
)


# ── 1. CONTRACT TESTS ────────────────────────────────────────────────────────

def test_devil_check_result_contract():
    """Verify DevilCheckResult dataclass serializes cleanly to dict."""
    res = DevilCheckResult(
        all_passed=True,
        failure_reason="All 8 devil checks run",
        passed_checks=["Gap Risk", "Liquidity"],
        failed_checks=[],
        details={"Gap Risk": "Acceptable"},
    )
    d = res.to_dict()
    assert d["all_passed"] is True
    assert len(d["passed_checks"]) == 2


# ── 2. INDIVIDUAL CHECK TESTS ────────────────────────────────────────────────

def test_check_gap_risk():
    """Verify check_gap_risk approves within threshold and rejects beyond 1.5x."""
    # SL distance = 10. Expected move = 5 (0.5x) -> Pass
    passed, _ = check_gap_risk(sl_distance=10.0, expected_overnight_move=5.0)
    assert passed is True

    # SL distance = 10. Expected move = 16 (1.6x > 1.5x) -> Fail
    passed, reason = check_gap_risk(sl_distance=10.0, expected_overnight_move=16.0)
    assert passed is False
    assert "exceeds" in reason


def test_check_liquidity():
    """Verify check_liquidity rejects spreads > 0.5%."""
    assert check_liquidity(0.15)[0] is True
    assert check_liquidity(0.60)[0] is False


def test_check_data_quality():
    """Verify check_data_quality rejects score < 85%."""
    assert check_data_quality(95.0)[0] is True
    assert check_data_quality(80.0)[0] is False


def test_check_pattern_memory():
    """Verify check_pattern_memory vetoes setups with 3+ recent failures."""
    with patch("db.repository.get_pattern_failures", return_value=3):
        passed, reason = check_pattern_memory("hash_xyz", lookback_days=90)
        assert passed is False
        assert "failed 3 times" in reason

    with patch("db.repository.get_pattern_failures", return_value=1):
        assert check_pattern_memory("hash_xyz")[0] is True


def test_check_correlation_with_underlying_extraction():
    """Verify check_correlation identifies same-sector holdings even across options."""
    open_trades = [{"symbol": "HDFCBANK", "entry_price": 1500, "quantity": 10}]

    # ICICIBANK is same sector (BANKING) -> Fail correlation
    passed, reason = check_correlation("ICICIBANK", open_trades)
    assert passed is False
    assert "High correlation" in reason

    # TCS is IT sector -> Pass correlation
    passed, _ = check_correlation("TCS", open_trades)
    assert passed is True


def test_check_real_rr_bidirectional():
    """Verify check_real_rr for both LONG/BUY and SHORT/SELL directions."""
    # LONG: Entry 100, SL 95 (Risk 5), Target 115 (Reward 15), Cost 1.0 -> Net Reward 14 / Net Risk 6 = 2.33 -> Pass
    passed_long, _ = check_real_rr(entry=100.0, stop_loss=95.0, target=115.0, total_cost=10.0, quantity=10, direction="BUY")
    assert passed_long is True

    # SHORT: Entry 100, SL 105 (Risk 5), Target 85 (Reward 15), Cost 1.0 -> Net Reward 14 / Net Risk 6 = 2.33 -> Pass
    passed_short, _ = check_real_rr(entry=100.0, stop_loss=105.0, target=85.0, total_cost=10.0, quantity=10, direction="SELL")
    assert passed_short is True

    # Bad RR: Entry 100, SL 95 (Risk 5), Target 105 (Reward 5) -> RR ~ 0.8 < 2.0 -> Fail
    passed_bad, _ = check_real_rr(entry=100.0, stop_loss=95.0, target=105.0, total_cost=10.0, quantity=10, direction="BUY")
    assert passed_bad is False


def test_check_portfolio_limits():
    """Verify check_portfolio_limits rejects when positions >= 5 or capital >= 80%."""
    # 5 positions open -> Fail
    open_5 = [{"symbol": f"SYM_{i}"} for i in range(5)]
    assert check_portfolio_limits(open_5, growth_pool_deployed_pct=30.0)[0] is False

    # Capital deployed 85% -> Fail
    assert check_portfolio_limits([], growth_pool_deployed_pct=85.0)[0] is False

    # 2 positions and 40% deployed -> Pass
    assert check_portfolio_limits(open_5[:2], growth_pool_deployed_pct=40.0)[0] is True


def test_check_event_risk():
    """Verify check_event_risk blocks signals within 4 hours of high-impact events."""
    events = [{"name": "RBI Rate Decision", "hours_away": 2.5, "impact": "HIGH"}]
    passed, reason = check_event_risk(events, block_hours=4.0)
    assert passed is False
    assert "RBI Rate Decision" in reason

    # 6 hours away -> Pass
    events_safe = [{"name": "RBI Rate Decision", "hours_away": 6.0, "impact": "HIGH"}]
    assert check_event_risk(events_safe, block_hours=4.0)[0] is True


# ── 3. MASTER ORCHESTRATION TESTS ────────────────────────────────────────────

def test_run_all_devil_checks_live_vs_research():
    """Verify LIVE mode vetoes on failure while RESEARCH mode warns."""
    bad_signal = {
        "symbol": "RELIANCE",
        "entry_price": 2500.0,
        "stop_loss": 2490.0,
        "target": 2505.0,  # Bad RR (< 2.0)
        "quantity": 10,
        "total_cost": 50.0,
        "strategy_id": "ORB_15M",
    }

    # LIVE mode -> Hard VETO
    passed_live, reason_live, _ = run_all_devil_checks(
        signal=bad_signal,
        open_trades=[],
        system_mode="LIVE",
    )
    assert passed_live is False
    assert "Real RR" in reason_live

    # RESEARCH mode -> Passes with warning
    passed_res, _, checks = run_all_devil_checks(
        signal=bad_signal,
        open_trades=[],
        system_mode="RESEARCH",
    )
    assert passed_res is True
    assert any("Real RR*" in c for c in checks)
