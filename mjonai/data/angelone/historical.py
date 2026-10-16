"""
Module: data/angelone/historical.py
Purpose: High-Performance Historical OHLCV & Open Interest (OI) Candle Engine.
         Fetches historical candle data from AngelOne SmartAPI with yfinance fallback.
         Supports multi-timeframe intervals (1m, 3m, 5m, 10m, 15m, 30m, 1h, 1d),
         automated 3 req/sec rate limiting (HTTP 429 protection), dynamic token resolution,
         and mathematical candle invariant sanitization.

Architectural Principles:
  1. Strict 3 Req/Sec Rate Limiter: Thread-safe token bucket prevents API key bans.
  2. 6 vs 7 Column Dynamic Parsing: Native support for Open Interest (OI) on F&O derivatives.
  3. Automatic Token Resolution: Seamlessly resolves tokens via token_map if not provided.
  4. Mathematical Candle Sanitization: Validates high/low invariants and drops corrupt ticks.
  5. Multi-Asset & Timeframe Coverage: Supports NSE, NFO, BSE, BFO (Sensex), MCX, and CDS.
"""

from datetime import datetime, timedelta
from enum import Enum
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from mjonai.core.time_utils import Exchange
from mjonai.data.angelone.token_map import get_token_for_symbol

logger = logging.getLogger(__name__)


# ── 1. ENUMS & DATA PROVIDER PROVENANCE ───────────────────────────────────────

class CandleInterval(str, Enum):
    """AngelOne SmartAPI candle intervals."""
    ONE_MINUTE     = "ONE_MINUTE"
    THREE_MINUTE   = "THREE_MINUTE"    # Scalping & ORB breakouts
    FIVE_MINUTE    = "FIVE_MINUTE"     # Primary intraday scanning
    TEN_MINUTE     = "TEN_MINUTE"
    FIFTEEN_MINUTE = "FIFTEEN_MINUTE"  # Trend & confirmation
    THIRTY_MINUTE  = "THIRTY_MINUTE"
    ONE_HOUR       = "ONE_HOUR"
    ONE_DAY        = "ONE_DAY"         # Daily baseline & EMAs


class DataProvider(str, Enum):
    """Provenance tracking for historical feeds."""
    SMART_API = "SMART_API"
    YFINANCE  = "YFINANCE"
    OFFLINE   = "OFFLINE"


# Interval mapping for yfinance fallback (only bars Yahoo natively serves)
YF_INTERVAL_MAP: Dict[CandleInterval, str] = {
    CandleInterval.ONE_MINUTE:     "1m",
    CandleInterval.FIVE_MINUTE:    "5m",
    CandleInterval.FIFTEEN_MINUTE: "15m",
    CandleInterval.THIRTY_MINUTE:  "30m",
    CandleInterval.ONE_HOUR:       "1h",
    CandleInterval.ONE_DAY:        "1d",
}

# Yahoo has no native 3-minute or 10-minute bars. The old mapping silently served
# 2m/15m bars under a 3m/10m label — wrong bar sizes. Instead, fetch the nearest
# finer native interval and aggregate up to the requested bar size.
YF_RESAMPLE_MAP: Dict[CandleInterval, Tuple[str, str]] = {
    CandleInterval.THREE_MINUTE: ("1m", "3min"),   # (source_interval, target_bar)
    CandleInterval.TEN_MINUTE:   ("5m", "10min"),
}


def _resample_to_interval(df: pd.DataFrame, bar: str) -> pd.DataFrame:
    """
    Aggregate finer-grained candles into larger OHLCV bars:
    Open=first, High=max, Low=min, Close=last, Volume=sum (OpenInterest=last when present).
    Expects a DatetimeIndex (as returned by yf.download after column flattening).
    """
    if df.empty or not isinstance(df.index, pd.DatetimeIndex):
        return df

    agg_map: Dict[str, str] = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    if "Volume" in df.columns:
        agg_map["Volume"] = "sum"
    if "OpenInterest" in df.columns:
        agg_map["OpenInterest"] = "last"

    resampled = df.resample(bar).agg(agg_map)
    # Empty resample bins (market-closed gaps) have NaN OHLC — drop them
    ohlc_cols = [c for c in ("Open", "High", "Low", "Close") if c in resampled.columns]
    return resampled.dropna(subset=ohlc_cols) if ohlc_cols else resampled


# ── 2. RATE LIMITER (MAX 3 REQ/SEC FOR SMARTAPI) ──────────────────────────────

