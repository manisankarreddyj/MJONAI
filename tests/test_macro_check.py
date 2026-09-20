# Unit & Boundary Integration Tests for data/macro/macro_check.py
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from mjonai.data.macro.macro_check import (
    MacroSentimentLevel,
    MacroThresholds,
    MacroCorrelationWeights,
    MacroSentimentSnapshot,
    FIIDIICashFlow,
    MACRO_SYMBOLS,
    DEFAULT_MACRO_WEIGHTS,
    get_macro_symbols,
    fetch_fii_dii_cash_flow,
    fetch_macro_sentiment,
    get_cached_macro_sentiment,
    reset_macro_cache,
)

@pytest.fixture(autouse=True)
def clean_cache():
    reset_macro_cache()
    yield
    reset_macro_cache()

def _mock_df(prev_close, last_close):
    return pd.DataFrame({'Close': [prev_close, last_close]})

def test_macro_sentiment_enums():
    assert MacroSentimentLevel.BULLISH == 'BULLISH'
    assert MacroSentimentLevel.NEUTRAL == 'NEUTRAL'
    assert MacroSentimentLevel.BEARISH == 'BEARISH'
    assert MacroSentimentLevel.RISK_OFF == 'RISK_OFF'

def test_macro_correlation_weights_normalization():
    w = DEFAULT_MACRO_WEIGHTS
    total = w.us_equities_weight + w.gift_asia_weight + w.energy_weight + w.fx_dollar_weight + w.rates_vix_weight
    assert round(total, 4) == 1.0

def test_get_macro_symbols_and_env_override(monkeypatch):
    default_map = get_macro_symbols()
    assert 'sp500' in default_map
    assert 'gift_nifty' in default_map
    assert 'crude' in default_map
    assert 'us_vix' in default_map

    monkeypatch.setenv('MJONAI_MACRO_SYMBOLS', 'sp500:CUSTOM_SP,crude:CUSTOM_OIL')
    overridden = get_macro_symbols()
    assert overridden['sp500'] == 'CUSTOM_SP'
    assert overridden['crude'] == 'CUSTOM_OIL'
    assert overridden['brent'] == 'BZ=F'

def test_fii_dii_cash_flow_streak(monkeypatch):
    monkeypatch.setenv('MJONAI_FII_NET_CR', '-3500.0')
    monkeypatch.setenv('MJONAI_DII_NET_CR', '2100.0')
    flow = fetch_fii_dii_cash_flow()
    assert flow.fii_net_crores == -3500.0
    assert flow.dii_net_crores == 2100.0
    assert flow.net_institutional_flow == -1400.0
    assert flow.is_fii_heavy_selling is True
    assert flow.fii_consecutive_sell_days == 3
    assert flow.feed_available is True
    assert flow.date_str != ''

def test_fii_dii_cash_flow_no_feed_is_honest_sentinel(monkeypatch):
    # No real feed and no env override -> feed_available=False sentinel. The
    # zeros are noise, never a fabricated live reading; date_str stays empty.
    monkeypatch.delenv('MJONAI_FII_NET_CR', raising=False)
    monkeypatch.delenv('MJONAI_DII_NET_CR', raising=False)
    flow = fetch_fii_dii_cash_flow()
    assert flow.feed_available is False
    assert flow.is_fii_heavy_selling is False
    assert flow.fii_consecutive_sell_days == 0
    assert flow.date_str == ''

def test_macro_sentiment_snapshot_dual_access():
    snap = MacroSentimentSnapshot(
        sp500_change_pct=1.5,
        gift_nifty_change_pct=0.8,
        crude_change_pct=-0.8,
        overall='BULLISH',
        signal_limit_adjustment=0,
        risk_score=-1,
        composite_score=42.5,
        flags=['Bullish alignment'],
    )
    assert snap.sp500_change_pct == 1.5
    assert snap.overall == 'BULLISH'
    assert snap.composite_score == 42.5
    assert snap.is_risk_off is False
    assert snap['sp500_change_pct'] == 1.5
    assert snap['overall'] == 'BULLISH'
    assert snap.get('crude_change_pct') == -0.8
    assert snap.get('non_existent', 'DEFAULT') == 'DEFAULT'
    d = snap.to_dict()
    assert isinstance(d, dict)
    assert d['overall'] == 'BULLISH'

