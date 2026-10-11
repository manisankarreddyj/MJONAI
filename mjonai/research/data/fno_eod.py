"""
Module: research/data/fno_eod.py
Purpose: NSE F&O bhavcopy ingester — official EOD derivatives chain (options +
         futures, every strike/expiry) into the house parquet warehouse.

Sources:
  - UDiFF era (>= 2024-07): nsearchives.nseindia.com BhavCopy_NSE_FO_*.csv.zip
  - Legacy era (<  2024-07): archives.nseindia.com fo{DDMMMYYYY}bhav.csv.zip
    (legacy mapping is best-effort; primary research window is the UDiFF era)

Canonical output row (one contract per trading day):
  trade_date, underlying, kind (OPT|FUT), option_type (CE|PE|""), strike,
  expiry, open/high/low/close/last/settle/prev_close, underlying_price,
  volume, turnover, trades, oi, oi_change, lot_size

Storage: {out_dir}/eod/{YYYY-MM}.parquet (idempotent: existing months are
merged with duplicate-drop on the natural key).
"""

from __future__ import annotations

import io
import logging
import os
import zipfile
from datetime import date, datetime, timedelta
from functools import lru_cache

import pandas as pd
import requests

logger = logging.getLogger(__name__)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
NSEARCHIVES = "https://nsearchives.nseindia.com/content/fo/"
ARCHIVES = "https://archives.nseindia.com/content/fo/"

CANON = [
    "trade_date", "underlying", "kind", "option_type", "strike", "expiry",
    "open", "high", "low", "close", "last", "settle", "prev_close",
    "underlying_price", "volume", "turnover", "trades", "oi", "oi_change",
    "lot_size",
]

_NATKEY = ["trade_date", "underlying", "kind", "option_type", "strike", "expiry"]


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def _parse_udiff(csv_bytes: bytes, trade_date: date) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(csv_bytes))
    kind_map = {"IDF": "FUT", "STF": "FUT", "IDO": "OPT", "STO": "OPT"}
    opt_map = {"CA": "CE", "PA": "PE"}  # older UDiFF variants; modern files ship CE/PE directly
    out = pd.DataFrame({
        "trade_date": pd.Timestamp(trade_date),
        "underlying": df["TckrSymb"].astype(str).str.upper(),
        "kind": df["FinInstrmTp"].map(kind_map).fillna("OPT"),
        "option_type": df["OptnTp"].astype(str).str.strip().str.upper()
                       .map(lambda v: opt_map.get(v, "" if v in ("NAN", "NAT") else v)),
        "strike": _num(df["StrkPric"]),
        "expiry": pd.to_datetime(df["XpryDt"]).dt.date,
        "open": _num(df["OpnPric"]),
        "high": _num(df["HghPric"]),
        "low": _num(df["LwPric"]),
        "close": _num(df["ClsPric"]),
        "last": _num(df["LastPric"]),
        "settle": _num(df["SttlmPric"]),
        "prev_close": _num(df["PrvsClsgPric"]),
        "underlying_price": _num(df["UndrlygPric"]),
        "volume": _num(df["TtlTradgVol"]).fillna(0).astype("int64"),
        "turnover": _num(df["TtlTrfVal"]),
        "trades": _num(df["TtlNbOfTxsExctd"]).fillna(0).astype("int64"),
        "oi": _num(df["OpnIntrst"]).fillna(0).astype("int64"),
        "oi_change": _num(df["ChngInOpnIntrst"]).fillna(0).astype("int64"),
        "lot_size": _num(df["NewBrdLotQty"]).fillna(0).astype("int64"),
    })
    return out[CANON]


