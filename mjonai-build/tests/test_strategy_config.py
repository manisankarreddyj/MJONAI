"""
Unit and Institutional Test Suite for strategy/config.py
Tests 10-Factor Confidence Scoring, Directional Position Limits,
Beta-Weighted Sector Caps, Dynamic Universes, and Contract Telemetry.
"""

from datetime import date, datetime
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from strategy.config import (
    ConfidenceScoreResult,
    DynamicPositionLimits,
    SectorLimitResult,
    WATCHLIST,
    UNIVERSE_NIFTY50,
    UNIVERSE_INDICES_AND_COMMODITIES,
    get_universe,
    extract_underlying_symbol,
    calculate_confidence,
    evaluate_confidence_score,
    get_dynamic_position_limit,
    get_directional_position_limits,
    check_sector_limits,
    evaluate_sector_limits,
    _build_calendar_events,
)


# ── 1. CONTRACT SERIALIZATION TESTS ──────────────────────────────────────────

def test_contracts_serialization():
    """Verify dataclasses serialize cleanly to dict."""
    c_res = ConfidenceScoreResult(
        confidence=78.5,
        is_approved=True,
        breakdown={"technical": 80.0, "mtf": 75.0},
        rejection_reason="",
    )
    assert c_res.to_dict()["confidence"] == 78.5

    p_res = DynamicPositionLimits(
        max_longs=5,
        max_shorts=1,
        max_total=5,
        market_state="BULL",
        mqi_level="HIGH",
        vix=14.5,
    )
    assert p_res.to_dict()["max_longs"] == 5

    s_res = SectorLimitResult(
        is_allowed=True,
        reason="Approved",
        sector="IT",
        stocks_open=1,
        capital_used=25000.0,
        max_allowed_capital=40000.0,
    )
    assert s_res.to_dict()["sector"] == "IT"


# ── 2. DYNAMIC MULTI-ASSET UNIVERSES ─────────────────────────────────────────

def test_get_universe_tiers():
    """Verify universe tier retrieval."""
    assert len(get_universe("TIER_1")) in (15, 17)
    assert len(get_universe("NIFTY_50")) in (50, 52)
    assert "NIFTY" in get_universe("DERIVATIVES")
    assert "CRUDEOIL" in get_universe("DERIVATIVES")


def test_extract_underlying_symbol():
    """Verify underlying root symbol extraction for equity, options, and futures."""
    assert extract_underlying_symbol("RELIANCE.NS") == "RELIANCE"
    assert extract_underlying_symbol("TCS.BO") == "TCS"
    assert extract_underlying_symbol("NIFTY26AUG24500CE") == "NIFTY"
    assert extract_underlying_symbol("BANKNIFTY26AUGFUT") == "BANKNIFTY"
    assert extract_underlying_symbol("RELIANCE26AUG2500CE") == "RELIANCE"
    assert extract_underlying_symbol("CRUDEOIL26AUGFUT") == "CRUDEOIL"


# ── 3. 10-FACTOR CONFIDENCE SCORING ENGINE ───────────────────────────────────

def test_confidence_scoring_weights_and_rejection():
    """Verify 10-factor composite scoring and minimum thresholds."""
    # Technical < 60 rejected immediately
    res_low_tech = evaluate_confidence_score(technical=55.0)
    assert res_low_tech.is_approved is False
    assert "below minimum 60.0" in res_low_tech.rejection_reason

    # High quality multi-factor setup
    res_high = evaluate_confidence_score(
        technical=85.0,
        mtf=90.0,
        relative_strength=85.0,
        rvol=80.0,
        sector_breadth=80.0,
        mqi_score=75.0,
        derivative_oi=70.0,
        pattern_expectancy=75.0,
        real_rr=80.0,
        event_clearance=100.0,
        system_mode="LIVE",
    )
    assert res_high.is_approved is True
    assert res_high.confidence >= 80.0
    assert all(res_high.breakdown[k] is not None for k in (
        "technical", "mtf", "relative_strength", "rvol", "sector_breadth",
        "mqi_score", "derivative_oi", "pattern_expectancy", "real_rr", "event_clearance",
    ))
    assert res_high.factors_available == 10

    # H3 contract: technical + one auxiliary = 0.35 weight < minimum
    # evidence (0.40). The old code fabricated the missing eight and
    # approved; honest math must refuse.
    score, reason = calculate_confidence(technical=85.0, mtf=90.0, system_mode="LIVE")
    assert score is None
    assert "Insufficient evidence" in reason


