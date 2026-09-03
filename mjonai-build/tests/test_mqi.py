"""
12-Dimensional Production Test Suite for core/mqi.py
Tests Unit, Integration, Fault Injection, Financial Correctness, Invariants,
Performance Latency, Concurrency, and Observability.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
import math
import pytest
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from core.mqi import (
    MQILevel,
    MQISnapshot,
    EventRiskType,
    ExecutionThrottleMode,
    DataQuality,
    SessionPhase,
    calculate_mqi,
    get_cached_mqi,
    update_intraday_mqi,
    reset_mqi_cache,
    get_event_proximity_score,
    get_atr_score,
    get_vix_change_score,
    is_strategy_allowed_for_mqi,
    normalize_mqi_level,
)
from core.market_state import AssetClass


# ── DIMENSION 1 & 2: UNIT TESTING & FACTOR BOUNDARIES ─────────────────────────

def test_high_market_quality_score():
    """Unit Test: Clean trading day produces HIGH MQI (>= 70%) and allows 2 signals."""
    # ATR Compressed (2), VIX Stable (2), Clean Calendar (2), Breadth (1), Volume (1) = 8/10 (80%)
    snapshot = calculate_mqi(
        custom_atr_score=2,
        custom_vix_change_score=2,
        target_date=date(2026, 8, 21),  # Normal Friday (Tue 2026-08-19? no - Aug 18 is now weekly EXPIRY day)
        session_phase=SessionPhase.PRE_MARKET_0830
    )
    assert snapshot.mqi_level == "HIGH"
    assert snapshot.signals_allowed == 2
    assert snapshot.no_trade is False
    assert snapshot.mqi_pct == 80.0
    assert snapshot.total_score == 8
    assert snapshot.throttle_mode == ExecutionThrottleMode.FULL_DEPLOYMENT
    assert snapshot.data_quality == DataQuality.CONFIDENT


def test_medium_and_low_market_quality_scores():
    """Unit Test: Medium (50-69%) and Low (30-49%) allow 1 signal."""
    # Medium MQI: ATR Normal (1), VIX Normal (1), Clean Event (2), Breadth (1), Volume (1) = 6/10 (60%)
    snap_med = calculate_mqi(
        custom_atr_score=1,
        custom_vix_change_score=1,
        target_date=date(2026, 8, 21)
    )
    assert snap_med.mqi_level == "MEDIUM"
    assert snap_med.signals_allowed == 1
    assert snap_med.no_trade is False
    assert snap_med.mqi_pct == 60.0
    assert snap_med.throttle_mode == ExecutionThrottleMode.CONSERVATIVE_HALF

    # Low MQI: ATR Expanding (0), VIX Normal (1), Weekly Expiry (1), Breadth (1), Volume (1) = 4/10 (40%)
    snap_low = calculate_mqi(
        custom_atr_score=0,
        custom_vix_change_score=1,
        target_date=date(2026, 8, 11)  # Tuesday Weekly Expiry
    )
    assert snap_low.mqi_level == "LOW"
    assert snap_low.signals_allowed == 1
    assert snap_low.no_trade is False
    assert snap_low.mqi_pct == 40.0
    assert snap_low.throttle_mode == ExecutionThrottleMode.STRICT_DEFENSE


def test_very_low_no_trade_day():
    """Unit Test: Extreme chop + event day produces VERY LOW (< 30%) and triggers NO TRADE DAY."""
    snap_no_trade = calculate_mqi(
        custom_atr_score=0,
        custom_vix_change_score=0,
        target_date=date(2026, 8, 7)  # RBI MPC Decision Day
    )
    assert snap_no_trade.mqi_level == "VERY LOW"
    assert snap_no_trade.signals_allowed == 0
    assert snap_no_trade.no_trade is True
    assert snap_no_trade.mqi_pct == 20.0
    assert snap_no_trade.throttle_mode == ExecutionThrottleMode.COMPLETE_HALT
    assert snap_no_trade.event_risk_type == EventRiskType.RBI_MPC_DECISION
    assert "RBI MPC" in snap_no_trade.event_reason


# ── DIMENSION 4: FAULT INJECTION & ZERO FREE POINTS VERIFICATION ──────────────

def test_data_degradation_fault_injection():
    """
    Fault Injection Test:
    Verify that failed market feeds trigger DEGRADED data quality, 0 signals,
    and do NOT award free points!
    """
    with patch("core.mqi.get_atr_score", return_value=(0, None, None, DataQuality.DEGRADED, "ATR Feed Failed")), \
         patch("core.mqi.get_vix_change_score", return_value=(0, None, DataQuality.DEGRADED, "VIX Feed Failed")):
        
        snapshot = calculate_mqi(target_date=date(2026, 8, 18))
        assert snapshot.data_quality == DataQuality.DEGRADED
        assert snapshot.mqi_level == "DEGRADED"
        assert snapshot.signals_allowed == 0
        assert snapshot.no_trade is True
        assert snapshot.throttle_mode == ExecutionThrottleMode.COMPLETE_HALT


# ── DIMENSION 5: FINANCIAL CORRECTNESS (HOLIDAY EXPIRY & EVENT CALENDAR) ───────

def test_rbi_mpc_and_budget_event_risk():
    """Financial Correctness: Verify RBI MPC decision days, eve of decision, and budget day/week scores."""
    # 1. RBI MPC Day (Score 0, EventRiskType.RBI_MPC_DECISION)
    score_mpc, reason_mpc, risk_mpc = get_event_proximity_score(date(2026, 8, 7))
    assert score_mpc == 0
    assert "RBI MPC" in reason_mpc
    assert risk_mpc == EventRiskType.RBI_MPC_DECISION

    # 2. Eve of RBI MPC (Score 1, EventRiskType.RBI_MPC_DECISION)
    score_eve, reason_eve, risk_eve = get_event_proximity_score(date(2026, 8, 6))
    assert score_eve == 1
    assert "Day before RBI MPC" in reason_eve
    assert risk_eve == EventRiskType.RBI_MPC_DECISION

    # 3. Budget Day itself (Feb 1 -> Score 0, EventRiskType.UNION_BUDGET)
    score_bday, reason_bday, risk_bday = get_event_proximity_score(date(2026, 2, 1))
    assert score_bday == 0
    assert "Budget Day" in reason_bday
    assert risk_bday == EventRiskType.UNION_BUDGET

    # 4. Budget Lead-up Week (Jan 30 -> Score 1, EventRiskType.UNION_BUDGET)
    score_budget, reason_budget, risk_budget = get_event_proximity_score(date(2026, 1, 30))
    assert score_budget == 1
    assert "Budget Lead-up" in reason_budget
    assert risk_budget == EventRiskType.UNION_BUDGET


def test_holiday_aware_monthly_expiry_detection():
    """Financial Correctness: Verify monthly expiry detection on the last TUESDAY (NSE circular 111/2025)."""
    aug_last_tuesday = date(2026, 8, 25)
    score, reason, risk_type = get_event_proximity_score(aug_last_tuesday)
    assert score in (0, 1)
    assert "Expiry" in reason
    assert risk_type == EventRiskType.MONTHLY_EXPIRY


def test_strategy_specific_mqi_gating():
    """Verify strategy-specific minimum MQI quality requirement enforcement."""
    # S03 (Turtle Breakout) requires HIGH
    assert is_strategy_allowed_for_mqi("S03", MQILevel.HIGH) is True
    assert is_strategy_allowed_for_mqi("S03", MQILevel.MEDIUM) is False
    assert is_strategy_allowed_for_mqi("S03", MQILevel.LOW) is False

    # S01 (Trend Pullback) requires MEDIUM
    assert is_strategy_allowed_for_mqi("S01", MQILevel.HIGH) is True
    assert is_strategy_allowed_for_mqi("S01", MQILevel.MEDIUM) is True
    assert is_strategy_allowed_for_mqi("S01", MQILevel.LOW) is False

    # S08 (Micro-Scalp) allows LOW
    assert is_strategy_allowed_for_mqi("S08", MQILevel.LOW) is True

    # VERY LOW / DEGRADED rejects ALL strategies
    assert is_strategy_allowed_for_mqi("S08", MQILevel.VERY_LOW) is False
    assert is_strategy_allowed_for_mqi("S01", MQILevel.DEGRADED) is False


def test_multi_asset_mqi_calendars():
    """Verify multi-asset event sentry (US Equities & Crypto)."""
    # US FOMC Decision Day (e.g. 2026-03-18)
    us_score, us_reason, us_risk = get_event_proximity_score(date(2026, 3, 18), asset_class=AssetClass.US_EQUITY_NYSE)
    assert us_score == 0
    assert us_risk == EventRiskType.GLOBAL_FED_FOMC

    # Crypto clean window
    c_score, c_reason, c_risk = get_event_proximity_score(date(2026, 8, 18), asset_class=AssetClass.CRYPTO)
    assert c_score == 2
    assert c_risk == EventRiskType.NONE


# ── DIMENSION 7: PROPERTY & INVARIANT TESTING ─────────────────────────────────

def test_mqi_mathematical_invariants():
    """
    Property / Invariant Testing:
    Verify that across all possible factor permutations, mathematical invariants hold:
    - MQI % in [0.0, 100.0]
    - signals_allowed in {0, 1, 2}
    - no_trade is strictly boolean
    - total_score in [0, 10]
    """
    for atr in [0, 1, 2]:
        for vix in [0, 1, 2]:
            snap = calculate_mqi(
                custom_atr_score=atr,
                custom_vix_change_score=vix,
                target_date=date(2026, 8, 18)
            )
            assert 0.0 <= snap.mqi_pct <= 100.0
            assert snap.signals_allowed in (0, 1, 2)
            assert isinstance(snap.no_trade, bool)
            assert 0 <= snap.total_score <= 10
            if snap.mqi_pct < 30.0:
                assert snap.no_trade is True
                assert snap.signals_allowed == 0


# ── DIMENSION 8: PERFORMANCE & MICROSECOND LATENCY BENCHMARK ─────────────────

def test_hot_path_latency_and_caching():
    """
    Performance Test:
    Verify warm-cache in-memory read executes in under 100 microseconds (O(1) hot path).
    """
    # 1. Warm cache
    # G6: pin target_date — unpinned, event-proximity factors track the REAL
    # clock and the expected level flips across expiry boundaries.
    calculate_mqi(custom_atr_score=2, custom_vix_change_score=2, target_date=date(2026, 8, 21))

    # 2. Benchmark 1,000 warm cache reads
    start_t = time.perf_counter()
    for _ in range(1000):
        cached = get_cached_mqi()
        assert cached.mqi_level == "HIGH"
    elapsed = time.perf_counter() - start_t
    
    avg_latency_us = (elapsed / 1000) * 1_000_000
    assert avg_latency_us < 100.0, f"Hot path latency too high: {avg_latency_us:.2f} μs"


# ── DIMENSION 9: CONCURRENCY & THREAD SAFETY ─────────────────────────────────

def test_concurrent_hot_path_readers():
    """
    Concurrency Test:
    Verify multiple scanner worker threads can read cached MQI simultaneously without corruption.
    """
    # G6: pinned date — see test_hot_path_latency_and_caching.
    calculate_mqi(custom_atr_score=2, custom_vix_change_score=2, target_date=date(2026, 8, 21))

    def _reader_task():
        for _ in range(100):
            snap = get_cached_mqi()
            assert snap.mqi_level == "HIGH"
            assert snap.signals_allowed == 2
        return True

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(_reader_task) for _ in range(8)]
        results = [f.result() for f in futures]
        assert all(results)


# ── DIMENSION 10 & 11: PRODUCTION SIMULATION & BACKWARD COMPATIBILITY ─────────

def test_tuple_unpacking_backwards_compatibility():
    """Integration Test: Legacy caller code `level, signals, no_trade, pct = calculate_mqi()` works seamlessly."""
    snapshot = calculate_mqi(
        custom_atr_score=2,
        custom_vix_change_score=2,
        target_date=date(2026, 8, 21)
    )
    # Unpack as 4-tuple
    mqi_level, signals_allowed, no_trade, mqi_pct = snapshot
    assert mqi_level == "HIGH"
    assert signals_allowed == 2
    assert no_trade is False
    assert mqi_pct == 80.0


def test_production_session_lifecycle_simulation():
    """
    Production Simulation:
    Step through 08:30 AM pre-market baseline -> 11:30 AM intraday update.
    """
    # 1. 08:30 AM Pre-Market Baseline
    pre_market_snap = calculate_mqi(
        custom_atr_score=1,
        custom_vix_change_score=1,
        target_date=date(2026, 8, 18),
        session_phase=SessionPhase.PRE_MARKET_0830
    )
    assert pre_market_snap.session_phase == SessionPhase.PRE_MARKET_0830
    assert pre_market_snap.mqi_level == "MEDIUM"

    # 2. 11:30 AM Intraday Tick Update (ATR compresses nicely).
    # G6: intraday pinned to a known post-expiry date so the HIGH expectation
    # is deterministic regardless of the real calendar.
    intraday_snap = update_intraday_mqi(
        custom_atr_score=2,
        custom_vix_change_score=2,
        target_date=date(2026, 8, 21),
    )
    assert intraday_snap.session_phase == SessionPhase.INTRADAY
    assert intraday_snap.mqi_level == "HIGH"
    assert get_cached_mqi().mqi_level == "HIGH"


# ── DIMENSION 12: OBSERVABILITY & EXPLAINABILITY ──────────────────────────────

def test_observability_and_provenance():
    """
    Observability Test:
    Verify snapshot explains WHAT was calculated, WHY, and DATA QUALITY clearly.
    """
    snap = calculate_mqi(custom_atr_score=2, custom_vix_change_score=1)
    assert snap.provenance_reason is not None
    assert "Event:" in snap.provenance_reason
    assert "Quality:" in snap.provenance_reason
    assert snap.timestamp_utc is not None