def _parse_legacy(csv_bytes: bytes, trade_date: date) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(csv_bytes))
    cols = {c.strip().upper(): c for c in df.columns}
    def g(*names):
        for n in names:
            if n in cols:
                return cols[n]
        raise KeyError(names)
    out = pd.DataFrame({
        "trade_date": pd.Timestamp(trade_date),
        "underlying": df[g("SYMBOL")].astype(str).str.upper(),
        "kind": "OPT",
        "option_type": df[g("OPTION_TYP")].astype(str).str.replace("XX", "", regex=False),
        "strike": _num(df[g("STRIKE_PR")]),
        "expiry": pd.to_datetime(df[g("EXPIRY_DT")]).dt.date,
        "open": _num(df[g("OPEN")]),
        "high": _num(df[g("HIGH")]),
        "low": _num(df[g("LOW")]),
        "close": _num(df[g("CLOSE")]),
        "last": _num(df[g("CLOSE")]),
        "settle": _num(df[g("SETTLE_PR")]),
        "prev_close": _num(df[g("PREVIOUS_CLOSE", "CLOSE")]),
        "underlying_price": _num(df[g("UNDERLYING_VALUE", "UNDERLYING")]),
        "volume": _num(df[g("TOT_TRD_QTY", "TOTAL_TRADES")]).fillna(0).astype("int64"),
        "turnover": _num(df[g("TOT_TRD_VAL", "TOT_TRD_VAL_LAKHS")]),
        "trades": _num(df[g("TOTAL_TRADES", "NO_OF_TRADES", "TOT_TRD_QTY")]).fillna(0).astype("int64"),
        "oi": _num(df[g("OPEN_INT", "OPEN_INT_TOTAL")]).fillna(0).astype("int64"),
        "oi_change": _num(df[g("CHG_IN_OPEN_INT")]).fillna(0).astype("int64"),
        "lot_size": _num(df[g("LOT_SIZE", "LOT_CONT_QUANTITY")]).fillna(0).astype("int64"),
    })
    # futures rows in legacy files carry OPTION_TYP == XX and no strike meaning
    fut_mask = df[g("INSTRUMENT_TYPE", "OPTION_TYP")].astype(str).str.upper().isin(
        ["FUTIDX", "FUTSTK", "XX"])
    out.loc[fut_mask, "kind"] = "FUT"
    return out[CANON]


def fetch_fo_bhavcopy(day: date) -> pd.DataFrame | None:
    """Return canonical EOD chain rows for `day`, or None when unavailable."""
    d = day.strftime("%Y%m%d")
    url = NSEARCHIVES + f"BhavCopy_NSE_FO_0_0_0_{d}_F_0000.csv.zip"
    try:
        r = requests.get(url, headers=UA, timeout=30)
        if r.status_code == 200 and r.content[:2] == b"PK":
            z = zipfile.ZipFile(io.BytesIO(r.content))
            return _parse_udiff(z.read(z.namelist()[0]), day)
        legacy_name = day.strftime("fo%d%b%Ybhav.csv.zip").upper().replace("BHAV", "bhav")
        r2 = requests.get(ARCHIVES + legacy_name, headers=UA, timeout=30)
        if r2.status_code == 200 and r2.content[:2] == b"PK":
            z2 = zipfile.ZipFile(io.BytesIO(r2.content))
            return _parse_legacy(z2.read(z2.namelist()[0]), day)
    except Exception as exc:
        logger.warning("[fno_eod] %s fetch error: %s", day, exc)
        return None
    return None  # holiday / not published


def _month_path(out_dir: str, ts: pd.Timestamp) -> str:
    return os.path.join(out_dir, "eod", f"{ts:%Y-%m}.parquet")


@lru_cache(maxsize=32)
def _read_month_cached(path: str) -> pd.DataFrame | None:
    """Read one month parquet with a bounded in-process cache.

    Research runs evaluate one bar at a time; for chain-aware strategies the
    month-level frame is loaded ONCE per month instead of once per bar. The
    caller must treat the returned frame as read-only.
    """
    if not os.path.exists(path):
        return None
    try:
        return pd.read_parquet(path)
    except Exception as exc:  # corrupt/unreadable month file
        logger.warning("[fno_eod] %s unreadable: %s", path, exc)
        return None