class SmartAPIRateLimiter:
    """Thread-safe rate limiter to strictly respect AngelOne's 3 requests/sec rule."""
    def __init__(self, min_interval_seconds: float = 0.35):
        self.min_interval = min_interval_seconds
        self.last_request_time = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Enforce spacing between consecutive API calls to prevent HTTP 429."""
        with self._lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_request_time = time.time()


_GLOBAL_RATE_LIMITER = SmartAPIRateLimiter(min_interval_seconds=0.35)

# ── 3. IN-MEMORY HIGH-SPEED CANDLE CACHE (TTL DEDUPLICATOR) ───────────────────

_CANDLE_CACHE: Dict[str, Tuple[datetime, pd.DataFrame]] = {}
_candle_cache_lock = threading.Lock()
_DEFAULT_CANDLE_TTL_SECONDS: int = 60  # 60s TTL for real-time strategy deduplication
# Hard memory cap: 500 cached series (key -> frame) is plenty for a full scan universe;
# beyond that the oldest-inserted entries are dropped.
_CANDLE_CACHE_MAX_ENTRIES: int = 500


def _store_in_candle_cache(cache_key: str, df: pd.DataFrame, ttl_seconds: int) -> None:
    """
    Insert a candle frame into the RAM cache, then evict:
      1. entries whose stored timestamp is older than the TTL (stale series), and
      2. the oldest-by-timestamp entries whenever the cache exceeds 500 entries.
    Keeps unbounded symbol x interval x days_back fan-out from leaking RAM.
    """
    now = datetime.now()
    with _candle_cache_lock:
        _CANDLE_CACHE[cache_key] = (now, df.copy())

        expired = [
            key for key, (stored_at, _) in _CANDLE_CACHE.items()
            if (now - stored_at).total_seconds() >= ttl_seconds
        ]
        for key in expired:
            del _CANDLE_CACHE[key]

        overflow = len(_CANDLE_CACHE) - _CANDLE_CACHE_MAX_ENTRIES
        if overflow > 0:
            oldest_keys = sorted(_CANDLE_CACHE.items(), key=lambda kv: kv[1][0])[:overflow]
            for key, _ in oldest_keys:
                del _CANDLE_CACHE[key]


def clear_candle_cache() -> None:
    """Flush all in-memory candle caches (e.g. at market open or test reset)."""
    with _candle_cache_lock:
        _CANDLE_CACHE.clear()


# ── 3b. SINGLE-FLIGHT GUARD (cache-stampede deduplicator) ────────────────────
# The web tier polls build_open_trades() from the 500ms WS loop AND the 10s
# dashboard loop on overlapping threads: without this, every tick re-fires the
# same 29 symbols × 2 intervals at yfinance concurrently and the 60s TTL cache
# never gets a chance to serve (4k+ duplicate fetches/day in web.log
# 2026-10-16). Per-key locks coalesce concurrent same-key fetches: the first
# thread fetches, waiters re-read the freshly stored frame. Lock order is
# always key-lock (outer) -> cache-lock (inner, short); no other path takes
# them in reverse, so no deadlock. Keys are stable (symbol×token×interval×
# days×exchange), so the lock table stays small with no eviction.
_KEY_LOCKS_GUARD = threading.Lock()
_KEY_LOCKS: Dict[str, threading.Lock] = {}
_SINGLEFLIGHT_WAIT_SECONDS = 60


def _key_lock(cache_key: str) -> threading.Lock:
    with _KEY_LOCKS_GUARD:
        lock = _KEY_LOCKS.get(cache_key)
        if lock is None:
            lock = threading.Lock()
            _KEY_LOCKS[cache_key] = lock
        return lock


def get_candle_cache_size() -> int:
    """Return count of active cached candle series in RAM."""
    with _candle_cache_lock:
        return len(_CANDLE_CACHE)


# ── 4. CANDLE SANITIZER & INVARIANT ENFORCER ──────────────────────────────────

def _sanitize_candles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sanitize OHLCV candles ensuring mathematical validity:
    - High >= max(Open, Close)
    - Low <= min(Open, Close)
    - Volume >= 0
    - Drop NaN / Inf values
    """
    if df.empty:
        return df

    # Drop NaNs or Infs
    df = df.replace([float("inf"), float("-inf")], float("nan")).dropna(subset=["Open", "High", "Low", "Close"])
    if df.empty:
        return df

    # Enforce candle invariants
    df["High"] = df[["High", "Open", "Close"]].max(axis=1)
    df["Low"] = df[["Low", "Open", "Close"]].min(axis=1)
    if "Volume" in df.columns:
        df["Volume"] = df["Volume"].clip(lower=0)
    if "OpenInterest" in df.columns:
        df["OpenInterest"] = df["OpenInterest"].clip(lower=0)

    return df


# ── 5. MASTER HISTORICAL CANDLE FETCHER ───────────────────────────────────────

