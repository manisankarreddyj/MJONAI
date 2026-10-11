"""
Module: research/data/option_desk.py
Purpose: pure option-desk analytics over the official F&O EOD chain warehouse
(the OpenAlgo options-suite reference cluster — ADR registry #8).

Research-tier display analytics: chain window, OI-based PCR, max pain, OI profile.
Pure functions over the loader's frame so the CLI (run_chain_read.py) and the web
tier (apps/web) share ONE implementation — no second copy of the math.

Honesty contract: these are *descriptive* analytics of stored chain rows (OI,
closes). They are not signals, they carry no edge claim, and empty inputs return
empty/None — never a fabricated zero-OI reading.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd


def chain_window(frame: Optional[pd.DataFrame], n_strikes: int = 5) -> dict:
    """Pivot one trading day's chain to per-strike CE/PE rows, N strikes around spot.

    Selection is by |strike - spot| so partial/odd strike grids still return the
    nearest available N. A missing leg renders as None (NaN stays honest).
    """
    if frame is None or frame.empty:
        return {"spot": None, "strikes": [], "rows": []}
    f = frame.copy()
    spot = float(pd.to_numeric(f["underlying_price"], errors="coerce").dropna().median())
    f["strike"] = pd.to_numeric(f["strike"], errors="coerce")
    f["oi"] = pd.to_numeric(f["oi"], errors="coerce").fillna(0.0)
    f["close"] = pd.to_numeric(f["close"], errors="coerce")

    strikes = sorted(f["strike"].dropna().unique())
    if not strikes:
        return {"spot": round(spot, 2), "strikes": [], "rows": []}
    window = sorted(sorted(strikes, key=lambda k: abs(k - spot))[: max(0, int(n_strikes))])

    rows = []
    for k in window:
        leg = f[f["strike"] == k]
        ce = leg[leg["option_type"].astype(str).str.upper() == "CE"]
        pe = leg[leg["option_type"].astype(str).str.upper() == "PE"]

        def _v(part, col):
            return float(part[col].iloc[0]) if len(part) and pd.notna(part[col].iloc[0]) else None

        rows.append({
            "strike": float(k),
            "ce_close": _v(ce, "close"), "ce_oi": _v(ce, "oi"),
            "pe_close": _v(pe, "close"), "pe_oi": _v(pe, "oi"),
        })
    return {"spot": round(spot, 2), "strikes": window, "rows": rows}


def window_pcr(rows: list[dict]) -> Optional[float]:
    """OI-based put-call ratio over the window rows. None when the call side is 0."""
    ce = sum(r["ce_oi"] or 0.0 for r in rows)
    pe = sum(r["pe_oi"] or 0.0 for r in rows)
    return round(pe / ce, 3) if ce else None


def max_pain(frame: Optional[pd.DataFrame]) -> Optional[dict]:
    """Strike minimizing total option-buyer payout at expiry over the whole chain.

    For candidate strike K: CE buyers at strikes S <= K lose (K - S) * ce_oi(S);
    PE buyers at S >= K lose (S - K) * pe_oi(S). The argmin of the summed payout
    is the classic 'max pain' level. Descriptive only — not an edge claim.
    """
    if frame is None or frame.empty:
        return None
    f = frame.copy()
    f["strike"] = pd.to_numeric(f["strike"], errors="coerce")
    f["oi"] = pd.to_numeric(f["oi"], errors="coerce").fillna(0.0)
    f["kind"] = f["option_type"].astype(str).str.upper()
    f = f.dropna(subset=["strike"])
    if f.empty:
        return None
    best = None
    for k, grp in f.groupby("strike"):
        k = float(k)
        ce_loss = float(((k - grp.loc[grp["kind"] == "CE", "strike"]).clip(lower=0)
                         * grp.loc[grp["kind"] == "CE", "oi"]).sum())
        pe_loss = float(((grp.loc[grp["kind"] == "PE", "strike"] - k).clip(lower=0)
                         * grp.loc[grp["kind"] == "PE", "oi"]).sum())
        total = ce_loss + pe_loss
        if best is None or total < best["total_payout"]:
            best = {"strike": k, "total_payout": total}
    return best


def oi_profile(rows: list[dict]) -> dict:
    """Per-strike CE/PE OI arrays for charting (x = strike)."""
    return {
        "strikes": [r["strike"] for r in rows],
        "ce_oi": [r["ce_oi"] or 0.0 for r in rows],
        "pe_oi": [r["pe_oi"] or 0.0 for r in rows],
    }
