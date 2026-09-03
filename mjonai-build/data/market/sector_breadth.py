"""
Module: data/market/sector_breadth.py
Purpose: Real-Time Sectoral Market Breadth & Intermarket Rotation Engine (TD-011).
         Tracks the 12 primary NSE sectoral indices in real-time.
         Calculates broad market participation percentage (% advancing sectors)
         to feed directly into `core/market_state.py` (Factor 2) and `core/mqi.py` (Factor 3).

Architectural Principles:
  1. O(1) Fast-Path Memory Cache: In-memory live tick tracking eliminates redundant historical calls.
  2. Multi-Sector Universe: Tracks Banking, IT, Auto, FMCG, Metal, Pharma, Realty, Energy, FinServ, PSU Banks, Media.
  3. Robust Fallback: Handles partial feed outages gracefully with offline baseline fallbacks.
  4. Typed Immutable Snapshot: Produces `SectorBreadthSnapshot` with complete performance provenance.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from pathlib import Path
import sys
import threading
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

# Ensure workspace root is in sys.path
_root_dir = Path(__file__).resolve().parent.parent.parent
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

from core.time_utils import now_ist, today_ist

logger = logging.getLogger(__name__)


# ── 1. ENUMS & DATA CONTRACTS ────────────────────────────────────────────────

class SectorIndex(str, Enum):
    """Primary NSE Sectoral Indices."""
    NIFTY_BANK       = "NIFTY BANK"
    NIFTY_IT         = "NIFTY IT"
    NIFTY_AUTO       = "NIFTY AUTO"
    NIFTY_FMCG       = "NIFTY FMCG"
    NIFTY_METAL      = "NIFTY METAL"
    NIFTY_PHARMA     = "NIFTY PHARMA"
    NIFTY_REALTY     = "NIFTY REALTY"
    NIFTY_ENERGY     = "NIFTY ENERGY"
    NIFTY_FIN_SERVICE = "NIFTY FIN SERVICE"
    NIFTY_PSU_BANK   = "NIFTY PSU BANK"
    NIFTY_PVT_BANK   = "NIFTY PVT BANK"
    NIFTY_MEDIA      = "NIFTY MEDIA"


# Canonical Sector Symbol & Angel One Index Token Map
SECTOR_TOKEN_MAP: Dict[SectorIndex, str] = {
    SectorIndex.NIFTY_BANK:        "99926009",
    SectorIndex.NIFTY_IT:          "99926008",
    SectorIndex.NIFTY_AUTO:        "99926005",
    SectorIndex.NIFTY_FMCG:        "99926006",
    SectorIndex.NIFTY_METAL:       "99926010",
    SectorIndex.NIFTY_PHARMA:      "99926011",
    SectorIndex.NIFTY_REALTY:      "99926012",
    SectorIndex.NIFTY_ENERGY:      "99926014",
    SectorIndex.NIFTY_FIN_SERVICE: "99926037",
    SectorIndex.NIFTY_PSU_BANK:    "99926013",
    SectorIndex.NIFTY_PVT_BANK:    "99926015",
    SectorIndex.NIFTY_MEDIA:       "99926007",
}


@dataclass(frozen=True)
class SectorPerformance:
    """Individual Sector Index Performance Snapshot."""
    sector: SectorIndex
    token: str
    ltp: float
    prev_close: float
    change_pct: float
    is_advancing: bool
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sector": self.sector.value,
            "token": self.token,
            "ltp": self.ltp,
            "prev_close": self.prev_close,
            "change_pct": round(self.change_pct, 4),
            "is_advancing": self.is_advancing,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass(frozen=True)
class SectorBreadthSnapshot:
    """
    Immutable Broad Market Sectoral Breadth Assessment.
    """
    timestamp: datetime
    breadth_pct: float               # Percentage of advancing sectors (0.0 to 1.0)
    advancing_count: int             # Number of advancing sectors
    declining_count: int             # Number of declining sectors
    unchanged_count: int             # Number of flat sectors
    total_sectors: int               # Total tracked sectors evaluated
    top_sector: Optional[str]        # Strongest outperforming sector name
    top_change_pct: Optional[float]  # Gain of strongest sector
    lag_sector: Optional[str]        # Weakest underperforming sector name
    lag_change_pct: Optional[float]  # Loss of weakest sector
    is_strong_bull: bool             # breadth_pct >= 0.60 (60% sectors green)
    is_strong_bear: bool             # breadth_pct <= 0.40 (40% sectors green)
    provenance_reason: str           # Human-readable quantitative audit trail
    sector_details: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "breadth_pct": round(self.breadth_pct, 4),
            "advancing_count": self.advancing_count,
            "declining_count": self.declining_count,
            "unchanged_count": self.unchanged_count,
            "total_sectors": self.total_sectors,
            "top_sector": self.top_sector,
            "top_change_pct": round(self.top_change_pct, 4) if self.top_change_pct is not None else None,
            "lag_sector": self.lag_sector,
            "lag_change_pct": round(self.lag_change_pct, 4) if self.lag_change_pct is not None else None,
            "is_strong_bull": self.is_strong_bull,
            "is_strong_bear": self.is_strong_bear,
            "provenance_reason": self.provenance_reason,
            "sector_details": self.sector_details,
        }


# ── 2. IN-MEMORY SECTOR STATE STORE ──────────────────────────────────────────

_live_sector_prices: Dict[SectorIndex, Tuple[float, float, datetime]] = {}  # (ltp, prev_close, ts)
_sector_lock = threading.RLock()

# Staleness & coverage guards for the live-tick breadth path:
#   - A tick older than SECTOR_TICK_STALENESS_SECONDS (vs its stored timestamp)
#     is excluded from breadth computation.
#   - Bull/Bear regime flags require at least MIN_SECTOR_COVERAGE fresh sectors
#     out of the 12 tracked indices. Below that threshold the snapshot is
#     explicitly NEUTRAL (partial/stale feeds must never drive regime flags).
SECTOR_TICK_STALENESS_SECONDS = 600.0
MIN_SECTOR_COVERAGE = 8


def update_sector_price(sector: Union[SectorIndex, str], ltp: float, prev_close: float) -> None:
    """
    Ingest real-time tick for a sectoral index.
    """
    sec = SectorIndex(sector) if isinstance(sector, str) else sector
    if ltp <= 0.0 or prev_close <= 0.0:
        return
    with _sector_lock:
        _live_sector_prices[sec] = (ltp, prev_close, now_ist())


def clear_sector_prices() -> None:
    """Reset sector prices in memory."""
    with _sector_lock:
        _live_sector_prices.clear()


# ── 3. BREADTH CALCULATION ENGINE ────────────────────────────────────────────

def calculate_sector_breadth(
    custom_returns: Optional[Union[Mapping[SectorIndex, float], Mapping[str, float], Mapping[Any, float]]] = None
) -> SectorBreadthSnapshot:
    """
    Calculate broad sectoral market breadth ratio and intermarket leaders/laggards.

    Args:
        custom_returns: Optional mapping of sector names/enums to percentage returns (e.g. {"NIFTY BANK": 0.012})
                        Used for simulations, backtesting, and unit test injection.

    Coverage & Staleness Guards (live-tick path only):
        - Live ticks older than SECTOR_TICK_STALENESS_SECONDS are excluded.
        - If fewer than MIN_SECTOR_COVERAGE fresh sectors remain, a NEUTRAL
          snapshot is returned (no strong_bull/strong_bear flags) with the
          reason citing insufficient coverage. A zero-sample result is also
          explicitly NEUTRAL — missing data is never interpreted as bearish.

    Returns:
        SectorBreadthSnapshot: Typed immutable breadth snapshot.
    """
    now = now_ist()
    details: Dict[str, Dict[str, Any]] = {}
    advancing = 0
    declining = 0
    unchanged = 0
    used_live_ticks = False
    stale_excluded = 0

    sorted_sectors: List[Tuple[str, float]] = []

    # 1. Path A: Custom Returns Injection
    if custom_returns is not None and len(custom_returns) > 0:
        for sec_key, chg in custom_returns.items():
            sec_name = sec_key.value if isinstance(sec_key, SectorIndex) else str(sec_key)
            is_adv = chg > 0.0001
            is_dec = chg < -0.0001
            if is_adv:
                advancing += 1
            elif is_dec:
                declining += 1
            else:
                unchanged += 1

            sorted_sectors.append((sec_name, chg))
            details[sec_name] = {
                "change_pct": round(chg, 4),
                "is_advancing": is_adv,
            }

    # 2. Path B: Live In-Memory Ticks (staleness-filtered)
    else:
        used_live_ticks = True
        cutoff = now - timedelta(seconds=SECTOR_TICK_STALENESS_SECONDS)
        with _sector_lock:
            for sec, (ltp, prev_close, tick_ts) in list(_live_sector_prices.items()):
                if tick_ts < cutoff:
                    stale_excluded += 1  # Stale tick: excluded from breadth sample
                    continue
                chg = (ltp - prev_close) / prev_close if prev_close > 0 else 0.0
                is_adv = chg > 0.0001
                is_dec = chg < -0.0001
                if is_adv:
                    advancing += 1
                elif is_dec:
                    declining += 1
                else:
                    unchanged += 1

                sorted_sectors.append((sec.value, chg))
                details[sec.value] = {
                    "ltp": ltp,
                    "prev_close": prev_close,
                    "change_pct": round(chg, 4),
                    "is_advancing": is_adv,
                }

    total = len(sorted_sectors)

    # 3. Fallback: Zero usable samples -> explicitly NEUTRAL (never bearish)
    if total == 0:
        if stale_excluded > 0:
            reason = (
                "Sector Breadth: No Fresh Sector Ticks "
                f"({stale_excluded} stale ticks older than {SECTOR_TICK_STALENESS_SECONDS:.0f}s excluded) "
                "-> 50% Neutral"
            )
        else:
            reason = "Sector Breadth: Offline Baseline (50% Neutral)"
        return SectorBreadthSnapshot(
            timestamp=now,
            breadth_pct=0.50,
            advancing_count=0,
            declining_count=0,
            unchanged_count=0,
            total_sectors=0,
            top_sector=None,
            top_change_pct=None,
            lag_sector=None,
            lag_change_pct=None,
            is_strong_bull=False,
            is_strong_bear=False,
            provenance_reason=reason,
            sector_details={},
        )

    # 4. Coverage gate (live-tick path): a partial feed must never drive the
    #    bull/bear regime flags. Reject sub-threshold samples as NEUTRAL.
    if used_live_ticks and total < MIN_SECTOR_COVERAGE:
        return SectorBreadthSnapshot(
            timestamp=now,
            breadth_pct=0.50,
            advancing_count=0,
            declining_count=0,
            unchanged_count=0,
            total_sectors=0,  # sample rejected: no usable breadth sample
            top_sector=None,
            top_change_pct=None,
            lag_sector=None,
            lag_change_pct=None,
            is_strong_bull=False,
            is_strong_bear=False,
            provenance_reason=(
                f"Sector Breadth: Insufficient Coverage ({total}/{len(SectorIndex)} fresh sectors, "
                f"{MIN_SECTOR_COVERAGE} required) -> 50% Neutral"
            ),
            sector_details={},
        )

    # Calculate metrics
    breadth_pct = advancing / total if total > 0 else 0.50
    sorted_sectors.sort(key=lambda x: x[1], reverse=True)

    top_sec, top_chg = sorted_sectors[0]
    lag_sec, lag_chg = sorted_sectors[-1]

    is_strong_bull = breadth_pct >= 0.60
    is_strong_bear = breadth_pct <= 0.40

    if is_strong_bull:
        reason = f"Sector Breadth Strong ({breadth_pct*100:.0f}% Green: {advancing}/{total} sectors | Leader: {top_sec} {top_chg*100:+.2f}%)"
    elif is_strong_bear:
        reason = f"Sector Breadth Weak ({breadth_pct*100:.0f}% Green: {advancing}/{total} sectors | Laggard: {lag_sec} {lag_chg*100:+.2f}%)"
    else:
        reason = f"Sector Breadth Neutral ({breadth_pct*100:.0f}% Green: {advancing}/{total} sectors)"

    return SectorBreadthSnapshot(
        timestamp=now,
        breadth_pct=breadth_pct,
        advancing_count=advancing,
        declining_count=declining,
        unchanged_count=unchanged,
        total_sectors=total,
        top_sector=top_sec,
        top_change_pct=top_chg,
        lag_sector=lag_sec,
        lag_change_pct=lag_chg,
        is_strong_bull=is_strong_bull,
        is_strong_bear=is_strong_bear,
        provenance_reason=reason,
        sector_details=details,
    )


# ── 4. ADVANCE / DECLINE & SECTOR RELATIVE STRENGTH ENGINES ───────────────────

@dataclass(frozen=True)
class AdvanceDeclineSnapshot:
    """
    Immutable Broad Market Advance/Decline Participation Assessment.
    """
    advances: int
    declines: int
    unchanged: int
    ad_ratio: float
    ad_spread: int
    is_bullish: bool
    is_bearish: bool
    timestamp: datetime
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "advances": self.advances,
            "declines": self.declines,
            "unchanged": self.unchanged,
            "ad_ratio": round(self.ad_ratio, 4),
            "ad_spread": self.ad_spread,
            "is_bullish": self.is_bullish,
            "is_bearish": self.is_bearish,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
        }


def calculate_advance_decline_ratio(
    advances: int,
    declines: int,
    unchanged: int = 0
) -> AdvanceDeclineSnapshot:
    """
    Calculate market-wide Advance/Decline (A/D) participation ratio and net spread.
    """
    now = now_ist()

    # Zero-participation guard: with no advances and no declines there is no
    # breadth signal at all. ad_ratio degenerates to 0.0, which previously
    # tripped the bearish threshold and emitted "Bearish Liquidation" on
    # empty data. Return an explicitly NEUTRAL snapshot instead.
    if advances == 0 and declines == 0:
        return AdvanceDeclineSnapshot(
            advances=advances,
            declines=declines,
            unchanged=unchanged,
            ad_ratio=0.0,
            ad_spread=0,
            is_bullish=False,
            is_bearish=False,
            timestamp=now,
            message=f"A/D Ratio Neutral (No Participation Data: {advances} advances / {declines} declines)",
        )

    safe_dec = max(1, declines)
    ad_ratio = advances / safe_dec
    spread = advances - declines

    is_bull = ad_ratio >= 1.5 and spread > 0
    is_bear = ad_ratio <= 0.65 or spread < 0

    if is_bull:
        msg = f"A/D Ratio Bullish Accumulation ({ad_ratio:.2f}x | Net +{spread} advances)"
    elif is_bear:
        msg = f"A/D Ratio Bearish Liquidation ({ad_ratio:.2f}x | Net {spread} declines)"
    else:
        msg = f"A/D Ratio Neutral ({ad_ratio:.2f}x | Spread: {spread:+d})"

    return AdvanceDeclineSnapshot(
        advances=advances,
        declines=declines,
        unchanged=unchanged,
        ad_ratio=ad_ratio,
        ad_spread=spread,
        is_bullish=is_bull,
        is_bearish=is_bear,
        timestamp=now,
        message=msg,
    )


def get_sector_relative_strength(
    nifty_change_pct: float,
    custom_returns: Optional[Union[Mapping[SectorIndex, float], Mapping[str, float], Mapping[Any, float]]] = None
) -> Dict[str, float]:
    """
    Calculate Sector Alpha / Relative Strength against Benchmark NIFTY 50.
    Returns dictionary mapping sector name -> relative alpha (sector_pct - nifty_pct).
    """
    rel_strength: Dict[str, float] = {}

    if custom_returns is not None and len(custom_returns) > 0:
        for sec_key, chg in custom_returns.items():
            sec_name = sec_key.value if isinstance(sec_key, SectorIndex) else str(sec_key)
            rel_strength[sec_name] = round(chg - nifty_change_pct, 4)
    else:
        with _sector_lock:
            for sec, (ltp, prev_close, _) in _live_sector_prices.items():
                chg = (ltp - prev_close) / prev_close if prev_close > 0 else 0.0
                rel_strength[sec.value] = round(chg - nifty_change_pct, 4)

    return rel_strength


# ── 5. SELF-DIAGNOSTIC TEST HARNESS ──────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("===================================================================")
    print("MJONAI REAL-TIME SECTOR BREADTH & ROTATION ENGINE")
    print("===================================================================")

    # Simulation Injection
    mock_returns = {
        SectorIndex.NIFTY_BANK:        0.0145,
        SectorIndex.NIFTY_IT:          0.0085,
        SectorIndex.NIFTY_AUTO:        0.0110,
        SectorIndex.NIFTY_FMCG:       -0.0025,
        SectorIndex.NIFTY_METAL:       0.0180,
        SectorIndex.NIFTY_PHARMA:     -0.0040,
        SectorIndex.NIFTY_REALTY:      0.0210,
        SectorIndex.NIFTY_ENERGY:      0.0065,
        SectorIndex.NIFTY_FIN_SERVICE: 0.0130,
        SectorIndex.NIFTY_PSU_BANK:    0.0250,
        SectorIndex.NIFTY_PVT_BANK:    0.0120,
        SectorIndex.NIFTY_MEDIA:      -0.0080,
    }

    snapshot = calculate_sector_breadth(mock_returns)
    top_str = f"{snapshot.top_change_pct*100:+.2f}%" if snapshot.top_change_pct is not None else "N/A"
    lag_str = f"{snapshot.lag_change_pct*100:+.2f}%" if snapshot.lag_change_pct is not None else "N/A"
    print(f"Timestamp          : {snapshot.timestamp.isoformat()}")
    print(f"Sector Breadth Pct : {snapshot.breadth_pct * 100:.1f}%")
    print(f"Advancing / Total  : {snapshot.advancing_count} / {snapshot.total_sectors}")
    print(f"Leader Sector      : {snapshot.top_sector} ({top_str})")
    print(f"Laggard Sector     : {snapshot.lag_sector} ({lag_str})")
    print(f"Strong Bull Flag   : {snapshot.is_strong_bull}")
    print(f"Audit Trail        : {snapshot.provenance_reason}")
    print("===================================================================")
