"""Tests for the TradingTick index spot/futures daily ingester.

Offline by contract: requests.get is mocked at the module boundary; no real
network is touched. Covers epoch -> naive IST normalization, spot and futures
row construction (all source fields carried, no fabrication), the finance
"0"-year filter sanitization, the year/month enumeration fence, warehouse
merge idempotency (spot key trade_date; futures key trade_date+expiry), and
fail-closed behavior on empty/foreign responses.
"""

import json
from datetime import date

import pandas as pd
import pytest

import mjonai.research.data.tradingtick_index as tti

# 2014-01-01 00:00:00 IST = 1388514600 epoch seconds UTC (trading-day anchor
# used by the source for both spot and futures daily rows). The source's
# `time` field is the day anchor at midnight IST, not a 09:15 bar-open.
_SPOT1 = {"time": 1388514600, "symbol": "NIFTY", "date": "2014-01-01",
          "open": 6323.8, "high": 6327.2, "low": 6298.25, "close": 6301.6,
          "prev_close": 6304, "change": -2.4, "change_perc": -0.04,
          "otc": -22.2, "otc_perc": -0.35, "gap_up": 19.8, "gap_up_perc": 0.31,
          "high_low": 28.95}
_FUT1 = {"time": 1388514600, "date": "2014-01-01", "expiry": "2014-01-30",
         "open": 6340.0, "high": 6383.0, "low": 6335.0, "close": 6372.05,
         "ltp": 6370.2, "settle_price": 6372.05, "volume": 119090,
         "turnover": 379113, "oi": 19739300, "coi": 786650,
         "spot": 6313.8, "basis": 58.25, "built_up": "Long Buildup"}


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
    monkeypatch.setattr(tti.requests, "get", _get)


def month_responder(rows, years=None, months=None):
    years = years if years is not None else {"years": ["2014"]}
    months = months if months is not None else {"months": [{"value": "Jan", "name": "January"}]}
    return {
        "years": years,
        "months": months,
        "rows": rows,
    }


def filters(url):
    if "action=filters" in url and "year=" not in url:
        return month_responder([])["years"]
    if "action=filters" in url:
        return month_responder([])["months"]
    return None


def test_fetch_month_spot_normalizes_and_carries_all_fields(monkeypatch):
    def responder(url):
        f = filters(url)
        return f if f is not None else [_SPOT1]
    patch_get(monkeypatch, responder)
    df = tti.fetch_month("NIFTY", "2014", "Jan", "spot")
    assert df is not None
    assert len(df) == 1
    row = df.iloc[0]
    assert row["trade_date"] == pd.Timestamp("2014-01-01 00:00:00")
    assert row["underlying"] == "NIFTY"
    assert row["open"] == 6323.8
    assert row["high"] == 6327.2
    assert row["low"] == 6298.25
    assert row["close"] == 6301.6
    assert row["prev_close"] == 6304
    assert row["otc"] == -22.2
    assert row["gap_up"] == 19.8
    assert row["high_low"] == 28.95
    assert "expiry" not in df.columns


def test_fetch_month_futures_carries_contract_fields(monkeypatch):
    def responder(url):
        f = filters(url)
        return f if f is not None else [_FUT1]
    patch_get(monkeypatch, responder)
    df = tti.fetch_month("BANKNIFTY", "2014", "Jan", "futures")
    assert df is not None
    row = df.iloc[0]
    assert row["trade_date"] == pd.Timestamp("2014-01-01 00:00:00")
    assert row["expiry"] == pd.Timestamp("2014-01-30")
    assert row["volume"] == 119090
    assert row["oi"] == 19739300
    assert row["coi"] == 786650
    assert row["basis"] == 58.25
    assert row["built_up"] == "Long Buildup"


def test_fetch_month_empty_is_none(monkeypatch):
    patch_get(monkeypatch, lambda url: filters(url))
    assert tti.fetch_month("NIFTY", "2014", "Jan", "spot") is None
    assert tti.fetch_month("NIFTY", "2014", "Jan", "futures") is None


def test_fetch_month_network_failure_is_none(monkeypatch):
    patch_get(monkeypatch, lambda url: None)
    assert tti.fetch_month("NIFTY", "2014", "Jan", "spot") is None


def test_list_years_drops_banknifty_zero_year(monkeypatch):
    patch_get(monkeypatch, lambda url: {"years": ["2026", "2014", "0"]})
    years = tti.list_years("BANKNIFTY", "spot")
    assert "0" not in years
    assert years == ["2026", "2014"]


def test_unsupported_underlying_raises(monkeypatch):
    patch_get(monkeypatch, lambda url: {})
    with pytest.raises(ValueError):
        tti.list_years("SENSEX", "spot")
    with pytest.raises(ValueError):
        tti.fetch_month("SENSEX", "2014", "Jan", "futures")


