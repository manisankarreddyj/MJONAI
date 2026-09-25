"""Tests for the TradingTick 1-minute index-bar ingester.

Offline by contract: requests.get is mocked at the module boundary; no real
network is touched. Covers timestamp normalization (UTC epoch -> naive IST
bar-open), OHLC passthrough, the never-fabricate-Volume guarantee, empty/
malformed-day fail-closed behavior, the year/month/date enumeration fence,
response-shape tolerance (bare list vs {"dates": [...]}), and warehouse merge
idempotency.
"""

import json
from datetime import date

import pandas as pd
import pytest

import mjonai.research.data.tradingtick_1min as tt1

# 2015-01-09 09:15:00 IST = 1420775100 epoch seconds UTC (bar-open semantics).
_BAR1 = {"time": 1420775100, "open": 8285.45, "high": 8290.1,
         "low": 8284.9, "close": 8292.1}
_BAR2 = {"time": 1420775160, "open": 8292.1, "high": 8300.0,
         "low": 8291.7, "close": 8299.55}


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def patch_get(monkeypatch, responder):
    def _get(url, headers=None, timeout=None):
        return FakeResponse(responder(url))
    monkeypatch.setattr(tt1.requests, "get", _get)


def day_responder(rows=None, dates=None):
    rows = rows if rows is not None else [_BAR1, _BAR2]
    dates = dates if dates is not None else {"dates": ["2015-01-09"]}
    return {
        "years": {"years": ["2015"]},
        "months": {"months": [{"value": "Jan", "name": "January"}]},
        "dates": dates,
        "candles": rows,
    }


def test_fetch_day_normalizes_epoch_to_naive_ist(monkeypatch):
    patch_get(monkeypatch, lambda url: day_responder()["candles"])
    df = tt1.fetch_day("NIFTY", "2015-01-09")
    assert df is not None
    assert list(df.index) == [
        pd.Timestamp("2015-01-09 09:15:00"),
        pd.Timestamp("2015-01-09 09:16:00"),
    ]
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert df.index.name == "timestamp"
    assert df.iloc[0]["Open"] == 8285.45
    assert df.iloc[0]["Close"] == 8292.1
    assert df.iloc[-1]["Close"] == 8299.55


def test_fetch_day_never_fabricates_volume(monkeypatch):
    patch_get(monkeypatch, lambda url: day_responder()["candles"])
    df = tt1.fetch_day("NIFTY", "2015-01-09")
    assert df["Volume"].isna().all()
    assert not df["Open"].isna().any()
    assert not df["Close"].isna().any()


def test_fetch_day_empty_is_none(monkeypatch):
    patch_get(monkeypatch, lambda url: [])
    assert tt1.fetch_day("NIFTY", "2015-01-09") is None


def test_fetch_day_network_failure_is_none(monkeypatch):
    patch_get(monkeypatch, lambda url: None)
    assert tt1.fetch_day("BANKNIFTY", "2015-01-09") is None


def test_fetch_day_skips_malformed_rows(monkeypatch):
    bad = {"time": "garbage", "open": "x"}
    patch_get(monkeypatch, lambda url: [bad, _BAR1])
    df = tt1.fetch_day("NIFTY", "2015-01-09")
    assert len(df) == 1
    assert df.iloc[0]["Close"] == 8292.1


def test_fetch_day_all_malformed_is_none(monkeypatch):
    patch_get(monkeypatch, lambda url: [{"time": "garbage"}])
    assert tt1.fetch_day("NIFTY", "2015-01-09") is None


def test_unsupported_underlying_raises(monkeypatch):
    patch_get(monkeypatch, lambda url: {})
    with pytest.raises(ValueError):
        tt1.fetch_day("SENSEX", "2015-01-09")


def test_dates_response_shape_tolerance(monkeypatch):
    for shape in (["2015-01-09", "2015-01-12"],
                  {"dates": ["2015-01-09", "2015-01-12"]}):
        patch_get(monkeypatch, lambda url: shape if "action=dates" in url else
                  day_responder()["years"] if "action=years" in url else
                  day_responder()["months"] if "action=months" in url else None)
        assert tt1.list_dates("NIFTY", "2015", "Jan") == ["2015-01-09", "2015-01-12"]


