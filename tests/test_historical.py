"""
Production-Level Test Suite for data/angelone/historical.py
Tests Historical Candle Fetching, SmartAPI 3 req/sec Rate Limiter,
6 vs 7 Column Parsing (Open Interest), Candle Sanitization, and Fallbacks.
"""

from datetime import datetime, timedelta
from pathlib import Path
import sys
import time
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from mjonai.data.angelone.historical import (
    CandleInterval,
    Exchange,
    DataProvider,
    SmartAPIRateLimiter,
    _sanitize_candles,
    fetch_historical_candles,
    clear_candle_cache,
)


@pytest.fixture(autouse=True)
def clean_candle_cache_for_test():
    """Ensure complete cache isolation between test runs."""
    clear_candle_cache()
    yield
    clear_candle_cache()


def test_enums_completeness():
    """Verify all critical intervals and multi-asset exchanges are supported."""
    assert CandleInterval.THREE_MINUTE.value == "THREE_MINUTE"
    assert CandleInterval.FIVE_MINUTE.value == "FIVE_MINUTE"
    assert CandleInterval.ONE_DAY.value == "ONE_DAY"

    assert Exchange.NSE.value == "NSE"
    assert Exchange.NFO.value == "NFO"
    assert Exchange.BFO.value == "BFO"
    assert Exchange.MCX.value == "MCX"
    assert Exchange.CDS.value == "CDS"

    assert DataProvider.SMART_API.value == "SMART_API"
    assert DataProvider.YFINANCE.value == "YFINANCE"


def test_smart_api_rate_limiter_timing():
    """Verify rate limiter enforces minimum interval spacing between calls."""
    limiter = SmartAPIRateLimiter(min_interval_seconds=0.05)
    t0 = time.time()
    limiter.acquire()
    limiter.acquire()
    t1 = time.time()
    # Ensure at least 0.045s elapsed
    assert (t1 - t0) >= 0.045


def test_candle_sanitizer_invariants():
    """Verify candle sanitizer fixes inverted wicks and cleans NaNs/Infs."""
    raw_df = pd.DataFrame([
        {"Open": 100.0, "High": 90.0, "Low": 110.0, "Close": 105.0, "Volume": -50.0},  # Inverted high/low & negative volume
        {"Open": 102.0, "High": float("nan"), "Low": 98.0, "Close": 101.0, "Volume": 100.0},  # NaN row
        {"Open": 105.0, "High": 110.0, "Low": 104.0, "Close": 108.0, "Volume": 500.0},  # Valid row
    ])

    cleaned = _sanitize_candles(raw_df)
    assert len(cleaned) == 2  # NaN row dropped
    # High adjusted to max(Open, Close) = 105.0
    assert cleaned.iloc[0]["High"] == 105.0
    # Low adjusted to min(Open, Close) = 100.0
    assert cleaned.iloc[0]["Low"] == 100.0
    # Volume clipped to 0
    assert cleaned.iloc[0]["Volume"] == 0.0


def test_fetch_historical_candles_smart_api_equity_6_cols():
    """Verify 6-column parsing for Equity SmartAPI candle response."""
    mock_client = MagicMock()
    mock_client.getCandleData.return_value = {
        "status": True,
        "data": [
            ["2026-08-17T09:15:00+05:30", 2500.0, 2510.0, 2495.0, 2505.0, 15000],
            ["2026-08-17T09:20:00+05:30", 2505.0, 2515.0, 2502.0, 2512.0, 18000],
        ]
    }

    df = fetch_historical_candles(
        symbol="RELIANCE",
        token="2885",
        interval=CandleInterval.FIVE_MINUTE,
        exchange=Exchange.NSE,
        smart_api_client=mock_client,
    )

    assert df is not None
    assert len(df) == 2
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert df.attrs.get("data_provider") == "SMART_API"
    assert df.iloc[0]["Close"] == 2505.0


def test_fetch_historical_candles_smart_api_fo_7_cols_open_interest():
    """Verify 7-column parsing with Open Interest (OI) for F&O SmartAPI responses."""
    mock_client = MagicMock()
    mock_client.getCandleData.return_value = {
        "status": True,
        "data": [
            ["2026-08-17T09:15:00+05:30", 120.0, 135.0, 115.0, 130.0, 50000, 1200000],
            ["2026-08-17T09:20:00+05:30", 130.0, 140.0, 128.0, 138.0, 65000, 1250000],
        ]
    }

    df = fetch_historical_candles(
        symbol="NIFTY26AUG24500CE",
        token="54321",
        interval=CandleInterval.FIVE_MINUTE,
        exchange=Exchange.NFO,
        smart_api_client=mock_client,
    )

    assert df is not None
    assert len(df) == 2
    assert "OpenInterest" in df.columns
    assert df.iloc[0]["OpenInterest"] == 1200000
    assert df.iloc[1]["OpenInterest"] == 1250000


def test_auto_token_resolution_when_token_none():
    """Verify token is auto-resolved via token_map when token is None."""
    mock_client = MagicMock()
    mock_client.getCandleData.return_value = {
        "status": True,
        "data": [["2026-08-17T09:15:00+05:30", 100.0, 102.0, 99.0, 101.0, 1000]]
    }

    # Pass symbol without explicit token
    df = fetch_historical_candles(
        symbol="RELIANCE",
        token=None,
        interval=CandleInterval.FIVE_MINUTE,
        exchange=Exchange.NSE,
        smart_api_client=mock_client,
    )

    assert df is not None
    # Verify smart_api_client was called with resolved token
    call_args = mock_client.getCandleData.call_args[0][0]
    assert call_args["symboltoken"] is not None
    assert len(call_args["symboltoken"]) > 0


def test_historical_candle_in_memory_ttl_cache():
    """Verify in-memory candle TTL cache deduplicates network requests and obeys cache flush."""
    from mjonai.data.angelone.historical import clear_candle_cache, get_candle_cache_size

    clear_candle_cache()
    assert get_candle_cache_size() == 0

    mock_client = MagicMock()
    mock_client.getCandleData.return_value = {
        "status": True,
        "data": [["2026-08-17T09:15:00+05:30", 100.0, 102.0, 99.0, 101.0, 1000]]
    }

    # 1. First fetch -> misses cache and queries SmartAPI
    df1 = fetch_historical_candles(
        symbol="TCS",
        token="11536",
        interval=CandleInterval.FIVE_MINUTE,
        smart_api_client=mock_client,
        use_cache=True,
        cache_ttl_seconds=60,
    )
    assert df1 is not None
    assert mock_client.getCandleData.call_count == 1
    assert get_candle_cache_size() == 1

    # 2. Second immediate fetch for same symbol/timeframe -> served from RAM cache (0 extra network calls)
    df2 = fetch_historical_candles(
        symbol="TCS",
        token="11536",
        interval=CandleInterval.FIVE_MINUTE,
        smart_api_client=mock_client,
        use_cache=True,
        cache_ttl_seconds=60,
    )
    assert df2 is not None
    assert mock_client.getCandleData.call_count == 1  # Still 1 call!
    assert len(df2) == len(df1)

    # 3. Bypass cache explicitly
    df3 = fetch_historical_candles(
        symbol="TCS",
        token="11536",
        interval=CandleInterval.FIVE_MINUTE,
        smart_api_client=mock_client,
        use_cache=False,
    )
    assert df3 is not None
    assert mock_client.getCandleData.call_count == 2  # Increments to 2

    # 4. Flush cache
    clear_candle_cache()
    assert get_candle_cache_size() == 0
