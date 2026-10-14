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
    nearest available N. A missing leg renders as None (NaN stays honest). Rows
    also carry the source-recorded OI change (bhavcopy era); the close-only
    TradingTick era leaves it None rather than fabricating a zero.
    """
    if frame is None or frame.empty:
        return {"spot": None, "strikes": [], "rows": []}
    f = frame.copy()
    spot = float(pd.to_numeric(f["underlying_price"], errors="coerce").dropna().median())
    f["strike"] = pd.to_numeric(f["strike"], errors="coerce")
    f["oi"] = pd.to_numeric(f["oi"], errors="coerce").fillna(0.0)
    f["close"] = pd.to_numeric(f["close"], errors="coerce")
    if "oi_change" in f.columns:
        f["oi_change"] = pd.to_numeric(f["oi_change"], errors="coerce")

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
            "ce_oi_change": _v(ce, "oi_change"), "pe_oi_change": _v(pe, "oi_change"),
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


def payoff_curve(legs: list[dict], spots: list[float], lot_size: int = 25) -> dict:
    """Expiry payoff (₹) for option legs across spot levels. PURE math — no data.

    legs: [{"type": "CE"|"PE", "side": "BUY"|"SELL", "strike": K, "premium": P,
            "lots": n}] — expiry intrinsic minus net premium, times lots x lot_size.
    Breakevens are the curve's zero crossings (empty when none).
    """
    if not legs or not spots:
        return {"spots": [], "pnl": [], "legs": legs or [], "lot_size": lot_size, "breakevens": []}
    curve = []
    for s in spots:
        pnl = 0.0
        for leg in legs:
            k = float(leg["strike"])
            prem = float(leg.get("premium") or 0.0)
            sign = -1.0 if str(leg.get("side", "BUY")).upper() in ("SELL", "SHORT", "WRITE") else 1.0
            intrinsic = max(0.0, s - k) if str(leg.get("type", "CE")).upper() in ("CE", "CALL") else max(0.0, k - s)
            pnl += sign * (intrinsic - prem) * float(leg.get("lots", 1)) * float(lot_size)
        curve.append(round(pnl, 2))
    breakevens = []
    for i in range(1, len(curve)):
        prev, cur = curve[i - 1], curve[i]
        if cur == 0 or (prev < 0 < cur) or (prev > 0 > cur):  # touch or sign change
            be = round(float(spots[i]), 2)
            if be not in breakevens:  # an exact zero must not also register as the next crossing
                breakevens.append(be)
    return {"spots": [round(float(s), 2) for s in spots], "pnl": curve,
            "legs": legs, "lot_size": lot_size, "breakevens": breakevens}


def straddle_pnl(spot_price: float, ce_strike: float, pe_strike: float,
                 ce_premium: float, pe_premium: float, lot_size: int = 25,
                 side: str = "BUY", span_pct: float = 0.10, points: int = 41) -> dict:
    """Long/short straddle payoff around spot — the OpenAlgo Straddle-PnL pattern."""
    legs = [{"type": "CE", "side": side, "strike": ce_strike, "premium": ce_premium},
            {"type": "PE", "side": side, "strike": pe_strike, "premium": pe_premium}]
    lo, hi = spot_price * (1 - span_pct), spot_price * (1 + span_pct)
    spots = [lo + (hi - lo) * i / max(1, points - 1) for i in range(points)]
    return payoff_curve(legs, spots, lot_size=lot_size)


def iv_smile(rows: list[dict], spot: float, dte_days: float) -> dict:
    """Per-strike CE/PE implied vol from warehouse closes.

    Strikes whose close is <= 0.05 are IV=None — the BS solver's silent 0.15
    fallback must never masquerade as an implied vol.
    """
    from mjonai.options.greeks import calculate_implied_volatility

    ce, pe = [], []
    for r in rows:
        for kind, key in (("CE", "ce_close"), ("PE", "pe_close")):
            price = r.get(key)
            iv = None
            if isinstance(price, (int, float)) and price > 0.05 and spot > 0 and dte_days > 0:
                try:
                    iv = calculate_implied_volatility(float(price), spot, float(r["strike"]),
                                                      dte_days, option_type=kind)
                except Exception:
                    iv = None
            (ce if kind == "CE" else pe).append(iv)
    return {"strikes": [r["strike"] for r in rows], "ce_iv": ce, "pe_iv": pe}


def gex_profile(frame: Optional[pd.DataFrame], rows: list[dict], smile: dict,
                spot: Optional[float], dte_days: float) -> Optional[dict]:
    """Dealer GEX via the CANONICAL engine over the chain's own OI/lot/IV.

    Per-strike arrays come from the engine's additive `strike_gex` field (added
    2026-10-11) so the dashboard charts the same formula the engine prices.
    Honesty: strikes whose close was <= 0.05 have no solvable IV — the window's
    median solved IV stands in and `iv_estimated` discloses exactly that.
    """
    if not rows or spot is None or spot <= 0:
        return None
    import numpy as np

    from mjonai.data.derivatives.gex_engine import calculate_gamma_exposure

    strikes = [float(r["strike"]) for r in rows]
    ce_oi = [float(r["ce_oi"] or 0.0) for r in rows]
    pe_oi = [float(r["pe_oi"] or 0.0) for r in rows]
    ce_iv = list(smile.get("ce_iv") or [None] * len(rows))
    pe_iv = list(smile.get("pe_iv") or [None] * len(rows))
    known = [v for v in ce_iv + pe_iv if isinstance(v, (int, float))]
    fallback = float(np.median(known)) if known else 0.14
    iv_estimated = any(not isinstance(v, (int, float)) for v in ce_iv + pe_iv)
    ce_iv = [v if isinstance(v, (int, float)) else fallback for v in ce_iv]
    pe_iv = [v if isinstance(v, (int, float)) else fallback for v in pe_iv]

    lot = 25
    if frame is not None and "lot_size" in getattr(frame, "columns", []):
        lots = pd.to_numeric(frame["lot_size"], errors="coerce").dropna()
        if len(lots):
            lot = int(lots.mode().iloc[0])

    snap = calculate_gamma_exposure(
        underlying="INDEX", spot_price=float(spot), strikes=strikes,
        call_oi=ce_oi, put_oi=pe_oi, dte_days=max(float(dte_days), 0.5),
        call_iv=ce_iv, put_iv=pe_iv, lot_size=lot,
    )
    out = snap.to_dict()
    out["lot_size"] = lot
    out["iv_estimated"] = iv_estimated
    out["iv_fallback"] = round(fallback, 4) if iv_estimated else None
    return out


def greeks_for_strikes(rows: list[dict], smile: dict, spot: Optional[float],
                       dte_days: float) -> Optional[dict]:
    """Per-strike CE/PE Black-Scholes greeks at the ACTUAL spot/DTE, using the IVs
    solved from the chain's own closes (window-median fallback, disclosed).

    Thin wrapper over the canonical `mjonai.options.greeks` engine — model values,
    not market prints. None when there is nothing to price.
    """
    if not rows or spot is None or spot <= 0 or dte_days <= 0:
        return None
    from mjonai.options.greeks import calculate_black_scholes_greeks

    ce_iv = list(smile.get("ce_iv") or [None] * len(rows))
    pe_iv = list(smile.get("pe_iv") or [None] * len(rows))
    known = [v for v in ce_iv + pe_iv if isinstance(v, (int, float))]
    fallback = (sum(known) / len(known)) if known else 0.14
    iv_estimated = any(not isinstance(v, (int, float)) for v in ce_iv + pe_iv)

    def _legs(kind, ivs):
        out = []
        for r, iv in zip(rows, ivs):
            iv_used = iv if isinstance(iv, (int, float)) else fallback
            try:
                g = calculate_black_scholes_greeks(
                    spot=float(spot), strike=float(r["strike"]),
                    dte_days=float(dte_days), iv=float(iv_used), option_type=kind,
                )
            except Exception:
                out.append({"strike": float(r["strike"]), "iv": round(float(iv_used), 4)})
                continue
            out.append({
                "strike": float(r["strike"]), "iv": round(float(iv_used), 4),
                "delta": g["delta"], "gamma": g["gamma"],
                "theta_per_day": g["theta_per_day"], "vega_per_pct": g["vega_per_pct"],
                "theoretical_price": g["theoretical_price"],
                "intrinsic_value": g["intrinsic_value"], "time_value": g["time_value"],
            })
        return out

    return {
        "ce": _legs("CE", ce_iv),
        "pe": _legs("PE", pe_iv),
        "iv_estimated": iv_estimated,
        "iv_fallback": round(fallback, 4) if iv_estimated else None,
    }


def oi_track(rows: list[dict]) -> Optional[dict]:
    """Per-strike OI buildup/unwinding — the OpenAlgo OI-tracker pattern.

    Uses the OI change RECORDED with the source rows (bhavcopy 2024+); the
    close-only TradingTick era leaves it None and is reported as absent rather
    than fabricated as zero.
    """
    if not rows:
        return None
    known = [r for r in rows if r.get("ce_oi_change") is not None or r.get("pe_oi_change") is not None]
    return {
        "strikes": [r["strike"] for r in rows],
        "ce_oi_change": [r.get("ce_oi_change") for r in rows],
        "pe_oi_change": [r.get("pe_oi_change") for r in rows],
        "source_recorded": bool(known),
        "strikes_with_record": len(known),
    }


def vol_surface(warehouse: str, underlying: str, as_of, n_strikes: int = 7,
                max_expiries: int = 2) -> Optional[dict]:
    """IV surface across the nearest `max_expiries` expiries (OpenAlgo vol-surface).

    Uses the loader's additive `expiry_rank` so both expiries come from the same
    warehouse rows (no scraping, no synthetic expiries). Each leg whose price is
    <= 0.05 stays None — the surface has honest gaps, never solver defaults.
    Returns None when even the nearest expiry is absent.
    """
    import pandas as pd

    from mjonai.research.data.fno_eod import load_eod_chain_for_date

    ts = pd.Timestamp(as_of).normalize()
    legs = []
    for rank in range(max(1, int(max_expiries))):
        frame = load_eod_chain_for_date(warehouse, underlying, ts, expiry_rank=rank)
        if frame is None:
            break
        win = chain_window(frame, n_strikes=n_strikes)
        if not win["rows"]:
            continue
        dte = max(0, (pd.Timestamp(min(pd.to_datetime(frame["expiry"]))).normalize() - ts).days)
        smile = iv_smile(win["rows"], win["spot"], dte)
        legs.append({
            "expiry": str(pd.Timestamp(min(pd.to_datetime(frame["expiry"]))).date()),
            "dte_days": dte,
            "spot": win["spot"],
            "strikes": smile["strikes"],
            "ce_iv": smile["ce_iv"],
            "pe_iv": smile["pe_iv"],
        })
    if not legs:
        return None
    return {"expiries": legs, "expiry_count": len(legs)}


def oi_history(warehouse: str, underlying: str, as_of, expiry, n_strikes: int = 5,
               lookback_days: int = 10) -> Optional[dict]:
    """OI history for ONE expiry across the trading days it was listed (OpenAlgo
    OI-tracker depth): walks back from `as_of`, loading only days where that exact
    expiry was listed (the loader's explicit-expiry seam), and returns per-strike
    CE/PE OI per date. Days before the expiry's listing simply don't appear — no
    gap-filling, no other-expiry substitution.
    """
    import pandas as pd

    from mjonai.research.data.fno_eod import load_eod_chain_for_date

    ts = pd.Timestamp(as_of).normalize()
    exp = pd.Timestamp(expiry).normalize()
    points = []
    spot = None
    for back in range(max(1, int(lookback_days))):
        day = ts - pd.Timedelta(days=back)
        frame = load_eod_chain_for_date(warehouse, underlying, day, expiry=exp)
        if frame is None:
            continue
        win = chain_window(frame, n_strikes=n_strikes)
        if not win["rows"]:
            continue
        spot = win["spot"]
        points.append({
            "date": day.date().isoformat(),
            "dte_days": int((exp - day).days),
            "strikes": [r["strike"] for r in win["rows"]],
            "ce_oi": [r["ce_oi"] for r in win["rows"]],
            "pe_oi": [r["pe_oi"] for r in win["rows"]],
        })
    if not points:
        return None
    points.sort(key=lambda p: p["date"])
    return {"expiry": exp.date().isoformat(), "as_of": ts.date().isoformat(),
            "spot": spot, "points": points, "days": len(points)}


def greeks_history(warehouse: str, underlying: str, as_of, expiry,
                   lookback_days: int = 10) -> Optional[dict]:
    """ATM Greeks history for ONE expiry across the trading days it was listed
    (OpenAlgo `/ivchart` tool, clean-room — mechanism reimplemented against our
    own warehouse, no code copied).

    Each listed day resolves its own ATM strike (nearest to that day's spot —
    the strike TRACKS the market, exactly like a rolling ATM series), solves
    CE/PE IV from the day's own closes, and prices delta/theta/vega/gamma at
    the day's own DTE. A day the expiry wasn't listed is skipped (never
    substituted); an unsolvable leg is None with `iv_estimated` disclosed.
    Model values from stored closes — not market prints, not a signal.
    """
    import pandas as pd

    from mjonai.options.greeks import calculate_black_scholes_greeks
    from mjonai.research.data.fno_eod import load_eod_chain_for_date

    ts = pd.Timestamp(as_of).normalize()
    exp = pd.Timestamp(expiry).normalize()
    points = []
    for back in range(max(1, int(lookback_days))):
        day = ts - pd.Timedelta(days=back)
        frame = load_eod_chain_for_date(warehouse, underlying, day, expiry=exp)
        if frame is None or frame.empty:
            continue
        win = chain_window(frame, n_strikes=1)
        if not win["rows"]:
            continue
        row = win["rows"][0]
        spot = win["spot"]
        dte = max(int((exp - day).days), 0)
        smile = iv_smile([row], spot, dte)
        point = {
            "date": day.date().isoformat(),
            "dte_days": dte,
            "atm_strike": row["strike"],
            "spot": spot,
            "ce_iv": smile["ce_iv"][0],
            "pe_iv": smile["pe_iv"][0],
        }
        for kind, key in (("CE", "ce_iv"), ("PE", "pe_iv")):
            iv = point[key]
            prefix = key.split("_")[0]
            if not isinstance(iv, (int, float)) or spot <= 0 or dte <= 0:
                point.update({f"{prefix}_delta": None, f"{prefix}_theta": None,
                              f"{prefix}_vega": None, f"{prefix}_gamma": None})
                continue
            try:
                g = calculate_black_scholes_greeks(
                    spot=float(spot), strike=float(row["strike"]),
                    dte_days=float(dte), iv=float(iv), option_type=kind)
                point.update({f"{prefix}_delta": g["delta"], f"{prefix}_theta": g["theta_per_day"],
                              f"{prefix}_vega": g["vega_per_pct"], f"{prefix}_gamma": g["gamma"]})
            except Exception:
                point.update({f"{prefix}_delta": None, f"{prefix}_theta": None,
                              f"{prefix}_vega": None, f"{prefix}_gamma": None})
        points.append(point)
    if not points:
        return None
    points.sort(key=lambda p: p["date"])
    return {"expiry": exp.date().isoformat(), "as_of": ts.date().isoformat(),
            "points": points, "days": len(points)}


def strategy_builder(spot: float, legs: list[dict], lot_size: int = 25) -> dict:
    """
    Build and evaluate a multi-leg options strategy at expiry.

    Args:
        spot: Current spot price
        legs: [{"type": "CE"|"PE", "side": "BUY"|"SELL", "strike": K, "premium": P,
                "lots": n, "label": "optional"}]
        lot_size: Exchange lot size (default 25 for Nifty)

    Returns:
        Dict with payoff curve, breakevens, max profit/loss, risk metrics
    """
    if not legs:
        return {"error": "No legs provided"}

    # Build spot range ±15% around current spot (configurable)
    span = 0.15
    spots = [spot * (1 - span) + 2 * spot * span * i / 80 for i in range(81)]

    return payoff_curve(legs, spots, lot_size=lot_size)


__all__ = [
    "chain_window",
    "window_pcr",
    "max_pain",
    "oi_profile",
    "payoff_curve",
    "straddle_pnl",
    "iv_smile",
    "gex_profile",
    "greeks_for_strikes",
    "oi_track",
    "vol_surface",
    "oi_history",
    "strategy_builder",
]
