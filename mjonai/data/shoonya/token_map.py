"""
Module: data/shoonya/token_map.py
Purpose: High-Performance Finvasia Shoonya Instrument & Security Token Resolver.
         Maps NSE cash equities and NFO derivative option contracts to Shoonya security tokens.
         Provides dynamic strike steps, lot sizes, and option chain ladders.
"""

from __future__ import annotations

import csv
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
import threading
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

_BUILD_ROOT = Path(__file__).resolve().parent.parent.parent

# In-memory fast token caches for Shoonya
SHOONYA_EQUITY_TOKEN_MAP: Dict[str, str] = {}    # "RELIANCE" -> "2885"
SHOONYA_REVERSE_EQUITY_MAP: Dict[str, str] = {}  # "2885" -> "RELIANCE"
SHOONYA_OPTION_TOKEN_MAP: Dict[str, str] = {}    # "NIFTY_08SEP2026_23800.0_CE" -> "54210"
SHOONYA_REVERSE_OPTION_MAP: Dict[str, str] = {}  # "54210" -> "NIFTY08SEP2623800CE"
SHOONYA_LOT_SIZE_MAP: Dict[str, int] = {}        # "NIFTY" -> 65, "BANKNIFTY" -> 30
SHOONYA_TICK_SIZE_MAP: Dict[str, float] = {}     # "RELIANCE" -> 0.05

_shoonya_map_lock = threading.RLock()
_is_initialized = False

# Standard Index Strike Intervals
INDEX_STRIKE_INTERVALS: Dict[str, float] = {
    "NIFTY": 50.0,
    "BANKNIFTY": 100.0,
    "FINNIFTY": 50.0,
    "MIDCPNIFTY": 25.0,
    "NIFTYNXT50": 100.0,
    "SENSEX": 100.0,
    "BANKEX": 100.0,
}

# Standard Index Spot Tokens on NSE / BSE
INDEX_SPOT_TOKENS: Dict[str, str] = {
    "NIFTY": "26000",
    "NIFTY 50": "26000",
    "NIFTY50": "26000",
    "BANKNIFTY": "26009",
    "NIFTY BANK": "26009",
    "FINNIFTY": "26037",
    "MIDCPNIFTY": "26074",
    "INDIAVIX": "26017",
    "INDIA VIX": "26017",
    "SENSEX": "1",
}


def _normalize_symbol(symbol: str) -> str:
    """Canonical uppercase symbol normalization."""
    if not symbol:
        return ""
    return symbol.strip().upper().replace("NSE:", "").replace("BSE:", "").replace("-EQ", "").replace(".NS", "").replace(".BO", "")


def initialize_shoonya_token_map(force_refresh: bool = False) -> None:
    """
    Initialize Shoonya token maps from local cache or shared exchange master.
    """
    global _is_initialized
    with _shoonya_map_lock:
        if _is_initialized and not force_refresh:
            return

        # Seed standard index spot tokens
        for name, tok in INDEX_SPOT_TOKENS.items():
            SHOONYA_EQUITY_TOKEN_MAP[name] = tok
            SHOONYA_REVERSE_EQUITY_MAP[tok] = name

        # Load shared equity tokens
        cache_path = _BUILD_ROOT / "data" / "angelone" / "instrument_master_cache.json"
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                token_map = payload.get("token_map", {})
                for tok, sym in token_map.items():
                    clean = _normalize_symbol(sym)
                    if clean and tok:
                        SHOONYA_EQUITY_TOKEN_MAP[clean] = tok
                        SHOONYA_REVERSE_EQUITY_MAP[tok] = clean
                        SHOONYA_LOT_SIZE_MAP[clean] = 1
                        SHOONYA_TICK_SIZE_MAP[clean] = 0.05
            except Exception as e:
                logger.warning(f"[shoonya_token_map] Failed loading base snapshot: {e}")

        _is_initialized = True
        logger.info(f"[shoonya_token_map] Initialized: {len(SHOONYA_EQUITY_TOKEN_MAP)} equities, {len(SHOONYA_OPTION_TOKEN_MAP)} options.")


