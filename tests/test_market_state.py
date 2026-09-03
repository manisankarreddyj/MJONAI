"""
Unit & Boundary Integration Tests for core/market_state.py
Tests Macro Regimes, Data Quality Degradation, Pre-Market vs Intraday Semantics,
High Volatility Overrides, Tuple Unpacking Backward Compatibility, and O(1) Caching.
"""

from datetime import datetime, timezone
import pytest
import sys
from pathlib import Path
from unittest.mock import patch

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from mjonai.core.market_state import (
    MarketRegime,
    DataQuality,
    SessionPhase,
    AssetClass,
    VolatilityRegime,
    IntradayWindow,
    MarketRegimePolicy,
    MarketStateSnapshot,
    calculate_market_state,
    get_market_state,
    get_cached_market_state,
    update_intraday_market_state,
    reset_market_state_cache,
    get_current_intraday_window,
)


def test_bull_market_regime():
    """Verify strong bull regime when Nifty > EMA200 (+1%) and VIX < 14."""
    # Nifty 25,000 vs EMA200 24,000 (+4.16%), VIX 12.5
    snapshot = calculate_market_state(
        custom_nifty_price=25000.0,
        custom_ema200=24000.0,
        custom_vix=12.5,
        session_phase=SessionPhase.PRE_MARKET_0830
    )
    assert snapshot.market_state == "BULL"
    assert snapshot.total_score == 2
    assert snapshot.price_score == 1
    assert snapshot.vix_score == 1
    assert snapshot.vix_regime == "LOW_VOL"
    assert snapshot.high_vol_override is False
    assert snapshot.data_quality == DataQuality.CONFIDENT


def test_bear_market_regime():
    """Verify strong bear regime when Nifty < EMA200 (-1%) and VIX > 20."""
    # Nifty 23,000 vs EMA200 24,000 (-4.16%), VIX 22.0
    snapshot = calculate_market_state(
        custom_nifty_price=23000.0,
        custom_ema200=24000.0,
        custom_vix=22.0,
        session_phase=SessionPhase.PRE_MARKET_0830
    )
    assert snapshot.market_state == "BEAR"
    assert snapshot.total_score == -2
    assert snapshot.price_score == -1
    assert snapshot.vix_score == -1
    assert snapshot.vix_regime == "ELEVATED"
    assert snapshot.high_vol_override is False


def test_neutral_market_regime():
    """Verify neutral consolidation when Nifty is near EMA200 and VIX is normal (14-20)."""
    # Nifty 24,050 vs EMA200 24,000 (+0.2%), VIX 16.5
    snapshot = calculate_market_state(
        custom_nifty_price=24050.0,
        custom_ema200=24000.0,
        custom_vix=16.5,
        session_phase=SessionPhase.PRE_MARKET_0830
    )
    assert snapshot.market_state == "NEUTRAL"
    assert snapshot.total_score == 0
    assert snapshot.price_score == 0
    assert snapshot.vix_score == 0
    assert snapshot.vix_regime == "NORMAL"
    assert snapshot.data_quality == DataQuality.CONFIDENT


def test_high_volatility_panic_override():
    """Verify high volatility override activates when VIX > 25.0 even if price is bullish."""
    snapshot = calculate_market_state(
        custom_nifty_price=25000.0,
        custom_ema200=24000.0,
        custom_vix=28.5,  # Election / Panic VIX Spike
        session_phase=SessionPhase.INTRADAY
    )
    assert snapshot.high_vol_override is True
    assert snapshot.vix_regime == "PANIC"
    assert "HIGH VOL OVERRIDE ACTIVE" in snapshot.provenance_reason


def test_degraded_data_not_silently_neutral():
    """
    CRITICAL ARCHITECTURAL TEST:
    Verify that missing/failed market data results in DEGRADED quality and DEGRADED state,
    NEVER pretending to be a confident neutral market!
    """
    # Missing Nifty & VIX data (both failed to fetch)
    with patch("mjonai.core.market_state._fetch_nifty_data", return_value=(None, None, None, "FALLBACK")), \
         patch("mjonai.core.market_state._fetch_vix_data", return_value=(None, "FALLBACK")):
        
        snapshot = calculate_market_state()
        assert snapshot.data_quality == DataQuality.DEGRADED
        assert snapshot.market_state == "DEGRADED"
        assert "unavailable" in snapshot.provenance_reason


def test_tuple_unpacking_backwards_compatibility():
    """Verify legacy caller code `state, total, vix, high_vol = get_market_state()` works seamlessly."""
    snapshot = calculate_market_state(
        custom_nifty_price=25000.0,
        custom_ema200=24000.0,
        custom_vix=13.0
    )
    # Unpack as 4-tuple
    state, total, vix, high_vol = snapshot
    assert state == "BULL"
    assert total == 2
    assert vix == 13.0
    assert high_vol is False


