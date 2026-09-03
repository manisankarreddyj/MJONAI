"""
Unit and Institutional Test Suite for strategy/signal_builder.py
Tests SignalIntelligencePayload, 3-Tranche Geometry, Indicator Snapshots,
Directional SL Math, Pattern Hash Linkages, and Multi-Asset Metadata.
"""

from datetime import datetime
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from mjonai.strategy.signal_builder import (
    SignalIntelligencePayload,
    build_signal_record,
    _build_signal_record,
    evaluate_signal_payload,
)


# ── 1. CONTRACT SERIALIZATION TESTS ──────────────────────────────────────────

def test_signal_payload_contract_serialization():
    """Verify SignalIntelligencePayload dataclass serializes cleanly to dict."""
    payload = SignalIntelligencePayload(
        symbol="RELIANCE",
        signal_type="APPROVED",
        strategy_id="S01_MomentumRSI",
        strategy_version="1.0",
        system_mode="LIVE",
        market_state="BULL",
        mqi_level="HIGH",
        generated_at="2026-08-18T10:30:00+05:30",
        market_open_minutes=75,
        time_of_day_bucket="MORNING",
        day_of_week="Tuesday",
        week_of_month=3,
        entry_price=2800.0,
        stop_loss=2750.0,
        target=2925.0,
        target_1=2875.0,
        target_2=2925.0,
        planned_quantity=20,
        t1_quantity=10,
        t2_quantity=6,
        runner_quantity=4,
    )
    d = payload.to_dict()
    assert d["symbol"] == "RELIANCE"
    assert d["t1_quantity"] == 10
    assert d["runner_quantity"] == 4
    assert d["target_1"] == 2875.0


# ── 2. 3-TRANCHE SCALING & DIRECTIONAL DISTANCE TESTS ────────────────────────

def test_3_tranche_scaling_and_directional_distance_long():
    """Verify 3-tranche quantity assignments and SL distance for LONG trades."""
    levels = {
        "entry": 1000.0,
        "stop_loss": 980.0,
        "target": 1050.0,
        "target_1": 1030.0,
        "target_2": 1050.0,
        "quantity": 10,
        "t1_quantity": 5,
        "t2_quantity": 3,
        "runner_quantity": 2,
        "real_rr": 2.5,
        "atr": 15.0,
    }

    record = build_signal_record(
        symbol="TCS",
        signal_type="APPROVED",
        market_state="BULL",
        mqi_level="HIGH",
        vix=13.5,
        levels=levels,
        signal_direction="LONG",
    )

    assert record["entry_price"] == 1000.0
    assert record["t1_quantity"] == 5
    assert record["t2_quantity"] == 3
    assert record["runner_quantity"] == 2
    assert record["planned_capital"] == 10000.0
    assert record["sl_distance_pct"] == 2.0  # (1000 - 980) / 1000 * 100
    assert record["target_distance_pct"] == 5.0  # (1050 - 1000) / 1000 * 100


def test_directional_distance_short():
    """Verify directional SL and target distance math for SHORT trades."""
    levels = {
        "entry": 1000.0,
        "stop_loss": 1020.0,  # SL above entry for SHORT
        "target": 950.0,      # Target below entry for SHORT
        "quantity": 10,
        "real_rr": 2.5,
    }

    record = build_signal_record(
        symbol="INFY",
        signal_type="APPROVED",
        market_state="BEAR",
        mqi_level="HIGH",
        vix=18.0,
        levels=levels,
        signal_direction="SHORT",
    )

    # Positive percentage distance
    assert record["sl_distance_pct"] == 2.0
    assert record["target_distance_pct"] == 5.0


# ── 3. STRUCTURED INDICATOR SNAPSHOT TESTS ───────────────────────────────────

def test_indicator_scores_and_raw_values_snapshot():
    """Verify structured indicator scores and raw values are stored cleanly."""
    ind_scores = {"rsi_score": 20.0, "ema_score": 20.0, "macd_score": 15.0}
    ind_values = {"rsi_14": 64.5, "adx_14": 31.2, "rvol": 2.4}

    record = build_signal_record(
        symbol="HDFCBANK",
        signal_type="GENERATED",
        market_state="BULL",
        mqi_level="HIGH",
        vix=14.0,
        indicator_scores=ind_scores,
        indicator_values=ind_values,
    )

    assert record["indicator_scores"]["rsi_score"] == 20.0
    assert record["indicator_values"]["rsi_14"] == 64.5


def test_legacy_checkmark_fallback():
    """Verify fallback string parser for legacy checkmark reasons."""
    reasons = ["RSI bullish ✓", "MACD bullish ✓", "EMA aligned ✓"]
    record = build_signal_record(
        symbol="ICICIBANK",
        signal_type="GENERATED",
        market_state="BULL",
        mqi_level="HIGH",
        reasons=reasons,
    )
    assert record["indicator_scores"]["rsi_score"] == 20.0
    assert record["indicator_scores"]["macd_score"] == 20.0


# ── 4. DETERMINISTIC PATTERN HASH LINKAGE ────────────────────────────────────

def test_deterministic_pattern_hash_auto_generation():
    """Verify setup_hash is automatically generated and attached to signal."""
    record = build_signal_record(
        symbol="RELIANCE",
        signal_type="APPROVED",
        market_state="BULL",
        mqi_level="HIGH",
        strategy_id="S01_MomentumRSI",
    )
    assert record["setup_hash"] is not None
    assert "S01_MOMENTUMRSI" in record["setup_hash"].upper()
    assert "BULL" in record["setup_hash"].upper()


# ── 5. 8 DEVIL CHECKS & MULTI-AGENT TELEMETRY ────────────────────────────────

def test_devil_checks_and_multi_agent_unraveling():
    """Verify 8 devil check flags and multi-agent debate verdicts."""
    devil_checks = ["Gap Risk", "Liquidity", "Data Quality", "Real RR"]
    bull = {"verdict": "BULLISH", "confidence": 85.0, "key_reasons": ["RSI Momentum"]}
    bear = {"verdict": "CAUTION", "confidence": 60.0, "red_flags": ["VIX elevated"]}
    sup = {"final_decision": "APPROVE", "rejection_reason": None}

    record = build_signal_record(
        symbol="LT",
        signal_type="APPROVED",
        market_state="BULL",
        mqi_level="HIGH",
        devil_checks=devil_checks,
        devil_passed=True,
        bull_result=bull,
        bear_result=bear,
        supervisor_result=sup,
    )

    assert record["devil_gap_risk"] is True
    assert record["devil_liquidity"] is True
    assert record["devil_correlation"] is False  # Not in passed list
    assert record["bull_verdict"] == "BULLISH"
    assert record["bear_verdict"] == "CAUTION"
    assert record["supervisor_decision"] == "APPROVE"


# ── 6. MULTI-ASSET & DERIVATIVE METADATA ─────────────────────────────────────

def test_multi_asset_derivative_fields():
    """Verify option and derivative metadata fields."""
    record = build_signal_record(
        symbol="NIFTY26AUG24500CE",
        signal_type="APPROVED",
        market_state="BULL",
        mqi_level="HIGH",
        asset_class="INDEX_OPTION",
        extra={
            "strike": 24500.0,
            "option_type": "CE",
            "expiry_date": "2026-08-27",
            "lot_size": 25,
        }
    )

    assert record["asset_class"] == "INDEX_OPTION"
    assert record["underlying_symbol"] == "NIFTY"
    assert record["strike"] == 24500.0
    assert record["lot_size"] == 25