# ── 4. DIRECTIONAL REGIME POSITION LIMITS ────────────────────────────────────

def test_directional_position_limits():
    """Verify directional long and short limits across regimes."""
    # Bull Market
    bull_lim = get_directional_position_limits(market_state="BULL", mqi_level="HIGH", vix=13.5)
    assert bull_lim.max_longs == 5
    assert bull_lim.max_shorts == 1
    assert bull_lim.max_total == 5

    # Bear Market (Aggressive Short Sizing)
    bear_lim = get_directional_position_limits(market_state="BEAR", mqi_level="HIGH", vix=18.0)
    assert bear_lim.max_longs == 1
    assert bear_lim.max_shorts == 4
    assert bear_lim.max_total == 4

    # High VIX Panic (> 25)
    panic_lim = get_directional_position_limits(market_state="BULL", mqi_level="HIGH", vix=28.0)
    assert panic_lim.max_total == 1

    # Backward-compatible integer return
    assert get_dynamic_position_limit("BULL", "HIGH", 13.5) == 5


# ── 5. BETA-WEIGHTED SECTOR CONCENTRATION TESTS ──────────────────────────────

def test_beta_weighted_sector_limits():
    """Verify 18% cap on high-beta Realty/Metal vs 30% cap on FMCG."""
    # Candidate: DLF (Realty, 18% cap = ₹14,400 on ₹80,000 Growth pool)
    open_trades_realty = [
        {"symbol": "GODREJPROP", "entry_price": 2000.0, "quantity": 10},  # ₹20,000 used
    ]

    # Adding ₹10,000 DLF breaches ₹14,400 cap (₹20,000 + ₹10,000 = ₹30,000 > ₹14,400)
    res_realty = evaluate_sector_limits(
        candidate_symbol="DLF",
        candidate_entry=1000.0,
        candidate_qty=10,
        open_trades=open_trades_realty,
    )
    assert res_realty.is_allowed is False
    assert "Sector capital" in res_realty.reason

    # Candidate: HINDUNILVR (FMCG, 30% cap = ₹24,000 on ₹80,000 Growth pool)
    open_trades_fmcg = [
        {"symbol": "ITC", "entry_price": 400.0, "quantity": 50},  # ₹20,000 used
    ]
    # Adding ₹2,500 HINDUNILVR passes (₹20k + ₹2.5k = ₹22.5k <= ₹24k cap)
    res_fmcg = evaluate_sector_limits(
        candidate_symbol="HINDUNILVR",
        candidate_entry=2500.0,
        candidate_qty=1,
        open_trades=open_trades_fmcg,
    )
    assert res_fmcg.is_allowed is True

    # 2 Stocks already open in same sector -> blocked by stock count
    open_trades_2 = [
        {"symbol": "TCS", "entry_price": 3500.0, "quantity": 2},
        {"symbol": "INFY", "entry_price": 1500.0, "quantity": 5},
    ]
    res_it_count = evaluate_sector_limits(
        candidate_symbol="WIPRO",
        candidate_entry=500.0,
        candidate_qty=10,
        open_trades=open_trades_2,
    )
    assert res_it_count.is_allowed is False
    assert "Sector cap: 2/2" in res_it_count.reason


# ── 6. CALENDAR EVENT SYNCHRONIZATION TESTS ──────────────────────────────────

def test_calendar_events_builder():
    """Verify macro events builder executes cleanly."""
    events = _build_calendar_events()
    assert isinstance(events, list)