def test_intraday_refresh_and_o1_caching():
    """Verify O(1) in-memory hot path caching and intraday updates."""
    # 1. Set pre-market baseline
    initial_snapshot = calculate_market_state(
        custom_nifty_price=24500.0,
        custom_ema200=24000.0,
        custom_vix=15.0,
        session_phase=SessionPhase.PRE_MARKET_0830
    )
    
    # 2. Query cached snapshot (O(1) memory lookup)
    cached = get_cached_market_state()
    assert cached.nifty_price == 24500.0
    assert cached.session_phase == SessionPhase.PRE_MARKET_0830

    # 3. Update intraday tick (e.g. at 11:00 AM)
    updated = update_intraday_market_state(
        current_nifty=25200.0,
        current_vix=11.5,
        ema200=24000.0,
        ema20=24800.0
    )
    assert updated.session_phase == SessionPhase.INTRADAY
    assert updated.nifty_price == 25200.0
    assert updated.ema20 == 24800.0
    assert updated.market_state == "BULL"

    # Cached state now reflects the intraday update
    assert get_cached_market_state().nifty_price == 25200.0


def test_ema20_trend_alignment():
    """Verify short-term EMA20 confirmation enhances trend scoring."""
    # Bullish alignment: Price > EMA200 and Price > EMA20
    bull_snap = calculate_market_state(
        custom_nifty_price=25000.0,
        custom_ema200=24000.0,
        custom_ema20=24800.0,
        custom_vix=13.0
    )
    assert "Aligned Bull" in bull_snap.provenance_reason

    # Bearish alignment: Price < EMA200 and Price < EMA20
    bear_snap = calculate_market_state(
        custom_nifty_price=23000.0,
        custom_ema200=24000.0,
        custom_ema20=23500.0,
        custom_vix=22.0
    )
    assert "Aligned Bear" in bear_snap.provenance_reason


def test_sector_breadth_scoring():
    """Verify Factor 2 sector breadth scoring (>= 60% Bull, <= 40% Bear)."""
    # Strong breadth (75% sectors positive) -> +1 point
    snap_strong = calculate_market_state(
        custom_nifty_price=24000.0,
        custom_ema200=24000.0,
        custom_vix=16.0,
        custom_breadth_pct=0.75
    )
    assert snap_strong.breadth_score == 1
    assert "Sector Breadth Strong" in snap_strong.provenance_reason

    # Weak breadth (25% sectors positive) -> -1 point
    snap_weak = calculate_market_state(
        custom_nifty_price=24000.0,
        custom_ema200=24000.0,
        custom_vix=16.0,
        custom_breadth_pct=0.25
    )
    assert snap_weak.breadth_score == -1
    assert "Sector Breadth Weak" in snap_weak.provenance_reason


def test_pcr_flow_scoring():
    """Verify Factor 4 Option Chain PCR flow scoring (>= 1.25 Bull, <= 0.75 Bear)."""
    # High PCR (1.45) -> Bullish put support (+1 point)
    snap_pcr_bull = calculate_market_state(
        custom_nifty_price=24000.0,
        custom_ema200=24000.0,
        custom_vix=16.0,
        custom_pcr=1.45
    )
    assert snap_pcr_bull.fii_score == 1
    assert "PCR Bullish Support" in snap_pcr_bull.provenance_reason

    # Low PCR (0.60) -> Bearish call resistance (-1 point)
    snap_pcr_bear = calculate_market_state(
        custom_nifty_price=24000.0,
        custom_ema200=24000.0,
        custom_vix=16.0,
        custom_pcr=0.60
    )
    assert snap_pcr_bear.fii_score == -1
    assert "PCR Bearish Resistance" in snap_pcr_bear.provenance_reason


def test_vix_surge_gate():
    """Verify sudden intraday VIX spike (> +10%) penalizes score and logs warning."""
    snap_spike = calculate_market_state(
        custom_nifty_price=25000.0,
        custom_ema200=24000.0,
        custom_vix=15.0,
        custom_vix_delta_pct=14.5  # VIX jumped 14.5% in morning
    )
    assert snap_spike.vix_score == -1  # 0 normal - 1 spike penalty = -1
    assert "VIX Spike Warning" in snap_spike.provenance_reason


def test_multi_asset_and_intraday_windows():
    """Verify asset class and intraday session window resolution."""
    snap = calculate_market_state(
        custom_nifty_price=25000.0,
        custom_ema200=24000.0,
        custom_vix=13.0,
        session_phase=SessionPhase.INTRADAY
    )
    assert snap.asset_class == AssetClass.EQUITY_NSE
    assert snap.intraday_window is not None
    assert isinstance(snap.intraday_window, IntradayWindow)


def test_reset_market_state_cache():
    """Verify reset_market_state_cache clears in-memory state cleanly."""
    calculate_market_state(custom_nifty_price=25000.0, custom_ema200=24000.0, custom_vix=13.0)
    assert get_cached_market_state() is not None
    reset_market_state_cache()
    # Cache cleared; next fetch re-evaluates
    with patch("mjonai.core.market_state.calculate_market_state") as mock_calc:
        mock_calc.return_value = MarketStateSnapshot(
            market_state="NEUTRAL", total_score=0, nifty_price=24000.0, ema200=24000.0,
            price_score=0, vix=15.0, vix_score=0, vix_regime="NORMAL"
        )
        get_cached_market_state()
        mock_calc.assert_called_once()


def test_nan_inf_market_state_sanitization():
    """Verify passing NaN/Inf values is sanitized without crashing the engine."""
    snap = calculate_market_state(
        custom_nifty_price=float("nan"),
        custom_ema200=float("nan"),
        custom_vix=float("nan")
    )
    assert snap.data_quality == DataQuality.DEGRADED
    assert snap.vix == 15.0  # Safe default baseline
    assert snap.market_state == "DEGRADED"
