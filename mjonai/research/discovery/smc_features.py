"""
Module: research/discovery/smc_features.py
Purpose: LEAKAGE-SAFE Smart Money Concepts (SMC) research features.

Wraps the vendored smart-money-concepts library (storage/vendor/smc, pinned by
tools/scripts/fetch_smc.py). That library is NOT leakage-free: swing_highs_lows looks
forward ~swing_length bars (`high.shift(-N).rolling(2N).max()`), and fvg uses the NEXT bar
(`shift(-1)`). Every feature here is therefore lagged by a confirmation window so that the value
at bar t encodes only bars <= t — the raw library output in a live signal would read the future.

RESEARCH ONLY: this lives under research/discovery/ and must be imported by nothing in
apps/runtime, apps/web, or a non-research kernel module (machine-enforced by
tests/test_architecture_rules.py). Its only judge is the discovery harness's WFE/DSR gate;
anything that survives there is what a strategy may eventually consume.

Failure is honest: if the vendored code is absent, RuntimeError with the fetch command — never a
fabricated feature.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

_VENDOR = Path(__file__).resolve().parents[3] / "storage" / "vendor" / "smc"
_RESEARCH_MISSING = (
    "smart-money-concepts is not vendored. Run: python tools/scripts/fetch_smc.py "
    "(pure pandas/numpy; no torch required)."
)


def load_smc():
    """Return the vendored `smc` class (lazy; no import-time network or dep)."""
    import os
    import sys

    # The upstream package prints a unicode "star" banner at import that raises
    # UnicodeEncodeError on a cp1252 console; SMC_CREDIT=0 (its documented switch) silences it.
    os.environ.setdefault("SMC_CREDIT", "0")

    # On-disk check first so an absent/unpatched vendor raises deterministically even if a
    # prior import left `smartmoneyconcepts` in sys.modules.
    if not (_VENDOR / "smartmoneyconcepts" / "smc.py").is_file():
        raise RuntimeError(_RESEARCH_MISSING)

    vendor = str(_VENDOR)
    if vendor not in sys.path:
        sys.path.insert(0, vendor)
    try:
        from smartmoneyconcepts import smc  # type: ignore
    except ImportError as exc:
        raise RuntimeError(_RESEARCH_MISSING) from exc
    return smc


def _lower_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """MJONAI frames are Capitalized (Open/High/Low/Close/Volume); the library uses lowercase."""
    return df.rename(columns={c: str(c).lower() for c in df.columns})


def smc_features(
    df: pd.DataFrame,
    swing_length: int = 20,
    confirm_lag: Optional[int] = None,
) -> pd.DataFrame:
    """Leakage-safe SMC structural features for a Capitalized OHLCV frame ordered oldest->newest.

    Features (all causal — value at bar t uses only bars <= t):
      smc_swing_hl      : +1 most recent CONFIRMED swing high, -1 swing low (else 0)
      smc_dist_to_swing : (close - swing_level)/close, signed distance to last confirmed swing
      smc_fvg_dir       : +1 last confirmed bullish FVG, -1 bearish FVG (else 0)
      smc_in_bull_fvg   : 1.0 when close sits inside a confirmed bullish FVG zone (mitigation target)
      smc_in_bear_fvg   : 1.0 when close sits inside a confirmed bearish FVG zone

    The confirmation lag defaults to swing_length + 2 (>= the forward look), which is conservative:
    it may discard the newest swing but can never let a future bar influence bar t.
    """
    smc = load_smc()
    lag = int(confirm_lag) if confirm_lag is not None else (int(swing_length) + 2)

    lc = _lower_ohlcv(df).copy()
    for col in ("open", "high", "low", "close"):
        if col not in lc.columns:
            raise ValueError(f"SMC features need '{col}' column")

    close = lc["close"].astype(float)

    shl = smc.swing_highs_lows(lc, swing_length=int(swing_length))
    fvg = smc.fvg(lc)
    # The library builds its outputs off numpy arrays, so they carry a RangeIndex; re-label to the
    # frame's index so downstream comparison against `close` aligns positionally.
    shl = shl.set_axis(df.index)
    fvg = fvg.set_axis(df.index)

    # De-bias by each function's own look-ahead: swing detects over a forward window of
    # ~swing_length bars (known at bar i+N); fvg uses bar i+1 (known at bar i+1).
    swing_hl = shl["HighLow"].shift(lag).fillna(0.0)
    swing_lvl = shl["Level"].shift(lag)
    fvg_dir = fvg["FVG"].shift(1)
    fvg_top = fvg["Top"].shift(1)
    fvg_bot = fvg["Bottom"].shift(1)

    # An FVG's zone [bottom, top] is defined by bars i-1 and i+1, so it only exists once bar i+1
    # closes -> confirmed one bar late (shift(1) above). Carry the most recent CONFIRMED gap
    # forward as the "active zone": ffill of a lagged series is still causal (each value is a
    # past gap). A bullish gap then acts as support (price holds above its floor); bearish as
    # resistance (price holds under its ceiling) — the leakage-safe way to use an unfilled gap.
    zone_valid = ~fvg_top.isna() & ~fvg_bot.isna()
    active_dir = fvg_dir.where(zone_valid).ffill().fillna(0.0)
    active_top = fvg_top.where(zone_valid).ffill()
    active_bot = fvg_bot.where(zone_valid).ffill()
    active_valid = ~active_top.isna() & ~active_bot.isna()

    feat = pd.DataFrame(index=df.index)
    feat["smc_swing_hl"] = swing_hl
    feat["smc_dist_to_swing"] = ((close - swing_lvl) / close.replace(0.0, np.nan)).astype(float)
    feat["smc_fvg_dir"] = active_dir
    feat["smc_in_bull_fvg"] = ((active_dir == 1) & (close >= active_bot)).where(active_valid, False).astype(float).fillna(0.0)
    feat["smc_in_bear_fvg"] = ((active_dir == -1) & (close <= active_top)).where(active_valid, False).astype(float).fillna(0.0)

    # ── Additive primitives (2026-10-11): order blocks, BOS/CHoCH, liquidity. ──
    # Each library function consumes the swing frame (which looks forward), so each
    # output is shifted by the SAME confirmation lag as the swings — the same
    # de-bias discipline, and a library error yields 0.0 (no marker) rather than a
    # fabricated level. Existing columns above are byte-identical, so the A8 verdict
    # stays valid.
    def _lagged(fn, column: str, extra_lag: int = 0) -> pd.Series:
        try:
            raw = fn(lc, shl).set_axis(df.index)
            return raw[column].shift(lag + extra_lag).fillna(0.0)
        except Exception:
            return pd.Series(0.0, index=df.index)

    feat["smc_ob_dir"] = _lagged(smc.ob, "OB")
    feat["smc_bos"] = _lagged(smc.bos_choch, "BOS")
    feat["smc_choch"] = _lagged(smc.bos_choch, "CHOCH")
    feat["smc_liquidity"] = _lagged(smc.liquidity, "Liquidity")
    return feat
