"""GDELT keyless news reader: strict-shape parsing, red-flag contract, live gate.

UNVERIFIED LIVE (2026-10-14): api.gdeltproject.org 429'd every probe from
this machine, so all fixtures below are canned from the DOCUMENTED shape.
Nothing in the engine calls this module until verify_live() passes once on
the owner machine — enforced by is_live_verified().
"""
import sys
import types

import pytest

from mjonai.research.data import gdelt_news as gn


def _doc_shape():
    return {
        "query_details": {"title": "x"},
        "articles": [
            {"url": "https://ex.com/a1", "url_mobile": "", "title": "SEBI bars broker for fraud",
             "seendate": "20261014120000", "socialimage": "", "domain": "ex.com",
             "language": "English", "sourcecountry": "India"},
            {"url": "https://ex.com/a2", "title": "Nifty closes higher on bank gains",
             "seendate": "20261014110000", "domain": "ex.com"},
            {"url": "", "title": "No URL here"},                       # refused: blank url
            {"url": "https://ex.com/a4", "title": "   "},              # refused: blank title
            "not-a-dict",                                              # refused: wrong type
            {"url": "https://ex.com/a5", "title": "RBI holds rates",
             "seendate": "not-a-date", "domain": "ex.com"},            # kept, date None
        ],
    }


def test_parse_accepts_documented_shape_only():
    arts = gn._parse_articles(_doc_shape())
    assert len(arts) == 3
    assert arts[0]["title"] == "SEBI bars broker for fraud"
    assert arts[0]["seendate"] == "2026-10-14T12:00:00+00:00"
    assert arts[0]["domain"] == "ex.com"
    assert arts[2]["seendate"] is None  # bad date keeps the row, nulls the field


def test_parse_refuses_wrong_shapes():
    assert gn._parse_articles({}) == []
    assert gn._parse_articles({"articles": {"not": "a list"}}) == []
    assert gn._parse_articles(None) == []
    assert gn._parse_articles([{"title": "x", "url": "y"}]) == []


def test_red_flags_match_documented_triggers():
    arts = gn.flag_red_flags(gn._parse_articles(_doc_shape()))
    assert "fraud" in arts[0]["red_flags"]
    assert arts[1]["red_flags"] == []
    assert arts[2]["red_flags"] == []


def _install_fake_requests(monkeypatch, payload=None, status=200):
    calls = {}

    class FakeResponse:
        status_code = status

        def __init__(self):
            calls["n"] = calls.get("n", 0) + 1

        @property
        def ok(self):
            return 200 <= self.status_code < 300

        def json(self):
            return payload

    def fake_get(url, params=None, headers=None, timeout=None):
        calls["params"] = params
        return FakeResponse()

    fake = types.ModuleType("requests")
    fake.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake)
    return calls


def test_fetch_fail_closed_on_429_and_network(monkeypatch):
    _install_fake_requests(monkeypatch, status=429)
    assert gn.fetch_headlines("NIFTY") == []

    def boom(url, params=None, headers=None, timeout=None):
        raise ConnectionError("down")

    fake = types.ModuleType("requests")
    fake.get = boom
    monkeypatch.setitem(sys.modules, "requests", fake)
    assert gn.fetch_headlines("NIFTY") == []
    assert gn.fetch_headlines("") == []


def test_fetch_sends_documented_params(monkeypatch):
    calls = _install_fake_requests(monkeypatch, payload=_doc_shape())
    arts = gn.fetch_headlines("NIFTY", maxrecords=10, timespan="24h")
    assert len(arts) == 3
    assert calls["params"]["query"] == "NIFTY"
    assert calls["params"]["mode"] == "artlist"
    assert calls["params"]["maxrecords"] == 10


def test_live_gate_defaults_closed():
    assert gn.is_live_verified() is False
