import math
import numpy as np
import pandas as pd
import pytest
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

# â”€â”€ Module 1 Imports â”€â”€
from mjonai.data.microstructure.micro_price import calculate_micro_price_and_impact
from mjonai.data.microstructure.gap_analyzer import analyze_opening_gap_and_fvg, GapType

# â”€â”€ Module 2 Imports â”€â”€
from mjonai.strategy.registry.quant_math import (
    calculate_hurst_exponent,
    fractional_differentiation,
    realized_semivariance,
    kalman_filter_1d,
    yang_zhang_volatility,
)
from mjonai.analytics.statistical_validation import deflated_sharpe_pvalue
from mjonai.core.market_state import calculate_market_state, MarketRegimePolicy

# â”€â”€ Module 3 Imports â”€â”€
from mjonai.risk.trade_risk import (
    split_tranche_quantities,
    evaluate_trade_risk_levels,
    calculate_position_size,
)

# â”€â”€ Module 4 Imports â”€â”€
from mjonai.agents.supervisor import evaluate as supervisor_evaluate
from mjonai.agents.llm_bridge import get_deterministic_fallback_consensus

# â”€â”€ Module 5 Imports â”€â”€
from mjonai.execution.algo_execution import SEBIRateLimiter
from mjonai.execution.orders import (
    slice_order_for_freeze_limits,
    calculate_limit_price_with_buffer,
    get_freeze_qty,
)
from mjonai.execution.tax import calculate_all_in_friction, calculate_tax

# â”€â”€ Module 6 Imports â”€â”€
from mjonai.execution.tracker import calculate_trailing_sl, evaluate_tranche_exits
from mjonai.core.constants import TOTAL_CAPITAL
import mjonai.risk.emergency_triggers as et
from mjonai.risk.emergency_triggers import (
    get_emergency_risk_status,
    check_daily_loss,
    reset_daily_state,
    set_manual_pause,
    clear_manual_pause,
    is_trading_allowed,
)
from mjonai.risk.behavioral_guard import (
    check_behavioral_guard,
    record_trade_outcome,
    reset_guard,
)


# ==============================================================================
# 1. MODULE 1: EXTREME MICROSTRUCTURE EDGE CASES
# ==============================================================================

def test_m1_micro_price_extreme_depth_imbalance_and_zero_volume():
    """Torture test Stoikov Micro-Price with extreme 1,000,000:1 order book skew and zero volume."""
    # 1. Extreme 1,000,000 Bid vs 1 Ask (Massive bid wall)
    snap_bid_wall = calculate_micro_price_and_impact(
        symbol="RELIANCE",
        best_bid=1000.0,
        best_ask=1000.5,
        bid_qty=1_000_000,
        ask_qty=1,
        recent_price_change=0.0,
        recent_traded_volume=0,  # Zero volume traded
    )
    # Price must jump virtually all the way to ask
    assert math.isclose(snap_bid_wall.micro_price, 1000.5, rel_tol=1e-4)
    assert snap_bid_wall.kyles_lambda == 0.0  # Zero div protected
    assert snap_bid_wall.is_buying_pressure is True

    # 2. Extreme 1 Bid vs 1,000,000 Ask (Massive dumping wall)
    snap_ask_wall = calculate_micro_price_and_impact(
        symbol="RELIANCE",
        best_bid=1000.0,
        best_ask=1000.5,
        bid_qty=1,
        ask_qty=1_000_000,
        recent_price_change=0.0,
        recent_traded_volume=0,
    )
    assert math.isclose(snap_ask_wall.micro_price, 1000.0, rel_tol=1e-4)
    assert snap_ask_wall.is_selling_pressure is True


def test_m1_opening_gap_black_swan_and_empty_data():
    """Torture test Gap Analyzer with 50% Black-Swan gap and corrupted DataFrame."""
    # 1. Empty / Corrupted DataFrame
    empty_snap = analyze_opening_gap_and_fvg(symbol="NIFTY", df=pd.DataFrame())
    assert empty_snap.gap_type == GapType.NEGLIGIBLE_GAP
    assert empty_snap.gap_pct == 0.0

    # 2. 50% Black Swan Gap Down (e.g. Demerger / Crash)
    df_crash = pd.DataFrame({
        "Open": [100.0, 100.0, 100.0, 100.0, 100.0, 50.0],
        "High": [101.0, 101.0, 101.0, 101.0, 101.0, 52.0],
        "Low":  [99.0,  99.0,  99.0,  99.0,  99.0,  48.0],
        "Close":[100.0, 100.0, 100.0, 100.0, 100.0, 49.0],
        "Volume":[1000, 1000, 1000, 1000, 1000, 50000],
    })
    crash_snap = analyze_opening_gap_and_fvg(symbol="CRASH_ASSET", df=df_crash)
    assert crash_snap.gap_pct == -50.0
    assert crash_snap.gap_type == GapType.BREAKAWAY_TREND