def get_token_for_symbol(symbol: str, exchange: str = "NSE") -> Optional[str]:
    """Resolve Shoonya instrument token for an equity or index symbol."""
    if not _is_initialized:
        initialize_shoonya_token_map()

    clean = _normalize_symbol(symbol)
    if clean in INDEX_SPOT_TOKENS:
        return INDEX_SPOT_TOKENS[clean]

    # Dynamic regex parsing for option tickers (e.g. NIFTY08SEP2623800CE)
    opt_match = re.match(r"^([A-Z]+)(\d{2}[A-Z]{3}\d{2})(\d+(?:\.\d+)?)(CE|PE)$", clean)
    if opt_match:
        underlying = opt_match.group(1)
        raw_exp = opt_match.group(2)
        strike_val = float(opt_match.group(3))
        opt_type = opt_match.group(4)
        
        day_mon = raw_exp[:5]
        yr = raw_exp[5:]
        full_exp = f"{day_mon}20{yr}" if len(yr) == 2 else raw_exp
        
        tok = get_option_token(underlying, full_exp, strike_val, opt_type)
        if tok:
            return tok

    return SHOONYA_EQUITY_TOKEN_MAP.get(clean)


def get_symbol_for_token(token: str, exchange: str = "NSE") -> Optional[str]:
    """Reverse lookup: resolve canonical symbol name from Shoonya token."""
    if not _is_initialized:
        initialize_shoonya_token_map()
    clean_tok = token.strip()
    return SHOONYA_REVERSE_EQUITY_MAP.get(clean_tok) or SHOONYA_REVERSE_OPTION_MAP.get(clean_tok)


def get_option_token(underlying: str, expiry_str: str, strike_price: float, option_type: str) -> Optional[str]:
    """Resolve Shoonya option contract token."""
    if not _is_initialized:
        initialize_shoonya_token_map()

    clean_underlying = _normalize_symbol(underlying)
    clean_type = option_type.strip().upper()
    clean_expiry = expiry_str.strip().upper()
    key = f"{clean_underlying}_{clean_expiry}_{strike_price:.1f}_{clean_type}"
    return SHOONYA_OPTION_TOKEN_MAP.get(key)


def register_option_token(underlying: str, expiry_str: str, strike_price: float, option_type: str, token: str) -> None:
    """Register dynamically discovered Shoonya option token in memory."""
    clean_underlying = _normalize_symbol(underlying)
    clean_type = option_type.strip().upper()
    clean_expiry = expiry_str.strip().upper()
    key = f"{clean_underlying}_{clean_expiry}_{strike_price:.1f}_{clean_type}"
    with _shoonya_map_lock:
        SHOONYA_OPTION_TOKEN_MAP[key] = token
        SHOONYA_REVERSE_OPTION_MAP[token] = f"{clean_underlying}_{clean_expiry}_{strike_price:.1f}_{clean_type}"


def get_strike_interval(underlying: str) -> float:
    """Dynamically get strike step size for an underlying index or stock."""
    clean = _normalize_symbol(underlying)
    return INDEX_STRIKE_INTERVALS.get(clean, 50.0)


def get_atm_strike(underlying: str, spot_price: float, strike_interval: Optional[float] = None) -> float:
    """Calculate At-The-Money (ATM) strike price for an underlying asset."""
    clean = _normalize_symbol(underlying)
    step = strike_interval or get_strike_interval(clean)
    return round(spot_price / step) * step


def get_lot_size(symbol: str) -> int:
    """Get market lot size for an equity or index contract."""
    clean = _normalize_symbol(symbol)
    if clean == "NIFTY":
        return 65
    elif clean in ("BANKNIFTY", "FINNIFTY"):
        return 30
    elif clean == "MIDCPNIFTY":
        return 50
    return SHOONYA_LOT_SIZE_MAP.get(clean, 1)


def get_tick_size(symbol: str) -> float:
    """Get minimum tick size."""
    clean = _normalize_symbol(symbol)
    return SHOONYA_TICK_SIZE_MAP.get(clean, 0.05)
