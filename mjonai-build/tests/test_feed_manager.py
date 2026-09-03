from datetime import datetime
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Add workspace root to sys.path
_root_dir = Path(__file__).resolve().parent.parent
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

from core.time_utils import Exchange
from data.feed_manager import (
    LiveQuoteSnapshot,
    LiveFeedManager,
    register_feed_provider,
    update_multi_asset_tick,
)
from data.token_resolver import BrokerType

@pytest.fixture(autouse=True)
def clean_manager():
    LiveFeedManager.reset_feed_manager()
    yield
    LiveFeedManager.reset_feed_manager()

def test_live_quote_snapshot_contract():
    snap = LiveQuoteSnapshot(
        symbol='RELIANCE',
        token='2885',
        exchange='NSE',
        ltp=2540.50,
        volume=1200000,
        oi=50000,
        vwap=2538.20,
        best_bid=2540.00,
        best_ask=2540.50,
        spread_bps=1.97,
        order_imbalance_ratio=0.15,
        timestamp=datetime.now(),
        staleness_seconds=0.2,
    )
    assert snap.symbol == 'RELIANCE'
    assert snap.ltp == 2540.50
    assert snap.vwap == 2538.20
    assert snap['ltp'] == 2540.50
    assert snap.get('spread_bps') == 1.97
    d = snap.to_dict()
    assert isinstance(d, dict)
    assert d['symbol'] == 'RELIANCE'
    assert d['vwap'] == 2538.20

@patch('data.feed_manager._angel_get_price')
@patch('data.feed_manager.TokenResolver.get_token')
def test_get_price_resolution(mock_get_token, mock_angel_price):
    mock_get_token.return_value = '2885'
    mock_angel_price.return_value = 2500.0

    # 1. By Symbol (triggers token resolution)
    price = LiveFeedManager.get_price('RELIANCE', exchange=Exchange.NSE)
    assert price == 2500.0
    mock_get_token.assert_called_with('RELIANCE', broker=BrokerType.ANGELONE, exchange='NSE')

    # 2. By Token directly (digits bypass token resolution)
    mock_get_token.reset_mock()
    price2 = LiveFeedManager.get_price('2885', exchange=Exchange.NSE)
    assert price2 == 2500.0
    mock_get_token.assert_not_called()

@patch('data.feed_manager._angel_get_staleness')
@patch('data.feed_manager._angel_get_price')
@patch('data.feed_manager.TokenResolver.get_token')
def test_get_price_staleness_guard(mock_get_token, mock_angel_price, mock_staleness):
    mock_get_token.return_value = '2885'
    mock_angel_price.return_value = 2500.0
    mock_staleness.return_value = 10.5  # 10.5 seconds old

    # Fresh tolerance passes
    p1 = LiveFeedManager.get_price('RELIANCE', max_staleness_seconds=15.0)
    assert p1 == 2500.0

    # Strict tolerance rejects stale price
    p2 = LiveFeedManager.get_price('RELIANCE', max_staleness_seconds=5.0)
    assert p2 is None

@patch('data.feed_manager._angel_fetch_candles')
@patch('data.feed_manager._angel_get_price')
@patch('data.feed_manager.TokenResolver.get_token')
def test_get_price_historical_candle_fallback(mock_get_token, mock_angel_price, mock_fetch_candles):
    mock_get_token.return_value = '2885'
    mock_angel_price.return_value = None  # WebSocket has not received tick yet
    mock_fetch_candles.return_value = pd.DataFrame({'close': [2480.0, 2495.5]})

    # Without fallback -> None
    p1 = LiveFeedManager.get_price('RELIANCE', fallback_to_candle=False)
    assert p1 is None

    # With fallback -> 2495.5
    p2 = LiveFeedManager.get_price('RELIANCE', fallback_to_candle=True)
    assert p2 == 2495.5

@patch('data.feed_manager._angel_get_price')
@patch('data.feed_manager.TokenResolver.get_token')
def test_get_prices_bulk_vector_retrieval(mock_get_token, mock_angel_price):
    mock_get_token.side_effect = lambda sym, **kw: '101' if sym == 'INFY' else '102'
    mock_angel_price.side_effect = lambda tok: 1500.0 if tok == '101' else 3500.0

    bulk = LiveFeedManager.get_prices_bulk(['INFY', 'TCS'], exchange=Exchange.NSE)
    assert len(bulk) == 2
    assert bulk['INFY'] == 1500.0
    assert bulk['TCS'] == 3500.0

