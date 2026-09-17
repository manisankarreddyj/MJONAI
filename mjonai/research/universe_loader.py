"""
Module: engine/research/universe_loader.py
Purpose: Dynamic Stock & Sector Universe Loader for Indian Equities.
         Supports Nifty 50, Bank Nifty, Nifty IT, Nifty Auto, Nifty Pharma, and Nifty 500.
"""

import os
import csv
import logging
from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from mjonai.research.pit_universe import (
    PitUniverseLedger,
    NIFTY50_INDEX_NAME,
)

logger = logging.getLogger(__name__)

# Path to master Nifty 500 token file (lives at the repo root — ADR-0008 layout).
NIFTY500_CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "angelone",
    "nifty500_tokens.csv",
)

# Standard Sector & Index Constituent Universes
SECTOR_UNIVERSES = {
    "NIFTY_50": [
        "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "BHARTIARTL", "ITC", "SBIN",
        "LICI", "HINDUNILVR", "LT", "BAJFINANCE", "HCLTECH", "MARUTI", "SUNPHARMA", "ADANIENT",
        "TATAMOTORS", "ONGC", "NTPC", "KOTAKBANK", "AXISBANK", "TITAN", "POWERGRID", "ADANIPORTS",
        "COALINDIA", "TATASTEEL", "ULTRACEMCO", "BAJAJFINSV", "M&M", "SIEMENS", "IOC", "SBILIFE",
        "GRASIM", "WIPRO", "TECHM", "NESTLEIND", "BPCL", "HEROMOTOCO", "EICHERMOT", "DIVISLAB",
        "DRREDDY", "CIPLA", "APOLLOHOSP", "TATACONSUM", "HINDALCO", "JSWSTEEL", "SHRIRAMFIN",
        "BRITANNIA", "BEL", "TRENT"
    ],
    "BANK_NIFTY": [
        "HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK",
        "BANKBARODA", "PNB", "FEDERALBNK", "AUBANK", "IDFCFIRSTB", "BANDHANBNK"
    ],
    "NIFTY_IT": [
        "TCS", "INFY", "HCLTECH", "WIPRO", "TECHM", "LTIM", "PERSISTENT",
        "COFORGE", "MPHASIS", "KPITTECH"
    ],
    "NIFTY_AUTO": [
        "TATAMOTORS", "M&M", "MARUTI", "BAJAJ-AUTO", "EICHERMOT", "HEROMOTOCO",
        "TVSMOTOR", "BHARATFORG", "ASHOKLEY", "APOLLOTYRE"
    ],
    "NIFTY_PHARMA": [
        "SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "LUPIN", "AUROPHARMA",
        "TORNTPHARM", "ALKEM", "ZYDUSLIFE", "BIOCON"
    ]
}


class UniverseTier(Enum):
    NIFTY_50 = "NIFTY_50"
    BANK_NIFTY = "BANK_NIFTY"
    NIFTY_IT = "NIFTY_IT"
    NIFTY_AUTO = "NIFTY_AUTO"
    NIFTY_PHARMA = "NIFTY_PHARMA"
    NIFTY_500 = "NIFTY_500"
    CUSTOM = "CUSTOM"


def load_universe_symbols(
    tier: UniverseTier = UniverseTier.NIFTY_50,
    max_count: int = 50,
    asof: Optional[date] = None,
) -> List[str]:
    """
    Dynamically load clean stock symbols for backtesting.

    Args:
        tier: UniverseTier (NIFTY_50, BANK_NIFTY, NIFTY_IT, NIFTY_500, etc.)
        max_count: Maximum number of stocks to return
        asof: Point-in-time membership date (Decision 6 Phase 3). When given,
            symbols are resolved through the PIT ledger so a backtest trades
            the index as it actually was — not today's list retrofitted onto
            history. Only tiers covered by the ledger (NIFTY_50) are supported;
            NIFTY_500 and sector tiers raise (fail-closed) rather than silently
            falling back to a snapshot list.

    Returns:
        List of clean uppercase symbols
    """
    tier_key = tier.value if hasattr(tier, "value") else str(tier)

    if asof is not None:
        return _load_pit_symbols(tier_key, asof, max_count)

    if tier_key in SECTOR_UNIVERSES:
        return SECTOR_UNIVERSES[tier_key][:max_count]

    if tier_key == "NIFTY_500":
        # H1 fix: this used to SILENTLY fall back to the hardcoded Nifty 50
        # names while callers believed they were running NIFTY_500 — a
        # universe-truth violation. Fail loudly instead.
        if not os.path.exists(NIFTY500_CSV_PATH):
            raise FileNotFoundError(
                f"[universe_loader] NIFTY_500 requested but token file is missing: "
                f"{NIFTY500_CSV_PATH}. Generate it from the index constituents; "
                "refusing to silently substitute a different universe."
            )
        symbols: List[str] = []
        try:
            with open(NIFTY500_CSV_PATH, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get("name", "").strip().upper()
                    if name and name not in symbols:
                        symbols.append(name)
                        if len(symbols) >= max_count:
                            break
        except Exception as e:
            raise RuntimeError(
                f"[universe_loader] Failed reading NIFTY_500 file {NIFTY500_CSV_PATH}: {e}"
            ) from e
        if not symbols:
            raise ValueError(
                f"[universe_loader] NIFTY_500 token file at {NIFTY500_CSV_PATH} yielded no symbols."
            )
        return symbols[:max_count]

    raise ValueError(
        f"[universe_loader] Unknown universe tier '{tier_key}'. Known tiers: "
        f"{sorted(SECTOR_UNIVERSES.keys()) + ['NIFTY_500']}."
    )


def _load_pit_symbols(
    tier_key: str,
    asof: date,
    max_count: int,
) -> List[str]:
    """PIT membership as-of a date via the curated ledger. Fail-closed: an
    unknown tier, an as-of before ledger coverage, or a missing ledger file
    raises instead of substituting today's constituents."""
    ledger = PitUniverseLedger()

    if tier_key != "NIFTY_50":
        raise ValueError(
            f"[universe_loader] PIT (as-of) resolution requested for '{tier_key}' but "
            "the curated ledger only covers NIFTY_50 (Decision 6 Phase 3 hard-scope). "
            "Use asof=None for snapshot universes."
        )

    if isinstance(asof, datetime):
        asof = asof.date()

    # coverage check happens inside ledger.members() (raises when asof
    # predates 2014-01-01 — no silent current-list substitution).
    return ledger.members(
        asof=asof,
        index_name=NIFTY50_INDEX_NAME,
    )[:max_count]