def fetch_historical_candles(
    symbol: str,
    token: Optional[str] = None,
    interval: CandleInterval = CandleInterval.FIVE_MINUTE,
    days_back: int = 5,
    exchange: Union[Exchange, str] = Exchange.NSE,
    smart_api_client: Optional[Any] = None,
    use_cache: bool = True,
    cache_ttl_seconds: int = 60,
) -> Optional[pd.DataFrame]:
    """
    Fetch historical candle data for an equity, index, or option contract.
    Priority: RAM TTL Cache -> AngelOne SmartAPI -> yfinance fallback -> None.

    Args:
        symbol: Clean symbol (e.g. "RELIANCE", "NIFTY") or with suffix ("RELIANCE.NS")
        token: AngelOne instrument token (optional; auto-resolved if None)
        interval: CandleInterval enum
        days_back: Number of calendar days of history to fetch
        exchange: Exchange enum or string ("NSE", "NFO", "BSE", "BFO", "MCX", "CDS")
        smart_api_client: Initialized SmartConnect instance (optional)
        use_cache: Enable sub-microsecond in-memory TTL caching (default True)
        cache_ttl_seconds: Cache validity window in seconds (default 60s)

    Returns:
        Standardized pandas DataFrame with columns: [Open, High, Low, Close, Volume]
        (and optionally [OpenInterest] for F&O) and DatetimeIndex, or None if fetch fails.
    """
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
    exch_str = exchange.value if isinstance(exchange, Exchange) else exchange.upper()

    # Auto-resolve token if not explicitly provided
    if token is None:
        token = get_token_for_symbol(clean_sym, exchange=exch_str)

    # Check In-Memory RAM Cache first
    cache_key = f"{clean_sym}_{token or 'NO_TOK'}_{interval.value}_{days_back}_{exch_str}"
    if use_cache:
        with _candle_cache_lock:
            entry = _CANDLE_CACHE.get(cache_key)
            if entry is not None:
                cached_time, cached_df = entry
                if (datetime.now() - cached_time).total_seconds() < cache_ttl_seconds:
                    return cached_df.copy()
        # Single-flight: coalesce concurrent same-key fetches onto the first
        # thread; waiters re-read the freshly stored frame below.
        key_lock = _key_lock(cache_key)
        acquired = key_lock.acquire(timeout=_SINGLEFLIGHT_WAIT_SECONDS)
        try:
            with _candle_cache_lock:
                entry = _CANDLE_CACHE.get(cache_key)
                if entry is not None:
                    cached_time, cached_df = entry
                    if (datetime.now() - cached_time).total_seconds() < cache_ttl_seconds:
                        return cached_df.copy()
            return _fetch_candles_uncached(
                symbol=symbol, token=token, interval=interval,
                days_back=days_back, exch_str=exch_str, clean_sym=clean_sym,
                smart_api_client=smart_api_client, use_cache=use_cache,
                cache_ttl_seconds=cache_ttl_seconds, cache_key=cache_key,
            )
        finally:
            if acquired:
                key_lock.release()
    return _fetch_candles_uncached(
        symbol=symbol, token=token, interval=interval,
        days_back=days_back, exch_str=exch_str, clean_sym=clean_sym,
        smart_api_client=smart_api_client, use_cache=use_cache,
        cache_ttl_seconds=cache_ttl_seconds, cache_key=cache_key,
    )