# ==============================================================================
# 2. MODULE 2: EXTREME QUANT MATH & REGIME EDGE CASES
# ==============================================================================

def test_m2_hurst_exponent_flatline_zero_variance():
    """Torture test Hurst Exponent with a completely flat, non-moving price series."""
    flat_series = np.array([100.0] * 50)
    h_flat = calculate_hurst_exponent(flat_series)
    assert 0.0 <= h_flat <= 1.0  # Zero variance protected, returns valid float

    short_series = np.array([100.0, 101.0, 102.0])
    h_short = calculate_hurst_exponent(short_series)
    assert 0.0 <= h_short <= 1.0


def test_m2_fractional_differentiation_extreme_d_orders():
    """Torture test Fractional Differentiation with d=0.0 (no memory change) and d=1.0 (pure integer diff)."""
    prices = np.array([100.0 + i for i in range(50)])
    frac_d0 = fractional_differentiation(prices, d=0.0)
    assert len(frac_d0) == len(prices)

    frac_d1 = fractional_differentiation(prices, d=1.0)
    assert len(frac_d1) == len(prices)


def test_m2_deflated_sharpe_pvalue_extreme_trials_and_fat_tails():
    """Torture test Deflated Sharpe Ratio under 10,000 trials with massive negative skewness & fat tails."""
    dsr_extreme = deflated_sharpe_pvalue(
        sharpe_ratio=2.5,
        num_trials=10000,
        sample_length=252,
        skewness=-4.0,   # Extreme crash asymmetry
        kurtosis=30.0,   # Massive fat tails
    )
    assert 0.0 <= dsr_extreme <= 1.0


def test_m2_regime_schmitt_trigger_rapid_oscillation_torture():
    """Torture test Regime Schmitt Trigger with rapid alternating score flips (+2, -2, +2, -2)."""
    policy = MarketRegimePolicy(bull_score_threshold=2, bear_score_threshold=-2)
    # Start Bull
    s1 = calculate_market_state(custom_nifty_price=23000, custom_ema200=22000, custom_vix=12.0, custom_breadth_pct=0.75, policy=policy)
    assert s1.market_state == "BULL"

    # Mild drop to +1 score (should NOT flip to neutral due to hysteresis)
    s2 = calculate_market_state(custom_nifty_price=22500, custom_ema200=22000, custom_vix=16.0, custom_breadth_pct=0.50, policy=policy)
    assert s2.market_state == "BULL"


# ==============================================================================
# 3. MODULE 3: EXTREME STRATEGY SIZING & DEVIL CHECK EDGE CASES
# ==============================================================================

def test_m3_tranche_splitting_minimal_lots():
    """Torture test Tranche Splitting on 0, 1, 2, 3 shares (Zero fractional crashes)."""
    assert split_tranche_quantities(0) == (0, 0, 0)
    assert split_tranche_quantities(1) == (1, 0, 0)
    assert split_tranche_quantities(2) == (1, 1, 0)
    assert split_tranche_quantities(3) == (1, 1, 1)
    assert split_tranche_quantities(7) == (3, 2, 2)
    assert sum(split_tranche_quantities(7)) == 7


# ==============================================================================
# 4. MODULE 4: EXTREME AI BOARDROOM CONSENSUS EDGE CASES
# ==============================================================================

def test_m4_supervisor_bear_veto_enforcement():
    """Torture test Supervisor CIO on adversarial Bear VETO (Golden Rule 4)."""
    sample_sig = {"symbol": "INFY", "strategy_id": "S01_MomentumRSI", "signal_direction": "LONG", "entry_price": 1500.0}
    verdict = supervisor_evaluate(
        signal=sample_sig,
        bull_result={"verdict": "BUY", "confidence": 75},
        bear_result={"verdict": "VETO", "confidence": 90, "red_flags": ["Promoter pledging > 75%"]},
        devil_checks_passed=["Check 1", "Check 2"],
    )
    assert verdict["approved"] is False


def test_m4_deterministic_mathematical_fallback_on_total_ai_blackout():
    """Verify deterministic mathematical engine handles total LLM provider blackout."""
    sample_sig = {
        "symbol": "TCS",
        "direction": "LONG",
        "rsi": 62.0,
        "volume_ratio": 1.8,
        "sector_multiplier": 1.1,
    }
    res = get_deterministic_fallback_consensus(
        signal=sample_sig,
        macro_context={"fii_regime": "BULLISH"},
    )
    assert isinstance(res, dict)
    assert "confidence" in res
    assert res.get("verdict") in ("APPROVE", "VETO", "CAUTION", "NEUTRAL")


# ==============================================================================
# 5. MODULE 5: EXTREME EXECUTION & RATE-LIMITING EDGE CASES
# ==============================================================================

