"""Tests for the TradingTick per-strike daily OHLC ingester.

Offline by contract: requests.get is mocked at the module boundary; no real
network is touched. Covers epoch -> naive IST normalization, OHLC field
carrying (NaN on null, never fabricated), option/underlying validation, the
year/month/expiry/strike enumeration fence, month-file bucketing across month
boundaries, warehouse merge idempotency on the natural key (trade_date,
expiry, option_type, strike), and fail-closed behavior on empty/foreign
responses and missing warehouse months in load_series.
"""

from datetime import date

import pandas as pd
import pytest

import mjonai.research.data.tradingtick_strike_ohlc as tts

# 2019-01-31 00:00:00 IST = 1548873000 epoch seconds UTC (day anchor).
_BAR = {"time": 1548873000, "open": 1700.0, "high": 1843.0,
        "low": 1689.0, "close": 1836.9}
_BAR2 = {"time": 1548959400, "open": 1850.0, "high": 2001.35,
         "low": 1830.0, "close": 1896.65}
_NULL = {"time": 1548873000, "open": None, "high": None, "low": None,
         "close": None}


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
    monkeypatch.setattr(tts.requests, "get", _get)


def _filters(url):
    if "action=filters" in url and "year=" not in url:
        return {"years": ["2019", "2016"]}
    if "action=months" in url:
        return {"months": [{"value": "Jan", "name": "January"},
                           {"value": "Feb", "name": "February"}]}
    if "action=expiries" in url:
        return {"expiries": ["2019-02-28"]}
    if "action=strikes" in url:
        return {"strikes": ["9000", "9050", "9100"]}
    return None


def _responder(url):
    f = _filters(url)
    return f if f is not None else [_BAR, _BAR2]


def test_fetch_strike_normalizes_and_carries_ohlc(monkeypatch):
    patch_get(monkeypatch, _responder)
    df = tts.fetch_strike("NIFTY", "2019", "Feb", "2019-02-28", "CE", "9000")
    assert df is not None
    assert len(df) == 2
    row = df.iloc[0]
    assert row["trade_date"] == pd.Timestamp("2019-01-31 00:00:00")
    assert row["expiry"] == pd.Timestamp("2019-02-28")
    assert row["option_type"] == "CE"
    assert row["strike"] == 9000.0
    assert row["open"] == 1700.0
    assert row["high"] == 1843.0
    assert row["low"] == 1689.0
    assert row["close"] == 1836.9


def test_fetch_strike_lowercase_option_normalized(monkeypatch):
    calls = []

    def responder(url):
        calls.append(url)
        f = _filters(url)
        return f if f is not None else [_BAR]
    patch_get(monkeypatch, responder)
    df = tts.fetch_strike("NIFTY", "2019", "Feb", "2019-02-28", "pe", "9000")
    assert df is not None
    assert df.iloc[0]["option_type"] == "PE"
    assert "option=PE" in calls[-1]


def test_fetch_strike_null_ohlc_becomes_nan_not_fabricated(monkeypatch):
    patch_get(monkeypatch, lambda url: [_NULL])
    df = tts.fetch_strike("NIFTY", "2019", "Feb", "2019-02-28", "CE", "9000")
    assert df is not None
    assert pd.isna(df.iloc[0]["open"])
    assert pd.isna(df.iloc[0]["close"])
    # never backfilled to a prior price
    assert df["open"].isna().all()


def test_fetch_strike_empty_is_none(monkeypatch):
    patch_get(monkeypatch, lambda url: _filters(url) if _filters(url) is not None else [])
    assert tts.fetch_strike("NIFTY", "2019", "Feb", "2019-02-28", "CE", "9000") is None


def test_fetch_strike_network_failure_is_none(monkeypatch):
    patch_get(monkeypatch, lambda url: None)
    assert tts.fetch_strike("NIFTY", "2019", "Feb", "2019-02-28", "CE", "9000") is None


def test_unsupported_option_and_underlying_raise(monkeypatch):
    patch_get(monkeypatch, lambda url: {})
    with pytest.raises(ValueError):
        tts.fetch_strike("NIFTY", "2019", "Feb", "2019-02-28", "XX", "9000")
    with pytest.raises(ValueError):
        tts.list_years("SENSEX")
    with pytest.raises(ValueError):
        tts.list_expiries("SENSEX", "2019", "Feb")