def test_enumerate_months_fence(monkeypatch):
    calls = []

    def responder(url):
        calls.append(url)
        f = filters(url)
        if f is not None:
            return f
        return []
    # years served: 2013, 2014, 2026; months: Jan only
    patch_get(monkeypatch, lambda url: (
        {"years": ["2013", "2014", "2026"]} if "action=filters" in url and "year=" not in url
        else {"months": [{"value": "Jan", "name": "January"}]} if "action=filters" in url
        else []))
    pairs = list(tti.enumerate_months("NIFTY", "spot", date(2014, 1, 1), date(2014, 12, 31)))
    assert pairs == [("2014", "Jan")]
    assert all("2013" not in c or "2013" != c.split("year=")[-1] for c in calls)


def test_ingest_range_writes_spot_and_futures_warehouses(tmp_path, monkeypatch):
    def responder(url):
        f = filters(url)
        if f is not None:
            return f
        return [_SPOT1] if "/nifty-spot.php" in url else [_FUT1]

    patch_get(monkeypatch, responder)
    out_dir = tmp_path
    s = tti.ingest_range(date(2014, 1, 1), date(2014, 1, 1), str(out_dir),
                         surfaces=["spot", "futures"], underlyings=["NIFTY"])
    assert s["months_total"] == 2
    assert s["rows_total"] == 2
    sp = tmp_path / "spot" / "NIFTY" / "2014-01.parquet"
    fu = tmp_path / "futures" / "NIFTY" / "2014-01.parquet"
    assert sp.exists()
    assert fu.exists()
    spot_df = pd.read_parquet(sp)
    fut_df = pd.read_parquet(fu)
    assert len(spot_df) == 1
    assert "expiry" not in spot_df.columns
    assert "expiry" in fut_df.columns
    assert len(fut_df) == 1

    # Re-run the same range -> idempotent keep=last merges, still 1 row each.
    s2 = tti.ingest_range(date(2014, 1, 1), date(2014, 1, 1), str(out_dir),
                          surfaces=["spot", "futures"], underlyings=["NIFTY"])
    assert s2["rows_total"] == 2
    assert len(pd.read_parquet(sp)) == 1
    assert len(pd.read_parquet(fu)) == 1


def test_ingest_range_futures_dedupes_by_expiry_plus_date(tmp_path, monkeypatch):
    fut2 = dict(_FUT1)
    fut2["expiry"] = "2014-02-27"  # different contract on the same trade_date

    def responder(url):
        f = filters(url)
        if f is not None:
            return f
        return [_FUT1, fut2]

    patch_get(monkeypatch, responder)
    out_dir = tmp_path
    tti.ingest_range(date(2014, 1, 1), date(2014, 1, 1), str(out_dir),
                     surfaces=["futures"], underlyings=["NIFTY"])
    fu = pd.read_parquet(tmp_path / "futures" / "NIFTY" / "2014-01.parquet")
    assert len(fu) == 2
    assert sorted(fu["expiry"].astype(str)) == ["2014-01-30", "2014-02-27"]


def test_ingest_range_fail_closed_on_empty_month(tmp_path, monkeypatch):
    patch_get(monkeypatch, lambda url: filters(url) if filters(url) is not None else [])
    out_dir = tmp_path
    s = tti.ingest_range(date(2014, 1, 1), date(2014, 1, 1), str(out_dir),
                         surfaces=["spot", "futures"], underlyings=["NIFTY"])
    assert s["months_total"] == 0
    assert s["months_empty"] == 2
    assert not any(tmp_path.rglob("*/NIFTY/*.parquet"))


def _build_warehouse(tmp_path, monkeypatch):
    """Ingest spot+futures NIFTY for 2014-01 into tmp_path and return it."""
    def responder(url):
        f = filters(url)
        if f is not None:
            return f
        return [_SPOT1] if "/nifty-spot.php" in url else [_FUT1]
    patch_get(monkeypatch, responder)
    out_dir = tmp_path
    tti.ingest_range(date(2014, 1, 1), date(2014, 1, 1), str(out_dir),
                     surfaces=["spot", "futures"], underlyings=["NIFTY"])
    return out_dir


def test_load_series_spot_roundtrip(tmp_path, monkeypatch):
    out_dir = _build_warehouse(tmp_path, monkeypatch)
    df = tti.load_series(str(out_dir), "spot", "NIFTY",
                         date(2014, 1, 1), date(2014, 1, 31))
    assert len(df) == 1
    assert df.iloc[0]["trade_date"] == pd.Timestamp("2014-01-01 00:00:00")
    assert df.iloc[0]["close"] == 6301.6


def test_load_series_futures_roundtrip(tmp_path, monkeypatch):
    out_dir = _build_warehouse(tmp_path, monkeypatch)
    df = tti.load_series(str(out_dir), "futures", "NIFTY",
                         date(2014, 1, 1), date(2014, 1, 31))
    assert len(df) == 1
    assert df.iloc[0]["expiry"] == pd.Timestamp("2014-01-30")
    assert df.iloc[0]["oi"] == 19739300


def test_load_series_missing_month_raises(tmp_path, monkeypatch):
    out_dir = _build_warehouse(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="missing month"):
        tti.load_series(str(out_dir), "spot", "NIFTY",
                        date(2014, 1, 1), date(2014, 3, 31))


def test_load_series_empty_range_is_empty_frame(tmp_path):
    df = tti.load_series(str(tmp_path), "spot", "NIFTY",
                         date(2015, 1, 1), date(2014, 1, 1))
    assert df.empty