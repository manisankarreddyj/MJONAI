"""
Module: data/market/opening_volume.py
Purpose: Quantitative 09:15-09:30 AM Opening Range Relative Volume (RVOL) Sentry (TD-011).
         Measures institutional conviction during the critical first 15-minute market opening auction bar.
         Feeds directly into `core/mqi.py` (Factor 6: Volume Confirmation Engine).

Architectural Principles:
  1. O(1) Fast-Path Scoring: Evaluates real-time opening bar volume vs 20-day historical average opening volume.
  2. Institutional Regime Classification: DRY (<0.8x), NORMAL (0.8x-1.5x), EXPANSION (1.5x-2.5x), ULTRA (>=2.5x).
  3. Seamless MQI Integration: Exposes `get_intraday_volume_score(rvol)` returning standard (+2, +1, 0) weights.
  4. Typed Immutable Snapshot: Produces `OpeningVolumeSnapshot` with complete quantitative provenance.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging
from pathlib import Path
import sys
import threading
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure workspace root is in sys.path
_root_dir = Path(__file__).resolve().parents[3]  # repo root (ADR-0008)
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

from mjonai.core.time_utils import now_ist, today_ist

logger = logging.getLogger(__name__)


# ── 1. ENUMS & DATA CONTRACTS ────────────────────────────────────────────────

class VolumeRegime(str, Enum):
    """Institutional Opening Volume Regime Classification."""
    DRY_VOLUME             = "DRY_VOLUME"              # RVOL < 0.8x (Low conviction, choppy trap risk)
    NORMAL_VOLUME          = "NORMAL_VOLUME"           # 0.8x <= RVOL < 1.5x (Standard baseline participation)
    EXPANSION_VOLUME       = "EXPANSION_VOLUME"        # 1.5x <= RVOL < 2.5x (Institutional expansion day)
    ULTRA_EXPANSION_VOLUME = "ULTRA_EXPANSION_VOLUME"  # RVOL >= 2.5x (Massive institutional catalyst / rebalance)
    INSUFFICIENT_DATA      = "INSUFFICIENT_DATA"       # Missing/unusable baseline or volume (RVOL not computable)


@dataclass(frozen=True)
class OpeningVolumeSnapshot:
    """
    Immutable 09:15-09:30 AM Opening Volume Analysis Contract.
    """
    symbol: str
    opening_volume_15m: float
    avg_20d_opening_volume: float
    rvol_ratio: float
    volume_regime: VolumeRegime
    is_expansion_volume: bool
    is_dry_volume: bool
    timestamp: datetime
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "opening_volume_15m": self.opening_volume_15m,
            "avg_20d_opening_volume": self.avg_20d_opening_volume,
            "rvol_ratio": round(self.rvol_ratio, 4),
            "volume_regime": self.volume_regime.value,
            "is_expansion_volume": self.is_expansion_volume,
            "is_dry_volume": self.is_dry_volume,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
        }


# ── 2. IN-MEMORY VOLUME CACHE ────────────────────────────────────────────────

# Map of symbol -> (20d_avg_opening_volume, timestamp)
_avg_opening_volume_cache: Dict[str, Tuple[float, datetime]] = {}
_vol_lock = threading.RLock()


def register_historical_opening_volume(symbol: str, avg_volume_20d: float) -> None:
    """
    Register or update the 20-day historical opening 15-minute average volume for a symbol.
    """
    clean_sym = symbol.strip().upper()
    if avg_volume_20d <= 0.0:
        return
    with _vol_lock:
        _avg_opening_volume_cache[clean_sym] = (avg_volume_20d, now_ist())


def clear_opening_volume_cache() -> None:
    """Clear in-memory historical opening volume baseline cache."""
    with _vol_lock:
        _avg_opening_volume_cache.clear()


# ── 3. RVOL CALCULATION & SCORING ENGINES ─────────────────────────────────────

def calculate_opening_rvol(
    symbol: str,
    opening_volume: Optional[float] = None,
    avg_20d_opening_volume: Optional[float] = None
) -> OpeningVolumeSnapshot:
    """
    Calculate 09:15-09:30 AM Opening Bar Relative Volume (RVOL) and classify the volume regime.

    Args:
        symbol: Canonical ticker symbol (e.g. "NIFTY", "RELIANCE", "BANKNIFTY")
        opening_volume: Actual volume recorded in the first 15 minutes
        avg_20d_opening_volume: Historical 20-day average 15-minute volume

    Returns:
        OpeningVolumeSnapshot: Immutable typed volume assessment. When either the
        20D baseline or the current opening volume is missing/unusable, an explicit
        insufficient-data snapshot is returned (regime INSUFFICIENT_DATA, rvol 0.0,
        MQI contribution 0) — no fabricated defaults.
    """
    clean_sym = symbol.strip().upper()
    now = now_ist()

    # 1. Resolve historical baseline
    baseline = avg_20d_opening_volume
    if baseline is not None and baseline <= 0.0:
        baseline = None  # unusable baseline value
    if baseline is None:
        with _vol_lock:
            cached = _avg_opening_volume_cache.get(clean_sym)
            if cached is not None and cached[0] > 0.0:
                baseline = cached[0]

    # 2. Resolve opening volume (None / negative => unusable measurement)
    vol_15m: Optional[float] = None
    if opening_volume is not None and opening_volume >= 0.0:
        vol_15m = float(opening_volume)

    # Insufficient-data guard: never fabricate a placeholder baseline, never reuse
    # the baseline as a stand-in for a missing opening volume. The previous
    # fallbacks (unknown baseline -> 100_000; missing volume -> baseline) produced
    # a fake rvol=1.0 "NORMAL_VOLUME" (+1 MQI score) for symbols with NO data.
    has_baseline = baseline is not None and baseline > 0.0
    has_volume = vol_15m is not None

    if not has_baseline or not has_volume:
        missing_parts = []
        if not has_baseline:
            missing_parts.append("20D avg opening volume baseline")
        if not has_volume:
            missing_parts.append("current opening volume")
        return OpeningVolumeSnapshot(
            symbol=clean_sym,
            opening_volume_15m=vol_15m if has_volume else 0.0,
            avg_20d_opening_volume=float(baseline) if has_baseline else 0.0,
            rvol_ratio=0.0,
            volume_regime=VolumeRegime.INSUFFICIENT_DATA,
            is_expansion_volume=False,
            is_dry_volume=False,
            timestamp=now,
            message=(
                "Insufficient Volume Data (missing: "
                + ", ".join(missing_parts)
                + "): RVOL regime unknown, MQI score contribution 0"
            ),
        )

    # 3. Compute RVOL Ratio (both inputs verified usable above)
    rvol = vol_15m / float(baseline)

    # 4. Classify Volume Regime
    if rvol >= 2.5:
        regime = VolumeRegime.ULTRA_EXPANSION_VOLUME
        is_exp = True
        is_dry = False
        msg = f"Ultra Expansion Volume ({rvol:.2f}x >= 2.5x 20D Avg: Heavy Institutional Footprint)"
    elif rvol >= 1.5:
        regime = VolumeRegime.EXPANSION_VOLUME
        is_exp = True
        is_dry = False
        msg = f"Expansion Opening Volume ({rvol:.2f}x >= 1.5x 20D Avg: Institutional Trend Day Confirmed)"
    elif rvol < 0.8:
        regime = VolumeRegime.DRY_VOLUME
        is_exp = False
        is_dry = True
        msg = f"Dry Opening Volume ({rvol:.2f}x < 0.8x 20D Avg: Low Conviction / Choppy Session Alert)"
    else:
        regime = VolumeRegime.NORMAL_VOLUME
        is_exp = False
        is_dry = False
        msg = f"Normal Opening Volume ({rvol:.2f}x: Standard Market Participation)"

    return OpeningVolumeSnapshot(
        symbol=clean_sym,
        opening_volume_15m=vol_15m,
        avg_20d_opening_volume=baseline,
        rvol_ratio=rvol,
        volume_regime=regime,
        is_expansion_volume=is_exp,
        is_dry_volume=is_dry,
        timestamp=now,
        message=msg,
    )


def get_intraday_volume_score(rvol_ratio: Optional[float] = None) -> Tuple[int, str]:
    """
    Direct MQI Factor 6 Quant Scoring Helper.

    Scoring Logic:
      - RVOL >= 1.5x  -> +2 points (High Institutional Conviction)
      - RVOL >= 0.8x  -> +1 point  (Baseline Participation)
      - RVOL <  0.8x  ->  0 points (Dry Volume Penalty)
      - None          ->  0 points (Insufficient Volume Data: never fabricate participation)

    Returns:
        (score, reason)
    """
    if rvol_ratio is None:
        return 0, "Opening Volume: Insufficient Volume Data (no RVOL available: 0)"

    if rvol_ratio >= 1.5:
        return 2, f"Opening Volume High Conviction ({rvol_ratio:.2f}x >= 1.5x: +2)"
    elif rvol_ratio >= 0.8:
        return 1, f"Opening Volume Normal ({rvol_ratio:.2f}x: +1)"
    else:
        return 0, f"Opening Volume Dry ({rvol_ratio:.2f}x < 0.8x: 0)"


def is_orb_volume_confirmed(
    symbol: str,
    opening_volume: Optional[float] = None,
    avg_20d_opening_volume: Optional[float] = None,
    rvol_threshold: float = 1.5
) -> bool:
    """
    Opening Range Breakout (ORB) Institutional Confirmation Guard.
    Returns True if the opening 15-minute bar volume meets or exceeds the institutional RVOL threshold.
    """
    snap = calculate_opening_rvol(
        symbol=symbol,
        opening_volume=opening_volume,
        avg_20d_opening_volume=avg_20d_opening_volume
    )
    return snap.rvol_ratio >= rvol_threshold


# ── 4. SELF-DIAGNOSTIC TEST HARNESS ──────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("===================================================================")
    print("MJONAI 09:15-09:30 AM OPENING RELATIVE VOLUME (RVOL) SENTRY")
    print("===================================================================")

    test_cases = [
        ("NIFTY", 4_500_000, 1_800_000),   # 2.50x Ultra Expansion
        ("RELIANCE", 850_000, 500_000),    # 1.70x Expansion
        ("TCS", 200_000, 220_000),         # 0.91x Normal
        ("INFY", 95_000, 180_000),         # 0.53x Dry
    ]

    for sym, vol, avg_vol in test_cases:
        snap = calculate_opening_rvol(sym, vol, avg_vol)
        score, reason = get_intraday_volume_score(snap.rvol_ratio)
        print(f"  - {sym:<10} | RVOL: {snap.rvol_ratio:.2f}x | Regime: {snap.volume_regime.value:<22} | Score: +{score} | {reason}")

    print("===================================================================")
