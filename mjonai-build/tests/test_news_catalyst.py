"""
Unit tests for intelligence/news_catalyst.py (Corporate News & Catalyst Sentry).
Verifies RSS parsing, keyword categorization, critical dealbreaker detection,
and fail-safe network error handling.
"""

from unittest.mock import MagicMock, patch
import pytest

from intelligence.news_catalyst import (
    parse_rss_feed,
    analyze_headlines,
    fetch_symbol_news,
    NewsSentimentResult,
)


def test_parse_rss_feed_valid_xml():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Google News</title>
        <item><title>Reliance secures mega contract for 5G expansion</title></item>
        <item><title>Tata Motors EV sales jump 45% in August</title></item>
      </channel>
    </rss>"""
    headlines = parse_rss_feed(xml)
    assert len(headlines) == 2
    assert "Reliance secures mega contract" in headlines[0]
    assert "Tata Motors" in headlines[1]


def test_parse_rss_feed_corrupt_xml():
    """Corrupt XML must return empty list without raising unhandled exceptions."""
    headlines = parse_rss_feed("<invalid>unclosed tag")
    assert headlines == []


def test_analyze_headlines_dealbreaker():
    headlines = [
        "Company statutory auditor resigns citing scope limitations",
        "Stock falls 5% in intraday trade",
    ]
    res = analyze_headlines("XYZCORP", headlines)
    assert res.is_dealbreaker is True
    assert res.sentiment == "CRITICAL_DEALBREAKER"
    assert res.score < 0
    assert len(res.red_flags) >= 1
    assert "auditor resigns" in res.red_flags[0].lower()


def test_analyze_headlines_bullish_catalyst():
    headlines = [
        "USFDA approval granted for generic blockbuster injection",
        "Wins order worth Rs 1,500 crore from Indian Railways",
        "Profit surges 60% in Q1 results",
    ]
    res = analyze_headlines("PHARMASHARE", headlines)
    assert res.is_dealbreaker is False
    assert res.sentiment == "BULLISH_CATALYST"
    assert res.score > 0.30
    assert len(res.bullish_catalysts) >= 2


def test_fetch_symbol_news_mocked_success():
    xml = """<rss><channel>
      <item><title>TCS secures multi-year cloud transformation deal</title></item>
    </channel></rss>"""

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = xml

    with patch("httpx.Client.get", return_value=mock_resp):
        res = fetch_symbol_news("TCS")
        assert res.symbol == "TCS"
        assert len(res.headlines) == 1
        assert "TCS secures" in res.headlines[0]


def test_fetch_symbol_news_network_timeout():
    """Network failure must return a neutral result without raising error."""
    with patch("httpx.Client.get", side_effect=Exception("Connection timeout")):
        res = fetch_symbol_news("INFY")
        assert res.symbol == "INFY"
        assert res.sentiment == "NEUTRAL"
        assert res.is_dealbreaker is False
