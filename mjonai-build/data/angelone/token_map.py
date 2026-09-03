"""
Module: data/angelone/token_map.py
Purpose: Self-Healing High-Performance Instrument & Security Token Resolver.
         Supports Cash Equities (NSE), Index Spot & Futures (NIFTY/BANKNIFTY/FINNIFTY),
         Index & Stock Options, Dynamic Lot Sizes & Tick Sizes, and local JSON caching.

Architectural Principles:
  1. 100% JSON-Native: Zero static CSV files. Eliminates stale manual CSV maintenance forever.
  2. Spot Index Separation: Explicit INDEX_TOKEN_MAP for Nifty 50, Bank Nifty, FinNifty, India VIX.
  3. Dynamic Lot & Tick Sizes: Automatically extracts live lotsize and ticksize from official broker master.
  4. Resilient Local JSON Snapshot: Caches daily snapshot locally for instant < 50ms startup.
  5. Dynamic Options Resolution: Resolves live weekly/monthly option strike tokens (e.g. NIFTY 24500 CE).
  6. O(1) Memory Lookups: Instant case-insensitive symbol <-> token conversions.
  7. 100% Backward Compatibility: Preserves TOKEN_MAP, SYMBOL_MAP, WATCHLIST_TOKENS for all existing callers.
"""

from datetime import date, datetime
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import urllib.request

logger = logging.getLogger(__name__)

# AngelOne Official Open-API Instrument Master URL
ANGELONE_SCRIP_MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

# In-Memory Fast Lookup Stores
TOKEN_MAP: Dict[str, str] = {}         # Token -> Symbol Name (e.g. "2885" -> "RELIANCE")
SYMBOL_MAP: Dict[str, str] = {}        # Symbol Name -> Token (e.g. "RELIANCE" -> "2885")
OPTION_TOKEN_MAP: Dict[str, str] = {}  # Formatted Key -> Token (e.g. "NIFTY_2026-08-27_24500.0_CE" -> "54321")
LOT_SIZE_MAP: Dict[str, int] = {}      # Symbol -> Contract Lot Size (e.g. "NIFTY" -> 65, "BANKNIFTY" -> 30)
TICK_SIZE_MAP: Dict[str, float] = {}   # Symbol -> Tick Size (e.g. "RELIANCE" -> 0.05)
WATCHLIST_TOKENS: Dict[str, Any] = {"exchangeType": 1, "tokens": []}

# Official AngelOne Index Spot Tokens on NSE
INDEX_TOKEN_MAP: Dict[str, str] = {
    "NIFTY": "99926000",
    "NIFTY 50": "99926000",
    "NIFTY50": "99926000",
    "BANKNIFTY": "99926009",
    "NIFTY BANK": "99926009",
    "FINNIFTY": "99926037",
    "NIFTY FINANCIAL SERVICES": "99926037",
    "MIDCPNIFTY": "99926074",
    "NIFTY MIDCAP SELECT": "99926074",
    "INDIAVIX": "99926017",
    "INDIA VIX": "99926017",
    "SENSEX": "99919000",
}

# Standard Option Strike Steps per Underlying
INDEX_STRIKE_INTERVALS: Dict[str, float] = {
    "NIFTY": 50.0,
    "NIFTY 50": 50.0,
    "NIFTY50": 50.0,
    "BANKNIFTY": 100.0,
    "NIFTY BANK": 100.0,
    "FINNIFTY": 50.0,
    "NIFTY FINANCIAL SERVICES": 50.0,
    "MIDCPNIFTY": 25.0,
    "NIFTY MIDCAP SELECT": 25.0,
    "SENSEX": 100.0,
    "BANKEX": 100.0,
}

_TOKEN_MAP_LOADED: bool = False
_LAST_SYNC_DATE: Optional[date] = None

# Paths
_CURRENT_DIR = Path(__file__).resolve().parent
_CACHE_JSON_PATH = _CURRENT_DIR / "instrument_master_cache.json"


def _send_token_map_alert(message: str) -> None:
    """Send Telegram alert on token map degradation. Non-blocking & crash-safe."""
    try:
        from communication.telegram import send_message
        send_message(f"⚠️ <b>MJONAI TOKEN MAP</b>\n{message}")
    except Exception:
        pass


def _normalize_symbol(symbol: str) -> str:
    """Sanitize and normalize symbol for robust case-insensitive lookup."""
    return symbol.strip().upper().replace("-EQ", "").replace(".NS", "").replace(".BO", "")