def test_list_years_drops_null_banknifty_year(monkeypatch):
    patch_get(monkeypatch, lambda url: {"years": ["2026", "2016", None]})
    years = tts.list_years("BANKNIFTY")
    assert years == ["2026", "2016"]


def test_enumerate_strikes_fence(monkeypatch):
    calls = []

    def responder(url):
        calls.append(url)
        f = _filters(url)
        return f if f is not None else [_BAR]
    patch_get(monkeypatch, responder)
    # 2019 Feb appears only if caller range includes it; 2019-01 / 2020 excluded.
    combos = list(tts.enumerate_strikes("NIFTY", date(2019, 2, 1), date(2019, 2, 28)))
    assert len(combos) == 2 * 3  # CE+PE x three strikes on the one expiry
    assert all(c[0] == "2019" and c[1] == "Feb" for c in combos)
    assert combos[0] == ("2019", "Feb", "2019-02-28", "CE", "9000")
    assert combos[-1] == ("2019", "Feb", "2019-02-28", "PE", "9100")


def test_ingest_range_buckets_cross_month_bars(tmp_path, monkeypatch):
    patch_get(monkeypatch, _responder)
    out_dir = tmp_path
    s = tts.ingest_range(date(2019, 2, 1), date(2019, 2, 28),
                         str(out_dir), underlyings=["NIFTY"])
    assert s["contracts_total"] == 6
    assert s["rows_total"] == 12
    jan = pd.read_parquet(tmp_path / "NIFTY" / "2019-01.parquet")
    feb = pd.read_parquet(tmp_path / "NIFTY" / "2019-02.parquet")
    # bar on 2019-01-31 lands in the prior month file; 2019-02-01 in Feb
    assert len(jan) == 6          # one bar per contract, all 6 contracts
    assert len(feb) == 6
    assert jan["trade_date"].eq(pd.Timestamp("2019-01-31")).all()
    assert feb["trade_date"].eq(pd.Timestamp("2019-02-01")).all()


def test_ingest_range_idempotent_keep_last(tmp_path, monkeypatch):
    patch_get(monkeypatch, _responder)
    out_dir = tmp_path
    tts.ingest_range(date(2019, 2, 1), date(2019, 2, 28), str(out_dir),
                     underlyings=["NIFTY"])
    tts.ingest_range(date(2019, 2, 1), date(2019, 2, 28), str(out_dir),
                     underlyings=["NIFTY"])
    feb = pd.read_parquet(tmp_path / "NIFTY" / "2019-02.parquet")
    assert len(feb) == 6          # not 12 — same natural keys merged
    assert sorted(feb["strike"].unique()) == [9000.0, 9050.0, 9100.0]


def test_ingest_range_fail_closed_on_empty_contracts(tmp_path, monkeypatch):
    patch_get(monkeypatch, lambda url: _filters(url) if _filters(url) is not None else [])
    out_dir = tmp_path
    s = tts.ingest_range(date(2019, 2, 1), date(2019, 2, 28), str(out_dir),
                         underlyings=["NIFTY"])
    assert s["contracts_total"] == 0
    assert s["contracts_empty"] == 6
    assert not any(tmp_path.rglob("*.parquet"))


def test_load_series_roundtrip(tmp_path, monkeypatch):
    patch_get(monkeypatch, _responder)
    out_dir = tmp_path
    tts.ingest_range(date(2019, 2, 1), date(2019, 2, 28), str(out_dir),
                     underlyings=["NIFTY"])
    df = tts.load_series(str(out_dir), "NIFTY", date(2019, 2, 1), date(2019, 2, 28))
    assert len(df) == 6
    assert df["trade_date"].eq(pd.Timestamp("2019-02-01")).all()  # clipped to range
    assert sorted(df["strike"].unique()) == [9000.0, 9050.0, 9100.0]
    assert set(df["option_type"].unique()) == {"CE", "PE"}


def test_load_series_missing_month_raises(tmp_path, monkeypatch):
    patch_get(monkeypatch, _responder)
    out_dir = tmp_path
    tts.ingest_range(date(2019, 2, 1), date(2019, 2, 28), str(out_dir),
                     underlyings=["NIFTY"])
    with pytest.raises(ValueError, match="missing month"):
        tts.load_series(str(out_dir), "NIFTY", date(2019, 3, 1), date(2019, 3, 31))


def test_load_series_empty_range_is_empty_frame(tmp_path):
    df = tts.load_series(str(tmp_path), "NIFTY", date(2019, 3, 1), date(2019, 2, 1))
    assert df.empty