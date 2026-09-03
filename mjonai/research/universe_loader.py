"""
Module: engine/research/universe_loader.py
Purpose: Dynamic Stock & Sector Universe Loader for Indian Equities.
         Supports Nifty 50, Bank Nifty, Nifty IT, Nifty Auto, Nifty Pharma, and Nifty 500.
"""

import os
import csv
import logging
from enum import Enum
from typing import List

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


def load_universe_symbols(tier: UniverseTier = UniverseTier.NIFTY_50, max_count: int = 50) -> List[str]:
    """
    Dynamically load clean stock symbols for backtesting.

    Args:
        tier: UniverseTier (NIFTY_50, BANK_NIFTY, NIFTY_IT, NIFTY_500, etc.)
        max_count: Maximum number of stocks to return

    Returns:
        List of clean uppercase symbols
    """
    tier_key = tier.value if hasattr(tier, "value") else str(tier)

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