@patch('data.feed_manager._angel_get_volume')
@patch('data.feed_manager._angel_get_oi')
def test_get_volume_and_oi(mock_oi, mock_vol):
    mock_vol.return_value = 500000
    mock_oi.return_value = 12000

    assert LiveFeedManager.get_volume('2885', exchange=Exchange.NSE) == 500000
    assert LiveFeedManager.get_oi('2885', exchange=Exchange.NFO) == 12000

@patch('data.feed_manager._angel_get_depth')
def test_order_imbalance_ratio(mock_depth):
    # Case 1: Neutral / equal book
    mock_depth.return_value = {'bid_qty': 1000, 'ask_qty': 1000}
    imb = LiveFeedManager.get_order_imbalance('2885', exchange=Exchange.NSE)
    assert imb == 0.0

    # Case 2: Heavy Buy Dominance (100% buy pressure)
    mock_depth.return_value = {'bid_qty': 3000, 'ask_qty': 1000}
    imb_buy = LiveFeedManager.get_order_imbalance('2885', exchange=Exchange.NSE)
    assert imb_buy == 0.5  # (3000-1000)/4000 = 0.5

    # Case 3: Empty depth
    mock_depth.return_value = None
    assert LiveFeedManager.get_order_imbalance('2885', exchange=Exchange.NSE) is None

def test_multi_asset_custom_provider_and_ticks():
    # 1. Custom Provider Registration
    def crypto_provider(sym):
        if sym == 'BTCUSDT':
            return {'ltp': 65000.0, 'volume': 100, 'vwap': 64800.0}
        return None

    register_feed_provider(Exchange.CRYPTO, crypto_provider)
    assert LiveFeedManager.get_price('BTCUSDT', exchange=Exchange.CRYPTO) == 65000.0
    assert LiveFeedManager.get_price('ETHUSDT', exchange=Exchange.CRYPTO) is None
    assert LiveFeedManager.get_vwap('BTCUSDT', exchange=Exchange.CRYPTO) == 64800.0

    # 2. Ingest Multi-Asset Tick Directly
    update_multi_asset_tick('AAPL', ltp=185.50, volume=5000000, vwap=184.90, best_bid=185.45, best_ask=185.55)
    assert LiveFeedManager.get_price('AAPL', exchange=Exchange.US_EQUITY) == 185.50
    assert LiveFeedManager.get_volume('AAPL', exchange=Exchange.US_EQUITY) == 5000000
    assert LiveFeedManager.get_vwap('AAPL', exchange=Exchange.US_EQUITY) == 184.90
    assert LiveFeedManager.get_spread('AAPL', exchange=Exchange.US_EQUITY) is not None

@patch('data.feed_manager._angel_is_healthy')
@patch('data.feed_manager._angel_get_stats')
def test_diagnostics_and_health(mock_stats, mock_healthy):
    mock_healthy.return_value = True
    mock_stats.return_value = {'is_healthy': True, 'total_ticks_received': 0}

    diag = LiveFeedManager.get_diagnostics()
    assert 'is_angelone_healthy' in diag
    assert 'custom_multi_asset_tracked' in diag
    assert 'registered_custom_exchanges' in diag
    assert LiveFeedManager.is_healthy(Exchange.NSE) is True

def test_get_quote_snapshot():
    update_multi_asset_tick('MSFT', ltp=420.50, volume=8000000, vwap=419.80, best_bid=420.40, best_ask=420.60)
    snap = LiveFeedManager.get_quote_snapshot('MSFT', exchange=Exchange.US_EQUITY)
    assert snap is not None
    assert isinstance(snap, LiveQuoteSnapshot)
    assert snap.symbol == 'MSFT'
    assert snap.ltp == 420.50
    assert snap.vwap == 419.80
    assert snap.best_bid == 420.40
    assert snap.best_ask == 420.60
    assert snap.spread_bps is not None