# ── 1. JSON CACHE LOADER ───────────────────────────────────────────────────────

def _load_local_json_cache() -> bool:
    """Load token mappings from local JSON snapshot if present."""
    global TOKEN_MAP, SYMBOL_MAP, OPTION_TOKEN_MAP, LOT_SIZE_MAP, TICK_SIZE_MAP, WATCHLIST_TOKENS, _TOKEN_MAP_LOADED, _LAST_SYNC_DATE
    if not _CACHE_JSON_PATH.exists():
        return False

    try:
        with open(_CACHE_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            TOKEN_MAP.clear()
            TOKEN_MAP.update(data.get("token_map", {}))
            SYMBOL_MAP.clear()
            SYMBOL_MAP.update(data.get("symbol_map", {}))
            OPTION_TOKEN_MAP.clear()
            OPTION_TOKEN_MAP.update(data.get("option_token_map", {}))
            LOT_SIZE_MAP.clear()
            LOT_SIZE_MAP.update(data.get("lot_size_map", {}))
            TICK_SIZE_MAP.clear()
            TICK_SIZE_MAP.update(data.get("tick_size_map", {}))
            WATCHLIST_TOKENS.clear()
            WATCHLIST_TOKENS.update(data.get("watchlist_tokens", {"exchangeType": 1, "tokens": []}))
            
            sync_str = data.get("sync_date")
            if sync_str:
                try:
                    _LAST_SYNC_DATE = date.fromisoformat(sync_str)
                except Exception:
                    _LAST_SYNC_DATE = None

            _TOKEN_MAP_LOADED = bool(TOKEN_MAP and SYMBOL_MAP)
            if _TOKEN_MAP_LOADED:
                logger.info(f"[token_map] Loaded instrument master snapshot: {len(TOKEN_MAP)} equities, {len(OPTION_TOKEN_MAP)} options, {len(LOT_SIZE_MAP)} lot specs")
                return True
    except Exception as e:
        logger.warning(f"[token_map] Failed to read JSON cache {_CACHE_JSON_PATH}: {e}")

    return False


# ── 2. DYNAMIC LIVE INSTRUMENT MASTER SYNC ────────────────────────────────────

def sync_instrument_master(force: bool = False, timeout_seconds: int = 15) -> bool:
    """
    Synchronize official daily Instrument Master JSON from AngelOne.
    Extracts equities, options, lot sizes, and tick sizes.
    Caches parsed tokens locally as JSON to guarantee sub-50ms future boots.
    """
    global TOKEN_MAP, SYMBOL_MAP, OPTION_TOKEN_MAP, LOT_SIZE_MAP, TICK_SIZE_MAP, WATCHLIST_TOKENS, _TOKEN_MAP_LOADED, _LAST_SYNC_DATE

    today = date.today()
    if not force and _LAST_SYNC_DATE == today and _TOKEN_MAP_LOADED:
        return True

    # 1. Check if fresh local JSON cache exists from today
    if not force and _CACHE_JSON_PATH.exists():
        try:
            mtime = date.fromtimestamp(_CACHE_JSON_PATH.stat().st_mtime)
            if mtime == today and _load_local_json_cache():
                return True
        except Exception:
            pass

    # 2. Network Download from AngelOne Master Feed
    logger.info(f"[token_map] Fetching live Scrip Master from AngelOne ({ANGELONE_SCRIP_MASTER_URL})...")
    try:
        req = urllib.request.Request(
            ANGELONE_SCRIP_MASTER_URL,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MJONAI/3.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            if response.status != 200:
                raise ValueError(f"HTTP {response.status} from AngelOne scrip master")
            raw_data = json.loads(response.read().decode("utf-8"))

        new_token_map: Dict[str, str] = {}
        new_symbol_map: Dict[str, str] = {}
        new_option_map: Dict[str, str] = {}
        new_lot_size_map: Dict[str, int] = {}
        new_tick_size_map: Dict[str, float] = {}
        watchlist_tokens_list: List[str] = []

        # Parse AngelOne master objects
        for item in raw_data:
            # UPPER-normalized: the live master now sends "NSE"/"NFO"/"BFO"
            # (older dumps used lowercase "nse_cm"). Matching one case only
            # silently dropped every cash-equity row from the sync.
            exch_seg = (item.get("exch_seg") or "").strip().upper()
            token = (item.get("token") or "").strip()
            name = (item.get("name") or "").strip()
            symbol = (item.get("symbol") or "").strip()
            inst_type = (item.get("instrumenttype") or "").upper()
            lotsize_raw = item.get("lotsize", 1)
            ticksize_raw = item.get("tick_size", 0.05)

            if not token:
                continue

            try:
                lotsize = int(lotsize_raw)
            except Exception:
                lotsize = 1

            try:
                t_val = float(ticksize_raw)
                # De-paise band: the master sends tick_size in PAISE as integers
                # (verified against OpenAPIScripMaster.json, Aug 2026 — NSE -EQ
                # rows carry raw values of 1 / 5 / 10 / 50 / 100 / 500 meaning
                # ₹0.01 / ₹0.05 / ₹0.10 / ₹0.50 / ₹1 / ₹5). Rupee-form ticks are
                # always < 1.0, paise-form ticks are >= 1, so anything >= 1 is
                # paise. The old `> 10` band left ~2600 of 2665 equities
                # (raw 1/5/10) wrong by 100x.
                ticksize = t_val / 100.0 if t_val >= 1.0 else t_val
            except Exception:
                ticksize = 0.05

            # Cash Equities on NSE ("NSE" current format, "NSE_CM" legacy dumps)
            if exch_seg in ("NSE", "NSE_CM") and symbol.endswith("-EQ"):
                clean_name = _normalize_symbol(name)
                new_token_map[token] = clean_name
                new_symbol_map[clean_name] = token
                new_lot_size_map[clean_name] = lotsize
                new_tick_size_map[clean_name] = ticksize
                watchlist_tokens_list.append(token)

            # Index & Stock Options on NFO/BFO
            elif exch_seg in ("NFO", "NFO_FO", "BFO") and inst_type in ("OPTIDX", "OPTSTK"):
                expiry_str = (item.get("expiry") or "").strip()
                strike_str = (item.get("strike") or "-1").strip()
                try:
                    s_val = float(strike_str)
                    # All strikes in AngelOne NFO/BFO options master are sent in PAISE (e.g. 2450000 for ₹24,500, 35000 for ₹350, 1200 for ₹12)
                    strike_val = s_val / 100.0 if s_val > 0 else 0.0
                except Exception:
                    strike_val = 0.0
                
                opt_type = "CE" if symbol.endswith("CE") else "PE" if symbol.endswith("PE") else ""
                clean_underlying = _normalize_symbol(name)
                if opt_type and clean_underlying and expiry_str:
                    canonical_key = f"{clean_underlying}_{expiry_str.upper()}_{strike_val:.1f}_{opt_type}"
                    new_option_map[canonical_key] = token
                    new_lot_size_map[clean_underlying] = lotsize
                    new_tick_size_map[clean_underlying] = ticksize

        if new_token_map:
            TOKEN_MAP.clear()
            TOKEN_MAP.update(new_token_map)
            SYMBOL_MAP.clear()
            SYMBOL_MAP.update(new_symbol_map)
            OPTION_TOKEN_MAP.clear()
            OPTION_TOKEN_MAP.update(new_option_map)
            LOT_SIZE_MAP.clear()
            LOT_SIZE_MAP.update(new_lot_size_map)
            TICK_SIZE_MAP.clear()
            TICK_SIZE_MAP.update(new_tick_size_map)
            WATCHLIST_TOKENS.clear()
            WATCHLIST_TOKENS.update({
                "exchangeType": 1,
                "tokens": watchlist_tokens_list
            })
            _TOKEN_MAP_LOADED = True
            _LAST_SYNC_DATE = today

            # Save clean local JSON cache
            try:
                cache_payload = {
                    "sync_date": today.isoformat(),
                    "token_map": TOKEN_MAP,
                    "symbol_map": SYMBOL_MAP,
                    "option_token_map": OPTION_TOKEN_MAP,
                    "lot_size_map": LOT_SIZE_MAP,
                    "tick_size_map": TICK_SIZE_MAP,
                    "watchlist_tokens": WATCHLIST_TOKENS
                }
                with open(_CACHE_JSON_PATH, "w", encoding="utf-8") as f:
                    json.dump(cache_payload, f)
                logger.info(f"[token_map] Master synced ({len(TOKEN_MAP)} equities, {len(OPTION_TOKEN_MAP)} options, {len(LOT_SIZE_MAP)} lot specs)")
            except Exception as e:
                logger.warning(f"[token_map] Could not write cache file: {e}")

            return True

    except Exception as e:
        logger.warning(f"[token_map] Live scrip master download failed ({e}), attempting local JSON cache...")

    # 3. Fallback to existing local JSON cache
    if _load_local_json_cache():
        return True

    logger.critical("[token_map] Failed to load instrument master from network and no valid local JSON cache exists")
    _send_token_map_alert("Failed to load instrument master from network and no local JSON cache exists.")
    return False


# ── 3. PUBLIC RESOLUTION & CONVENIENCE APIS ───────────────────────────────────

def get_token_for_symbol(symbol: str, exchange: str = "NSE") -> Optional[str]:
    """
    Get exchange security token for equity or option symbol.
    Case-insensitive with regex parsing for NSE option contract format.
    """
    if not symbol:
        return None
    clean = _normalize_symbol(symbol)
    
    # 1. Check index tokens
    if clean in INDEX_TOKEN_MAP:
        return INDEX_TOKEN_MAP[clean]
        
    # 2. Check cached equities
    if clean in SYMBOL_MAP:
        return SYMBOL_MAP[clean]

    # 3. Check direct option canonical keys
    if clean in OPTION_TOKEN_MAP:
        return OPTION_TOKEN_MAP[clean]

    # 4. Dynamic Option regex parser: e.g. NIFTY08SEP2623800CE or BANKNIFTY24500PE or NIFTY23800CE
    if clean.endswith("CE") or clean.endswith("PE"):
        import re
        m = re.match(r'^([A-Z]+?)(\d{2}[A-Z]{3}\d{2})?(\d{3,6})(CE|PE)$', clean)
        if m:
            underlying = m.group(1)
            expiry_raw = m.group(2)
            strike = float(m.group(3))
            opt_type = m.group(4)
            
            if expiry_raw:
                day = expiry_raw[:2]
                month = expiry_raw[2:5]
                yr = expiry_raw[5:7]
                full_yr = f"20{yr}" if len(yr) == 2 else yr
                expiry_str = f"{day}{month}{full_yr}"
            else:
                expiry_str = get_nearest_expiry(underlying) or ""

            canonical_key = f"{underlying}_{expiry_str.upper()}_{strike:.1f}_{opt_type}"
            tok = OPTION_TOKEN_MAP.get(canonical_key)
            if tok:
                SYMBOL_MAP[clean] = tok
                TOKEN_MAP[tok] = clean
                return tok

    return None


def get_symbol_for_token(token: str, exchange: str = "NSE") -> Optional[str]:
    """Get equity symbol name for a given token string."""
    clean_token = token.strip()
    # Check index tokens
    for idx_name, idx_tok in INDEX_TOKEN_MAP.items():
        if idx_tok == clean_token:
            return idx_name
    return TOKEN_MAP.get(clean_token)


def get_index_token(index_name: str) -> Optional[str]:
    """Get official AngelOne spot token for an index (e.g. 'NIFTY' -> '99926000', 'BANKNIFTY' -> '99926009')."""
    clean = _normalize_symbol(index_name)
    return INDEX_TOKEN_MAP.get(clean)


def get_option_token(
    underlying: str,
    expiry_str: str,
    strike_price: float,
    option_type: str
) -> Optional[str]:
    """
    Resolve live exchange token for Options contract.
    Example: get_option_token('NIFTY', '27AUG2026', 24500.0, 'CE') -> '54321'
    """
    clean_underlying = _normalize_symbol(underlying)
    clean_type = option_type.strip().upper()
    clean_expiry = expiry_str.strip().upper()
    key = f"{clean_underlying}_{clean_expiry}_{strike_price:.1f}_{clean_type}"
    return OPTION_TOKEN_MAP.get(key)


def get_strike_interval(underlying: str) -> float:
    """
    Dynamically calculate the listed strike interval for an underlying index or stock.
    Calculates the most common step between adjacent unique listed strikes in OPTION_TOKEN_MAP.
    Falls back to INDEX_STRIKE_INTERVALS or 50.0.
    """
    clean = _normalize_symbol(underlying)
    if clean in INDEX_STRIKE_INTERVALS:
        return INDEX_STRIKE_INTERVALS[clean]

    prefix = f"{clean}_"
    strikes = set()
    for k in OPTION_TOKEN_MAP.keys():
        if k.startswith(prefix):
            parts = k.split("_")
            if len(parts) >= 3:
                try:
                    strikes.add(float(parts[2]))
                except ValueError:
                    pass
    if len(strikes) >= 2:
        sorted_strikes = sorted(strikes)
        diffs = [round(sorted_strikes[i+1] - sorted_strikes[i], 2) for i in range(len(sorted_strikes)-1)]
        positive_diffs = [d for d in diffs if d > 0]
        if positive_diffs:
            from collections import Counter
            return float(Counter(positive_diffs).most_common(1)[0][0])

    return 50.0


def get_atm_strike(
    underlying: str,
    spot_price: float,
    strike_interval: Optional[float] = None
) -> float:
    """
    Calculate At-The-Money (ATM) strike price rounded to standard exchange step.
    Example: get_atm_strike('NIFTY', 24532.5) -> 24550.0
    """
    clean = _normalize_symbol(underlying)
    step = strike_interval or get_strike_interval(clean)
    return round(spot_price / step) * step


def get_option_chain_tokens(
    underlying: str,
    expiry_str: str,
    spot_price: float,
    num_strikes: int = 5,
    strike_interval: Optional[float] = None
) -> Dict[str, Any]:
    """
    Resolve option contract tokens for ATM and surrounding ITM/OTM strike ladder.
    Returns dictionary with all strike specs and a flat list of tokens ready for WebSocket streaming.
    """
    clean = _normalize_symbol(underlying)
    atm = get_atm_strike(clean, spot_price, strike_interval)
    step = strike_interval or get_strike_interval(clean)

    strikes_ladder: List[Dict[str, Any]] = []
    tokens_to_stream: List[str] = []

    for offset in range(-num_strikes, num_strikes + 1):
        strike = atm + (offset * step)
        ce_tok = get_option_token(clean, expiry_str, strike, "CE")
        pe_tok = get_option_token(clean, expiry_str, strike, "PE")
        
        strikes_ladder.append({
            "strike": strike,
            "offset": offset,
            "is_atm": offset == 0,
            "ce_token": ce_tok,
            "pe_token": pe_tok,
        })
        if ce_tok:
            tokens_to_stream.append(ce_tok)
        if pe_tok:
            tokens_to_stream.append(pe_tok)

    return {
        "underlying": clean,
        "expiry": expiry_str.strip().upper(),
        "spot_price": spot_price,
        "atm_strike": atm,
        "strike_interval": step,
        "num_strikes": num_strikes,
        "strikes": strikes_ladder,
        "tokens_to_stream": tokens_to_stream,
    }


def get_lot_size(symbol: str) -> Optional[int]:
    """Get live market lot size for an equity or index contract."""
    clean = _normalize_symbol(symbol)
    return LOT_SIZE_MAP.get(clean)


def get_active_expiries(underlying: str) -> List[str]:
    """Get sorted list of future active option expiries for an underlying index/stock."""
    clean = _normalize_symbol(underlying)
    prefix = f"{clean}_"
    expiries = set()
    for k in OPTION_TOKEN_MAP.keys():
        if k.startswith(prefix):
            parts = k.split("_")
            if len(parts) >= 2:
                expiries.add(parts[1])

    from core.time_utils import today_ist
    today = today_ist()
    parsed = []
    for exp in expiries:
        try:
            dt = datetime.strptime(exp, "%d%b%Y").date()
            if dt >= today:
                parsed.append((dt, exp))
        except Exception:
            pass
    parsed.sort()
    return [exp for _, exp in parsed]


def get_nearest_expiry(underlying: str) -> Optional[str]:
    """Get the nearest future active weekly or monthly option expiry for an underlying."""
    active = get_active_expiries(underlying)
    return active[0] if active else None


def get_tick_size(symbol: str) -> Optional[float]:
    """Get live minimum tick size for an instrument."""
    clean = _normalize_symbol(symbol)
    return TICK_SIZE_MAP.get(clean, 0.05)


def is_token_map_loaded() -> bool:
    """Health check helper for startup verification."""
    return _TOKEN_MAP_LOADED and len(SYMBOL_MAP) > 0


# ── 4. INITIALIZE ON IMPORT ───────────────────────────────────────────────────

# Load tokens immediately on module import (uses cache or network sync)
try:
    if not _load_local_json_cache():
        sync_instrument_master(force=False)
except Exception as _e:
    logger.critical(f"[token_map] Fatal error initializing token map: {_e}")
    _send_token_map_alert(f"Token map initialization failed: {_e}")