def _merge_month(path: str, frame: pd.DataFrame) -> int:
    if os.path.exists(path):
        old = pd.read_parquet(path)
        frame = pd.concat([old, frame], ignore_index=True)
        frame = frame.drop_duplicates(subset=_NATKEY, keep="last")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    frame.sort_values(_NATKEY).to_parquet(path, index=False)
    return len(frame)


def ingest_range(start: date, end: date, out_dir: str,
                 underlyings: list[str] | None = None) -> dict:
    """Ingest [start, end] inclusive. Returns summary stats."""
    summary = {"days_ok": 0, "days_missing": 0, "rows_total": 0, "skipped_days": []}
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            df = fetch_fo_bhavcopy(cur)
            if df is None or df.empty:
                summary["days_missing"] += 1
                summary["skipped_days"].append(str(cur))
            else:
                if underlyings:
                    df = df[df["underlying"].isin({u.upper() for u in underlyings})]
                n = _merge_month(_month_path(out_dir, pd.Timestamp(cur)), df)
                summary["days_ok"] += 1
                summary["rows_total"] += len(df)  # new-day rows only (merge return = month-cumulative)
                if summary["days_ok"] % 20 == 0:
                    print(f"  {cur}: cumulative rows {summary['rows_total']:,}", flush=True)
        else:
            summary["skipped_days"].append(str(cur))
        cur += timedelta(days=1)
    return summary


def load_eod_chain_for_date(
    out_dir: str,
    underlying: str,
    as_of_date: date | pd.Timestamp,
    expiry_rank: int = 0,
    expiry: "date | pd.Timestamp | None" = None,
) -> pd.DataFrame | None:
    """
    Return the UDiFF-era option-chain rows for ONE underlying on ONE trading
    day from the local parquet warehouse, as one expiry.

    Fail-closed by contract: a missing month file, a non-F&O underlying, a
    non-trading `as_of_date`, or a requested expiry not listed that day all
    return None (never empty fabrications). The caller decides what None means.

    Expiry selection (mutually exclusive, `expiry` wins):
      `expiry_rank` — which expiry by distance from the trade date
                      (0 = nearest money, 1 = next, ...)
      `expiry`      — a specific expiry date, the OI-history seam: a chain that
                      predates/postdates the expiry's listing correctly returns
                      None instead of silently substituting another expiry.
    Additive: defaults preserve every existing caller (S13 GEX, chain reader,
    options desk).
    """
    ts = pd.Timestamp(as_of_date).normalize()
    path = _month_path(out_dir, ts)
    month = _read_month_cached(path)
    if month is None or month.empty:
        return None
    day = month[
        (month["underlying"].astype(str).str.upper() == underlying.upper())
        & (month["kind"] == "OPT")
        & (pd.to_datetime(month["trade_date"]).dt.normalize() == ts)
    ]
    if day.empty:
        return None
    day = day.copy()
    expiries = pd.to_datetime(day["expiry"]).dt.normalize()
    day["_dte"] = (expiries - ts).dt.days
    day = day[day["_dte"] >= 0]
    if day.empty:
        return None
    if expiry is not None:
        chosen = day[expiries == pd.Timestamp(expiry).normalize()]
        return None if chosen.empty else chosen.drop(columns=["_dte"]).reset_index(drop=True)
    ranked = sorted(day["_dte"].unique())
    rank = max(0, int(expiry_rank))
    if rank >= len(ranked):
        return None
    chosen = day[day["_dte"] == ranked[rank]].drop(columns=["_dte"])
    return chosen.reset_index(drop=True)


if __name__ == "__main__":
    import sys
    s = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2026, 8, 18)
    e = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else s
    out = sys.argv[3] if len(sys.argv) > 3 else r"D:\MJONAI\storage\parquet\fno_chain"
    print(ingest_range(s, e, out))