def test_list_months_normalizes_to_short_form(monkeypatch):
    patch_get(monkeypatch, lambda url: {
        "months": [{"value": "Jan", "name": "January"},
                   {"value": "01", "name": "January"},
                   {"value": "jul", "name": "July"}]})
    assert tt1.list_months("NIFTY", "2015") == ["Jan", "Jan", "Jul"]


def test_enumerate_days_fence(monkeypatch):
    """Years outside [start.year, end.year] are never descended into, and
    trading dates outside [start, end] are excluded by the date fence."""
    calls = []

    def responder(url):
        calls.append(url)
        if "action=years" in url:
            return {"years": ["2015", "2016", "2026"]}
        if "action=months" in url:
            return {"months": [{"value": "Jan", "name": "January"}]}
        if "action=dates" in url:
            return {"dates": ["2014-12-30", "2015-01-09", "2015-01-12", "2016-02-01"]}
        return []

    patch_get(monkeypatch, responder)
    days = list(tt1.enumerate_days("NIFTY", date(2015, 1, 1), date(2015, 12, 31)))
    # 2016 and 2026 years never generate a dates fetch; 2014-12-30 and
    # 2016-02-01 fall outside the window.
    assert days == ["2015-01-09", "2015-01-12"]
    assert all("2016" not in c for c in calls)


def test_ingest_range_merges_into_per_underlying_warehouse(tmp_path, monkeypatch):
    def responder(url):
        if "action=years" in url:
            return {"years": ["2015"]}
        if "action=months" in url:
            return {"months": [{"value": "Jan", "name": "January"}]}
        if "action=dates" in url:
            return {"dates": ["2015-01-09"]}
        return [_BAR1, _BAR2]

    patch_get(monkeypatch, responder)
    out_dir = tmp_path
    s1 = tt1.ingest_range(date(2015, 1, 9), date(2015, 1, 9), str(out_dir),
                          underlyings=["NIFTY"])
    assert s1["days_ok"] == 1
    assert s1["bars_total"] == 2
    path = tmp_path / "NIFTY" / "2015-01.parquet"
    assert path.exists()
    first = pd.read_parquet(path)
    assert len(first) == 2
    assert first["timestamp"].iloc[0] == pd.Timestamp("2015-01-09 09:15:00")

    # Re-run the same range -> keep=last merge, still 2 bars.
    s2 = tt1.ingest_range(date(2015, 1, 9), date(2015, 1, 9), str(out_dir),
                          underlyings=["NIFTY"])
    assert s2["days_ok"] == 1
    assert len(pd.read_parquet(path)) == 2


def test_ingest_range_writes_both_indices_to_separate_files(tmp_path, monkeypatch):
    def responder(url):
        if "action=years" in url:
            return {"years": ["2015"]}
        if "action=months" in url:
            return {"months": [{"value": "Jan", "name": "January"}]}
        if "action=dates" in url:
            return {"dates": ["2015-01-09"]}
        return [_BAR1]

    patch_get(monkeypatch, responder)
    out_dir = tmp_path
    s = tt1.ingest_range(date(2015, 1, 9), date(2015, 1, 9), str(out_dir),
                         underlyings=["NIFTY", "BANKNIFTY"])
    assert s["days_ok"] == 2
    assert s["bars_total"] == 2
    assert (tmp_path / "NIFTY" / "2015-01.parquet").exists()
    assert (tmp_path / "BANKNIFTY" / "2015-01.parquet").exists()


def test_ingest_range_fail_closed_on_empty_day(tmp_path, monkeypatch):
    def responder(url):
        if "action=years" in url:
            return {"years": ["2015"]}
        if "action=months" in url:
            return {"months": [{"value": "Jan", "name": "January"}]}
        if "action=dates" in url:
            return {"dates": ["2015-01-09"]}
        return []  # the trading day itself has no bars
    patch_get(monkeypatch, responder)
    out_dir = tmp_path
    s = tt1.ingest_range(date(2015, 1, 9), date(2015, 1, 9), str(out_dir),
                         underlyings=["NIFTY"])
    assert s["days_ok"] == 0
    assert s["days_empty"] == 1
    assert not any(out_dir.rglob("NIFTY/*.parquet"))