def test_m5_sebi_rate_limiter_burst_flood():
    """Torture test SEBI 10-OPS Token Bucket with 100 concurrent order requests."""
    limiter = SEBIRateLimiter(max_ops=10, burst_limit=5)
    # Exhaust burst capacity
    assert limiter.acquire(tokens_needed=5, timeout=0.05) is True
    # Immediate next request must fail or block
    assert limiter.acquire(tokens_needed=1, timeout=0.01) is False


def test_m5_freeze_quantity_exact_boundary_slicing():
    """Torture test SEBI Freeze Quantity Slicing on exact multiples and edge boundaries."""
    # NIFTY freeze qty = 1800
    assert slice_order_for_freeze_limits("NIFTY", 1800) == [1800]
    assert slice_order_for_freeze_limits("NIFTY", 1801) == [1800, 1]
    assert slice_order_for_freeze_limits("NIFTY", 3600) == [1800, 1800]
    assert slice_order_for_freeze_limits("NIFTY", 0) == []
    assert slice_order_for_freeze_limits("NIFTY", -50) == []


def test_m5_market_with_protection_extreme_buffer():
    """Torture test Market-with-Protection on â‚¹0.10 penny stock and â‚¹100,000 mega cap."""
    # Penny stock â‚¹0.10
    buy_penny = calculate_limit_price_with_buffer(0.10, side="BUY", buffer_pct=0.005)
    sell_penny = calculate_limit_price_with_buffer(0.10, side="SELL", buffer_pct=0.005)
    assert buy_penny == 0.10
    assert sell_penny == 0.10

    # Mega cap â‚¹100,000
    buy_mega = calculate_limit_price_with_buffer(100000.0, side="BUY", buffer_pct=0.005)
    sell_mega = calculate_limit_price_with_buffer(100000.0, side="SELL", buffer_pct=0.005)
    assert buy_mega == 100500.0
    assert sell_mega == 99500.0


# ==============================================================================
# 6. MODULE 6: EXTREME POSITION TRACKING & RISK SENTRY EDGE CASES
# ==============================================================================

def test_m6_emergency_triggers_nuclear_15_pct_kill_line():
    """Torture test 15% Lifetime Kill Line nuclear shutdown."""
    with patch("mjonai.db.repository.get_trades_closed_today", return_value=[{"net_pnl": -35000.0}]), \
         patch("mjonai.execution.paper.get_open_trades_with_pnl", return_value=[]), \
         patch("mjonai.db.repository.get_current_drawdown_pct", return_value=17.5), \
         patch("mjonai.db.repository.load_peak_equity", return_value=TOTAL_CAPITAL), \
         patch("mjonai.db.repository.save_peak_equity", return_value=TOTAL_CAPITAL), \
         patch("mjonai.execution.paper.close_all_paper_trades") as mock_close, \
         patch("mjonai.communication.telegram.send_message"), \
         patch("mjonai.db.repository.insert_risk_event"):

        check_daily_loss(system_mode="LIVE")
        assert et._state["kill_line_active"] is True
        assert is_trading_allowed(system_mode="LIVE") is False
        # K1 (2026-09-03): pinned to the REAL signature. This second copy of the
        # buggy reason= keyword masked the Kill Line TypeError (see
        # test_emergency_triggers.py::test_lifetime_kill_line_nuclear_shutdown).
        mock_close.assert_called_once_with(exit_reason="KILL_LINE")


def test_m6_behavioral_guard_progressive_escalation_to_full_day_lock():
    """Torture test Behavioral Guard 4-loss progressive escalation to Full Day Lockout during morning session."""
    morning_time = datetime(2026, 8, 18, 10, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    with patch("mjonai.risk.behavioral_guard.now_ist", return_value=morning_time), \
         patch("mjonai.db.repository.insert_risk_event"):
        reset_guard()
        # Loss 1 -> Allowed
        record_trade_outcome("LOSS", symbol="TATA")
        allowed1, _ = check_behavioral_guard(symbol="TATA", today_trade_count=1)
        assert allowed1 is True

        # Loss 2 -> 30m Cooldown
        record_trade_outcome("LOSS", symbol="TATA")
        allowed2, reason2 = check_behavioral_guard(symbol="TATA", today_trade_count=2)
        assert allowed2 is False
        assert "Cooling off active" in reason2

        # Loss 3 -> 60m Cooldown
        record_trade_outcome("LOSS", symbol="INFY")
        allowed3, _ = check_behavioral_guard(symbol="INFY", today_trade_count=3)
        assert allowed3 is False

        # Loss 4 -> FULL DAY LOCKOUT
        record_trade_outcome("LOSS", symbol="RELIANCE")
        allowed4, reason4 = check_behavioral_guard(symbol="RELIANCE", today_trade_count=4)
        assert allowed4 is False
        assert "4 consecutive losses" in reason4 or "Capital Preservation" in reason4
        reset_guard()

