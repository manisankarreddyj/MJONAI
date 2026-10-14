"""DBnomics keyless macro reader: fail-closed parsing and fetching.

Clean-room from FinceptTerminal's DBnomicsService pattern (AGPL C++/Qt —
mechanism reimplemented, no code copied). Every test here is offline: the
HTTP layer is stubbed, so no test depends on network or on any real series.
"""

import sys
import types

import pytest

from mjonai.data.dbnomics import DbnomicsProvider


def _install_fake_requests(monkeypatch, payload=None, ok=True, exc=None):
    """Install a stub `requests` module returning one canned response."""
    calls = {}

    class FakeResponse:
        def __init__(self):
            self.status_code = 200 if ok else 404
            self._ok = ok
            calls["n"] = calls.get("n", 0) + 1

        @property
        def ok(self):
            return self._ok

        def json(self):
            if exc is not None:
                raise exc
            return payload

    def fake_get(url, params=None, timeout=None):
        calls["url"] = url
        calls["params"] = params
        if exc is not None and not ok:
            raise exc
        return FakeResponse()

    fake = types.ModuleType("requests")
    fake.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake)
    return calls


def _v22(periods, values):
    return {"series": {"docs": {"period": list(periods), "value": list(values)}}}


def test_fetch_series_returns_latest_finite_observation(monkeypatch):
    _install_fake_requests(
        monkeypatch,
        payload=_v22(["2024-01-01", "2024-02-01"], [4.5, 4.75]),
    )
    out = DbnomicsProvider().fetch_series("FRED", "X", "Y")
    assert out["available"] is True
    assert out["latest"] == {"period": "2024-02-01", "value": 4.75}


def test_fetch_series_skips_non_finite_trailing_values(monkeypatch):
    _install_fake_requests(
        monkeypatch,
        payload=_v22(["2024-01-01", "2024-02-01", "2024-03-01"], [4.5, None, "x"]),
    )
    out = DbnomicsProvider().fetch_series("FRED", "X", "Y")
    assert out["available"] is True
    assert out["latest"] == {"period": "2024-01-01", "value": 4.5}


def test_fetch_series_fail_closed_on_network_error(monkeypatch):
    _install_fake_requests(monkeypatch, ok=False, exc=ConnectionError("down"))
    out = DbnomicsProvider().fetch_series("FRED", "X", "Y")
    assert out == {"available": False, "reason": "fetch failed or feed disabled"}


def test_fetch_series_fail_closed_on_unexpected_shape(monkeypatch):
    _install_fake_requests(monkeypatch, payload={"unexpected": [1, 2, 3]})
    out = DbnomicsProvider().fetch_series("FRED", "X", "Y")
    assert out["available"] is False
    assert "shape" in out["reason"] or "finite" in out["reason"]


def test_fetch_series_blank_codes_fail_closed(monkeypatch):
    calls = _install_fake_requests(monkeypatch, payload=_v22(["d"], [1.0]))
    out = DbnomicsProvider().fetch_series("", "X", "Y")
    assert out["available"] is False
    assert "n" not in calls  # no HTTP request was even attempted


def test_fetch_many_drops_bad_series_without_poisoning(monkeypatch):
    _install_fake_requests(
        monkeypatch,
        payload=_v22(["2024-01-01"], [1.25]),
    )
    prov = DbnomicsProvider()
    out = prov.fetch_many([
        {"key": "good", "provider": "FRED", "dataset": "X", "series": "Y"},
        {"key": "blank", "provider": "", "dataset": "", "series": ""},
    ])
    assert out["available"] is True
    assert set(out["series"]) == {"good"}
    assert "blank" in out["dropped"]


def test_disabled_feed_never_fetches(monkeypatch):
    calls = _install_fake_requests(monkeypatch, payload=_v22(["d"], [1.0]))
    prov = DbnomicsProvider(disabled=True)
    assert prov.feed_available is False
    out = prov.fetch_series("FRED", "X", "Y")
    assert out["available"] is False
    assert "n" not in calls
