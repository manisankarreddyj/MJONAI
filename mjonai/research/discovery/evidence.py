"""
Module: research/discovery/evidence.py
Purpose: DAILY option-chain evidence features for the discovery harness.

WHY THIS EXISTS
---------------
The 2026-10-05 price-only sweep settled a question: 82 low-turnover daily index
configs, and NOT ONE beats buy-and-hold or has a White's Reality Check p-value
below 0.72. Price alone carries no detectable edge.

But MJONAI's own stated thesis (docs section 3, the 8-layer evidence framework)
says the edge comes from independent LAYERS, and layers 3-4 -- options
intelligence (PCR, max pain, GEX regime) and institutional flow -- have never
been in ANY backtest. This module finally makes layer 3 testable. It is the
first honest test of the project's central claim.

FEATURES (one row per trade_date, per underlying)
  pcr_oi              put OI / call OI on the front month
  maxpain_dist_pct    (spot - max_pain) / spot. Positive => OI positioning sits
                      ABOVE spot, i.e. the market must rally into it (the
                      "call wall magnet" effect in the Indian market).
  maxpain_gap_pct     |maxpain - spot| / spot, in strike units (pinned-ness)
  total_gex_crores    net dealer gamma exposure, canonical engine
  is_positive_gamma   dealers long gamma => mean-reverting, trend strategies
                      should be OFF in this regime (the key hypothesis)
  zero_gamma_level    the gamma-flip price
  atm_iv              ATM implied vol solved from the chain's own close

SINGLE-CANONICAL-SOURCE DISCIPLINE
-----------------------------------
Gamma comes from `mjonai.data.derivatives.gex_engine.calculate_gamma_exposure`
(the same engine S13 consumes) and IV from
`mjonai.options.greeks.calculate_implied_volatility`. Neither is reimplemented
here. This is a feature BUILDER, not a second options library.

HONEST LIMITATIONS (read before trusting a number)
--------------------------------------------------
  - No historical smile. IV is solved once per date at the ATM and applied flat
    across all strikes. A real smile would change gamma away from the money.
  - Front month only (nearest expiry strictly after trade_date). Weekly expiries
    mean the front month is often ~4 days out, and its DTE differs through the
    week, so gamma is not perfectly comparable day to day.
  - OI is EOD open interest, so features are end-of-day and can only be applied
    to DECISIONS MADE AFTER the close. Any signal using them is applied with a
    one-bar lag by the harness, which is the correct treatment.
  - Chain coverage starts 2019-02 (NIFTY) / 2016-06 (BANKNIFTY), so any test
    runs on a SHORTER window than the price-only sweep. Comparisons must
    therefore be made against a price-only baseline re-run on the SAME window.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

from mjonai.data.derivatives.gex_engine import calculate_gamma_exposure
from mjonai.options.greeks import calculate_implied_volatility

CHAIN_DIR = Path("storage") / "parquet" / "fno_chain" / "eod"

_READ_COLS = [
    "trade_date", "underlying", "kind", "option_type", "strike",
    "expiry", "oi", "close", "underlying_price", "lot_size",
]


def chain_root() -> Path:
    """Resolve the chain warehouse via the canonical path helper (portable)."""
    from mjonai.configs.research_paths import WORKSPACE_ROOT

    return WORKSPACE_ROOT / CHAIN_DIR


def _max_pain(strikes: np.ndarray, call_oi: np.ndarray, put_oi: np.ndarray) -> float:
    """Strike minimising total option-holder P&L at expiry (standard max pain).

    Options settle at intrinsic value only, so each leg contributes a POSITIVE
    part. Max pain is the settlement where holders' total P&L is most negative,
    i.e. where writers gain most.

        holder_pnl(S) = SUM max(0, S - K)*call_OI + SUM max(0, K - S)*put_OI

    The positive part is not cosmetic. An earlier revision used the linear form
    (S - K) and (K - S) with no max(0, .), which made prices far BELOW every
    strike look maximally painful -- the exact opposite of the real effect -- and
    silently corrupted the maxpain_dist_pct feature. A regression test
    (test_max_pain_picks_the_strike_that_minimises_writer_pnl) pins the
    positive-part form.
    """
    if len(strikes) == 0:
        return float("nan")
    best_strike, best_pnl = float("nan"), float("inf")
    for k in strikes:
        intrinsic_calls = np.maximum(0.0, k - strikes) * call_oi
        intrinsic_puts = np.maximum(0.0, strikes - k) * put_oi
        pnl = float(np.sum(intrinsic_calls) + np.sum(intrinsic_puts))
        if pnl < best_pnl:
            best_pnl, best_strike = pnl, float(k)
    return best_strike


def build_evidence(
    underlying: str,
    start: str,
    end: str,
    chain_dir: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Build daily option-chain evidence features for `underlying`.

    Returns a frame indexed by trade_date with columns:
        pcr_oi, maxpain, maxpain_dist_pct, maxpain_gap_pct,
        total_gex_crores, is_positive_gamma, zero_gamma_level, atm_iv
    Fail-closed: a month that cannot be read, or a date with no usable chain,
    simply contributes no rows. Nothing is imputed or fabricated.
    """
    import pyarrow.parquet as pq

    root = Path(chain_dir) if chain_dir else chain_root()
    underlying = underlying.upper()
    lo, hi = pd.Timestamp(start), pd.Timestamp(end)

    rows: list[dict] = []
    for month_file in sorted(root.glob("*.parquet")):
        # Cheap pre-filter on the month stamp before paying for the read.
        stamp = pd.to_datetime(month_file.stem + "-01", errors="coerce")
        if pd.isna(stamp) or stamp < lo.replace(day=1) or stamp > hi:
            continue
        try:
            df = pq.read_table(month_file, columns=_READ_COLS).to_pandas()
        except Exception:
            continue
        if df.empty:
            continue
        df = df[(df["underlying"] == underlying) & (df["kind"] == "OPT")]
        if df.empty:
            continue
        df = df.dropna(subset=["expiry", "strike", "underlying_price"])
        if df.empty:
            continue
        df = df[df["option_type"].isin(["CE", "PE"])]
        if df.empty:
            continue

        for day, grp in df.groupby("trade_date", sort=True):
            day = pd.Timestamp(day)
            if day < lo or day > hi:
                continue
            spot = float(grp["underlying_price"].dropna().iloc[0])
            if not np.isfinite(spot) or spot <= 0:
                continue

            # Front month = nearest expiry STRICTLY after the trade date, so an
            # expiry-day chain is never treated as the live front month.
            expiries = sorted(pd.Timestamp(e) for e in grp["expiry"].unique())
            future = [e for e in expiries if e > day]
            if not future:
                continue
            expiry = future[0]
            dte = max((expiry - day).days, 1)
            leg = grp[pd.to_datetime(grp["expiry"]) == expiry]
            if leg.empty:
                continue

            calls = leg[leg["option_type"] == "CE"].set_index("strike")["oi"]
            puts = leg[leg["option_type"] == "PE"].set_index("strike")["oi"]
            strikes = np.array(sorted(set(calls.index) | set(puts.index)), dtype=float)
            if len(strikes) == 0:
                continue
            call_oi = np.array([float(calls.get(s, 0.0) or 0.0) for s in strikes])
            put_oi = np.array([float(puts.get(s, 0.0) or 0.0) for s in strikes])
            call_oi = np.nan_to_num(call_oi)
            put_oi = np.nan_to_num(put_oi)
            if call_oi.sum() <= 0 and put_oi.sum() <= 0:
                continue

            lot_vals = leg["lot_size"].dropna()
            lot = int(np.median(np.nan_to_num(lot_vals.to_numpy(dtype=float), nan=65.0))) \
                if len(lot_vals) else 65

            # ATM implied vol solved from the chain's own close (not a constant).
            atm_i = int(np.argmin(np.abs(strikes - spot)))
            atm_strike = float(strikes[atm_i])
            ivs = []
            for opt_type, series, price_col in (("CE", calls, None), ("PE", puts, None)):
                px = leg[(leg["option_type"] == opt_type) & (leg["strike"] == atm_strike)]["close"]
                if len(px) and np.isfinite(px.iloc[0]) and float(px.iloc[0]) > 0.05:
                    ivs.append(calculate_implied_volatility(
                        float(px.iloc[0]), spot, atm_strike, dte, opt_type,
                    ))
            atm_iv = float(np.mean(ivs)) if ivs else 0.14
            if not np.isfinite(atm_iv) or atm_iv <= 0.001:
                atm_iv = 0.14

            snap = calculate_gamma_exposure(
                underlying=underlying,
                spot_price=spot,
                strikes=strikes,
                call_oi=call_oi,
                put_oi=put_oi,
                dte_days=float(dte),
                default_iv=atm_iv,
                lot_size=lot,
            )

            maxp = _max_pain(strikes, call_oi, put_oi)
            call_sum, put_sum = float(call_oi.sum()), float(put_oi.sum())

            rows.append({
                "trade_date": day,
                "spot": spot,
                "pcr_oi": (put_sum / call_sum) if call_sum > 0 else np.nan,
                "maxpain": maxp,
                "maxpain_dist_pct": ((spot - maxp) / spot) if np.isfinite(maxp) else np.nan,
                "maxpain_gap_pct": (abs(spot - maxp) / spot) if np.isfinite(maxp) else np.nan,
                "total_gex_crores": float(snap.total_gex_crores),
                "is_positive_gamma": bool(snap.is_in_positive_gamma),
                "zero_gamma_level": snap.zero_gamma_level,
                "atm_iv": atm_iv,
                "front_expiry": expiry,
                "dte_days": dte,
                "call_oi_total": call_sum,
                "put_oi_total": put_sum,
            })

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows).set_index("trade_date").sort_index()
    return out[~out.index.duplicated(keep="last")]