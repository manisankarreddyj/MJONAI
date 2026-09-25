"""Tests for the TradingTick historical option-chain ingester.

Offline by contract: requests.get is mocked at the module boundary; no real
network is touched. Covers normalization to the CANON close-only shape,
fail-closed empties, the filter-hierarchy enumeration fence, warehouse merge
idempotency, and the guarantee that OHLC/trades/lot_size are NEVER fabricated.
"""

import json
from datetime import date

import pandas as pd
import pytest

import mjonai.research.data.fno_tradingtick as tt


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
    monkeypatch.setattr(tt.requests, "get", _get)


def one_row():
    return {
        "Option": "CE",
        "OI": 25545,
        "OI_Change": 24310,
        "Volume": 753,
        "Turnover": 12809.0,
        "Close": 2178.45,
        "Strike": 24000,
        "ATM": 2200,
        "PE_Close": 0.05,
        "PE_Turnover": 1437850.0,
        "PE_Volume": 92169,
        "PE_OI_Change": 1220895,
        "PE_OI": 3156335,
        "PE_Option": "PE",
        "Spot": 26178.7,
        "PCR": 123.56,
    }


def test_fetch_chain_normalizes_to_canon_close_only(monkeypatch):
    patch_get(monkeypatch, lambda url: {"data": [one_row()]})
    frame = tt.fetch_chain("NIFTY", "2026-01-06", "2026-01-06")
    assert frame is not None
    assert len(frame) == 2  # CE + PE split

    can = frame.set_index("option_type")
    ce, pe = can.loc["CE"].to_dict(), can.loc["PE"].to_dict()
    assert ce["underlying"] == "NIFTY"
    assert ce["kind"] == "OPT"
    assert ce["strike"] == 24000.0
    assert ce["close"] == 2178.45
    assert ce["oi"] == 25545
    assert ce["oi_change"] == 24310
    assert ce["volume"] == 753
    assert pe["close"] == 0.05
    assert pe["oi"] == 3156335
    assert pe["underlying_price"] == 26178.7
    assert pd.Timestamp(ce["trade_date"]) == pd.Timestamp("2026-01-06")


def test_fetch_chain_never_fabricates_ohlc_or_lot(monkeypatch):
    patch_get(monkeypatch, lambda url: {"data": [one_row()]})
    frame = tt.fetch_chain("NIFTY", "2026-01-06", "2026-01-06")
    cols = ["open", "high", "low", "settle", "prev_close", "trades", "lot_size"]
    for c in cols:
        assert frame[c].isna().all(), f"{c} must stay NaN (close-only source)"
    # close/last ARE present (the only price truth the source provides)
    assert not frame["close"].isna().any()
    assert not frame["last"].isna().any()


def test_fetch_chain_empty_is_none(monkeypatch):
    patch_get(monkeypatch, lambda url: {"data": []})
    assert tt.fetch_chain("NIFTY", "2026-01-06", "2026-01-06") is None


def test_fetch_chain_network_failure_is_none(monkeypatch):
    patch_get(monkeypatch, lambda url: None)  # simulated request failure
    assert tt.fetch_chain("BANKNIFTY", "2026-01-27", "2025-12-30") is None


def test_fetch_chain_skips_bad_strike_rows(monkeypatch):
    bad = one_row()
    bad["Strike"] = "garbage"
    patch_get(monkeypatch, lambda url: {"data": [bad, one_row()]})
    frame = tt.fetch_chain("NIFTY", "2026-01-06", "2026-01-06")
    assert len(frame) == 2  # only the valid strike survives


def test_unsupported_underlying_raises(monkeypatch):
    patch_get(monkeypatch, lambda url: {})
    with pytest.raises(ValueError):
        tt.fetch_chain("SENSEX", "2026-01-06", "2026-01-06")


def test_enumerate_pairs_fence(monkeypatch):
    """The filter hierarchy is walked, but expiries outside [start.year,
    end.year] are never descended into, and trading dates outside [start, end]
    are excluded by the date fence before they can be fetched."""
    calls = []

    def responder(url):
        calls.append(url)
        if "type=year" in url:
            return ["2020", "2021", "2026"]
        if "type=month" in url:
            return ["January"] if "year=2021" in url else []
        if "type=expiryDate" in url:
            return ["2026-01-08"]
        if "type=date" in url:
            return ["2020-12-30", "2021-01-04", "2022-02-01"]
        return {"data": []}

    patch_get(monkeypatch, responder)
    pairs = list(tt.enumerate_pairs("NIFTY", date(2021, 1, 1), date(2021, 12, 31)))
    # 2020 (< start.year) and 2026 (> end.year) never generate a date fetch;
    # of the three dates listed for the in-window expiry, only 2021-01-04 lands.
    assert pairs == [("2026-01-08", "2021-01-04")]


def test_ingest_range_merges_into_shared_warehouse(tmp_path, monkeypatch):
    """tradingtick rows land in the SAME monthly parquet as the NSE bhavcopy
    ingester and re-running an (expiry, date) is idempotent (keep=last)."""
    row = one_row()
    calls = {"n": 0}

    def responder(url):
        calls["n"] += 1
        if "type=year" in url:
            return ["2026"]
        if "type=month" in url:
            return ["January"]
        if "type=expiryDate" in url:
            return ["2026-01-06"]
        if "type=date" in url:
            return ["2026-01-06"]
        return {"data": [row]}

    patch_get(monkeypatch, responder)
    out_dir = tmp_path
    s1 = tt.ingest_range(date(2026, 1, 6), date(2026, 1, 6), str(out_dir),
                         underlyings=["NIFTY"])
    assert s1["pairs_ok"] == 1
    assert s1["rows_total"] == 2
    path = tmp_path / "eod" / "2026-01.parquet"
    assert path.exists()
    first = pd.read_parquet(path)
    assert len(first) == 2

    # Re-run the same range -> pair re-fetched, merge keep=last, still 2 rows.
    s2 = tt.ingest_range(date(2026, 1, 6), date(2026, 1, 6), str(out_dir),
                         underlyings=["NIFTY"])
    assert s2["pairs_ok"] == 1
    assert len(pd.read_parquet(path)) == 2


def test_ingest_range_fail_closed_on_empty_chain(tmp_path, monkeypatch):
    def responder(url):
        if "type=year" in url:
            return ["2026"]
        if "type=month" in url:
            return ["January"]
        if "type=expiryDate" in url:
            return ["2026-01-06"]
        if "type=date" in url:
            return ["2026-01-06"]
        return {"data": []}  # the chain snapshot itself is empty
    patch_get(monkeypatch, responder)
    out_dir = tmp_path
    s = tt.ingest_range(date(2026, 1, 6), date(2026, 1, 6), str(out_dir),
                        underlyings=["NIFTY"])
    assert s["pairs_ok"] == 0
    assert s["pairs_empty"] == 1  # one (expiry, date) with no rows
    assert not any(out_dir.rglob("eod/*.parquet"))