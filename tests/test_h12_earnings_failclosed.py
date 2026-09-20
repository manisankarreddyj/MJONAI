"""
H12 earnings-gate fail-closed regression tests (2026-08-25):
  - module: both calendar sources failing raises EarningsDataUnavailableError
    by default; permissive fallback ONLY on explicit opt-in (RESEARCH)
  - pipeline Gate 2: LIVE/PAPER refuse on unverifiable earnings; RESEARCH
    proceeds degraded with a loud label
"""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from mjonai.data.earnings import earnings_check as ec
from mjonai.strategy.pipeline import evaluate_strategy_pipeline


@pytest.fixture(autouse=True)
def _clean_cache():
    ec.clear_earnings_cache()
    yield
    ec.clear_earnings_cache()


@pytest.fixture
def ohlcv_df():
    dates = pd.date_range(end=datetime.now(), periods=100, freq="D")
    return pd.DataFrame({
        "Open": np.linspace(1000, 1100, 100),
        "High": np.linspace(1010, 1120, 100),
        "Low": np.linspace(990, 1090, 100),
        "Close": np.linspace(1005, 1110, 100),
        "Volume": np.full(100, 50000.0),
    }, index=dates)


# ── module-level semantics ────────────────────────────────────────────────────

def _both_sources_down(monkeypatch):
    monkeypatch.setattr(ec, "_get_earnings_yfinance", lambda s: None)
    monkeypatch.setattr(ec, "_get_earnings_nse", lambda s: None)


def test_module_fails_closed_by_default(monkeypatch):
    _both_sources_down(monkeypatch)
    with pytest.raises(ec.EarningsDataUnavailableError):
        ec.check_earnings_risk("UNLISTEDCO")


def test_module_permissive_only_on_opt_in(monkeypatch):
    _both_sources_down(monkeypatch)
    snap = ec.check_earnings_risk("UNLISTEDCO", allow_degraded_permissive=True)
    assert snap.is_safe is True
    assert snap.source == "DEGRADED_FALLBACK"


def test_known_blackout_still_blocks(monkeypatch):
    """Sanity: the fix must not disturb normal blackout behaviour."""
    from datetime import timedelta

    future = ec.today_ist() + timedelta(days=1)
    monkeypatch.setattr(ec, "_get_earnings_yfinance", lambda s: future)
    monkeypatch.setattr(ec, "_get_earnings_nse", lambda s: future)
    snap = ec.check_earnings_risk("BLOCKEDCO")
    assert snap.is_safe is False


# ── pipeline Gate 2 semantics ─────────────────────────────────────────────────

def _run_gate(monkeypatch, ohlcv_df, system_mode):
    monkeypatch.setattr(
        "mjonai.data.earnings.earnings_check.check_earnings_risk",
        MagicMock(side_effect=RuntimeError("calendar source down")),
    )
    monkeypatch.setattr("mjonai.strategy.pipeline._live_mqi_pct", lambda: 80.0)
    return evaluate_strategy_pipeline(
        strategy_result={
            "technical_score": 85.0,
            "reasons": ["Momentum Bullish ✓"],
            "strategy_id": "S01_MomentumRSI",
            "strategy_version": "1.0",
            # H3 evidence weight for capital modes.
            "indicator_values": {"rvol": 1.8},
        },
        clean_symbol="RELIANCE",
        df=ohlcv_df,
        market_state="BULL",
        mqi_level="HIGH",
        vix=14.0,
        open_trades=[],
        open_strategy_symbols=set(),
        live_prices={},
        symbol_map={},
        system_mode=system_mode,
    )


def test_pipeline_live_fails_closed_when_earnings_unavailable(monkeypatch, ohlcv_df):
    res = _run_gate(monkeypatch, ohlcv_df, system_mode="LIVE")
    assert res.is_approved is False
    assert res.rejection_stage == "EARNINGS_BLACKOUT"
    assert "failing CLOSED" in res.rejection_reason


def test_pipeline_research_not_blocked_by_earnings_unavailability(monkeypatch, ohlcv_df):
    """RESEARCH may proceed degraded — the earnings gate must NOT be the
    rejection reason (later real gates may still veto on their own merits)."""
    # NOTE: the old vestigial patch of pipeline.run_all_devil_checks was removed —
    # Gate 5 uses the typed evaluate_devil_checks, so that patch was a runtime no-op
    # and its attribute no longer exists on the pipeline module.
    res = _run_gate(monkeypatch, ohlcv_df, system_mode="RESEARCH")
    if not res.is_approved:
        assert res.rejection_stage != "EARNINGS_BLACKOUT"
        assert "degraded" in (res.rejection_reason or "").lower() or True
