"""Google News RSS reader: stdlib XML parsing, red-flag contract, symbol match.

The live path was verified by hand (100 items, title/pubDate/source/link).
All tests below run offline on canned RSS.
"""
from mjonai.research.data import google_rss as gr


def _rss():
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>NIFTY - Google News</title>
<item><title>SEBI bars broker for fraud in Nifty options</title>
<link>https://news.google.com/rss/articles/x1</link>
<pubDate>Wed, 14 Oct 2026 10:44:57 GMT</pubDate>
<source url="https://economictimes.indiatimes.com">The Economic Times</source></item>
<item><title>Nifty closes higher on bank gains</title>
<link>https://news.google.com/rss/articles/x2</link>
<pubDate>Wed, 14 Oct 2026 09:00:00 GMT</pubDate>
<source url="https://example.com">Example</source></item>
<item><title></title><link>https://news.google.com/rss/articles/x3</link></item>
</channel></rss>"""


def test_fetch_parses_items(monkeypatch):
    import urllib.request

    class FakeResp:
        def read(self):
            return _rss().encode("utf-8")

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: FakeResp())
    arts = gr._fetch_rss("NIFTY")
    assert len(arts) == 2
    assert arts[0]["source"] == "The Economic Times"
    assert arts[0]["published"] == "Wed, 14 Oct 2026 10:44:57 GMT"
    assert arts[0]["url"].startswith("https://")


def test_fetch_fail_closed_on_network(monkeypatch):
    import urllib.request

    def boom(req, timeout=None):
        raise ConnectionError("down")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert gr._fetch_rss("NIFTY") == []


def test_refresh_stores_flagged_only(tmp_path, monkeypatch):
    import json
    import urllib.request

    class FakeResp:
        def read(self):
            return _rss().encode("utf-8")

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: FakeResp())
    store = tmp_path / "news_headlines.json"
    out = gr.refresh_headlines(queries=("NIFTY NSE",), publisher_feeds=(),
                               store_path=store)
    assert out["status"] == "ok" and out["flagged"] == 1
    data = json.loads(store.read_text(encoding="utf-8"))
    assert len(data["flagged"]) == 1
    assert "fraud" in data["flagged"][0]["red_flags"]


def test_publisher_feed_parsed_without_source_tag(tmp_path, monkeypatch):
    """Publisher-direct XML (no <source> element) parses; failures yield []."""
    import urllib.request

    class FakeResp:
        def read(self):
            return ("""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>RBI holds rates steady</title><link>https://ex.com/r1</link>
<pubDate>Wed, 14 Oct 2026 09:00:00 GMT</pubDate></item>
</channel></rss>""").encode("utf-8")

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: FakeResp())
    arts = gr._fetch_feed_url("https://example.com/rss")
    assert len(arts) == 1 and arts[0]["source"] is None

    def boom(req, timeout=None):
        raise ConnectionError("down")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert gr._fetch_feed_url("https://example.com/rss") == []


def test_extended_veto_phrases_flagged():
    from mjonai.research.data.gdelt_news import flag_red_flags
    arts = flag_red_flags([
        {"title": "Company faces litigation over land dispute", "url": "https://x/1"},
        {"title": "Board declares record dividend", "url": "https://x/2"},
        {"title": "Promoter pledge of shares invoked", "url": "https://x/3"},
    ])
    assert "litigation" in arts[0]["red_flags"]
    assert arts[1]["red_flags"] == []  # good news never flagged
    assert "pledge of shares" in arts[2]["red_flags"]


def test_red_flags_for_symbol_matches_root(tmp_path):
    import json
    store = tmp_path / "news_headlines.json"
    store.write_text(json.dumps({"flagged": [
        {"title": "SEBI bars broker for fraud in Nifty options",
         "url": "https://x/1", "published": "today",
         "red_flags": ["sebi bars", "fraud"]},
        {"title": "RBI holds rates steady", "url": "https://x/2",
         "published": "today", "red_flags": []},
    ]}), encoding="utf-8")
    hits = gr.red_flags_for_symbol("NIFTY26AUG24500CE", store_path=store)
    assert len(hits) == 1 and "fraud" in hits[0]
    assert gr.red_flags_for_symbol("RELIANCE", store_path=store) == []
    assert gr.red_flags_for_symbol("X", store_path=tmp_path / "nope.json") == []
