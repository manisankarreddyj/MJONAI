"""
Module: data/macro/macro_check.py
Purpose: Elite Multi-Asset Global Macro, Intermarket Sentiment & Institutional Flow Engine.
         Fetches real-time cues across US Equities, E-mini Futures (ES/NQ), GIFT Nifty,
         Crude Oil (WTI/Brent), US Dollar Index (DXY), US 10Y Yields, US VIX, and Asian Equities.
         Ingests daily FII/DII institutional net flows, computes correlation-weighted composite scores,
         features zero-dependency multi-provider fallback, and delivers compound risk throttling.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
import os
from pathlib import Path
import ssl
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import urllib.request

# Ensure workspace root is in sys.path when executed directly
_root_dir = Path(__file__).resolve().parents[3]  # repo root (ADR-0008)
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

import yfinance as yf

from mjonai.core.time_utils import now_ist, today_ist

logger = logging.getLogger(__name__)


# ── 1. ENUMS & DATA STRUCTURES ───────────────────────────────────────────────

class MacroSentimentLevel(str, Enum):
    """Institutional macro sentiment classification."""
    BULLISH  = "BULLISH"   # Global green, low yields, stable dollar -> Standard positioning
    NEUTRAL  = "NEUTRAL"   # Mixed signals -> Balanced positioning
    BEARISH  = "BEARISH"   # US sell-off / Asian gap-down -> Reduce signal limit by 1
    RISK_OFF = "RISK_OFF"  # Compound oil spike + USD spike + US dump -> Max defense (-2 limit)


# Master Intermarket Benchmark Symbols (10 Pillars)
MACRO_SYMBOLS: Dict[str, str] = {
    "sp500":          "^GSPC",     # S&P 500 Cash (Overnight US Cash Close)
    "us_futures":     "ES=F",      # S&P 500 E-mini Futures (Live Pre-Market Sentiment)
    "nasdaq_futures": "NQ=F",      # Nasdaq 100 E-mini Futures (Tech / High-Beta Sentiment)
    "gift_nifty":     "^NSEI",     # GIFT Nifty / Pre-Market Indian Gap Estimate
    "crude":          "CL=F",      # WTI Crude Oil (Domestic Inflation & Manufacturing Risk)
    "brent":          "BZ=F",      # Brent Crude Oil (Primary Indian Import Benchmark)
    "dxy":            "DX-Y.NYB",  # US Dollar Index (FII Emerging Market Capital Outflow)
    "us_10y_yield":   "^TNX",      # US 10-Year Treasury Yield (Equity Multiple Contraction)
    "us_vix":         "^VIX",      # CBOE Volatility Index (Global Fear & Spillover)
    "nikkei":         "^N225",     # Nikkei 225 (Early Asian Morning Opening Sentiment)
}


def get_macro_symbols() -> Dict[str, str]:
    """
    Return active macro benchmark symbols with optional environment variable overrides.
    Example: MJONAI_MACRO_SYMBOLS="sp500:^GSPC,crude:CL=F"
    """
    override_str = os.getenv("MJONAI_MACRO_SYMBOLS")
    if override_str:
        try:
            custom_map = dict(MACRO_SYMBOLS)
            for pair in override_str.split(","):
                if ":" in pair:
                    k, v = pair.split(":", 1)
                    custom_map[k.strip()] = v.strip()
            return custom_map
        except Exception as e:
            logger.warning(f"[macro_check] Failed parsing MJONAI_MACRO_SYMBOLS: {e}")
    return MACRO_SYMBOLS


# ── 2. QUANTITATIVE CORRELATION WEIGHTS & AUDITED THRESHOLDS ─────────────────

@dataclass(frozen=True)
class MacroCorrelationWeights:
    """
    Institutional empirical correlation weights for Indian Equities (Nifty 50).
    Normalized to sum = 1.0.
    """
    us_equities_weight: float   = 0.35  # S&P 500, ES, NQ futures (Dominant global sentiment)
    gift_asia_weight: float     = 0.25  # GIFT Nifty + Nikkei 225 (Direct opening cue)
    energy_weight: float        = 0.20  # WTI + Brent crude (Domestic macroeconomic margin risk)
    fx_dollar_weight: float     = 0.10  # US Dollar Index (FII capital flow sensitivity)
    rates_vix_weight: float     = 0.10  # US 10Y Yield + US VIX (Valuation multiples & fear)


DEFAULT_MACRO_WEIGHTS = MacroCorrelationWeights()


@dataclass(frozen=True)
class MacroThresholds:
    """Audited macro risk trigger thresholds for Indian equity positioning."""
    sp500_bearish_pct: float     = -1.00  # S&P down > 1.0% -> Bearish opening pressure
    sp500_bullish_pct: float     = 1.00   # S&P up > 1.0% -> Bullish opening tailwind
    futures_bearish_pct: float   = -0.75  # US Futures down > 0.75% -> Pre-market gap risk
    gift_nifty_gap_pct: float    = -0.60  # GIFT Nifty down > 0.60% -> Gap-down opening alert
    crude_risk_pct: float        = 3.00   # Crude up > 3.0% -> Inflation & margin risk
    dxy_risk_pct: float          = 0.50   # DXY up > 0.50% -> FII outflow pressure
    yield_spike_pct: float       = 2.50   # 10Y Yield surge > 2.5% -> Multiple compression
    us_vix_spike_pct: float      = 10.00  # US VIX up > 10.0% -> Global fear spillover
    asian_bearish_pct: float     = -1.20  # Nikkei down > 1.2% -> Morning gap-down risk


DEFAULT_MACRO_THRESHOLDS = MacroThresholds()

# Legacy dictionary for 100% backward compatibility
THRESHOLDS: Dict[str, float] = {
    "sp500_bearish":  DEFAULT_MACRO_THRESHOLDS.sp500_bearish_pct,
    "crude_risk":      DEFAULT_MACRO_THRESHOLDS.crude_risk_pct,
    "dxy_risk":        DEFAULT_MACRO_THRESHOLDS.dxy_risk_pct,
}


# ── 3. FII / DII DAILY INSTITUTIONAL FLOW CONTRACT (TD-012) ──────────────────

@dataclass(frozen=True)
class FIIDIICashFlow:
    """
    Daily Foreign (FII) and Domestic (DII) cash market flow intelligence.
    Values in INR Crores (₹ Cr).

    `feed_available` is the honesty gate: it is TRUE only when a real feed or
    an explicit env override produced the values. A `feed_available=False`
    flow is the no-feed sentinel — its zero values carry NO meaning and MUST
    NOT be presented as a live reading. Consumers gate on `feed_available`
    before treating the values as real.
    """
    fii_net_crores: float = 0.0          # e.g. -2,450.0 Cr (FII Net Selling)
    dii_net_crores: float = 0.0          # e.g. +3,120.0 Cr (DII Net Absorption)
    fii_consecutive_sell_days: int = 0   # Persistent institutional headwind streak
    net_institutional_flow: float = 0.0  # FII + DII total net absorption
    date_str: str = ""
    is_fii_heavy_selling: bool = False   # True if FII sold > ₹3,000 Cr in single session
    feed_available: bool = False         # False = honest no-feed sentinel (zeros are noise)


def fetch_fii_dii_cash_flow() -> FIIDIICashFlow:
    """
    Dev/test override INJECTOR only — no live FII/DII cash feed is wired yet
    (the TD-012 data source is absent; a future feed routes here exactly like
    S15/S17's data-gating pattern).

    Reads the `MJONAI_FII_NET_CR` / `MJONAI_DII_NET_CR` env overrides for
    seeding during tests/simulations. Without either override it returns the
    honest no-feed sentinel (`feed_available=False`, zeros, empty date) — it
    never fabricates a live "0.0 Cr" reading.
    """
    fii_override = os.getenv("MJONAI_FII_NET_CR")
    dii_override = os.getenv("MJONAI_DII_NET_CR")
    feed_available = fii_override is not None or dii_override is not None

    fii_val = float(fii_override) if fii_override is not None else 0.0
    dii_val = float(dii_override) if dii_override is not None else 0.0
    net_flow = fii_val + dii_val

    return FIIDIICashFlow(
        fii_net_crores=fii_val,
        dii_net_crores=dii_val,
        fii_consecutive_sell_days=3 if (feed_available and fii_val < -2000.0) else 0,
        net_institutional_flow=net_flow,
        date_str=str(today_ist()) if feed_available else "",
        is_fii_heavy_selling=bool(feed_available and fii_val < -3000.0),
        feed_available=feed_available,
    )


# ── 4. IMMUTABLE MACRO SENTIMENT SNAPSHOT CONTRACT ───────────────────────────

@dataclass(frozen=True)
class MacroSentimentSnapshot:
    """
    Immutable, rich dimensional macro sentiment intelligence payload.
    Supports dictionary-like indexing for seamless backward compatibility.
    """
    sp500_change_pct: float = 0.0
    us_futures_change_pct: float = 0.0
    nasdaq_futures_change_pct: float = 0.0
    gift_nifty_change_pct: float = 0.0
    crude_change_pct: float = 0.0
    brent_change_pct: float = 0.0
    dxy_change_pct: float = 0.0
    us_10y_yield_change_pct: float = 0.0
    us_vix_change_pct: float = 0.0
    nikkei_change_pct: float = 0.0
    flags: List[str] = field(default_factory=list)
    signal_limit_adjustment: int = 0
    risk_score: int = 0                  # Discrete cluster trigger score (-4 to +6)
    composite_score: float = 0.0         # Continuous weighted quant macro score (-100 to +100)
    fii_dii_flow: Optional[FIIDIICashFlow] = None
    overall: str = "NEUTRAL"
    fetched_at: str = ""
    successful_fetches: int = 0
    total_symbols: int = 0
    data_quality: str = "CONFIDENT"
    provider_used: str = "YFINANCE_PARALLEL"

    @property
    def is_risk_off(self) -> bool:
        """Convenience flag for fast hot-path risk sentry checks."""
        return self.overall in ("BEARISH", "RISK_OFF") or self.signal_limit_adjustment <= -1

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to native dictionary."""
        return {
            "sp500_change_pct": self.sp500_change_pct,
            "us_futures_change_pct": self.us_futures_change_pct,
            "nasdaq_futures_change_pct": self.nasdaq_futures_change_pct,
            "gift_nifty_change_pct": self.gift_nifty_change_pct,
            "crude_change_pct": self.crude_change_pct,
            "brent_change_pct": self.brent_change_pct,
            "dxy_change_pct": self.dxy_change_pct,
            "us_10y_yield_change_pct": self.us_10y_yield_change_pct,
            "us_vix_change_pct": self.us_vix_change_pct,
            "nikkei_change_pct": self.nikkei_change_pct,
            "flags": list(self.flags),
            "signal_limit_adjustment": self.signal_limit_adjustment,
            "risk_score": self.risk_score,
            "composite_score": self.composite_score,
            "is_risk_off": self.is_risk_off,
            "overall": self.overall,
            "fetched_at": self.fetched_at,
            "successful_fetches": self.successful_fetches,
            "total_symbols": self.total_symbols,
            "data_quality": self.data_quality,
            "provider_used": self.provider_used,
        }


# ── 5. MULTI-PROVIDER RESILIENT FETCHING (PRIMARY + DIRECT HTTP FALLBACK) ────

_CACHED_MACRO_SNAPSHOT: Optional[MacroSentimentSnapshot] = None
_MACRO_CACHE_TIMESTAMP: float = 0.0
_MACRO_CACHE_TTL_SECONDS: float = 300.0  # 5-minute cache TTL


def _fetch_direct_http_change(symbol: str, timeout_seconds: float = 3.0) -> Optional[float]:
    """
    Zero-dependency direct REST HTTP fallback to Yahoo Finance chart API.
    Used automatically if yfinance encounters an exception or is IP-throttled.
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    try:
        # P1-DATA-2: TLS verified by default — same posture as the
        # participant-OI feed fix. MJONAI_NSE_TLS_INSECURE=1 remains the
        # explicit kill-switch for MITM-proxy environments.
        import os as _os

        ctx = ssl.create_default_context()
        if _os.getenv("MJONAI_NSE_TLS_INSECURE", "").strip().lower() in ("1", "true", "yes"):
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            logger.warning(
                "[macro_check] TLS verification DISABLED via MJONAI_NSE_TLS_INSECURE — "
                "macro fallback feed exposed to tampering; never use outside a trusted proxy"
            )
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout_seconds, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            result = data.get("chart", {}).get("result", [])
            if not result:
                return None
            closes = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
            valid_closes = [c for c in closes if c is not None and c > 0]
            if len(valid_closes) < 2:
                return None
            prev_c = valid_closes[-2]
            last_c = valid_closes[-1]
            return round(((last_c - prev_c) / prev_c) * 100.0, 2)
    except Exception as e:
        logger.debug(f"[macro_check] Direct HTTP fallback failed for {symbol}: {e}")
        return None


def _fetch_single_symbol_change(symbol: str, timeout_seconds: float = 3.5) -> Tuple[Optional[float], str]:
    """
    Resilient multi-provider symbol change fetcher.
    Attempts primary yfinance -> falls back to direct REST HTTP.
    """
    # 1. Primary Attempt: yfinance
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d", interval="1d", timeout=timeout_seconds)
        if hist is not None and len(hist) >= 2:
            prev_close = float(hist["Close"].iloc[-2])
            last_close = float(hist["Close"].iloc[-1])
            if prev_close > 0.0:
                change_pct = ((last_close - prev_close) / prev_close) * 100.0
                return round(change_pct, 2), "YFINANCE_PRIMARY"
    except Exception as e:
        logger.debug(f"[macro_check] Primary yfinance fetch failed for {symbol}: {e}")

    # 2. Secondary Attempt: Direct REST HTTP fallback
    http_val = _fetch_direct_http_change(symbol, timeout_seconds=timeout_seconds)
    if http_val is not None:
        return http_val, "DIRECT_HTTP_FALLBACK"

    return None, "FAILED"


# ── 6. MULTI-ASSET PARALLEL INGESTION & QUANT REGIME SYNTHESIS ───────────────

def fetch_macro_sentiment(
    thresholds: Optional[MacroThresholds] = None,
    weights: Optional[MacroCorrelationWeights] = None,
    max_workers: int = 8,
    force_refresh: bool = False
) -> MacroSentimentSnapshot:
    """
    Fetch multi-asset macro sentiment across 10 global pillars with weighted scoring.
    """
    global _CACHED_MACRO_SNAPSHOT, _MACRO_CACHE_TIMESTAMP

    # In-memory TTL Cache check
    now_ts = time.time()
    if not force_refresh and _CACHED_MACRO_SNAPSHOT is not None:
        if (now_ts - _MACRO_CACHE_TIMESTAMP) < _MACRO_CACHE_TTL_SECONDS:
            return _CACHED_MACRO_SNAPSHOT

    cfg = thresholds or DEFAULT_MACRO_THRESHOLDS
    w = weights or DEFAULT_MACRO_WEIGHTS
    active_symbols = get_macro_symbols()
    total_symbols = len(active_symbols)

    changes: Dict[str, float] = {k: 0.0 for k in active_symbols}
    successful_fetches = 0
    provider_counts: Dict[str, int] = {}

    # Parallel Sub-Second Ingestion
    with ThreadPoolExecutor(max_workers=min(max_workers, total_symbols)) as executor:
        future_to_key = {
            executor.submit(_fetch_single_symbol_change, sym): key
            for key, sym in active_symbols.items()
        }
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                val, provider = future.result()
                if val is not None:
                    changes[key] = val
                    successful_fetches += 1
                    provider_counts[provider] = provider_counts.get(provider, 0) + 1
            except Exception as e:
                logger.warning(f"[macro_check] Thread error for {key}: {e}")

    flags: List[str] = []
    risk_score = 0
    signal_limit_adj = 0

    sp = changes.get("sp500", 0.0)
    us_fut = changes.get("us_futures", 0.0)
    nasdaq_fut = changes.get("nasdaq_futures", 0.0)
    gift_nifty = changes.get("gift_nifty", 0.0)
    crude = changes.get("crude", 0.0)
    brent = changes.get("brent", 0.0)
    dxy = changes.get("dxy", 0.0)
    yield_10y = changes.get("us_10y_yield", 0.0)
    us_vix = changes.get("us_vix", 0.0)
    nikkei = changes.get("nikkei", 0.0)

    # ── CLUSTER RISK CHECKS ──
    # 1. Equities Cluster
    if sp < cfg.sp500_bearish_pct:
        flags.append(f"S&P 500 down {sp:+.2f}% overnight -> Bearish opening pressure")
        risk_score += 1
    if us_fut < cfg.futures_bearish_pct:
        flags.append(f"US E-mini Futures down {us_fut:+.2f}% -> Pre-market gap risk")
        risk_score += 1
    if nasdaq_fut < cfg.futures_bearish_pct:
        flags.append(f"Nasdaq Futures down {nasdaq_fut:+.2f}% -> High-beta tech weakness")
        risk_score += 1

    # 2. Asian & Pre-Market GIFT Cues
    if gift_nifty < cfg.gift_nifty_gap_pct:
        flags.append(f"GIFT Nifty pre-market gap {gift_nifty:+.2f}% -> Gap-down opening alert")
        risk_score += 1
    if nikkei < cfg.asian_bearish_pct:
        flags.append(f"Nikkei 225 down {nikkei:+.2f}% -> Asian opening weakness")
        risk_score += 1

    # 3. Energy Cluster (Inflation & Margin Risk)
    if crude > cfg.crude_risk_pct:
        flags.append(f"WTI Crude up {crude:+.2f}% -> Domestic inflation & manufacturing margin risk")
        risk_score += 1
    if brent > cfg.crude_risk_pct:
        flags.append(f"Brent Crude up {brent:+.2f}% -> Indian import bill pressure flagged")
        risk_score += 1

    # 4. Currency & Sovereign Rates
    if dxy > cfg.dxy_risk_pct:
        flags.append(f"US Dollar Index (DXY) up {dxy:+.2f}% -> FII capital outflow pressure")
        risk_score += 1
    if yield_10y > cfg.yield_spike_pct:
        flags.append(f"US 10Y Yield up {yield_10y:+.2f}% -> Valuation multiple compression")
        risk_score += 1

    # 5. Overnight US VIX Spillover
    if us_vix > cfg.us_vix_spike_pct:
        flags.append(f"US VIX surged {us_vix:+.2f}% overnight -> Global volatility spillover alert")
        risk_score += 1

    # ── FII / DII INSTITUTIONAL NET FLOW INGESTION ──
    # Only a feed-available flow can fire the heavy-selling flag; the honest
    # no-feed sentinel (feed_available=False) must never leak a risk flag.
    fii_flow = fetch_fii_dii_cash_flow()
    if fii_flow.feed_available and fii_flow.is_fii_heavy_selling:
        flags.append(f"FII Heavy Net Selling (₹{abs(fii_flow.fii_net_crores):,.0f} Cr) -> Institutional Headwind")
        risk_score += 1

    # ── QUANTITATIVE WEIGHTED COMPOSITE SCORE (-100 to +100) ──
    eq_score = ((sp + us_fut + nasdaq_fut) / 3.0) * 15.0
    gift_score = ((gift_nifty + nikkei) / 2.0) * 15.0
    energy_score = -((crude + brent) / 2.0) * 10.0   # Higher crude = negative score
    fx_score = -(dxy) * 20.0                         # Higher USD = negative score
    rates_score = -((yield_10y + us_vix) / 2.0) * 10.0

    raw_composite = (
        eq_score * w.us_equities_weight +
        gift_score * w.gift_asia_weight +
        energy_score * w.energy_weight +
        fx_score * w.fx_dollar_weight +
        rates_score * w.rates_vix_weight
    )
    composite_score = round(max(-100.0, min(100.0, raw_composite)), 1)

    # ── COMPOUND RISK-OFF SYNTHESIS ──
    is_compound_risk_off = (
        (us_fut < cfg.futures_bearish_pct or sp < cfg.sp500_bearish_pct or gift_nifty < cfg.gift_nifty_gap_pct)
        and (crude > cfg.crude_risk_pct or brent > cfg.crude_risk_pct)
        and (dxy > cfg.dxy_risk_pct or us_vix > cfg.us_vix_spike_pct)
    )

    if successful_fetches < 4:
        overall = MacroSentimentLevel.NEUTRAL.value
        signal_limit_adj = 0
        data_quality = "DEGRADED"
        flags.append(f"Insufficient macro feeds ({successful_fetches}/{total_symbols}) -> defaulting to NEUTRAL")
        logger.warning(f"[macro_check] Data degraded: only {successful_fetches}/{total_symbols} fetched.")
    elif is_compound_risk_off:
        overall = MacroSentimentLevel.RISK_OFF.value
        signal_limit_adj = -2
        data_quality = "CONFIDENT"
        flags.append("COMPOUND RISK-OFF TRIGGER: Simultaneous US/GIFT Drop + Oil Surge + Dollar/VIX Spike -> Max Defense (-2 Signals)")
    elif risk_score >= 3 or composite_score <= -25.0:
        overall = MacroSentimentLevel.BEARISH.value
        signal_limit_adj = -1
        data_quality = "CONFIDENT"
    elif risk_score <= 1 and composite_score >= 15.0 and (sp > 0.0 or us_fut > 0.0):
        overall = MacroSentimentLevel.BULLISH.value
        signal_limit_adj = 0
        data_quality = "CONFIDENT"
    else:
        overall = MacroSentimentLevel.NEUTRAL.value
        signal_limit_adj = 0
        data_quality = "CONFIDENT"

    provider_primary = "DIRECT_HTTP_FALLBACK" if provider_counts.get("DIRECT_HTTP_FALLBACK", 0) > provider_counts.get("YFINANCE_PRIMARY", 0) else "YFINANCE_PARALLEL"

    snapshot = MacroSentimentSnapshot(
        sp500_change_pct=sp,
        us_futures_change_pct=us_fut,
        nasdaq_futures_change_pct=nasdaq_fut,
        gift_nifty_change_pct=gift_nifty,
        crude_change_pct=crude,
        brent_change_pct=brent,
        dxy_change_pct=dxy,
        us_10y_yield_change_pct=yield_10y,
        us_vix_change_pct=us_vix,
        nikkei_change_pct=nikkei,
        flags=flags,
        signal_limit_adjustment=signal_limit_adj,
        risk_score=risk_score,
        composite_score=composite_score,
        fii_dii_flow=fii_flow if fii_flow.feed_available else None,
        overall=overall,
        fetched_at=now_ist().isoformat(),
        successful_fetches=successful_fetches,
        total_symbols=total_symbols,
        data_quality=data_quality,
        provider_used=provider_primary,
    )

    _CACHED_MACRO_SNAPSHOT = snapshot
    _MACRO_CACHE_TIMESTAMP = now_ts

    logger.info(
        f"[macro_check] S&P={sp:+.2f}% | GIFT={gift_nifty:+.2f}% | Crude={crude:+.2f}% | "
        f"DXY={dxy:+.2f}% | VIX={us_vix:+.2f}% | Score={composite_score:+.1f} | Overall={overall} (Adj: {signal_limit_adj})"
    )
    return snapshot


def get_cached_macro_sentiment() -> MacroSentimentSnapshot:
    """O(1) fast memory lookup for macro sentiment."""
    global _CACHED_MACRO_SNAPSHOT
    if _CACHED_MACRO_SNAPSHOT is None:
        return fetch_macro_sentiment()
    return _CACHED_MACRO_SNAPSHOT


def reset_macro_cache() -> None:
    """Clear memory cache for testing or fresh intraday runs."""
    global _CACHED_MACRO_SNAPSHOT, _MACRO_CACHE_TIMESTAMP
    _CACHED_MACRO_SNAPSHOT = None
    _MACRO_CACHE_TIMESTAMP = 0.0


# ── 7. SELF-DIAGNOSTIC TEST HARNESS ──────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sentiment = fetch_macro_sentiment(force_refresh=True)
    print("===================================================================")
    print("MJONAI MULTI-ASSET GLOBAL MACRO & INSTITUTIONAL FLOW ENGINE")
    print("===================================================================")
    print(f"Overall Macro Sentiment : {sentiment.overall} (Score: {sentiment.risk_score}, Composite: {sentiment.composite_score:+.1f})")
    print(f"Signal Limit Adjustment : {sentiment.signal_limit_adjustment:+d}")
    print(f"Risk-Off Mode Active    : {sentiment.is_risk_off}")
    print(f"Provider Active         : {sentiment.provider_used}")
    print(f"Data Quality            : {sentiment.data_quality} ({sentiment.successful_fetches}/{sentiment.total_symbols} feeds)")
    print(f"Fetched At (IST)        : {sentiment.fetched_at}")
    print("-------------------------------------------------------------------")
    print(f"  - S&P 500 Cash        : {sentiment.sp500_change_pct:+.2f}%")
    print(f"  - US E-mini Futures   : {sentiment.us_futures_change_pct:+.2f}%")
    print(f"  - Nasdaq 100 Futures  : {sentiment.nasdaq_futures_change_pct:+.2f}%")
    print(f"  - GIFT Nifty Pre-Open : {sentiment.gift_nifty_change_pct:+.2f}%")
    print(f"  - WTI Crude Oil       : {sentiment.crude_change_pct:+.2f}%")
    print(f"  - Brent Crude Oil     : {sentiment.brent_change_pct:+.2f}%")
    print(f"  - US Dollar Index(DXY): {sentiment.dxy_change_pct:+.2f}%")
    print(f"  - US 10Y Bond Yield   : {sentiment.us_10y_yield_change_pct:+.2f}%")
    print(f"  - CBOE US VIX         : {sentiment.us_vix_change_pct:+.2f}%")
    print(f"  - Nikkei 225 (Japan)  : {sentiment.nikkei_change_pct:+.2f}%")
    print("-------------------------------------------------------------------")
    if sentiment.fii_dii_flow:
        print(f"FII Net Flow (INR)      : INR {sentiment.fii_dii_flow.fii_net_crores:+,.1f} Cr")
        print(f"DII Net Flow (INR)      : INR {sentiment.fii_dii_flow.dii_net_crores:+,.1f} Cr")
        print(f"Net Institutional Absorption : INR {sentiment.fii_dii_flow.net_institutional_flow:+,.1f} Cr")
        print("-------------------------------------------------------------------")
    if sentiment.flags:
        print("Active Risk & Macro Flags:")
        for f in sentiment.flags:
            print(f"  [WARN] {f}")
    else:
        print("Active Risk & Macro Flags: None (Calm Conditions)")
    print("===================================================================")

