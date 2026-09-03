"""
Unit and Institutional Test Suite for strategy/pipeline.py
Tests the 7-Stage Verification Funnel, Index Earnings Exemptions,
3-Tranche Geometry, Devil Checks, AI Debate Room, and Typed Contracts.
"""

from datetime import datetime
import pandas as pd
import numpy as np
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from mjonai.strategy.pipeline import (
    PipelineProcessingResult,
    evaluate_strategy_pipeline,
    process_single_strategy_signal,
)


@pytest.fixture
def sample_ohlcv_df():
    """Generates 100 periods of mock OHLCV candle data."""
    dates = pd.date_range(end=datetime.now(), periods=100, freq="D")
    df = pd.DataFrame({
        "Open": np.linspace(1000, 1100, 100),
        "High": np.linspace(1010, 1120, 100),
        "Low": np.linspace(990, 1090, 100),
        "Close": np.linspace(1005, 1110, 100),
        "Volume": np.full(100, 50000),
    }, index=dates)
    return df


# ── 1. CONTRACT SERIALIZATION TESTS ──────────────────────────────────────────

def test_pipeline_processing_result_contract():
    """Verify PipelineProcessingResult dataclass serialization."""
    res = PipelineProcessingResult(
        is_approved=True,
        rejection_stage="",
        rejection_reason="",
        signal_data={"symbol": "RELIANCE", "entry_price": 2800.0},
        signal_intelligence_id="uuid-1234",
    )
    d = res.to_dict()
    assert d["is_approved"] is True
    assert d["signal_intelligence_id"] == "uuid-1234"
    assert res.signal_data is not None
    assert res.signal_data["symbol"] == "RELIANCE"


# ── 2. GATE 1: CONFIDENCE FILTER TESTS ───────────────────────────────────────

def test_gate1_low_confidence_rejected(sample_ohlcv_df):
    """Verify signal with low technical score is rejected at Gate 1."""
    res = evaluate_strategy_pipeline(
        strategy_result={
            "technical_score": 40.0,  # Below 65% LIVE cutoff
            "reasons": ["RSI Weak ✗"],
            "strategy_id": "S01_MomentumRSI",
            "strategy_version": "1.0",
        },
        clean_symbol="TCS",
        df=sample_ohlcv_df,
        market_state="BULL",
        mqi_level="HIGH",
        vix=14.0,
        open_trades=[],
        open_strategy_symbols=set(),
        live_prices={},
        symbol_map={},
        system_mode="LIVE",
    )
    assert res.is_approved is False
    assert res.rejection_stage == "CONFIDENCE_FILTER"


# ── 3. GATE 2: INDEX EARNINGS EXEMPTION TESTS ────────────────────────────────

