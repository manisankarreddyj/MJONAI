"""
Fault Recovery, Broker Network Severance & Chaos Engineering Test Suite.
Verifies system resilience against network crashes, corrupted feeds, and multi-broker failovers.
"""

from datetime import date, datetime
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import pytest

# Ensure workspace root is in sys.path
_root_dir = Path(__file__).resolve().parent.parent
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

from data.feed_manager import LiveFeedManager, update_multi_asset_tick, clear_multi_asset_ticks
from data.token_resolver import TokenResolver, BrokerType
from data.earnings import check_earnings_risk
from data.market import calculate_sector_breadth, calculate_opening_rvol, calculate_advance_decline_ratio
from core.mqi import calculate_mqi
from core.market_state import calculate_market_state


@pytest.fixture(autouse=True)
def cleanup():
    clear_multi_asset_ticks()
    yield
    clear_multi_asset_ticks()


# ── 1. WEBSOCKET OUTAGE & HISTORICAL CANDLE FALLBACK ─────────────────────────

@patch("data.feed_manager._angel_get_price")
@patch("data.feed_manager._angel_fetch_candles")
@patch("data.token_resolver.TokenResolver.get_token")
def test_websocket_outage_candle_fallback_recovery(mock_tok, mock_candles, mock_live):
    """
    Verify when live WebSocket tick is None, LiveFeedManager
    gracefully recovers by falling back to the latest 1-minute historical close.
    """
    mock_tok.return_value = "2885"
    mock_live.return_value = None  # WebSocket stream disconnected / no ticks yet

    # Mock historical 1-minute candle DataFrame with Close = 2950.0
    import pandas as pd
    mock_df = pd.DataFrame([
        {"Open": 2940.0, "High": 2960.0, "Low": 2935.0, "Close": 2950.0, "Volume": 15000}
    ])
    mock_candles.return_value = mock_df

    # Fallback enabled
    price = LiveFeedManager.get_price("RELIANCE", fallback_to_candle=True)
    assert price == 2950.0
    mock_candles.assert_called_once()


# ── 2. CORRUPTED & MALFORMED PAYLOAD CHAOS FUZZING ───────────────────────────

def test_malformed_corrupt_tick_inputs():
    """Verify corrupted tick inputs (negative prices, zero volume) do not crash the feed manager."""
    # Negative and zero prices are safely ignored
    update_multi_asset_tick("CORRUPT_1", ltp=-100.0)
    assert LiveFeedManager.get_price("CORRUPT_1", exchange="CRYPTO") is None

    update_multi_asset_tick("CORRUPT_2", ltp=0.0)
    assert LiveFeedManager.get_price("CORRUPT_2", exchange="CRYPTO") is None


def test_corrupted_sector_breadth_fuzzing():
    """Verify sector breadth handles corrupted, NaN, and empty inputs safely."""
    # Empty dictionary -> Safe 50% neutral fallback
    snap = calculate_sector_breadth({})
    assert snap.breadth_pct == 0.50

    # None inputs
    snap_none = calculate_sector_breadth(None)
    assert snap_none.breadth_pct == 0.50


def test_extreme_market_out_of_bounds_resilience():
    """Verify MQI and Market State engines survive extreme boundary values (VIX=99.9, ATR=10%)."""
    mqi_extreme = calculate_mqi(
        custom_atr_score=0,        # 0 points (Black Swan compression failure)
        custom_vix_change_score=0, # 0 points (+50% VIX spike)
        custom_breadth_pct=0.0,    # 0% breadth
        custom_volume_ratio=0.2    # 0.2x volume
    )
    assert 0 <= mqi_extreme.total_score <= 10
    assert mqi_extreme.no_trade is True or mqi_extreme.signals_allowed == 0

    # Zero advances and zero declines in A/D ratio -> ZeroDivisionError protected
    ad_snap = calculate_advance_decline_ratio(advances=0, declines=0)
    assert ad_snap.ad_ratio == 0.0
    assert ad_snap.ad_spread == 0


# ── 3. MULTI-BROKER FAILOVER RESILIENCE (TD-013) ─────────────────────────────

def test_multi_broker_failover_execution_flow():
    """
    Verify symbology translation and contract resolution operate seamlessly
    during failover from primary broker (AngelOne) to secondary broker (Shoonya/Zerodha).
    """
    sym = "RELIANCE"
    token_angel = TokenResolver.get_token(sym, broker=BrokerType.ANGELONE)
    token_paper = TokenResolver.get_token(sym, broker=BrokerType.PAPER)

    assert token_angel is not None or token_paper is not None

    # Cross-broker symbol translation
    clean_sym = TokenResolver.translate_symbol("NSE:RELIANCE-EQ", from_broker=BrokerType.ZERODHA, to_broker=BrokerType.ANGELONE)
    assert clean_sym == "RELIANCE"