def _fetch_candles_uncached(
    *,
    symbol: str,
    token: Optional[str],
    interval: CandleInterval,
    days_back: int,
    exch_str: str,
    clean_sym: str,
    smart_api_client: Optional[Any],
    use_cache: bool,
    cache_ttl_seconds: int,
    cache_key: str,
) -> Optional[pd.DataFrame]:
    """Network half of fetch_historical_candles (see single-flight note above)."""
    # Auto-discover active AngelOne SmartConnect session if client was omitted
    # (ADR-0008 documented exception: guarded lazy bridge to the runtime app —
    # the kernel must work when the app is absent, so this stays try/except.)
    if smart_api_client is None:
        try:
            import apps.runtime.main as main
            if hasattr(main, "angel_obj") and main.angel_obj is not None:
                smart_api_client = main.angel_obj
        except Exception:
            pass

    # 1. Try AngelOne SmartAPI if client & token available
    if smart_api_client is not None and token is not None:
        try:
            # Enforce 3 req/sec rate limit to prevent HTTP 429
            _GLOBAL_RATE_LIMITER.acquire()

            to_date = datetime.now()
            from_date = to_date - timedelta(days=days_back)

            # Format dates depending on timeframe
            if interval == CandleInterval.ONE_DAY:
                from_date_str = from_date.strftime("%Y-%m-%d 00:00")
                to_date_str = to_date.strftime("%Y-%m-%d 23:59")
            else:
                from_date_str = from_date.strftime("%Y-%m-%d 09:15")
                to_date_str = to_date.strftime("%Y-%m-%d 15:30")

            params = {
                "exchange": exch_str,
                "symboltoken": token,
                "interval": interval.value,
                "fromdate": from_date_str,
                "todate": to_date_str,
            }

            response = smart_api_client.getCandleData(params)
            if response and response.get("status") and response.get("data"):
                raw_data = response["data"]
                if not raw_data:
                    logger.warning(f"[historical] Empty data returned for {clean_sym} (Token {token})")
                    return None

                # Detect 6 vs 7 elements (Open Interest on F&O)
                sample_row = raw_data[0]
                num_cols = len(sample_row)

                if num_cols >= 7:
                    cols = ["Timestamp", "Open", "High", "Low", "Close", "Volume", "OpenInterest"]
                    # Slice to first 7 columns if extra fields exist
                    cleaned_rows = [r[:7] for r in raw_data]
                    df = pd.DataFrame(cleaned_rows, columns=cols)
                else:
                    cols = ["Timestamp", "Open", "High", "Low", "Close", "Volume"]
                    cleaned_rows = [r[:6] for r in raw_data]
                    df = pd.DataFrame(cleaned_rows, columns=cols)

                df["Timestamp"] = pd.to_datetime(df["Timestamp"])
                df.set_index("Timestamp", inplace=True)
                
                # Convert numeric columns to float
                numeric_cols = [c for c in df.columns if c != "Timestamp"]
                df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")

                df = _sanitize_candles(df)
                df.attrs["data_provider"] = DataProvider.SMART_API.value

                # Store in RAM Cache (with TTL + size eviction)
                if use_cache and not df.empty:
                    _store_in_candle_cache(cache_key, df, cache_ttl_seconds)

                logger.debug(f"[historical] Fetched {len(df)} {interval.value} candles for {clean_sym} via AngelOne")
                return df

        except Exception as e:
            logger.warning(f"[historical] AngelOne fetch failed for {clean_sym}: {e} — attempting yfinance fallback")

    # 2. Fallback to yfinance (Skip derivative option contracts as Yahoo does not index NSE options)
    # Check that it actually is an option (has strike digits or NFO/BFO exchange) to prevent false-positives like RELIANCE ending in 'CE'
    is_option_contract = (exch_str in ("NFO", "BFO") or any(c.isdigit() for c in clean_sym)) and (clean_sym.endswith("CE") or clean_sym.endswith("PE"))
    if is_option_contract:
        return None

    try:
        import yfinance as yf
        yf_sym = f"{clean_sym}.NS" if not symbol.endswith(".NS") and not symbol.startswith("^") else symbol
        if clean_sym in ("NIFTY", "NIFTY 50", "NIFTY50"):
            yf_sym = "^NSEI"
        elif clean_sym in ("BANKNIFTY", "NIFTY BANK"):
            yf_sym = "^NSEBANK"
        elif clean_sym in ("FINNIFTY", "NIFTY FINANCIAL SERVICES"):
            yf_sym = "NIFTY_FIN_SERVICE.NS"
        elif clean_sym in ("INDIAVIX", "INDIA VIX"):
            yf_sym = "^INDIAVIX"
        elif clean_sym in ("TATAMOTORS", "TATA MOTORS"):
            yf_sym = "TMPV.NS"

        # Non-native Yahoo bars (3m / 10m): fetch the finer native source and resample
        resample_spec = YF_RESAMPLE_MAP.get(interval)
        if resample_spec is not None:
            yf_interval, target_bar = resample_spec
        else:
            yf_interval = YF_INTERVAL_MAP.get(interval, "5m")
        period_str = f"{max(1, days_back)}d" if days_back <= 60 else "1y"

        df = yf.download(yf_sym, period=period_str, interval=yf_interval, progress=False, auto_adjust=True)
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # Standardize column naming
            col_map = {c: c.capitalize() for c in df.columns}
            df = df.rename(columns=col_map)

            req_cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
            df = df[req_cols]

            # Aggregate up to the requested bar size (3m from 1m, 10m from 5m)
            if resample_spec is not None:
                df = _resample_to_interval(df, target_bar)

            df = _sanitize_candles(df)
            df.attrs["data_provider"] = DataProvider.YFINANCE.value

            # Store in RAM Cache (with TTL + size eviction)
            if use_cache and not df.empty:
                _store_in_candle_cache(cache_key, df, cache_ttl_seconds)

            logger.debug(f"[historical] Fetched {len(df)} candles for {clean_sym} via yfinance ({yf_interval})")
            return df

    except Exception as e:
        logger.error(f"[historical] yfinance fallback failed for {clean_sym}: {e}")

    return None