@patch("mjonai.strategy.pipeline.insert_signal_intelligence")
@patch("mjonai.strategy.pipeline.evaluate_trade_risk_levels")
@patch("mjonai.strategy.pipeline.evaluate_devil_checks")
@patch("mjonai.strategy.pipeline.supervisor_evaluate", return_value={"approved": True, "summary": "Approved"})
def test_gate2_index_exempt_from_earnings_blackout(
    mock_sup, mock_devil, mock_risk, mock_db, sample_ohlcv_df, monkeypatch
):
    from mjonai.risk.devil_checks import DevilCheckResult
    mock_devil.return_value = DevilCheckResult(
        all_passed=True,
        failure_reason="",
        passed_checks=["GAP_RISK", "LIQUIDITY", "DATA_QUALITY"],
        failed_checks=[],
        details={"scaled_quantity": 50, "scaling_factor": 1.0},
    )
    monkeypatch.setattr("mjonai.strategy.pipeline._live_mqi_pct", lambda: 80.0)
    """Verify NIFTY index options bypass single-stock corporate earnings check."""
    mock_risk.return_value = MagicMock(
        is_approved=True,
        to_dict=lambda: {
            "entry": 24500.0, "stop_loss": 24400.0, "target": 24700.0,
            "target_1": 24650.0, "target_2": 24700.0, "quantity": 50,
            "t1_quantity": 25, "t2_quantity": 15, "runner_quantity": 10,
            "real_rr": 2.0, "total_cost": 5000.0, "atr": 100.0,
            "sl_method": "STRUCTURE", "swing_low": 24400.0,
        }
    )

    res = evaluate_strategy_pipeline(
        strategy_result={
            "technical_score": 85.0,
            "reasons": ["Index Momentum Bullish ✓"],
            "strategy_id": "S01_MomentumRSI",
            "strategy_version": "1.0",
            "asset_class": "INDEX",
            # H3: LIVE mode needs >=0.40 REAL evidence weight (tech 0.20 +
            # rvol 0.10 + mqi 0.10 patched below).
            "indicator_values": {"rvol": 1.8},
        },
        clean_symbol="NIFTY",
        df=sample_ohlcv_df,
        market_state="BULL",
        mqi_level="HIGH",
        vix=14.0,
        open_trades=[],
        open_strategy_symbols=set(),
        live_prices={},
        symbol_map={},
        system_mode="LIVE",
    )
    assert res.is_approved is True
    assert res.signal_data is not None
    assert res.signal_data["underlying_symbol"] == "NIFTY"


# ── 4. GATE 3: SECTOR CONCENTRATION TESTS ────────────────────────────────────

@patch("mjonai.strategy.pipeline.evaluate_sector_limits")
def test_gate3_sector_limit_breach_rejected(mock_sector_limits, sample_ohlcv_df, monkeypatch):
    monkeypatch.setattr("mjonai.strategy.pipeline._live_mqi_pct", lambda: 80.0)
    """Verify signal is rejected when sector exposure is exceeded."""
    mock_sector_limits.return_value = MagicMock(
        is_allowed=False,
        reason="Sector IT capped at 2 stocks"
    )

    res = evaluate_strategy_pipeline(
        strategy_result={
            "technical_score": 80.0,
            "reasons": ["Momentum Bullish ✓"],
            "strategy_id": "S01_MomentumRSI",
            "strategy_version": "1.0",
            # H3: real-evidence weight for LIVE floor (see gate2 comment).
            "indicator_values": {"rvol": 1.8},
        },
        clean_symbol="INFY",
        df=sample_ohlcv_df,
        market_state="BULL",
        mqi_level="HIGH",
        vix=14.0,
        open_trades=[],
        open_strategy_symbols=set(),
        live_prices={},
        symbol_map={},
        system_mode="LIVE",
    )
    assert res.is_approved is False
    assert res.rejection_stage == "SECTOR_LIMIT"


# ── 5. GATE 5: DEVIL CHECKS REJECTION TESTS ──────────────────────────────────

@patch("mjonai.strategy.pipeline.run_all_devil_checks", return_value=(False, "Liquidity Veto: Average volume below ₹5Cr", []))
def test_gate5_devil_checks_veto(mock_devil, sample_ohlcv_df, monkeypatch):
    monkeypatch.setattr("mjonai.strategy.pipeline._live_mqi_pct", lambda: 80.0)
    """Verify signal is rejected when Devil Checks fail."""
    res = evaluate_strategy_pipeline(
        strategy_result={
            "technical_score": 80.0,
            "reasons": ["Momentum Bullish ✓"],
            "strategy_id": "S01_MomentumRSI",
            "strategy_version": "1.0",
            # H3: real-evidence weight for LIVE floor (see gate2 comment).
            "indicator_values": {"rvol": 1.8},
        },
        clean_symbol="RELIANCE",
        df=sample_ohlcv_df,
        market_state="BULL",
        mqi_level="HIGH",
        vix=14.0,
        open_trades=[],
        open_strategy_symbols=set(),
        live_prices={},
        symbol_map={},
        system_mode="LIVE",
    )
    assert res.is_approved is False
    assert res.rejection_stage == "DEVIL_CHECKS_VETO"
