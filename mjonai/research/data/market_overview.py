"""
Module: research/data/market_overview.py
Purpose: Finviz-style market overview analytics over MJONAI's OWN equity panel.

CONCEPT SOURCE (clean-room, no code copied): finviz.com's home dashboard —
advancing/declining breadth, above/below SMA50/SMA200 counts, and the signal tables
(top gainers/losers, unusual volume, new highs/lows) — plus its treemap "Maps".
Re-implemented here against the local per-symbol parquet panel
(`storage/parquet/yahoo_equity`, 497 symbols): NO market data is fetched, no live
feed is required, and every figure is computed from bars already on disk.

Honesty contract: the panel is the project's own cache (Yahoo-sourced), so this is
descriptive analytics of stored history — the newest bar is the panel's last bar,
which can be stale. Absent/short symbols are skipped, never zero-filled.
"""
from __future__ import annotations

import glob
import os
from typing import Optional

import numpy as np
import pandas as pd

PANEL_DIR = os.path.join("storage", "parquet", "yahoo_equity")


def load_symbol_summaries(min_bars: int = 60) -> pd.DataFrame:
    """One pass over the per-symbol parquets -> per-symbol summary rows.

    Columns: symbol, last_close, prev_close, chg_pct, sma50, sma200,
    above_sma50, above_sma200, high52, low52, new_52w_high, new_52w_low,
    vol_ratio (last volume / 20d mean volume).
    """
    rows = []
    for f in sorted(glob.glob(os.path.join(PANEL_DIR, "*.parquet"))):
        try:
            d = pd.read_parquet(f)
        except Exception:
            continue
        d.columns = [str(c).lower() for c in d.columns]
        if "close" not in d.columns or "date" not in d.columns:
            continue
        d = d.set_index(pd.to_datetime(d["date"])).sort_index()
        close = pd.to_numeric(d["close"], errors="coerce").dropna()
        if len(close) < min_bars:
            continue
        last = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close) > 1 else None
        sma50 = float(close.tail(50).mean())
        sma200 = float(close.tail(200).mean()) if len(close) >= 200 else None
        high52 = float(close.tail(252).max())
        low52 = float(close.tail(252).min())
        vol_ratio = None
        if "volume" in d.columns:
            vol = pd.to_numeric(d["volume"], errors="coerce").dropna()
            if len(vol) >= 21 and float(vol.tail(20).mean()) > 0:
                vol_ratio = float(vol.iloc[-1]) / float(vol.tail(20).mean())
        rows.append({
            "symbol": os.path.splitext(os.path.basename(f))[0],
            "last_close": round(last, 2),
            "prev_close": round(prev, 2) if prev else None,
            "chg_pct": round((last / prev - 1.0) * 100.0, 2) if prev else None,
            "sma50": round(sma50, 2),
            "sma200": round(sma200, 2) if sma200 else None,
            "above_sma50": bool(last > sma50),
            "above_sma200": bool(last > sma200) if sma200 else None,
            "high52": round(high52, 2), "low52": round(low52, 2),
            "new_52w_high": bool(last >= high52), "new_52w_low": bool(last <= low52),
            "vol_ratio": round(vol_ratio, 2) if vol_ratio is not None else None,
        })
    return pd.DataFrame(rows)


def market_overview(min_bars: int = 60, top: int = 8) -> Optional[dict]:
    """Finviz-style breadth + signal tables + heatmap rows over the local panel."""
    if not os.path.isdir(PANEL_DIR):
        return None
    df = load_symbol_summaries(min_bars=min_bars)
    if df.empty:
        return None

    with_chg = df[df["chg_pct"].notna()]
    advancing = int((with_chg["chg_pct"] > 0).sum())
    declining = int((with_chg["chg_pct"] < 0).sum())
    total = int(len(with_chg))

    def _table(frame: pd.DataFrame) -> list[dict]:
        return [{"symbol": r["symbol"], "chg_pct": r["chg_pct"], "last_close": r["last_close"],
                 "vol_ratio": r["vol_ratio"]} for _, r in frame.iterrows()]

    gainers = with_chg.sort_values("chg_pct", ascending=False).head(top)
    losers = with_chg.sort_values("chg_pct", ascending=True).head(top)

    unusual = df[df["vol_ratio"].notna()].sort_values("vol_ratio", ascending=False).head(top)
    volume_available = bool(df["vol_ratio"].notna().any())

    highs = df[df["new_52w_high"]]
    lows = df[df["new_52w_low"]]
    with200 = df[df["above_sma200"].notna()]
    above200 = int((with200["above_sma200"]).sum())
    above50 = int((df["above_sma50"]).sum())

    return {
        "available": True,
        "universe": total,
        "as_of": None,  # filled by the caller from the newest panel bar it has
        "breadth": {
            "advancing": advancing, "declining": declining,
            "advancing_pct": round(100.0 * advancing / total, 1) if total else None,
            "above_sma50": above50, "above_sma50_pct": round(100.0 * above50 / total, 1) if total else None,
            "above_sma200": above200,
            "above_sma200_pct": round(100.0 * above200 / int(len(with200)), 1) if len(with200) else None,
        },
        "top_gainers": _table(gainers),
        "top_losers": _table(losers),
        "unusual_volume": _table(unusual),
        "volume_available": volume_available,
        "new_52w_highs": [{"symbol": s["symbol"], "last_close": s["last_close"]} for _, s in highs.iterrows()],
        "new_52w_lows": [{"symbol": s["symbol"], "last_close": s["last_close"]} for _, s in lows.iterrows()],
        "heatmap": [
            {"name": r["symbol"], "value": r["chg_pct"], "last_close": r["last_close"]}
            for _, r in with_chg.sort_values("chg_pct", ascending=False).iterrows()
        ],
        "disclosure": (
            "RESEARCH DATA VIEW — descriptive analytics computed from MJONAI's own Yahoo-sourced "
            "equity panel (497 symbols). Not a signal, no edge claim; the newest bar is the panel's "
            "last bar, which may be stale."
        ),
    }