@patch('yfinance.Ticker')
def test_fetch_macro_sentiment_bullish(mock_ticker_cls):
    def side_effect(symbol):
        mock_t = MagicMock()
        if symbol in ('^GSPC', 'ES=F', 'NQ=F', '^NSEI', '^N225'):
            mock_t.history.return_value = _mock_df(100.0, 101.5)
        elif symbol in ('CL=F', 'BZ=F'):
            mock_t.history.return_value = _mock_df(100.0, 98.5)
        elif symbol == 'DX-Y.NYB':
            mock_t.history.return_value = _mock_df(100.0, 99.5)
        else:
            mock_t.history.return_value = _mock_df(100.0, 100.0)
        return mock_t

    mock_ticker_cls.side_effect = side_effect
    snapshot = fetch_macro_sentiment(force_refresh=True)
    assert snapshot.overall == 'BULLISH'
    assert snapshot.signal_limit_adjustment == 0
    assert snapshot.is_risk_off is False
    assert snapshot.successful_fetches == len(MACRO_SYMBOLS)
    assert snapshot.data_quality == 'CONFIDENT'
    assert snapshot.composite_score > 0

@patch('yfinance.Ticker')
def test_fetch_macro_sentiment_compound_risk_off(mock_ticker_cls):
    def side_effect(symbol):
        mock_t = MagicMock()
        if symbol in ('^GSPC', 'ES=F', 'NQ=F', '^NSEI'):
            mock_t.history.return_value = _mock_df(100.0, 98.0)
        elif symbol in ('CL=F', 'BZ=F'):
            mock_t.history.return_value = _mock_df(100.0, 104.5)
        elif symbol == 'DX-Y.NYB':
            mock_t.history.return_value = _mock_df(100.0, 101.0)
        elif symbol == '^VIX':
            mock_t.history.return_value = _mock_df(100.0, 115.0)
        elif symbol == '^N225':
            mock_t.history.return_value = _mock_df(100.0, 98.0)
        else:
            mock_t.history.return_value = _mock_df(100.0, 103.0)
        return mock_t

    mock_ticker_cls.side_effect = side_effect
    snapshot = fetch_macro_sentiment(force_refresh=True)
    assert snapshot.overall == 'RISK_OFF'
    assert snapshot.signal_limit_adjustment == -2
    assert snapshot.is_risk_off is True
    assert any('COMPOUND RISK-OFF' in f for f in snapshot.flags)

@patch('mjonai.data.macro.macro_check._fetch_direct_http_change')
@patch('yfinance.Ticker')
def test_fetch_macro_sentiment_direct_http_fallback(mock_ticker_cls, mock_http):
    mock_ticker_cls.side_effect = Exception('Rate limited')
    mock_http.return_value = 0.5

    snapshot = fetch_macro_sentiment(force_refresh=True)
    assert snapshot.successful_fetches == len(MACRO_SYMBOLS)
    assert snapshot.provider_used == 'DIRECT_HTTP_FALLBACK'

@patch('mjonai.data.macro.macro_check._fetch_direct_http_change')
@patch('yfinance.Ticker')
def test_fetch_macro_sentiment_degraded_network_fallback(mock_ticker_cls, mock_http):
    mock_ticker_cls.side_effect = Exception('HTTP 503 Service Unavailable')
    mock_http.return_value = None

    snapshot = fetch_macro_sentiment(force_refresh=True)
    assert snapshot.overall == 'NEUTRAL'
    assert snapshot.signal_limit_adjustment == 0
    assert snapshot.data_quality == 'DEGRADED'
    assert snapshot.successful_fetches == 0

@patch('yfinance.Ticker')
def test_in_memory_ttl_caching(mock_ticker_cls):
    mock_t = MagicMock()
    mock_t.history.return_value = _mock_df(100.0, 100.5)
    mock_ticker_cls.return_value = mock_t

    snap1 = fetch_macro_sentiment()
    assert mock_ticker_cls.call_count > 0
    calls_after_first = mock_ticker_cls.call_count

    snap2 = get_cached_macro_sentiment()
    assert snap2.fetched_at == snap1.fetched_at
    assert mock_ticker_cls.call_count == calls_after_first

    reset_macro_cache()
    snap3 = fetch_macro_sentiment(force_refresh=True)
    assert mock_ticker_cls.call_count > calls_after_first
